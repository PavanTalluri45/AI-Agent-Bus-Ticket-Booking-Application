class ContextPrioritizer:
    """
    Assigns priority levels to the currently available
    semantic context sources.

    Lower priority number means higher importance.

    Current learning priorities:
    1. System instruction
    2. User message

    Previous interaction ID is control metadata rather
    than semantic context, so it is not prioritized here.
    """

    PRIORITY = {
        "system_instruction": 1,
        "user_message": 2,
    }

    def prioritize(self, selected_context):
        prioritized_context = {}

        for source_name, source_value in selected_context.items():
            if not source_value:
                continue

            priority = self.PRIORITY.get(source_name)

            if priority is None:
                continue

            prioritized_context[source_name] = {
                "priority": priority,
                "value": source_value,
            }

        return dict(
            sorted(
                prioritized_context.items(),
                key=lambda item: item[1]["priority"],
            )
        )