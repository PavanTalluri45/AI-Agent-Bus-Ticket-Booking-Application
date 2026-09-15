from bus_booking_ai_agent.config.gemini import client, MODEL


SYSTEM_INSTRUCTION = """
You are a bus booking AI assistant.

Your job is to help users with bus travel and ticket booking questions.

Follow these rules:
- Be clear and concise.
- Ask for missing information when necessary.
- Do not invent bus, seat, price, or availability information.
- If you do not know something, clearly say that you do not know.
"""


def run():
    print("\n--- System Instructions ---")

    print("\nSystem Instruction:")
    print(SYSTEM_INSTRUCTION)

    user_input = input("\nYou: ").strip()

    if not user_input:
        print("No input provided.")
        return

    interaction = client.interactions.create(
        model=MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
        input=user_input,
    )

    print("\nGemini:")
    print(interaction.output_text)


if __name__ == "__main__":
    run()