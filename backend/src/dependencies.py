"""
FastAPI Dependencies
Shared dependencies for route handlers
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
    Dependency that validates JWT and checks for admin role.

    Used by admin-only endpoints to enforce role-based access control.

    Args:
        request: HTTP request with access_token cookie
        db: Database session

    Returns:
        Authenticated User with admin role

    Raises:
        HTTPException: 401 if not authenticated, 403 if not admin
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
