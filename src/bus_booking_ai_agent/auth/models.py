from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuthenticatedUser(BaseModel):
    """
    Represents a user authenticated by Supabase Auth.

    The `id` field is the real Supabase Auth user UUID.
    This model must never be constructed from client-supplied user data.
    """

    id: UUID
    email: str | None = None
    role: str | None = None

    app_metadata: dict[str, Any] = Field(default_factory=dict)
    user_metadata: dict[str, Any] = Field(default_factory=dict)