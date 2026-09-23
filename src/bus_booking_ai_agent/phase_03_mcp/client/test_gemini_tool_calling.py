from google.genai import interactions

from bus_booking_ai_agent.config.gemini import client, MODEL


SEARCH_BUSES_TOOL: interactions.FunctionParam = {
    "type": "function",
    "name": "search_buses",
    "description": (
        "Search scheduled buses between an origin and destination "
        "on a specific travel date."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "The city where the passenger boards the bus.",
            },
            "destination": {
                "type": "string",
                "description": "The city where the passenger gets off the bus.",
            },
            "travel_date": {
                "type": "string",
                "description": "Travel date in YYYY-MM-DD format.",
            },
        },
        "required": [
            "origin",
            "destination",
            "travel_date",
        ],
    },
}


def main():
    user_message = (
        "Find buses from Hyderabad to Bangalore on 2026-09-25."
    )

    response = client.interactions.create(
        model=MODEL,
        input=user_message,
        tools=[SEARCH_BUSES_TOOL],
    )

    print("\n=== GEMINI TOOL CALLING TEST ===")
    print(f"User: {user_message}")

    print("\nGemini output:")
    print(response)

    print("\n=== TOOL CALLS ===")

    found_tool_call = False

    for step in response.steps or []:
        if step.type == "function_call":
            found_tool_call = True

            print(f"Tool name: {step.name}")
            print(f"Arguments: {step.arguments}")

    if not found_tool_call:
        print("No tool call was requested.")


if __name__ == "__main__":
    main()