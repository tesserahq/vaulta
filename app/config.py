from pydantic import Field
from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Vaulta"
    otel_enabled: bool = Field(default=False, json_schema_extra={"env": "OTEL_ENABLED"})
    database_url: Optional[str] = None  # Will be set dynamically
    environment: str = Field(default="development", json_schema_extra={"env": "ENV"})
    log_level: str = Field(default="INFO", json_schema_extra={"env": "LOG_LEVEL"})
    disable_auth: bool = Field(default=False, json_schema_extra={"env": "DISABLE_AUTH"})
    rollbar_access_token: str = Field(
        ..., json_schema_extra={"env": "ROLLBAR_ACCESS_TOKEN"}
    )  # Required field
    
    # Storage settings
    storage_backend: str = "local"  # "local" or "s3"
    local_storage_dir: str = "storage"
    public_url_prefix: str = Field(default="/files", json_schema_extra={"env": "PUBLIC_URL_PREFIX"})
    
    # S3 settings
    s3_bucket_name: str = ""
    s3_region_name: str = "us-east-1"
    s3_endpoint_url: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None 
    
    oidc_domain: str = "test.oidc.com"
    oidc_api_audience: str = "https://test-api"
    oidc_issuer: str = "https://test.oidc.com/"
    oidc_algorithms: str = "RS256"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_service_name: str = "quore"
    redis_host: str = Field(
        default="localhost", json_schema_extra={"env": "REDIS_HOST"}
    )
    redis_port: int = Field(default=6379, json_schema_extra={"env": "REDIS_PORT"})
    redis_namespace: str = Field(
        default="llama_index", json_schema_extra={"env": "REDIS_NAMESPACE"}
    )

    @property
    def is_production(self) -> bool:
        """Check if the current environment is production."""
        return self.environment.lower() == "production"

    @property
    def is_test(self) -> bool:
        """Check if the current environment is test."""
        return self.environment.lower() == "test"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"  # Allow extra environment variables


def get_settings() -> Settings:
    """Get application settings with required environment variables."""
    return Settings()
