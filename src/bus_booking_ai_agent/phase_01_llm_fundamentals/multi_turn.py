from bus_booking_ai_agent.config.gemini import client, MODEL


def print_usage(label, usage):
    """Print token usage for an interaction."""
    print(f"\n--- {label} Usage ---")
    print(f"Input tokens: {usage.total_input_tokens}")
    print(f"Output tokens: {usage.total_output_tokens}")
    print(f"Thought tokens: {usage.total_thought_tokens}")
    print(f"Tool-use tokens: {usage.total_tool_use_tokens}")
    print(f"Cached tokens: {usage.total_cached_tokens}")
    print(f"Total tokens: {usage.total_tokens}")


def run():
    # Stores the previous Gemini interaction ID.
    # This allows subsequent requests to continue the conversation.
    previous_interaction_id = None

    print("Type your messages below. Enter 'exit' to finish the conversation.")

    while True:
        user_input = input("\nYou: ").strip()

        if user_input.lower() == "exit":
            print("Goodbye!")
            break

        if not user_input:
            continue

        # First interaction
        if previous_interaction_id is None:
            interaction = client.interactions.create(
                model=MODEL,
                input=user_input,
            )
        # Follow-up interaction using previous conversation
        else:
            interaction = client.interactions.create(
                model=MODEL,
                input=user_input,
                previous_interaction_id=previous_interaction_id,
            )

        # Display Gemini response
        print("\nGemini:")
        print(interaction.output_text)

        # Display token usage
        print_usage("Interaction", interaction.usage)

        # Save this interaction ID so the next request
        # can continue the same conversation.
        previous_interaction_id = interaction.id


if __name__ == "__main__":
    run()
