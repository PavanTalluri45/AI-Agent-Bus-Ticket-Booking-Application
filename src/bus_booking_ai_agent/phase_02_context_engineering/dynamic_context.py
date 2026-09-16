class DynamicContext:
    """
    Builds the context required for the current request.

    Dynamic values can change from one conversation turn
    to the next.
    """

    def build(
        self,
        context_sources,
        user_message,
        previous_interaction_id=None,
    ):
        context_sources.set_user_message(
            user_message
        )

        context_sources.set_previous_interaction_id(
            previous_interaction_id
        )

        return context_sources