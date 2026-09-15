from pydantic import BaseModel

from bus_booking_ai_agent.config.gemini import client, MODEL


class BusSearchRequest(BaseModel):
    origin: str
    destination: str
    travel_date: str
    passengers: int


SYSTEM_INSTRUCTION = """
You are a bus booking AI assistant.

Extract the user's bus search requirements.

Return the information using the required structured format.

If the user does not provide a required value,
do not invent it.
"""


def run():
    print("\n--- Structured Output ---")
    print("Describe your bus search request.")
    print("Example: I want to travel from Hyderabad to Bangalore")
    print("for 2 passengers on 2026-09-20.")
    print("Type 'exit' to finish.\n")

    user_input = input("You: ").strip()

    if user_input.lower() == "exit":
        return

    if not user_input:
        print("No input provided.")
        return

    interaction = client.interactions.create(
        model=MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
        input=user_input,
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

        print("\nIndividual Fields:")
        print(f"Origin: {bus_search_request.origin}")
        print(f"Destination: {bus_search_request.destination}")
        print(f"Travel Date: {bus_search_request.travel_date}")
        print(f"Passengers: {bus_search_request.passengers}")

    except Exception as error:
        print("\nValidation failed.")
        print(f"Error: {error}")


if __name__ == "__main__":
    run()