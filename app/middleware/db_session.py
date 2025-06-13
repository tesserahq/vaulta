# TODO: Is this the way we want to do this?
from starlette.middleware.base import BaseHTTPMiddleware
from app.db import SessionLocal  # or wherever your SQLAlchemy Session is


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.db_session = SessionLocal()
        try:
            response = await call_next(request)
        finally:
            request.state.db_session.close()
        return response
