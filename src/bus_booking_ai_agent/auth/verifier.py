import os
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import HTTPException, status
from pydantic import ValidationError

from .models import AuthenticatedUser


load_dotenv()


SUPABASE_USER_ENDPOINT = "/auth/v1/user"
SUPABASE_REQUEST_TIMEOUT = 10.0


def _get_supabase_configuration() -> tuple[str, str]:
    """
    Read and validate the Supabase configuration.

    Returns:
        A tuple containing:
        - Supabase URL
        - Supabase publishable key
    """

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_publishable_key = os.getenv(
        "SUPABASE_PUBLISHABLE_KEY"
    )

    if not supabase_url:
        raise RuntimeError(
            "SUPABASE_URL is not configured."
        )

    if not supabase_publishable_key:
        raise RuntimeError(
            "SUPABASE_PUBLISHABLE_KEY is not configured."
        )

    return (
        supabase_url,
        supabase_publishable_key,
    )


async def get_supabase_user(
    access_token: str,
) -> AuthenticatedUser:
    """
    Verify the Supabase access token by asking
    Supabase Auth for the authenticated user.

    Supabase remains the authentication authority.
    FastAPI does not decode or validate the JWT itself.
    """

    supabase_url, supabase_publishable_key = (
        _get_supabase_configuration()
    )

    if not access_token or not access_token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    try:
        async with httpx.AsyncClient(
            timeout=SUPABASE_REQUEST_TIMEOUT
        ) as client:

            response = await client.get(
                f"{supabase_url.rstrip('/')}"
                f"{SUPABASE_USER_ENDPOINT}",
                headers={
                    "Authorization": (
                        f"Bearer {access_token}"
                    ),
                    "apikey": supabase_publishable_key,
                },
            )

    except httpx.RequestError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable.",
        ) from error

    if response.status_code != httpx.codes.OK:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed.",
        )

    try:
        data: dict[str, Any] = response.json()

        return AuthenticatedUser(
            id=data["id"],
            email=data.get("email"),
            app_metadata=data.get(
                "app_metadata"
            ) or {},
            user_metadata=data.get(
                "user_metadata"
            ) or {},
        )

    except (
        KeyError,
        TypeError,
        ValidationError,
    ) as error:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed: invalid user data.",
        ) from error