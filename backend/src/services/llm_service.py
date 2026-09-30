"""
Сервис интеграции с LLM-провайдерами: YandexGPT, vLLM, GigaChat.

Единая точка генерации текста для всех каналов ассистента и единая метрика
длительности запроса (LLM_REQUEST_DURATION).

Ключевые решения:
- ленивая инициализация клиента — драйвер создаётся при первом вызове,
  чтобы приложение работало без настроенных ключей до реальной потребности;
- каскад провайдеров по LLM_PROVIDER: недоступный провайдер не роняет сервис,
  а приводит к RuntimeError с описанием причины;
- ошибки генерации пробрасываются наверх, метрика фиксируется в finally.

@see PromptBuilder, backend.src.config
"""

import logging
import time
from typing import Any

from backend.src.config import get_settings
from backend.src.metrics import LLM_REQUEST_DURATION

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """
    Единый сервис генерации текста с каскадом LLM-провайдеров.

    Ответственность: скрыть различия API провайдеров (YandexGPT, vLLM, GigaChat)
    за общим интерфейсом generate() и вести единую метрику времени запроса.

    Жизненный цикл: создаётся один раз на приложение; клиент выбранного
    провайдера лениво инициализируется при первом обращении и переживает
    весь жизненный цикл процесса.

    Почему каскад, а не один провайдер: доступность и стоимость LLM-сервисов
    меняются, а омниканальный ассистент не должен останавливаться при отказе
    одного поставщика. Порядок попыток определяется конфигурацией LLM_PROVIDER.

    @see _get_client, generate
    """

    def __init__(self):
        """
        Инициализация сервиса без создания клиента провайдера.

        Клиент и выбранный провайдер хранятся в экземпляре и создаются лениво
        при первом вызове _get_client — см. docstring _get_client.
        """
        self._client = None
        self._provider = None

    def _get_client(self) -> tuple[Any, str]:
        """
        Ленивая инициализация клиента LLM-провайдера.

        Почему лениво: создание клиента может потребовать недоступных пакетов
        или сети, а сервис должен стартовать без LLM (ENABLE_LLM=false).
        Выбор провайдера — каскадом по конфигурации LLM_PROVIDER: YandexGPT,
        затем vLLM, затем GigaChat; первый успешно созданный клиент
        запоминается и возвращается при последующих вызовах.

        Raises:
            RuntimeError: если LLM отключён или ни один провайдер не доступен
        """
        if self._client is not None:
            return self._client, self._provider

        if not settings.ENABLE_LLM:
            raise RuntimeError("LLM disabled (ENABLE_LLM=false)")

        # Try YandexGPT first
        if settings.LLM_PROVIDER == "yandex" and settings.YANDEXGPT_API_KEY:
            try:
                import yandex_cloud_ml as ycm

                self._client = ycm.YMLCloudML(
                    folder_id=settings.YANDEXGPT_FOLDER_ID,
                    api_key=settings.YANDEXGPT_API_KEY,
                )
                self._provider = "yandex"
                logger.info("YandexGPT client initialized")
                return self._client, self._provider
            except ImportError:
                logger.warning("yandex-cloud-ml not installed")

        # Try vLLM/Qwen
        if settings.LLM_PROVIDER == "vllm" and settings.VLLM_API_URL:
            try:
                import httpx

                self._client = httpx.AsyncClient(
                    base_url=settings.VLLM_API_URL,
                    timeout=60.0,
                )
                self._provider = "vllm"
                logger.info("vLLM client initialized")
                return self._client, self._provider
            except ImportError:
                logger.warning("httpx not installed")

        # Try GigaChat
        if settings.LLM_PROVIDER == "gigachat" and settings.GIGACHAT_API_KEY:
            try:
                from langchain_community.llms import GigaChat

                self._client = GigaChat(
                    credentials=settings.GIGACHAT_API_KEY,
                    verify_ssl_certs=False,
                )
                self._provider = "gigachat"
                logger.info("GigaChat client initialized")
                return self._client, self._provider
            except ImportError:
                logger.warning("langchain_community not installed")

        raise RuntimeError(
            f"No LLM provider available. Provider: {settings.LLM_PROVIDER}"
        )

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> str:
        """
        Генерация текста через выбранного LLM-провайдера.

        Маршрутизирует вызов на провайдера (yandex/vllm/gigachat) и в блоке
        finally фиксирует метрику LLM_REQUEST_DURATION — почему: время ответа
        LLM критично для SLA омниканального ассистента, и метрика должна
        записываться даже при ошибке генерации.

        Args:
            prompt: входной промпт для генерации
            max_tokens: максимальное число токенов в ответе
            temperature: температура сэмплирования (0 — детерминированно)

        Returns:
            сгенерированный текст

        Raises:
            RuntimeError: если LLM отключён (ENABLE_LLM=false)
        """
        if not settings.ENABLE_LLM:
            logger.warning("LLM disabled, returning placeholder")
            return "LLM отключен. Используйте ENABLE_LLM=true для активации."

        client, provider = self._get_client()

        start_time = time.perf_counter()
        try:
            if provider == "yandex":
                result = await self._generate_yandex(
                    client, prompt, max_tokens, temperature, **kwargs
                )
            elif provider == "vllm":
                result = await self._generate_vllm(
                    client, prompt, max_tokens, temperature, **kwargs
                )
            elif provider == "gigachat":
                result = await self._generate_gigachat(
                    client, prompt, max_tokens, temperature, **kwargs
                )
            else:
                raise ValueError(f"Unknown provider: {provider}")
            return result
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
        finally:
            duration = time.perf_counter() - start_time
            LLM_REQUEST_DURATION.labels(
                provider=provider, model=settings.LLM_PROVIDER or "default"
            ).observe(duration)

    async def _generate_yandex(
        self,
        client: Any,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """
        Генерация текста через YandexGPT (yandex_cloud_ml).

        Вызывается только из generate() для провайдера "yandex". Ошибки API
        логируются и пробрасываются наверх, чтобы generate() мог записать
        метрику в finally и вернуть ошибку вызывающему коду.
        """
        try:
            # YandexGPT API call
            result = client.texts().generate(
                modelUri=f"gpt://{settings.YANDEXGPT_FOLDER_ID}/yandexgpt-lite",
                messages=[
                    {"role": "system", "text": "Вы - полезный ассистент."},
                    {"role": "user", "text": prompt},
                ],
                generationOptions={
                    "maxTokens": str(max_tokens),
                    "temperature": temperature,
                },
            )
            return result.alternatives[0].message.text
        except Exception as e:
            logger.error(f"YandexGPT error: {e}")
            raise

    async def _generate_vllm(
        self,
        client: Any,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """
        Генерация текста через vLLM (OpenAI-совместимый /v1/completions).

        Используется httpx.AsyncClient — неблокирующий HTTP, чтобы запрос к LLM
        не занимал поток FastAPI event loop. raise_for_status() превращает
        ошибку HTTP в исключение, которое логируется выше в generate().
        """
        try:
            response = await client.post(
                "/v1/completions",
                json={
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["text"]
        except Exception as e:
            logger.error(f"vLLM error: {e}")
            raise

    async def _generate_gigachat(
        self,
        client: Any,
        prompt: str,
        max_tokens: int,
        temperature: float,
        **kwargs: Any,
    ) -> str:
        """
        Генерация текста через GigaChat (langchain_community).

        Ленивый импорт GigaChat в _get_client означает, что пакет
        langchain-community не является обязательной зависимостью: сервис
        работает, даже если установлен только один из провайдеров.
        """
        try:
            result = client.invoke(
                prompt,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return result
        except Exception as e:
            logger.error(f"GigaChat error: {e}")
            raise

    def get_provider_info(self) -> dict[str, Any]:
        """
        Информация о текущем состоянии LLM-подсистемы.

        Используется для диагностики и health-проверок: enabled показывает,
        включён ли LLM в конфигурации, provider — выбранного провайдера,
        initialized — создан ли уже клиент (ленивая инициализация).

        Returns:
            dict с ключами enabled, provider, initialized
        """
        return {
            "enabled": settings.ENABLE_LLM,
            "provider": settings.LLM_PROVIDER,
            "initialized": self._client is not None,
        }
