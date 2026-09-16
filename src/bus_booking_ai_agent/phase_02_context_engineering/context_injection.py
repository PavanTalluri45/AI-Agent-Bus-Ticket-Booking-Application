from bus_booking_ai_agent.config.gemini import client, MODEL


class ContextInjector:
    """
    Injects engineered context into Gemini while preserving
    multi-turn conversation continuity.
    """

    def inject(
        self,
        formatted_context,
        system_instruction=None,
        previous_interaction_id=None,
    ):
        return client.interactions.create(
            model=MODEL,
            system_instruction=system_instruction,
            input=formatted_context,
            previous_interaction_id=previous_interaction_id,
        )