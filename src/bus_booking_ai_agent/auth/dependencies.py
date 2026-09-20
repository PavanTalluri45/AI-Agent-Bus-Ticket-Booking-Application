from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from .models import AuthenticatedUser
from .verifier import get_supabase_user


_bearer_scheme = HTTPBearer(
    auto_error=False
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
) -> AuthenticatedUser:
    """
    FastAPI dependency that returns the currently
    authenticated Supabase user.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    access_token = credentials.credentials.strip()

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return await get_supabase_user(
        access_token
    )