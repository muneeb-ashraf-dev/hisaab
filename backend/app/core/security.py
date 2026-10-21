from __future__ import annotations

import secrets

from fastapi import Header, HTTPException, status

from app.core.config import settings


def require_auth(authorization: str | None = Header(default=None)) -> None:
    """Optional single-user bearer authentication.

    When ``API_AUTH_TOKEN`` is unset the API is intended for localhost-only use.
    When it is set, every /api/v1 route requires the token. The Next.js server
    proxy attaches the token server-side so it is never shipped to browsers.
    """
    if not settings.auth_enabled:
        return

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    supplied = authorization[7:].strip()
    if not secrets.compare_digest(supplied, settings.api_auth_token or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
