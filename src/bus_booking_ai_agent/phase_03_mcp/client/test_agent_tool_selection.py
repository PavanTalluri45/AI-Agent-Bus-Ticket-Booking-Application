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


GET_BUS_DETAILS_TOOL: interactions.FunctionParam = {
    "type": "function",
    "name": "get_bus_details",
    "description": (
        "Get detailed information about a specific scheduled bus "
        "using its schedule ID."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "schedule_id": {
                "type": "string",
                "description": "UUID of the scheduled bus.",
            },
        },
        "required": [
            "schedule_id",
        ],
    },
}


CHECK_SEAT_AVAILABILITY_TOOL: interactions.FunctionParam = {
    "type": "function",
    "name": "check_seat_availability",
    "description": (
        "Check available seats for a specific scheduled bus "
        "and journey segment."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "schedule_id": {
                "type": "string",
                "description": "UUID of the scheduled bus.",
            },
            "boarding_stop_id": {
                "type": "string",
                "description": "UUID of the boarding stop.",
            },
            "dropping_stop_id": {
                "type": "string",
                "description": "UUID of the dropping stop.",
            },
        },
        "required": [
            "schedule_id",
            "boarding_stop_id",
            "dropping_stop_id",
        ],
    },
}


TOOLS: list[interactions.ToolParam] = [
    SEARCH_BUSES_TOOL,
    GET_BUS_DETAILS_TOOL,
    CHECK_SEAT_AVAILABILITY_TOOL,
]


def test_tool_selection(user_message: str) -> None:
    response = client.interactions.create(
        model=MODEL,
        input=user_message,
        tools=TOOLS,
    )

    print("\n========================================")
    print("USER REQUEST")
    print("========================================")
    print(user_message)

    print("\n========================================")
    print("GEMINI TOOL SELECTION")
    print("========================================")

    found_tool_call = False

    for step in response.steps or []:
        if step.type == "function_call":
            found_tool_call = True

            print(f"Tool: {step.name}")
            print(f"Arguments: {step.arguments}")

    if not found_tool_call:
        print("No tool selected.")


def main():
    test_cases = [
        (
            "Find buses from Hyderabad to Bangalore "
            "on 2026-09-25."
        ),
        (
            "Show me the details of schedule "
            "53220a90-ee01-5210-99e2-e0387975cccc."
        ),
        (
            "Check available seats for schedule "
            "53220a90-ee01-5210-99e2-e0387975cccc "
            "between boarding stop "
            "e59ba1c8-1798-5ee2-93d5-06db16def156 "
            "and dropping stop "
            "2f1514d9-f73e-50a2-94ae-8b5ef444f1a9."
        ),
    ]

    for user_message in test_cases:
        test_tool_selection(user_message)


if __name__ == "__main__":
    main()