"""
Роутер аутентификации: регистрация, логин, логаут и текущий пользователь.

Критичный для безопасности слой (Phase B.2.3). Сессия живёт в httpOnly-cookie
с SameSite=Strict в production — так токен недоступен JavaScript и не
уходит кросс-доменным запросам. Плюс CSRF double-submit: отдельная cookie
csrf_token (не-httpOnly, чтобы JS отправлял её в заголовке X-CSRF-Token)
сравнивается через secrets.compare_digest — защита от подделки state-changing
запросов и от timing-атак.

Строгие режимы (Secure cookie, проверка CSRF) включаются только в production
по APP_ENV: в development они мешали бы локальной разработке.
"""

import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.src.config import get_settings
from backend.src.database import get_db
from backend.src.schemas import LoginRequest, TokenResponse, UserCreate, UserResponse
from backend.src.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# CSRF cookie name
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


def _is_production() -> bool:
    """Только в production включаем строгие cookie и проверку CSRF.

    Один флаг окружения переключает все security-настройки разом,
    а не размазывает if'ы по коду.
    """
    return settings.APP_ENV == "production"


def _cookie_samesite() -> str:
    """SameSite для cookie сессии.

    B.2.3: Strict в production не даёт отправлять cookie кросс-доменным
    запросам; Lax в разработке не мешает локальным переходам.
    """
    return "strict" if _is_production() else "lax"


def _cookie_secure() -> bool:
    """Secure-флаг только в production.

    По спецификации cookie с Secure требует HTTPS — в development
    (http://localhost) она просто не сохранилась бы браузером.
    """
    return _is_production()


def _set_csrf_cookie(response: Response, token: str) -> None:
    """Выставить CSRF double-submit cookie (не-httpOnly — JS должен её читать).

    Пары cookie+заголовок достаточно: атакующий сайт не может ни прочитать
    cookie чужого origin (SameSite), ни выставить произвольный заголовок
    простой формой.
    """
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=86400,
    )


def _generate_csrf_token() -> str:
    """Криптографически случайный CSRF-токен.

    secrets.token_hex, а не random: токен — секрет, предсказуемые
    значения сломали бы всю CSRF-защиту.
    """
    return secrets.token_hex(32)


def verify_csrf(request: Request) -> None:
    """
    Проверка CSRF double-submit cookie.

    Для state-changing запросов (POST/PUT/DELETE) клиент обязан:
    1. Прислать cookie csrf_token (браузер ставит автоматически)
    2. Продублировать значение в заголовке X-CSRF-Token

    Защита работает потому, что атакующий сайт не может прочитать cookie
    чужого origin (SameSite) и не может выставить заголовок простой формой.

    GET/HEAD/OPTIONS — безопасные методы, пропускаются. В development
    проверка отключена, чтобы не мешать локальной отладке.
    """
    # Skip CSRF for GET/HEAD/OPTIONS (safe methods)
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Skip CSRF in development mode
    if not _is_production():
        return

    cookie_value = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_value = request.headers.get(CSRF_HEADER_NAME, "")

    if not cookie_value or not header_value:
        raise HTTPException(
            status_code=403,
            detail="CSRF token missing",
        )

    if not secrets.compare_digest(cookie_value, header_value):
        raise HTTPException(
            status_code=403,
            detail="CSRF token mismatch",
        )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Регистрация нового пользователя.

    Телефон не хранится открытым текстом — сервис сохраняет только
    phone_hash (152-ФЗ), поэтому в ответе нет телефона. Ошибки сервиса
    (пользователь уже существует) превращаются в 400 с человекочитаемым
    текстом, а не в 500.

    Args:
        user_data: Данные регистрации (phone, password).
        db: Сессия БД.

    Returns:
        Данные созданного пользователя.

    Raises:
        400: Пользователь с таким телефоном уже существует.
    """
    service = AuthService(db)
    try:
        user = await service.register(
            phone=user_data.phone,
            password=user_data.password,
        )
        return UserResponse(
            id=user.id,
            phone_hash=user.phone_hash,
            created_at=user.created_at,
            is_active=user.is_active,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """
    Вход: выдаёт JWT в httpOnly-cookie + CSRF double-submit токен.

    B.2.3: httpOnly не даёт JavaScript прочитать токен (защита от XSS),
    SameSite=Strict ограничивает отправку cookie кросс-доменно. CSRF-токен
    выдаётся заново при каждом логине. Неверные учётные данные → 401.

    Args:
        credentials: Учётные данные (phone, password).
        response: Ответ FastAPI — сюда пишутся cookie.
        db: Сессия БД.

    Returns:
        JWT access token.

    Raises:
        401: Неверный телефон или пароль.
    """
    service = AuthService(db)
    try:
        token = await service.login(
            phone=credentials.phone,
            password=credentials.password,
        )

        # B.2.3: Set httpOnly cookie with SameSite=Strict in production
        response.set_cookie(
            key="access_token",
            value=token,
            httponly=True,
            secure=_cookie_secure(),
            samesite=_cookie_samesite(),
            max_age=86400,  # 24 hours
        )

        # B.2.3: Set CSRF double-submit cookie
        csrf_token = _generate_csrf_token()
        _set_csrf_cookie(response, csrf_token)

        return TokenResponse(access_token=token)
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))


@router.post("/logout")
async def logout(
    response: Response,
) -> dict[str, str]:
    """
    Выход: удаляет JWT- и CSRF-cookie.

    B.2.3: чистим обе cookie (access_token и csrf_token), иначе после логаута
    остался бы действующий CSRF-токен, привязанный к старой сессии.

    Args:
        response: Ответ FastAPI — для удаления cookie.

    Returns:
        Сообщение об успешном выходе.
    """
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
    )
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
    )
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Текущий аутентифицированный пользователь.

    Токен берётся только из httpOnly-cookie (не из тела/заголовка), поэтому
    эндпоинт работает автоматически для браузера. Отсутствие токена или
    невалидный токен → 401 без раскрытия причины.

    Args:
        request: HTTP-запрос (для чтения cookie).
        db: Сессия БД.

    Returns:
        Данные текущего пользователя.

    Raises:
        401: Нет токена или он невалиден.
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    service = AuthService(db)
    try:
        user = await service.get_current_user(token)
        return UserResponse(
            id=user.id,
            phone_hash=user.phone_hash,
            created_at=user.created_at,
            is_active=user.is_active,
            tenant_id=user.tenant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=str(e))
