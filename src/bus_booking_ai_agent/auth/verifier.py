import os

import httpx
from fastapi import HTTPException, status

from .models import AuthenticatedUser


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")


async def authenticate_supabase_token(
    token: str,
) -> AuthenticatedUser:
    """
    Authenticate a Supabase access token.

    Supabase Auth is responsible for validating the token.

    This application does not:
    - decode JWTs
    - verify JWT signatures
    - inspect JWT claims
    - generate tokens
    """

    if not SUPABASE_URL:
        raise RuntimeError("SUPABASE_URL is not configured.")

    if not SUPABASE_PUBLISHABLE_KEY:
        raise RuntimeError(
            "SUPABASE_PUBLISHABLE_KEY is not configured."
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SUPABASE_URL}/auth/v1/user",
                headers={
                    "Authorization": f"Bearer {token}",
                    "apikey": SUPABASE_PUBLISHABLE_KEY,
                },
                timeout=10.0,
            )

    except httpx.HTTPError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication service unavailable.",
        ) from error

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    try:
        data = response.json()

        return AuthenticatedUser(
            id=data["id"],
            email=data.get("email"),
            role=data.get("role"),
            app_metadata=data.get(
                "app_metadata",
                {},
            ),
            user_metadata=data.get(
                "user_metadata",
                {},
            ),
        )

    except (KeyError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid identity data.",
        ) from error