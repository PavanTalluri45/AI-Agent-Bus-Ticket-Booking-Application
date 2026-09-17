from bus_booking_ai_agent.phase_01_llm_fundamentals.system_instructions import (
    SYSTEM_INSTRUCTION,
)

from bus_booking_ai_agent.phase_02_context_engineering.agent_context import (
    AgentContext,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_sources import (
    ContextSources,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_selection import (
    ContextSelector,
)

from bus_booking_ai_agent.phase_02_context_engineering.context_prioritization import (
    ContextPrioritizer,
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


def create_context_manager():
    """
    Create and configure the context-engineering pipeline.
    """

    context_selector = ContextSelector()
    context_prioritizer = ContextPrioritizer()
    context_compressor = ContextCompressor()
    context_ordering = ContextOrdering()
    context_formatter = ContextFormatter()

    return ContextManager(
        context_selector=context_selector,
        context_prioritizer=context_prioritizer,
        context_compressor=context_compressor,
        context_ordering=context_ordering,
        context_formatter=context_formatter,
    )


def display_agent_context(agent_context):
    """
    Display the context currently available to the agent.
    """

    print("\n--- Agent Context ---")

    context = agent_context.get_context()

    for source_name, source_value in context.items():
        print(f"\n{source_name.upper()}:")
        print(source_value)


def display_context_pipeline(context_result):
    """
    Display the context-engineering pipeline.
    """

    print("\n--- Selected Context ---")

    for source_name, source_value in (
        context_result["selected_context"].items()
    ):
        print(f"\n{source_name.upper()}:")
        print(source_value)

    print("\n--- Prioritized Context ---")

    for source_name, context_data in (
        context_result["prioritized_context"].items()
    ):
        print(f"\n{source_name.upper()}:")
        print(f"Priority: {context_data['priority']}")
        print(context_data["value"])

    print("\n--- Compressed Context ---")

    for source_name, source_value in (
        context_result["compressed_context"].items()
    ):
        print(f"\n{source_name.upper()}:")
        print(source_value)

    print("\n--- Ordered Context ---")

    for source_name, source_value in (
        context_result["ordered_context"].items()
    ):
        print(f"\n{source_name.upper()}:")
        print(source_value)

    print("\n--- Formatted Context ---")
    print(context_result["formatted_context"])


def main():
    """
    Demonstrates Context Engineering for Agents.

    Flow:

        User Message
             ↓
        Dynamic Context
             ↓
        Agent Context
             ↓
        Context Manager
             ↓
        Selection
             ↓
        Prioritization
             ↓
        Compression
             ↓
        Ordering
             ↓
        Formatting
             ↓
        Context Injection
             ↓
        Gemini
    """

    print("\n========================================")
    print("   PHASE 02: CONTEXT ENGINEERING")
    print("   TOPIC 10: CONTEXT FOR AGENTS")
    print("========================================")

    # ----------------------------------------
    # Initialize components
    # ----------------------------------------

    agent_context = AgentContext()

    context_sources = ContextSources()

    dynamic_context = DynamicContext()

    context_manager = create_context_manager()

    context_injector = ContextInjector()

    # ----------------------------------------
    # Set static system instruction
    # ----------------------------------------

    agent_context.set_system_instruction(
        SYSTEM_INSTRUCTION
    )

    context_sources.set_system_instruction(
        SYSTEM_INSTRUCTION
    )

    print("\nType your messages below.")
    print("Type 'exit' to finish.")

    # ----------------------------------------
    # Conversation loop
    # ----------------------------------------

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == "exit":
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ------------------------------------
        # 1. Update dynamic context
        # ------------------------------------

        dynamic_context.build(
            context_sources=context_sources,
            user_message=user_input,
            previous_interaction_id=(
                context_sources.previous_interaction_id
            ),
        )

        # ------------------------------------
        # 2. Update agent context
        # ------------------------------------

        agent_context.set_user_message(
            user_input
        )

        # ------------------------------------
        # 3. Add conversation information
        # ------------------------------------

        if context_sources.previous_interaction_id:
            agent_context.set_conversation_history(
                "Previous Gemini interaction exists."
            )

        # ------------------------------------
        # 4. Display current agent context
        # ------------------------------------

        display_agent_context(
            agent_context
        )

        # ------------------------------------
        # 5. Prepare context
        # ------------------------------------

        context_result = context_manager.prepare(
            context_sources
        )

        # ------------------------------------
        # 6. Display context pipeline
        # ------------------------------------

        display_context_pipeline(
            context_result
        )

        # ------------------------------------
        # 7. Get previous interaction ID
        # ------------------------------------

        previous_interaction_id = (
            context_sources.previous_interaction_id
        )

        if previous_interaction_id:
            print("\n--- Previous Interaction ID ---")
            print(previous_interaction_id)

        # ------------------------------------
        # 8. Inject context into Gemini
        # ------------------------------------

        interaction = context_injector.inject(
            formatted_context=(
                context_result["formatted_context"]
            ),
            system_instruction=SYSTEM_INSTRUCTION,
            previous_interaction_id=(
                previous_interaction_id
            ),
        )

        # ------------------------------------
        # 9. Update conversation state
        # ------------------------------------

        context_sources.set_previous_interaction_id(
            interaction.id
        )

        # ------------------------------------
        # 10. Display Gemini response
        # ------------------------------------

        print("\nGemini:")
        print(interaction.output_text)

    print("\n========================================")
    print("  PHASE 2 FINISHED")
    print("========================================")


if __name__ == "__main__":
    main()