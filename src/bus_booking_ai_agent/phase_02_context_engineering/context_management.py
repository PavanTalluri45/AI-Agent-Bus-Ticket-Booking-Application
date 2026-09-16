class ContextManager:
    """
    Manages the lifecycle of context for the current request.

    The manager coordinates the existing context-engineering
    components without taking over their individual responsibilities.
    """

    def __init__(
        self,
        context_selector,
        context_compressor,
        context_ordering,
        context_formatter,
    ):
        self.context_selector = context_selector
        self.context_compressor = context_compressor
        self.context_ordering = context_ordering
        self.context_formatter = context_formatter

    def prepare(
        self,
        context_sources,
    ):
        # ----------------------------------------
        # 1. Select context
        # ----------------------------------------

        selected_context = self.context_selector.select(
            context_sources
        )

        # ----------------------------------------
        # 2. Compress context
        # ----------------------------------------

        compressed_context = self.context_compressor.compress(
            selected_context,
            exclude_sources=[
                "system_instruction",
                "previous_interaction_id",
            ],
        )

        # ----------------------------------------
        # 3. Order context
        # ----------------------------------------

        ordered_context = self.context_ordering.order(
            compressed_context
        )

        # ----------------------------------------
        # 4. Format context
        # ----------------------------------------

        formatted_context = self.context_formatter.format(
            ordered_context
        )

        return {
            "selected_context": selected_context,
            "compressed_context": compressed_context,
            "ordered_context": ordered_context,
            "formatted_context": formatted_context,
        }