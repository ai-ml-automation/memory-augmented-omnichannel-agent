"""
JWT-middleware: автоматическая валидация токена для защищённых маршрутов.

Реализовано как middleware (а не per-route `Depends`), потому что
защищать нужно ВСЕ маршруты по умолчанию, кроме явного списка публичных
(`PUBLIC_ENDPOINTS`) и вебхуков (`WEBHOOK_PREFIXES`) — новый роутер
оказывается защищённым без дополнительных действий.

Здесь проверяется только формат и срок действия JWT (нет доступа к БД);
полная загрузка пользователя выполняется в обработчиках через
`get_current_admin` (см. `backend.src.dependencies`). CORS настраивается
отдельно в `backend.src.main`.
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.src.config import get_settings

settings = get_settings()

# Публичные эндпоинты, не требующие аутентификации
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/login",
    "/auth/register",
}

# Вебхуки не требуют JWT — подпись проверяется в обработчиках webhooks
WEBHOOK_PREFIXES = {"/webhook/"}


class JWTMiddleware(BaseHTTPMiddleware):
    """
    Middleware валидации JWT на защищённых маршрутах.

    Жизненный цикл: регистрируется в `main.py`, обрабатывает каждый
    запрос до роутера. `BaseHTTPMiddleware` даёт перехват на уровне
    приложения; сессии БД нет — проверяется подпись и срок токена.
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Обработка запроса: публичные пути и вебхуки пропускаются,
        иначе cookie access_token: нет/невалиден/истёк → 401.
        Args:
            request: входящий запрос
            call_next: следующий middleware/обработчик
        Returns:
            Response от следующего обработчика либо JSON 401
        """
        # Пропустить проверку JWT для публичных эндпоинтов
        path = request.url.path
        if path in PUBLIC_ENDPOINTS or path.startswith("/docs"):
            return await call_next(request)

        # Пропустить проверку JWT для вебхуков
        if any(path.startswith(prefix) for prefix in WEBHOOK_PREFIXES):
            return await call_next(request)

        # Нет cookie — сразу 401, не тратим время на декодирование
        token = request.cookies.get("access_token")
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        # Проверка подписи и срока действия токена
        try:
            # Сессии БД здесь нет — проверяем только формат/подпись JWT
            # Полная загрузка пользователя — в обработчиках (get_current_admin)
            import jwt

            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )

            # Проверка срока действия (exp)
            from datetime import datetime

            exp = payload.get("exp")
            if exp and datetime.utcnow().timestamp() > exp:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Token expired"},
                )

        except jwt.PyJWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid token"},
            )

        # Токен валиден — передать запрос дальше
        response = await call_next(request)
        return response
