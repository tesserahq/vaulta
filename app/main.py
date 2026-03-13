import logging
from app.middleware.db_session import DBSessionMiddleware
from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
import rollbar
from rollbar.logger import RollbarHandler

from app.routers.assets import router as assets_router
from app.routers.clients import router as clients_router
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from app.telemetry import setup_tracing
from app.exceptions.handlers import register_exception_handlers
from app.logging_config import get_logger
from rollbar.contrib.fastapi import ReporterMiddleware as RollbarMiddleware
from app.db import db_manager
from app.utils.metrics import PrometheusMiddleware, metrics
from tessera_sdk.fastapi import get_livez_readyz_router

SKIP_PATHS = [
    "/assets/serve",
    "/livez",
    "/readyz",
    "/openapi.json",
    "/docs",
    "/metrics",
]


class EndpointFilter(logging.Filter):
    # Uvicorn endpoint access log filter
    def filter(self, record: logging.LogRecord) -> bool:
        return record.getMessage().find("GET /metrics") == -1


# Filter out /endpoint
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())


def create_app(testing: bool = False, auth_middleware=None) -> FastAPI:
    logger = get_logger()
    settings = get_settings()
    # Create FastAPI app with custom settings for file uploads
    app = FastAPI(
        title="Vaulta API",
        description="Asset management API",
        version="1.0.0",
    )

    if settings.is_production:
        # Initialize Rollbar SDK with your server-side access token
        rollbar.init(
            settings.rollbar_access_token,
            environment=settings.environment,
            handler="async",
        )

        # Report ERROR and above to Rollbar
        rollbar_handler = RollbarHandler()
        rollbar_handler.setLevel(logging.ERROR)

        # Attach Rollbar handler to the root logger
        logger.addHandler(rollbar_handler)
        app.add_middleware(RollbarMiddleware)

    if not testing and not settings.disable_auth:
        logger.info("Main: Adding authentication middleware")
        from tessera_sdk.utils.service_factory import create_service_factory

        # from app.middleware.authentication import AuthenticationMiddleware
        from tessera_sdk.middleware.authentication import AuthenticationMiddleware
        from tessera_sdk.middleware.user_onboarding import UserOnboardingMiddleware
        from app.repositories.user_repository import UserRepository

        # Create service factory for UserRepository
        user_service_factory = create_service_factory(UserRepository, db_manager)

        app.add_middleware(
            UserOnboardingMiddleware,
            user_service_factory=user_service_factory,
        )

        app.add_middleware(
            AuthenticationMiddleware,
            skip_paths=SKIP_PATHS,
            user_service_factory=user_service_factory,
        )

        # Setting metrics middleware
        app.add_middleware(PrometheusMiddleware, app_name=settings.app_name)
        app.add_route("/metrics", metrics)
    else:
        logger.info("Main: No authentication middleware")
        if auth_middleware:
            app.add_middleware(auth_middleware)

    # TODO: Restrict this to the allowed origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Puedes restringir esto a dominios específicos
        allow_credentials=True,
        allow_methods=["*"],  # Permitir todos los métodos (GET, POST, etc.)
        allow_headers=["*"],  # Permitir todos los headers
    )

    app.include_router(get_livez_readyz_router())

    app.include_router(assets_router)
    app.include_router(clients_router)

    register_exception_handlers(app)

    return app


# Production app instance
app = create_app()

settings = get_settings()
if settings.otel_enabled:
    tracer_provider = setup_tracing()  # Or use env/config
    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)


@app.get("/")
def main_route():
    return {"message": "Hey, It is me Goku"}
