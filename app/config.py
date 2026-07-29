import os
from typing import Optional

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings
from sqlalchemy.engine.url import URL, make_url

from app.providers import AnalysisProvider, StorageProvider

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/vaulta"
DEFAULT_TEST_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/vaulta_test"

SERVICE_NAME = "vaulta-api"


class Settings(BaseSettings):
    app_name: str = SERVICE_NAME
    otel_enabled: bool = Field(default=False, json_schema_extra={"env": "OTEL_ENABLED"})
    database_url: Optional[str] = None  # Will be set dynamically
    database_pool_size: int = Field(
        default=10, json_schema_extra={"env": "DATABASE_POOL_SIZE"}
    )
    database_max_overflow: int = Field(
        default=5, json_schema_extra={"env": "DATABASE_MAX_OVERFLOW"}
    )
    environment: str = Field(
        default="development",
        validation_alias=AliasChoices("ENV", "ENVIRONMENT"),
    )
    log_level: str = Field(default="INFO", json_schema_extra={"env": "LOG_LEVEL"})
    disable_auth: bool = Field(default=False, json_schema_extra={"env": "DISABLE_AUTH"})
    identies_host: str = Field(
        default="https://identies.com",
        json_schema_extra={"env": "IDENTIES_HOST"},
    )
    # Master secret key used for signing URLs and generating secure tokens
    # This key is used by the storage backend to create signed URLs for secure file access
    master_secret_key: Optional[str] = Field(
        default=None,
        description="Master secret key used for signing URLs and generating secure tokens",
        json_schema_extra={"env": "MASTER_SECRET_KEY"},
    )  # Optional field for URL signing, defaults to None
    rollbar_access_token: Optional[str] = Field(
        default=None, json_schema_extra={"env": "ROLLBAR_ACCESS_TOKEN"}
    )  # Optional field

    # Ceiling on how long a caller-requested serve_url (e.g. for email-embedded
    # images) may live for. Prevents an upload caller from minting an
    # effectively-unrevocable token for a sensitive asset.
    max_serve_url_expiry: int = Field(
        default=5 * 365 * 24 * 3600,  # 5 years
        description="Maximum allowed expires_in (seconds) for a requested long-lived serve_url",
        json_schema_extra={"env": "MAX_SERVE_URL_EXPIRY"},
    )

    # Storage settings
    storage_backend: str = StorageProvider.S3
    local_storage_dir: str = Field(
        default="storage",
        description="Local storage directory path. Can be relative (e.g., 'storage') or absolute (e.g., '/tmp/myfiles')",
        json_schema_extra={"env": "LOCAL_STORAGE_DIR"},
    )
    public_url_prefix: str = Field(
        default="/files", json_schema_extra={"env": "PUBLIC_URL_PREFIX"}
    )
    port: int = Field(default=8000, json_schema_extra={"env": "PORT"})
    # File upload settings
    max_file_size: int = Field(
        default=100 * 1024 * 1024,  # 100MB default
        description="Maximum file size in bytes",
        json_schema_extra={"env": "MAX_FILE_SIZE"},
    )
    max_file_size_mb: int = Field(
        default=100,
        description="Maximum file size in MB (for easier configuration)",
        json_schema_extra={"env": "MAX_FILE_SIZE_MB"},
    )
    db_app_name: str = Field(
        default="vaulta-api", json_schema_extra={"env": "DB_APP_NAME"}
    )

    # S3 settings
    s3_bucket_name: str = "vaulta"
    s3_region_name: str = "us-east-1"
    s3_endpoint_url: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

    # Document analysis settings
    analysis_backend: str = Field(
        default=AnalysisProvider.LOCAL, json_schema_extra={"env": "ANALYSIS_BACKEND"}
    )
    analysis_max_image_px: int = Field(
        default=2048, json_schema_extra={"env": "ANALYSIS_MAX_IMAGE_PX"}
    )
    google_dai_processor_id: Optional[str] = Field(
        default=None, json_schema_extra={"env": "GOOGLE_DAI_PROCESSOR_ID"}
    )
    google_application_credentials: Optional[str] = Field(
        default=None, json_schema_extra={"env": "GOOGLE_APPLICATION_CREDENTIALS"}
    )
    anthropic_api_key: Optional[str] = Field(
        default=None, json_schema_extra={"env": "ANTHROPIC_API_KEY"}
    )
    bedrock_region: Optional[str] = Field(
        default=None, json_schema_extra={"env": "BEDROCK_REGION"}
    )

    # Modela settings
    modela_audience: str = Field(
        default="", json_schema_extra={"env": "MODELA_AUDIENCE"}
    )
    modela_scope: str = Field(default="", json_schema_extra={"env": "MODELA_SCOPE"})

    oidc_domain: str = "test.oidc.com"
    oidc_api_audience: str = "https://test-api"
    oidc_issuer: str = "https://test.oidc.com/"
    oidc_algorithms: str = "RS256"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = SERVICE_NAME.lower()
    redis_host: str = Field(
        default="localhost", json_schema_extra={"env": "REDIS_HOST"}
    )
    redis_port: int = Field(default=6379, json_schema_extra={"env": "REDIS_PORT"})
    redis_namespace: str = Field(
        default="llama_index", json_schema_extra={"env": "REDIS_NAMESPACE"}
    )

    @model_validator(mode="before")
    def set_database_url(cls, values):
        """Set the database_url dynamically based on the environment field."""
        environment = values.get("environment", os.getenv("ENV", "development"))
        if environment.lower() == "test":
            values["database_url"] = os.getenv(
                "TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL
            )
        else:
            values["database_url"] = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

        return values

    @model_validator(mode="after")
    def set_max_file_size_from_mb(self):
        """Set max_file_size from max_file_size_mb if provided."""
        if hasattr(self, "max_file_size_mb") and self.max_file_size_mb:
            self.max_file_size = self.max_file_size_mb * 1024 * 1024
        return self

    @property
    def is_production(self) -> bool:
        """Check if the current environment is production."""
        return self.environment.lower() == "production"

    @property
    def is_test(self) -> bool:
        """Check if the current environment is test."""
        return self.environment.lower() == "test"

    @property
    def database_url_obj(self) -> URL:
        """Return the database URL as a URL object using sqlalchemy's make_url."""
        if not self.database_url:
            raise ValueError("Database URL is not set.")
        return make_url(self.database_url)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra environment variables


def get_settings() -> Settings:
    """Get application settings with required environment variables."""
    return Settings()
