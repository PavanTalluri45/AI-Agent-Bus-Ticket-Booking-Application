from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

from .models import AuthenticatedUser
from .verifier import authenticate_supabase_token


bearer_scheme = HTTPBearer(
    auto_error=False,
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> AuthenticatedUser:
    """
    FastAPI dependency that returns the authenticated Supabase user.

    The user identity comes only from the Supabase access token.
    """

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return await authenticate_supabase_token(
        credentials.credentials
    )