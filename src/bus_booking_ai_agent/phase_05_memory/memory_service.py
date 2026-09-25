from sqlalchemy import text

from bus_booking_ai_agent.config.database import engine


CREATE_MEMORY_SQL = """
INSERT INTO user_memories (
    user_id,
    memory_type,
    memory_key,
    memory_value
)
VALUES (
    :user_id,
    :memory_type,
    :memory_key,
    :memory_value
)
ON CONFLICT (
    user_id,
    memory_type,
    memory_key
)
DO UPDATE SET
    memory_value = EXCLUDED.memory_value,
    updated_at = NOW()
RETURNING
    id,
    user_id,
    memory_type,
    memory_key,
    memory_value,
    created_at,
    updated_at;
"""


GET_MEMORY_SQL = """
SELECT
    id,
    user_id,
    memory_type,
    memory_key,
    memory_value,
    created_at,
    updated_at
FROM user_memories
WHERE
    user_id = :user_id
    AND memory_type = :memory_type
    AND memory_key = :memory_key;
"""


GET_USER_MEMORIES_SQL = """
SELECT
    id,
    user_id,
    memory_type,
    memory_key,
    memory_value,
    created_at,
    updated_at
FROM user_memories
WHERE
    user_id = :user_id
ORDER BY updated_at DESC;
"""


DELETE_MEMORY_SQL = """
DELETE FROM user_memories
WHERE
    user_id = :user_id
    AND memory_type = :memory_type
    AND memory_key = :memory_key;
"""


def save_memory(
    user_id: str,
    memory_type: str,
    memory_key: str,
    memory_value: str,
) -> dict:

    with engine.begin() as connection:

        result = connection.execute(
            text(CREATE_MEMORY_SQL),
            {
                "user_id": user_id,
                "memory_type": memory_type,
                "memory_key": memory_key,
                "memory_value": memory_value,
            },
        )

        row = result.fetchone()

        if row is None:
            raise RuntimeError(
                "Memory was not saved."
            )

        return dict(row._mapping)


def get_memory(
    user_id: str,
    memory_type: str,
    memory_key: str,
) -> dict | None:

    with engine.connect() as connection:

        result = connection.execute(
            text(GET_MEMORY_SQL),
            {
                "user_id": user_id,
                "memory_type": memory_type,
                "memory_key": memory_key,
            },
        )

        row = result.fetchone()

        if row is None:
            return None

        return dict(row._mapping)


def get_user_memories(
    user_id: str,
) -> list[dict]:

    with engine.connect() as connection:

        result = connection.execute(
            text(GET_USER_MEMORIES_SQL),
            {
                "user_id": user_id,
            },
        )

        return [
            dict(row._mapping)
            for row in result
        ]


def delete_memory(
    user_id: str,
    memory_type: str,
    memory_key: str,
) -> bool:

    with engine.begin() as connection:

        result = connection.execute(
            text(DELETE_MEMORY_SQL),
            {
                "user_id": user_id,
                "memory_type": memory_type,
                "memory_key": memory_key,
            },
        )

        return result.rowcount > 0