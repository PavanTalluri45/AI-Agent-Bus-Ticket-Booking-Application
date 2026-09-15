from bus_booking_ai_agent.config.gemini import client, MODEL


def run():
    print("\n--- User Messages ---")
    print("Type a message for Gemini.")
    print("The message you enter will be sent as the user input.\n")

    user_input = input("You: ").strip()

    if not user_input:
        print("No input provided.")
        return

    interaction = client.interactions.create(
        model=MODEL,
        input=user_input,
    )

    print("\nGemini:")
    print(interaction.output_text)


if __name__ == "__main__":
    run()