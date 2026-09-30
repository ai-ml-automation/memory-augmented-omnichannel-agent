"""
Общие FastAPI-зависимости (dependencies) для обработчиков роутеров.

Вынесены в отдельный модуль, чтобы логика аутентификации и авторизации
не дублировалась в каждом роутере: роутеры лишь указывают
`Depends(get_current_admin)`.

Здесь реализована проверка admin-роли поверх JWT-аутентификации
(`AuthService.get_current_user`); базовую проверку формата токена
выполняет middleware `backend.src.middleware.JWTMiddleware`.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.database import get_db
from backend.src.models import User
from backend.src.services.auth_service import AuthService


async def get_current_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Dependency admin-эндпоинтов: JWT + роль (токен из HttpOnly-cookie,
    единая точка проверки; 401/403).

    Args:
        request: HTTP-запрос с cookie access_token
        db: сессия БД (из `get_db`)
    Returns:
        User: аутентифицированный пользователь с ролью admin
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    auth_service = AuthService(db)
    try:
        user = await auth_service.get_current_user(token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))

    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return user
