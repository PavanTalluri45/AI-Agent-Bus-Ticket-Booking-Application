class ContextFormatter:
    """
    Formats selected context sources without changing their order.

    Context ordering is handled separately by ContextOrdering.

    The system instruction and previous interaction ID can be
    excluded from the formatted model input because they are
    handled separately by Gemini.
    """

    def format(
        self,
        selected_context,
        exclude_sources=None,
    ):
        sections = []

        exclude_sources = exclude_sources or []

        for source_name, source_value in selected_context.items():
            if source_name in exclude_sources:
                continue

            if not source_value:
                continue

            label = source_name.replace("_", " ").upper()

            sections.append(
                f"{label}:\n"
                f"{source_value}"
            )

        return "\n\n".join(sections)