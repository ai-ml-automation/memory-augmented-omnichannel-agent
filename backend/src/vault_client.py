"""
Клиент HashiCorp Vault (KV v2) для хранения секретов в production.

Зачем Vault: секреты (JWT, ключи шифрования) не лежат в env-переменных и
не попадают в репозиторий; в development Vault пропускается — значения
берутся из .env через Settings.

Ключевые решения:
- ленивый синглтон get_vault_client — hvac не обязателен для запуска;
- get_vault_secret возвращает None при любой ошибке — приложение работает
  с fallback-значениями, а не падает.
"""

import logging

logger = logging.getLogger(__name__)

_vault_client = None


def get_vault_client():
    """
    Получение (и создание при первом вызове) синглтона Vault-клиента.

    Почему лениво: hvac — опциональная зависимость, а в development Vault
    не нужен вовсе, поэтому инициализация откладывается до первого чтения.

    Returns:
        hvac.Client при успешной аутентификации, иначе None (Vault отключён)
    """
    global _vault_client
    if _vault_client is not None:
        return _vault_client

    try:
        import hvac
    except ImportError:
        logger.warning("hvac not installed, Vault integration disabled")
        return None

    from backend.src.config import get_settings
    settings = get_settings()

    if settings.APP_ENV != "production":
        logger.info("Vault skipped (APP_ENV=%s)", settings.APP_ENV)
        return None

    if not settings.VAULT_URL or not settings.VAULT_TOKEN:
        logger.warning("Vault URL/token not configured")
        return None

    client = hvac.Client(
        url=settings.VAULT_URL,
        token=settings.VAULT_TOKEN,
    )
    if not client.is_authenticated():
        logger.error("Vault authentication failed")
        return None

    logger.info("Vault client initialized (url=%s)", settings.VAULT_URL)
    _vault_client = client
    return client


def get_vault_secret(path: str, key: str) -> str | None:
    """
    Чтение секрета из Vault KV v2; при любой ошибке — None.
    None позволяет вызывающему коду перейти на fallback из .env,
    а не упасть (правило «Vault недоступен — приложение живо»).
    Args:
        path: путь секрета в KV v2 (например, secret/omnichannel)
        key: имя ключа внутри секрета
    Returns:
        значение секрета или None
    """
    client = get_vault_client()
    if client is None:
        return None

    try:
        response = client.secrets.kv.v2.read_secret_version(path=path)
        return response["data"]["data"].get(key)
    except Exception as e:
        logger.error("Vault read failed for %s/%s: %s", path, key, e)
        return None