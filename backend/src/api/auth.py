"""
Auth Router
Endpoints for user registration, login, logout

Security (Phase B.2.3):
- SameSite=Strict cookies for production
- CSRF double-submit cookie pattern
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
    """Check if running in production environment."""
    return settings.APP_ENV == "production"


def _cookie_samesite() -> str:
    """B.2.3: SameSite=Strict in production, Lax in development."""
    return "strict" if _is_production() else "lax"


def _cookie_secure() -> bool:
    """Secure flag only in production (requires HTTPS)."""
    return _is_production()


def _set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF double-submit cookie (non-httpOnly so JS can read it)."""
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=_cookie_secure(),
        samesite=_cookie_samesite(),
        max_age=86400,
    )


def _generate_csrf_token() -> str:
    """Generate a cryptographically random CSRF token."""
    return secrets.token_hex(32)


def verify_csrf(request: Request) -> None:
    """
    Verify CSRF double-submit cookie.

    For state-changing requests (POST/PUT/DELETE), the client must:
    1. Include the csrf_token cookie (set automatically by the browser)
    2. Send the same value in the X-CSRF-Token header

    This prevents CSRF because an attacker cannot read cookies from
    a different origin (SameSite policy) and cannot set headers
    via simple forms.
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
    Register new user.

    Args:
        user_data: User registration data (phone, password)
        db: Database session

    Returns:
        Created user data

    Raises:
        400: If user already exists
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
    Login user and set JWT cookie.

    B.2.3: Sets SameSite=Strict cookie + CSRF double-submit token.

    Args:
        credentials: Login credentials (phone, password)
        response: FastAPI response for setting cookie
        db: Database session

    Returns:
        JWT access token

    Raises:
        401: If credentials are invalid
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
    Logout user by clearing JWT cookie.

    B.2.3: Clears CSRF cookie too.

    Args:
        response: FastAPI response for clearing cookie

    Returns:
        Success message
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
    Get current authenticated user.

    Args:
        request: HTTP request (for cookie access)
        db: Database session

    Returns:
        Current user data

    Raises:
        401: If not authenticated
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
