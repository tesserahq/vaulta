from app.schemas.user import UserOnboard
import jwt
import requests  # For making HTTP requests
from fastapi import HTTPException, status, Request
from fastapi.security import HTTPBearer

from app.config import get_settings
from app.repositories.user_repository import UserRepository

security = HTTPBearer()


class UnauthorizedException(HTTPException):
    def __init__(self, detail: str, **kwargs):
        """Returns HTTP 403"""
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class UnauthenticatedException(HTTPException):
    def __init__(self):
        """Returns HTTP 401"""
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Requires authentication"
        )


def get_db_from_request(request: Request):
    return request.state.db_session


def verify_token_dependency(request: Request, token: str):
    verifier = VerifyToken(get_db_from_request(request))
    user = verifier.verify(token)
    request.state.user = user


async def get_current_user(request: Request):
    if not hasattr(request.state, "user") or request.state.user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return request.state.user


class VerifyToken:
    """Does all the token verification using PyJWT"""

    def __init__(self, db_session):
        self.config = get_settings()
        self.db = db_session  # Store the DB session
        self.user_repository = UserRepository(self.db)

        if self.config.oidc_domain is None:
            raise ValueError("oidc domain is not set in the configuration.")

        # This gets the JWKS from a given URL and does processing so you can
        # use any of the keys available
        jwks_url = f"https://{self.config.oidc_domain}/.well-known/jwks.json"
        self.jwks_client = jwt.PyJWKClient(jwks_url, cache_keys=True)

    def verify(self, token: str):
        if token is None:
            raise UnauthenticatedException

        # This gets the 'kid' from the passed token
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token).key
        except jwt.exceptions.PyJWKClientError as error:
            # raise UnauthorizedException(str(error))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
            )
        except jwt.exceptions.DecodeError as error:
            # raise UnauthorizedException(str(error))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)
            )

        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=self.config.oidc_algorithms,
                audience=self.config.oidc_api_audience,
                issuer=self.config.oidc_issuer,
            )
        except Exception as error:
            raise UnauthorizedException(str(error))

        # Extract user ID from JWT payload
        user_id = payload["sub"]

        # User not in cache or cache was invalid, check database
        user = self.user_repository.get_user_by_external_id(user_id)

        if user:
            # User exists in database, cache the existence
            return user
        else:
            # User doesn't exist, cache the non-existence and fetch from OIDC
            userinfo = self.fetch_user_info_from_identies(token)
            user = self.handle_user_onboarding(payload, userinfo)
            return user

    def fetch_user_info_from_identies(self, access_token: str) -> dict:
        """Fetch user information from the oidc userinfo endpoint."""
        userinfo_url = f"{self.config.identies_host}/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}
        response = requests.get(userinfo_url, headers=headers)

        if response.status_code != 200:
            raise UnauthorizedException(
                f"Failed to fetch user info from oidc. "
                f"Status code: {response.status_code}, Response: {response.text}"
            )

        return response.json()

    def handle_user_onboarding(self, payload: dict, userinfo: dict):
        """Onboard the user locally using the userinfo data."""
        external_id = payload["sub"]

        # Onboard the user locally
        user = self.user_repository.onboard_user(
            UserOnboard(
                external_id=external_id,
                id=userinfo["id"],
                email=userinfo["email"],
                first_name=userinfo["first_name"],
                last_name=userinfo["last_name"],
                avatar_url=userinfo["avatar_url"],
            )
        )

        return user
