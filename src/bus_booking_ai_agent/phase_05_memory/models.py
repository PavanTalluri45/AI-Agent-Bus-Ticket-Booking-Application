from pydantic import BaseModel, Field


class UserMemory(BaseModel):
    id: str | None = None

    user_id: str

    memory_type: str = Field(min_length=1)
    memory_key: str = Field(min_length=1)
    memory_value: str = Field(min_length=1)