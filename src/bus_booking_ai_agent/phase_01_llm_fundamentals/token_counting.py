from bus_booking_ai_agent.config.gemini import client, MODEL


def run():
    user_input = input("\nYou: ").strip()
    if not user_input:
        print("No input provided.")
        return

    # Count tokens for the current user input before
    # sending the actual generation request.
    token_count = client.models.count_tokens(
        model=MODEL,
        contents=user_input,
    )

    print(
        f"\nCurrent input tokens before request: "
        f"{token_count.total_tokens}"
    )

    interaction = client.interactions.create(
        model=MODEL,
        input=user_input,
    )

    print("\nGemini:")
    print(interaction.output_text)


if __name__ == "__main__":
    run()
