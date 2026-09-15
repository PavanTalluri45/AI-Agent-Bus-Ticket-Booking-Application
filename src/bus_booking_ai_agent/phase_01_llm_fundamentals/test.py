from bus_booking_ai_agent.config.gemini import client, MODEL
from bus_booking_ai_agent.phase_01_llm_fundamentals.tokens import print_usage
from bus_booking_ai_agent.phase_01_llm_fundamentals.context_window import (
    print_model_limits,
)
from bus_booking_ai_agent.phase_01_llm_fundamentals.system_instructions import (
    SYSTEM_INSTRUCTION,
)
from bus_booking_ai_agent.phase_01_llm_fundamentals.conversation_history import (
    ConversationHistory,
)
from bus_booking_ai_agent.phase_01_llm_fundamentals.structured_output import (
    BusSearchRequest,
)


def main():
    print("\n========================================")
    print("   PHASE 01: LLM FUNDAMENTALS")
    print("========================================")

    print("\nCompleted Concepts:")
    print("1. LLM Integration")
    print("2. Tokens")
    print("3. Token Counting")
    print("4. Multi-turn Conversation")
    print("5. Context Window")
    print("6. System Instructions")
    print("7. User Messages")
    print("8. Conversation History")
    print("9. Structured Output")

    print("\n========================================")
    print("   INTEGRATED PHASE 01 TEST")
    print("========================================")

    print("\nSystem Instruction:")
    print(SYSTEM_INSTRUCTION)

    print_model_limits()

    conversation_history = ConversationHistory()

    print("\nType your messages below.")
    print("Type 'exit' to finish the Phase 01 test.")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == "exit":
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # ------------------------------------------------
        # TOKEN COUNTING
        # ------------------------------------------------
        token_count = client.models.count_tokens(
            model=MODEL,
            contents=user_input,
        )

        print(
            f"\nCurrent input tokens before request: "
            f"{token_count.total_tokens}"
        )

        # ------------------------------------------------
        # STRUCTURED OUTPUT
        # ------------------------------------------------
        if user_input.lower().startswith("structured:"):
            structured_input = user_input[len("structured:"):].strip()

            if not structured_input:
                print("\nPlease provide a structured bus search request.")
                continue

            interaction = client.interactions.create(
                model=MODEL,
                system_instruction=SYSTEM_INSTRUCTION,
                input=structured_input,
                response_format=BusSearchRequest,
            )

            print("\nGemini Structured Output:")
            print(interaction.output_text)

            try:
                bus_search_request = BusSearchRequest.model_validate_json(
                    interaction.output_text
                )

                print("\nValidated Python Object:")
                print(bus_search_request)

                print("\nStructured Fields:")
                print(f"Origin: {bus_search_request.origin}")
                print(f"Destination: {bus_search_request.destination}")
                print(f"Travel Date: {bus_search_request.travel_date}")
                print(f"Passengers: {bus_search_request.passengers}")

            except Exception as error:
                print("\nValidation failed.")
                print(f"Error: {error}")

            print_usage("Structured Output Interaction", interaction.usage)

            continue

        # ------------------------------------------------
        # NORMAL LLM + CONVERSATION HISTORY
        # ------------------------------------------------
        interaction = conversation_history.send_message(
            user_input=user_input,
            system_instruction=SYSTEM_INSTRUCTION,
        )

        print("\nGemini:")
        print(interaction.output_text)

        print_usage("Interaction", interaction.usage)

    print("\n========================================")
    print("   PHASE 01 TEST COMPLETED")
    print("========================================")


if __name__ == "__main__":
    main()