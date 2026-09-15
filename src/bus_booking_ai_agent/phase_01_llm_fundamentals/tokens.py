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
    user_input = input("\nYou: ").strip()
    if not user_input:
        print("No input provided.")
        return

    interaction = client.interactions.create(
        model=MODEL,
        input=user_input,
    )

    print("\nGemini:")
    print(interaction.output_text)

    print_usage("Interaction", interaction.usage)


if __name__ == "__main__":
    run()
