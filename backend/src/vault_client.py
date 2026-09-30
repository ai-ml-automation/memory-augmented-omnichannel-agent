"""
Vault Client
Reads secrets from HashiCorp Vault in production.
Falls back to .env in development mode.
"""

import logging

logger = logging.getLogger(__name__)

_vault_client = None


def get_vault_client():
    """Get or create Vault client singleton."""
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
    """Read a secret from Vault KV v2. Returns None on any failure."""
    client = get_vault_client()
    if client is None:
        return None

    try:
        response = client.secrets.kv.v2.read_secret_version(path=path)
        return response["data"]["data"].get(key)
    except Exception as e:
        logger.error("Vault read failed for %s/%s: %s", path, key, e)
        return None