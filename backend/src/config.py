"""
Application Configuration
Pydantic Settings for reading environment variables
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "omnichannel"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "changeme"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Qdrant
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # Neo4j
    NEO4J_HOST: str = "localhost"
    NEO4J_PORT: int = 7687
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changeme"
    NEO4J_URI: str = "bolt://localhost:7687"

    # MinIO (S3-compatible)
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "changeme"
    MINIO_SECRET_KEY: str = "changeme"
    MINIO_BUCKET: str = "omnichannel"

    # Security
    SECRET_KEY: str = "changeme-generate-with-openssl"
    JWT_SECRET: str = "changeme-generate-with-openssl"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    ENCRYPTION_KEY: str = Field(
        default="changeme-32-byte-key-for-aes256!",
        description="AES-256 encryption key for PII (32 bytes)",
    )

    # App
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    LOG_LEVEL: str = "INFO"

    # Feature Flags (all disabled by default)
    ENABLE_LLM: bool = False
    ENABLE_VOICE: bool = False
    ENABLE_ASR: bool = False
    ENABLE_TTS: bool = False
    ENABLE_MEMORY: bool = False

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Messenger Tokens
    MAX_BOT_TOKEN: str = Field(default="", description="MAX messenger bot token")
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram bot token")
    TELEGRAM_WEBHOOK_SECRET: str = Field(
        default="", description="Telegram webhook secret token"
    )
    VK_ACCESS_TOKEN: str = Field(default="", description="VK API access token")
    VK_GROUP_ID: str = Field(default="", description="VK group ID")
    VK_CALLBACK_SECRET: str = Field(default="", description="VK callback secret")

    # LLM
    LLM_PROVIDER: str = Field(default="yandexgpt", description="LLM provider name")
    YANDEXGPT_API_KEY: str = Field(default="", description="YandexGPT API key")
    YANDEX_FOLDER_ID: str = Field(default="", description="Yandex Cloud folder ID")
    LLM_API_BASE_URL: str = Field(default="", description="LLM API base URL")
    LLM_API_KEY: str = Field(default="", description="LLM API key")

    # ASR / TTS
    WHISPER_MODEL: str = "large-v3"
    SILERO_MODEL_PATH: str = ""

    # CTI (Naumen / Asterisk)
    CTI_API_URL: str = Field(default="", description="CTI API URL")
    CTI_API_KEY: str = Field(default="", description="CTI API key")

    # Vault
    VAULT_TOKEN: str = Field(default="", description="Vault dev token")
    VAULT_URL: str = Field(default="", description="Vault URL")
    VAULT_PATH: str = Field(
        default="secret/omnichannel",
        description="Vault KV v2 secret path",
    )

    # CORS (comma-separated origins, empty = deny all in production)
    CORS_ORIGINS: str = Field(
        default="http://localhost:3000",
        description="Comma-separated allowed origins",
    )

    @property
    def postgres_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def postgres_url_sync(self) -> str:
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS_ORIGINS comma-separated string into list."""
        if not self.CORS_ORIGINS:
            return []
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def effective_jwt_secret(self) -> str:
        """JWT secret: Vault in production, .env fallback."""
        if self.APP_ENV == "production":
            from backend.src.vault_client import get_vault_secret
            val = get_vault_secret(self.VAULT_PATH, "jwt_secret")
            if val:
                return val
        return self.JWT_SECRET

    @property
    def effective_encryption_key(self) -> str:
        """Encryption key: Vault in production, .env fallback."""
        if self.APP_ENV == "production":
            from backend.src.vault_client import get_vault_secret
            val = get_vault_secret(self.VAULT_PATH, "encryption_key")
            if val:
                return val
        return self.ENCRYPTION_KEY

    model_config = {"env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()

