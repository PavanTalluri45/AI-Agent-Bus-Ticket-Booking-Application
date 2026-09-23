import asyncio
import json
from pathlib import Path

from google.genai import interactions
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bus_booking_ai_agent.config.gemini import client, MODEL


# ============================================================
# CONFIGURATION
# ============================================================

MAX_TOOL_CALLS = 10


# ============================================================
# GEMINI TOOL DEFINITIONS
# ============================================================

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
                "description": (
                    "The city where the passenger boards the bus."
                ),
            },
            "destination": {
                "type": "string",
                "description": (
                    "The city where the passenger gets off the bus."
                ),
            },
            "travel_date": {
                "type": "string",
                "description": (
                    "Travel date in YYYY-MM-DD format."
                ),
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
        "Get detailed information about a specific scheduled bus."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "schedule_id": {
                "type": "string",
                "description": "The schedule UUID.",
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
        "Check available seats for a scheduled bus "
        "between a boarding stop and dropping stop."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "schedule_id": {
                "type": "string",
                "description": "The schedule UUID.",
            },
            "boarding_stop_id": {
                "type": "string",
                "description": "The boarding stop UUID.",
            },
            "dropping_stop_id": {
                "type": "string",
                "description": "The dropping stop UUID.",
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


# ============================================================
# MCP SERVER CONFIGURATION
# ============================================================

SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "mcp_server.py"
)


def create_server_parameters() -> StdioServerParameters:
    """
    Create the configuration required to start
    the MCP server through stdio.
    """

    return StdioServerParameters(
        command="uv",
        args=[
            "run",
            "python",
            str(SERVER_PATH),
        ],
    )


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_tool_calls(response) -> list:
    """
    Extract all function calls requested by Gemini
    from the current interaction response.
    """

    steps = getattr(response, "steps", None) or []

    return [
        step
        for step in steps
        if step.type == "function_call"
    ]


def parse_tool_arguments(arguments) -> dict:
    """
    Convert Gemini tool arguments into a Python dictionary.

    Gemini may provide arguments either as a dictionary
    or as a JSON string.
    """

    if isinstance(arguments, dict):
        return arguments

    if isinstance(arguments, str):
        return json.loads(arguments)

    raise TypeError(
        f"Unsupported tool argument type: {type(arguments).__name__}"
    )


def get_tool_result_text(result) -> str:
    """
    Convert an MCP tool result into JSON text that can be
    returned to Gemini as a function result.
    """

    structured_content = getattr(
        result,
        "structured_content",
        None,
    )

    if structured_content is not None:
        return json.dumps(
            structured_content,
            default=str,
        )

    content = getattr(
        result,
        "content",
        [],
    )

    return json.dumps(
        content,
        default=str,
    )


async def call_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Map the Gemini tool name to the corresponding MCP tool
    and execute it through the MCP client.
    """

    mcp_tool_names = {
        "search_buses": "search_buses_tool",
        "get_bus_details": "get_bus_details_tool",
        "check_seat_availability": "check_seat_availability_tool",
    }

    mcp_tool_name = mcp_tool_names.get(tool_name)

    if mcp_tool_name is None:
        raise ValueError(
            f"Unknown Gemini tool: {tool_name}"
        )

    result = await session.call_tool(
        mcp_tool_name,
        arguments=arguments,
    )

    tool_result_text = get_tool_result_text(result)

    if not tool_result_text.strip():
        return "[]"

    return tool_result_text


def create_function_result(
    tool_call,
    tool_result: str,
) -> interactions.FunctionResultStepParam:
    """
    Convert an MCP result into the Gemini function_result
    format.
    """

    return {
        "type": "function_result",
        "name": tool_call.name,
        "call_id": tool_call.id,
        "result": [
            {
                "type": "text",
                "text": tool_result,
            }
        ],
    }


# ============================================================
# TOOL CALLING LOOP
# ============================================================

async def run_tool_calling_loop() -> None:
    """
    Run the complete Gemini → MCP → Gemini tool-calling loop.

    Flow:

        User
          ↓
        Gemini
          ↓
        Function Call
          ↓
        MCP Client
          ↓
        MCP Server
          ↓
        MCP Tool
          ↓
        Tool Result
          ↓
        Gemini
          ↓
        Final Response

    The loop continues until Gemini stops requesting tools
    or MAX_TOOL_CALLS is reached.
    """

    user_message = (
        "Find buses from Hyderabad to Bangalore "
        "on 2026-09-25."
    )

    server_params = create_server_parameters()

    print("Connecting to MCP server...")

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("MCP connection established.")

            # ------------------------------------------------
            # INITIAL GEMINI INPUT
            # ------------------------------------------------

            current_input = user_message

            # This is critical.
            #
            # Every next Gemini request must continue the
            # previous interaction so Gemini remembers:
            #
            # - its previous tool call
            # - the tool result
            # - the conversation state
            #
            previous_interaction_id = None

            # ------------------------------------------------
            # TOOL CALLING LOOP
            # ------------------------------------------------

            for iteration in range(
                1,
                MAX_TOOL_CALLS + 1,
            ):

                print()
                print("=" * 60)
                print(f"ITERATION {iteration}")
                print("=" * 60)

                # ============================================
                # SEND INPUT TO GEMINI
                # ============================================

                print("\nSending input to Gemini:")

                if isinstance(current_input, str):
                    print(current_input)
                else:
                    print(
                        json.dumps(
                            current_input,
                            indent=2,
                            default=str,
                        )
                    )

                # ============================================
                # CREATE GEMINI INTERACTION
                # ============================================

                if previous_interaction_id is None:

                    response = client.interactions.create(
                        model=MODEL,
                        input=current_input,
                        tools=TOOLS,
                    )

                else:

                    response = client.interactions.create(
                        model=MODEL,
                        previous_interaction_id=(
                            previous_interaction_id
                        ),
                        input=current_input,
                        tools=TOOLS,
                    )

                # ============================================
                # FIND TOOL CALLS
                # ============================================

                tool_calls = get_tool_calls(response)

                # ============================================
                # NO TOOL CALL
                # ============================================

                if not tool_calls:

                    print("\nNo more tool calls requested.")

                    output_text = getattr(
                        response,
                        "output_text",
                        None,
                    )

                    print("\n=== FINAL RESPONSE ===")

                    if output_text:
                        print(output_text)
                    else:
                        print(
                            "Gemini returned no final text."
                        )

                    return

                # ============================================
                # GEMINI REQUESTED TOOLS
                # ============================================

                print("\n=== TOOL CALLS REQUESTED ===")

                function_results = []

                for tool_call in tool_calls:

                    print()
                    print(f"Tool: {tool_call.name}")
                    print(f"Call ID: {tool_call.id}")
                    print(
                        f"Arguments: {tool_call.arguments}"
                    )

                    # ========================================
                    # PARSE ARGUMENTS
                    # ========================================

                    arguments = parse_tool_arguments(
                        tool_call.arguments
                    )

                    # ========================================
                    # CALL MCP TOOL
                    # ========================================

                    print("\nCalling MCP tool...")

                    tool_result = await call_mcp_tool(
                        session=session,
                        tool_name=tool_call.name,
                        arguments=arguments,
                    )

                    # ========================================
                    # DISPLAY MCP RESULT
                    # ========================================

                    print("\nMCP tool result:")

                    try:
                        parsed_result = json.loads(
                            tool_result
                        )

                        print(
                            json.dumps(
                                parsed_result,
                                indent=2,
                                default=str,
                            )
                        )

                    except json.JSONDecodeError:
                        print(tool_result)

                    # ========================================
                    # CREATE GEMINI FUNCTION RESULT
                    # ========================================

                    function_result = create_function_result(
                        tool_call=tool_call,
                        tool_result=tool_result,
                    )

                    function_results.append(
                        function_result
                    )

                # ============================================
                # CONTINUE SAME GEMINI INTERACTION
                # ============================================

                previous_interaction_id = response.id

                if previous_interaction_id is None:
                    raise RuntimeError(
                        "Gemini response did not contain "
                        "an interaction ID."
                    )

                current_input = function_results

            # ------------------------------------------------
            # MAXIMUM ITERATION GUARD
            # ------------------------------------------------

            print()
            print("=" * 60)
            print("MAXIMUM TOOL CALL LIMIT REACHED")
            print("=" * 60)

            print(
                f"Gemini requested tools for "
                f"{MAX_TOOL_CALLS} iterations."
            )

            print(
                "Stopping the loop to prevent "
                "unbounded tool execution."
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(
        run_tool_calling_loop()
    )