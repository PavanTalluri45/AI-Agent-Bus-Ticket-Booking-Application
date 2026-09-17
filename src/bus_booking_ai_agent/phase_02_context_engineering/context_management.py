class ContextManager:
    """
    Manages the lifecycle of context for the current request.

    The manager coordinates:
    1. Context selection
    2. Context prioritization
    3. Context compression
    4. Context ordering
    5. Context formatting

    The manager does not perform model injection.
    """

    def __init__(
        self,
        context_selector,
        context_prioritizer,
        context_compressor,
        context_ordering,
        context_formatter,
    ):
        self.context_selector = context_selector
        self.context_prioritizer = context_prioritizer
        self.context_compressor = context_compressor
        self.context_ordering = context_ordering
        self.context_formatter = context_formatter

    def prepare(
        self,
        context_sources,
    ):
        # 1. Select relevant context
        selected_context = self.context_selector.select(
            context_sources
        )

        # 2. Prioritize semantic context
        prioritized_context = (
            self.context_prioritizer.prioritize(
                selected_context
            )
        )

        # 3. Compress context
        #
        # System instruction and previous interaction ID
        # are handled separately by Gemini.
        compressed_context = self.context_compressor.compress(
            selected_context,
            exclude_sources=[
                "system_instruction",
                "previous_interaction_id",
            ],
        )

        # 4. Order context
        ordered_context = self.context_ordering.order(
            compressed_context
        )

        # 5. Format context
        formatted_context = self.context_formatter.format(
            ordered_context
        )

        return {
            "selected_context": selected_context,
            "prioritized_context": prioritized_context,
            "compressed_context": compressed_context,
            "ordered_context": ordered_context,
            "formatted_context": formatted_context,
        }