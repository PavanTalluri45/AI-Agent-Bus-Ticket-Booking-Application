from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    """
    Trusted representation of the currently authenticated
    Supabase user.

    The identity originates from Supabase Auth.
    """

    id: UUID
    email: str | None = None

    app_metadata: dict[str, Any] = Field(
        default_factory=dict
    )

    user_metadata: dict[str, Any] = Field(
        default_factory=dict
    )