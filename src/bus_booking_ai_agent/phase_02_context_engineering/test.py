from bus_booking_ai_agent.phase_01_llm_fundamentals.system_instructions import (
    SYSTEM_INSTRUCTION,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_sources import (
    ContextSources,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_selection import (
    ContextSelector,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_compression import (
    ContextCompressor,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_ordering import (
    ContextOrdering,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_formatter import (
    ContextFormatter,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_injection import (
    ContextInjector,
)

from bus_booking_ai_agent.phase_02_context_engineering.dynamic_context import (
    DynamicContext,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_management import (
    ContextManager,
)


def main():
    print("\n========================================")
    print("   PHASE 02: CONTEXT ENGINEERING")
    print("========================================")

    print("\nTopic 08: Context Management")

    # ----------------------------------------
    # Initialize context components
    # ----------------------------------------

    context_sources = ContextSources()

    context_selector = ContextSelector()

    context_compressor = ContextCompressor()

    context_ordering = ContextOrdering()

    context_formatter = ContextFormatter()

    context_injector = ContextInjector()

    dynamic_context = DynamicContext()

    # ----------------------------------------
    # Initialize Context Manager
    #
    # ContextManager coordinates:
    # Selection
    # Compression
    # Ordering
    # Formatting
    # ----------------------------------------

    context_manager = ContextManager(
        context_selector=context_selector,
        context_compressor=context_compressor,
        context_ordering=context_ordering,
        context_formatter=context_formatter,
    )

    # ----------------------------------------
    # Set static system instruction
    # ----------------------------------------

    context_sources.set_system_instruction(
        SYSTEM_INSTRUCTION
    )

    print("\nType your messages below.")
    print("Type 'exit' to finish.")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == "exit":
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ----------------------------------------
        # 1. Build dynamic context
        # ----------------------------------------

        dynamic_context.build(
            context_sources=context_sources,
            user_message=user_input,
            previous_interaction_id=(
                context_sources.previous_interaction_id
            ),
        )

        # ----------------------------------------
        # 2. Context Management
        #
        # ContextManager handles:
        # - Context Selection
        # - Context Compression
        # - Context Ordering
        # - Context Formatting
        # ----------------------------------------

        managed_context = context_manager.prepare(
            context_sources
        )

        # ----------------------------------------
        # Extract managed context stages
        # ----------------------------------------

        selected_context = managed_context[
            "selected_context"
        ]

        compressed_context = managed_context[
            "compressed_context"
        ]

        ordered_context = managed_context[
            "ordered_context"
        ]

        formatted_context = managed_context[
            "formatted_context"
        ]

        # ----------------------------------------
        # 3. Display Selected Context
        # ----------------------------------------

        print("\n--- Selected Context ---")

        for source_name, source_value in selected_context.items():
            print(f"\n{source_name.upper()}:")
            print(source_value)

        # ----------------------------------------
        # 4. Display Compressed Context
        # ----------------------------------------

        print("\n--- Compressed Context ---")

        for source_name, source_value in compressed_context.items():
            print(f"\n{source_name.upper()}:")
            print(source_value)

        # ----------------------------------------
        # 5. Display Ordered Context
        # ----------------------------------------

        print("\n--- Ordered Context ---")

        for source_name, source_value in ordered_context.items():
            print(f"\n{source_name.upper()}:")
            print(source_value)

        # ----------------------------------------
        # 6. Display Formatted Context
        # ----------------------------------------

        print("\n--- Formatted Context ---")
        print(formatted_context)

        # ----------------------------------------
        # 7. Get previous interaction ID
        # ----------------------------------------

        previous_interaction_id = (
            context_sources.previous_interaction_id
        )

        if previous_interaction_id:
            print("\n--- Previous Interaction ID ---")
            print(previous_interaction_id)

        # ----------------------------------------
        # 8. Inject context into Gemini
        #
        # System instruction:
        #     sent separately
        #
        # Formatted context:
        #     sent as input
        #
        # Previous interaction ID:
        #     sent separately
        # ----------------------------------------

        interaction = context_injector.inject(
            formatted_context=formatted_context,
            system_instruction=SYSTEM_INSTRUCTION,
            previous_interaction_id=previous_interaction_id,
        )

        # ----------------------------------------
        # 9. Update dynamic state
        #
        # The current interaction becomes the
        # previous interaction for the next turn.
        # ----------------------------------------

        context_sources.set_previous_interaction_id(
            interaction.id
        )

        # ----------------------------------------
        # 10. Display Gemini response
        # ----------------------------------------

        print("\nGemini:")
        print(interaction.output_text)

    print("\n========================================")
    print("   TOPIC 08 COMPLETED")
    print("========================================")


if __name__ == "__main__":
    main()