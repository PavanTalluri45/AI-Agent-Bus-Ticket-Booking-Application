from bus_booking_ai_agent.config.gemini import client, MODEL


class ConversationHistory:
    """
    Manages the current Gemini conversation.

    The Gemini interaction ID is used to continue
    the conversation across multiple turns.
    """

    def __init__(self):
        self.previous_interaction_id = None

    def send_message(self, user_input, system_instruction=None):
        """
        Send a user message while preserving conversation history.
        """

        if self.previous_interaction_id is None:
            interaction = client.interactions.create(
                model=MODEL,
                system_instruction=system_instruction,
                input=user_input,
            )
        else:
            interaction = client.interactions.create(
                model=MODEL,
                system_instruction=system_instruction,
                input=user_input,
                previous_interaction_id=self.previous_interaction_id,
            )

        # Save the current interaction ID so the next
        # message continues the same conversation.
        self.previous_interaction_id = interaction.id

        return interaction

    def reset(self):
        """
        Start a new conversation.
        """
        self.previous_interaction_id = None