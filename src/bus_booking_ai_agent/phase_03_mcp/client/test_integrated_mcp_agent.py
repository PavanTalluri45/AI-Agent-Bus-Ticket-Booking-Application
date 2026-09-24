import asyncio
import json
from pathlib import Path

from google import genai
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


MODEL = "gemini-3.8-flash"

MAX_TOOL_CALLS = 10

client = genai.Client()


# ============================================================
# Gemini Tool Definitions (Interactions API uses plain dicts
# with JSON Schema, not types.Tool / types.Schema)
# ============================================================

SEARCH_BUSES_TOOL = {
    "type": "function",
    "name": "search_buses",
    "description": (
        "Search scheduled buses between an origin and destination "
        "for a specific travel date."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "origin": {
                "type": "string",
                "description": "Origin city.",
            },
            "destination": {
                "type": "string",
                "description": "Destination city.",
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


GET_BUS_DETAILS_TOOL = {
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
                "description": "Schedule UUID.",
            },
        },
        "required": ["schedule_id"],
    },
}


CHECK_SEAT_AVAILABILITY_TOOL = {
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
                "description": "Schedule UUID.",
            },
            "boarding_stop_id": {
                "type": "string",
                "description": "Boarding stop UUID.",
            },
            "dropping_stop_id": {
                "type": "string",
                "description": "Dropping stop UUID.",
            },
        },
        "required": [
            "schedule_id",
            "boarding_stop_id",
            "dropping_stop_id",
        ],
    },
}


TOOLS = [
    SEARCH_BUSES_TOOL,
    GET_BUS_DETAILS_TOOL,
    CHECK_SEAT_AVAILABILITY_TOOL,
]


# ============================================================
# MCP Server Configuration
# ============================================================

SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "mcp_server.py"
)


def create_server_parameters() -> StdioServerParameters:
    return StdioServerParameters(
        command="uv",
        args=[
            "run",
            "python",
            str(SERVER_PATH),
        ],
    )


# ============================================================
# Gemini Response Helpers
# ============================================================

def get_tool_calls(response) -> list:
    """
    Extract function-call steps from a Gemini interaction.
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
    """

    if isinstance(arguments, dict):
        return arguments

    if isinstance(arguments, str):
        return json.loads(arguments)

    raise TypeError(
        f"Unsupported tool argument type: {type(arguments)}"
    )


# ============================================================
# MCP Result Handling
# ============================================================

def get_tool_result_text(result) -> str:
    """
    Convert the MCP result into text that can be
    returned to Gemini.

    The official MCP SDK exposes `structuredContent`
    (camelCase), not `structured_content`.
    """

    structured_content = getattr(
        result,
        "structuredContent",
        None,
    )

    if structured_content is not None:
        return json.dumps(
            structured_content,
            default=str,
        )

    text_parts = [
        item.text
        for item in result.content
        if getattr(item, "type", None) == "text"
    ]

    return "\n".join(text_parts)


# ============================================================
# MCP Tool Mapping
# ============================================================

MCP_TOOL_NAMES = {
    "search_buses": "search_buses_tool",
    "get_bus_details": "get_bus_details_tool",
    "check_seat_availability": (
        "check_seat_availability_tool"
    ),
}


async def call_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict,
) -> str:

    mcp_tool_name = MCP_TOOL_NAMES.get(tool_name)

    if mcp_tool_name is None:
        raise ValueError(
            f"Unknown Gemini tool: {tool_name}"
        )

    print(f"\nCalling MCP tool: {mcp_tool_name}")

    result = await session.call_tool(
        mcp_tool_name,
        arguments=arguments,
    )

    tool_result_text = get_tool_result_text(result)

    if not tool_result_text.strip():
        return "[]"

    return tool_result_text


# ============================================================
# Function Result
# ============================================================

def create_function_result(
    tool_call,
    tool_result: str,
) -> dict:

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
# Integrated MCP Agent
# ============================================================

async def run_integrated_mcp_agent():

    user_message = (
        "Find buses from Hyderabad to Bangalore "
        "on 2026-09-25 and give me the available buses."
    )

    print("=" * 60)
    print("INTEGRATED MCP AGENT")
    print("=" * 60)

    print("\nUser:")
    print(user_message)

    server_parameters = create_server_parameters()

    print("\nConnecting to MCP server...")

    async with stdio_client(server_parameters) as (
        read,
        write,
    ):
        async with ClientSession(
            read,
            write,
        ) as session:

            await session.initialize()

            print("MCP connection established.")

            current_input = user_message

            previous_interaction_id = None

            for iteration in range(1, MAX_TOOL_CALLS + 1):

                print("\n" + "=" * 60)
                print(f"AGENT ITERATION {iteration}")
                print("=" * 60)

                # ------------------------------------------------
                # Ask Gemini
                # (previous_interaction_id is None on the first turn)
                # ------------------------------------------------

                response = client.interactions.create(
                    model=MODEL,
                    input=current_input,
                    tools=TOOLS,
                    previous_interaction_id=(
                        previous_interaction_id
                    ),
                    stream=False,
                )

                # ------------------------------------------------
                # Check for tool calls
                # ------------------------------------------------

                tool_calls = get_tool_calls(response)

                if not tool_calls:

                    output_text = getattr(
                        response,
                        "output_text",
                        None,
                    )

                    print("\n" + "=" * 60)
                    print("FINAL ANSWER")
                    print("=" * 60)

                    if output_text:
                        print(output_text)
                    else:
                        print(
                            "Gemini returned no final text."
                        )

                    return

                print("\nTool calls requested:")

                for tool_call in tool_calls:

                    print(
                        f"\nTool: {tool_call.name}"
                    )

                    print(
                        f"Call ID: {tool_call.id}"
                    )

                    print(
                        f"Arguments: "
                        f"{tool_call.arguments}"
                    )

                # ------------------------------------------------
                # Execute MCP tools
                # ------------------------------------------------

                function_results = []

                for tool_call in tool_calls:

                    arguments = parse_tool_arguments(
                        tool_call.arguments
                    )

                    tool_result = await call_mcp_tool(
                        session=session,
                        tool_name=tool_call.name,
                        arguments=arguments,
                    )

                    print("\nMCP tool result:")
                    print(tool_result)

                    function_result = (
                        create_function_result(
                            tool_call,
                            tool_result,
                        )
                    )

                    function_results.append(
                        function_result
                    )

                # ------------------------------------------------
                # Continue same Gemini interaction
                # ------------------------------------------------

                previous_interaction_id = response.id

                current_input = function_results

            # ----------------------------------------------------
            # Maximum iteration guard
            # ----------------------------------------------------

            print("\n" + "=" * 60)
            print("MAXIMUM ITERATION LIMIT REACHED")
            print("=" * 60)

            print(
                "The agent stopped to prevent "
                "an uncontrolled tool-calling loop."
            )


# ============================================================
# Entry Point
# ============================================================

if __name__ == "__main__":
    asyncio.run(
        run_integrated_mcp_agent()
    )