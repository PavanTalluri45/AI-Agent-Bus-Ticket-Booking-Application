class ContextOrdering:
    """
    Defines the order in which selected context sources
    should be presented to the LLM.
    """

    ORDER = [
        "system_instruction",
        "previous_interaction_id",
        "user_message",
    ]

    def order(self, selected_context):
        ordered_context = {}

        for source_name in self.ORDER:
            if source_name in selected_context:
                ordered_context[source_name] = (
                    selected_context[source_name]
                )

        return ordered_context