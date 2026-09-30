"""
Конфигурация приложения через pydantic-settings.

Значения берутся из переменных окружения и .env; при отсутствии — дефолт.
Типы приводятся автоматически (str/int/bool).

Ключевые решения:
- get_settings (lru_cache) — одно чтение настроек на процесс;
- в production JWT/ключ шифрования читаются из Vault, иначе дефолт из env;
- тесты переопределяют поля: Settings(APP_ENV="test") — изоляция без .env.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Настройки приложения (pydantic-settings): чтение env + .env.

    Создаётся один раз через get_settings (lru_cache); для тестов
    инстанцируется напрямую с переопределением полей.

    Поля сгруппированы по блокам (PostgreSQL, Redis, Qdrant, Neo4j,
    безопасность, LLM, Vault); секреты приходят из env/Vault, не из кода.
    """

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"  # хост БД
    POSTGRES_PORT: int = 5432  # порт БД
    POSTGRES_DB: str = "omnichannel"  # имя БД
    POSTGRES_USER: str = "postgres"  # пользователь БД
    POSTGRES_PASSWORD: str = "changeme"  # пароль БД (env в production)

    # Redis
    REDIS_HOST: str = "localhost"  # хост Redis (брокер Celery + кэш)
    REDIS_PORT: int = 6379  # порт Redis
    REDIS_DB: int = 0  # номер БД Redis

    # Qdrant
    QDRANT_HOST: str = "localhost"  # хост векторной БД
    QDRANT_PORT: int = 6333  # порт Qdrant
    QDRANT_URL: str = "http://localhost:6333"  # полный URL для клиента
    QDRANT_API_KEY: str = ""  # ключ доступа (пусто = без аутентификации)

    # Neo4j
    NEO4J_HOST: str = "localhost"  # хост графовой БД
    NEO4J_PORT: int = 7687  # порт bolt Neo4j
    NEO4J_USER: str = "neo4j"  # пользователь Neo4j
    NEO4J_PASSWORD: str = "changeme"  # пароль Neo4j (env в production)
    NEO4J_URI: str = "bolt://localhost:7687"  # URI для драйвера

    # MinIO (S3-compatible)
    MINIO_ENDPOINT: str = "localhost:9000"  # endpoint MinIO
    MINIO_ACCESS_KEY: str = "changeme"  # access key MinIO
    MINIO_SECRET_KEY: str = "changeme"  # secret key MinIO
    MINIO_BUCKET: str = "omnichannel"  # имя bucket

    # Security
    # Секреты подписи и шифрования; реальные значения — из env/Vault в production
    SECRET_KEY: str = "changeme-generate-with-openssl"
    JWT_SECRET: str = "changeme-generate-with-openssl"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    ENCRYPTION_KEY: str = Field(
        default="changeme-32-byte-key-for-aes256!",
        description="AES-256 encryption key for PII (32 bytes)",
    )

    # App
    APP_HOST: str = "0.0.0.0"  # адрес прослушивания
    APP_PORT: int = 8000  # порт HTTP
    APP_ENV: str = "development"  # development | production
    APP_DEBUG: bool = True  # режим отладки (False в production)
    LOG_LEVEL: str = "INFO"  # уровень логирования

    # Feature Flags (all disabled by default)
    ENABLE_LLM: bool = False  # включить LLM-пайплайн
    ENABLE_VOICE: bool = False  # включить голосовой сценарий
    ENABLE_ASR: bool = False  # включить распознавание речи
    ENABLE_TTS: bool = False  # включить синтез речи
    ENABLE_MEMORY: bool = False  # включить долговременную память

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"  # брокер задач (Redis)
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"  # хранилище результатов

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
    WHISPER_MODEL: str = "large-v3"  # модель распознавания Whisper
    SILERO_MODEL_PATH: str = ""  # путь к модели Silero TTS

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
    """
    Получение единственного экземпляра Settings (кэш процесса).

    lru_cache гарантирует, что настройки читаются из окружения один раз,
    что важно для согласованности значений и производительности.

    Returns:
        Settings: экземпляр с прочитанными настройками
    """
    return Settings()

