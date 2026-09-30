"""
JWT Middleware
Automatic JWT validation for protected routes
"""

from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from backend.src.config import get_settings

settings = get_settings()

# Public endpoints that don't require authentication
PUBLIC_ENDPOINTS = {
    "/",
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/auth/login",
    "/auth/register",
}

# Webhook endpoints that don't require authentication
WEBHOOK_PREFIXES = {"/webhook/"}


class JWTMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT validation on protected routes."""

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        """
        Process request through JWT middleware.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint handler

        Returns:
            Response from next handler or 401/403 error
        """
        # Skip JWT validation for public endpoints
        path = request.url.path
        if path in PUBLIC_ENDPOINTS or path.startswith("/docs"):
            return await call_next(request)

        # Skip JWT validation for webhook endpoints
        if any(path.startswith(prefix) for prefix in WEBHOOK_PREFIXES):
            return await call_next(request)

        # Skip if no cookie
        token = request.cookies.get("access_token")
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )

        # Validate token
        try:
            # Note: We don't have db session here, so we just validate the token format
            # The actual user lookup happens in route handlers
            import jwt

            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
            )

            # Check expiration
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

        # Continue to next handler
        response = await call_next(request)
        return response
