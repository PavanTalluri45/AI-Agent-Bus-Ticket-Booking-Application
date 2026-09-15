from bus_booking_ai_agent.config.gemini import client, MODEL


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


if __name__ == "__main__":
    run()
