class ContextCompressor:
    """
    Compresses selected context by removing context sources
    that do not need to be included in the formatted model input.

    This is a deterministic learning implementation.

    Important:
    System instructions and previous interaction IDs are not
    deleted from the overall application state. They are only
    excluded from the text context because Gemini handles them
    separately.
    """

    def compress(
        self,
        selected_context,
        exclude_sources=None,
    ):
        exclude_sources = exclude_sources or []

        compressed_context = {}

        for source_name, source_value in selected_context.items():
            if source_name in exclude_sources:
                continue

            if not source_value:
                continue

            compressed_context[source_name] = source_value

        return compressed_context