"""Application configuration using Pydantic Settings v2"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Project Information
    project_name: str = "CENA MASKIA CHAMPIONSHIP"
    version: str = "1.0.0"

    # Shared auth secrets for admin and team access
    admin_token: str = Field(default="1234", alias="ADMIN_TOKEN")
    team_shared_password: str = Field(default="1234", alias="TEAM_SHARED_PASSWORD")

    # Bilanci - sanction thresholds (perdita = utile negativo, valore assoluto)
    sanction_light_threshold: float = Field(
        default=20.0, alias="SANCTION_LIGHT_THRESHOLD"
    )
    sanction_medium_threshold: float = Field(
        default=60.0, alias="SANCTION_MEDIUM_THRESHOLD"
    )
    sanction_heavy_threshold: float = Field(
        default=120.0, alias="SANCTION_HEAVY_THRESHOLD"
    )

    # Uploads dir for balance Excel files
    uploads_dir: str = Field(default="uploads", alias="UPLOADS_DIR")

    # API Configuration
    api_v1_str: str = "/api/v1"

    # Database Configuration - Local PostgreSQL
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5436/app_db",
        alias="DATABASE_URL",
    )

    # Pool Configuration - Standard settings for local PostgreSQL
    database_pool_size: int = Field(default=5)
    database_max_overflow: int = Field(default=10)
    database_pool_timeout: int = Field(default=30)
    database_pool_recycle: int = Field(default=3600)
    database_pool_pre_ping: bool = Field(default=True)
    database_echo: bool = Field(default=False)
    database_pool_reset_on_return: str = Field(default="rollback")
    cache_ttl_default: int = Field(default=300)
    cache_ttl_users: int = Field(default=600)

    # CORS
    cors_origins: str = Field(default="http://localhost:4200,http://localhost:4300")

    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        if not self.cors_origins or self.cors_origins.strip() == "":
            return [
                "http://localhost:4200",
                "http://localhost:4300",
                "http://127.0.0.1:4200",
            ]
        return [
            origin.strip() for origin in self.cors_origins.split(",") if origin.strip()
        ]

    # Security (optional for production)
    secret_key: str = Field(
        default="dev-secret-key-change-in-production", alias="JWT_SECRET_KEY"
    )

    # Rate Limiting
    rate_limit_requests: int = Field(default=100)
    rate_limit_window: int = Field(default=60)

    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")

    # Monitoring
    enable_metrics: bool = Field(default=True)
    metrics_path: str = Field(default="/metrics")

    # Performance
    connection_timeout: int = Field(default=10)
    read_timeout: int = Field(default=30)

    # Remote Fantacalcio asset refresh
    fantacalcio_league_base_url: str = Field(
        default="https://leghe.fantacalcio.it", alias="FANTACALCIO_LEAGUE_BASE_URL"
    )
    fantacalcio_league_slug: str = Field(
        default="cena-maskia-championship", alias="FANTACALCIO_LEAGUE_SLUG"
    )
    fantacalcio_ssl_verify: bool = Field(default=True, alias="FANTACALCIO_SSL_VERIFY")
    fantacalcio_ca_bundle: str | None = Field(
        default=None, alias="FANTACALCIO_CA_BUNDLE"
    )
    fantacalcio_classifica_export_url: str | None = Field(
        default=None, alias="FANTACALCIO_CLASSIFICA_EXPORT_URL"
    )
    fantacalcio_rose_export_url: str | None = Field(
        default=None, alias="FANTACALCIO_ROSE_EXPORT_URL"
    )
    fantacalcio_calendar_export_url: str | None = Field(
        default=None, alias="FANTACALCIO_CALENDAR_EXPORT_URL"
    )
    fantacalcio_auto_standings_enabled: bool = Field(
        default=True, alias="FANTACALCIO_AUTO_STANDINGS_ENABLED"
    )
    fantacalcio_auto_refresh_timezone: str = Field(
        default="Europe/Rome", alias="FANTACALCIO_AUTO_REFRESH_TIMEZONE"
    )

    # Environment detection helpers
    debug: bool = Field(default=True)
    environment: str = Field(default="development")

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == "development" or self.debug

    @property
    def is_staging(self) -> bool:
        """Check if running in staging"""
        return self.environment == "staging"

    @property
    def is_production_like(self) -> bool:
        """Check if running in production or staging mode"""
        return self.environment in ("production", "staging")


# Create global settings instance
settings = Settings()
