class ContextSelector:
    """
    Selects the context sources required for the current request.

    Current selection policy:
    - System instructions are always selected because they define the
      assistant's behavior.
    - The current user message is always selected because it is the
      immediate task/request.
    - The previous interaction ID is selected only when a previous
      interaction exists.

    This is intentionally deterministic for the learning project.
    More advanced selection strategies will be introduced when
    additional real context sources become available.
    """

    def select(self, context_sources):
        selected_context = {}

        # Always include the rules that control the assistant.
        if context_sources.system_instruction:
            selected_context["system_instruction"] = (
                context_sources.system_instruction
            )

        # Always include the user's current request.
        if context_sources.user_message:
            selected_context["user_message"] = (
                context_sources.user_message
            )

        # Include the previous interaction ID only when it exists.
        if context_sources.previous_interaction_id:
            selected_context["previous_interaction_id"] = (
                context_sources.previous_interaction_id
            )

        return selected_context