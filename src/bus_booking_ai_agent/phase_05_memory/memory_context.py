from bus_booking_ai_agent.phase_05_memory.memory_service import (
    get_user_memories,
)


def get_relevant_memories(
    user_id: str,
) -> list[dict]:

    memories = get_user_memories(user_id)

    return [
        {
            "type": memory["memory_type"],
            "key": memory["memory_key"],
            "value": memory["memory_value"],
        }
        for memory in memories
    ]