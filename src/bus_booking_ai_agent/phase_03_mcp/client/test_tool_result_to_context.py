import asyncio
import json
from pathlib import Path

from google.genai import interactions
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bus_booking_ai_agent.config.gemini import client, MODEL


# ============================================================
# GEMINI TOOL DEFINITION
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


TOOLS: list[interactions.ToolParam] = [
    SEARCH_BUSES_TOOL
]


# ============================================================
# MCP SERVER PATH
# ============================================================

SERVER_PATH = (
    Path(__file__).resolve().parents[1]
    / "server"
    / "mcp_server.py"
)


# ============================================================
# MAIN
# ============================================================

async def main():

    user_message = (
        "Find buses from Hyderabad to Bangalore "
        "on 2026-09-25."
    )

    # ========================================================
    # MCP SERVER CONFIGURATION
    # ========================================================

    server_params = StdioServerParameters(
        command="uv",
        args=[
            "run",
            "python",
            str(SERVER_PATH),
        ],
    )

    print("Connecting to MCP server...")

    # ========================================================
    # CONNECT TO MCP SERVER
    # ========================================================

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            print("MCP connection established.")

            # =================================================
            # STEP 1
            # SEND USER REQUEST TO GEMINI
            # =================================================

            print(
                "\n=== STEP 1: SEND USER REQUEST TO GEMINI ==="
            )

            response = client.interactions.create(
                model=MODEL,
                input=user_message,
                tools=TOOLS,
            )

            print(
                f"User: {user_message}"
            )

            # =================================================
            # FIND GEMINI FUNCTION CALL
            # =================================================

            tool_call = None

            for step in response.steps or []:

                if step.type == "function_call":

                    tool_call = step

                    break

            # =================================================
            # NO TOOL CALL
            # =================================================

            if tool_call is None:

                print(
                    "\nGemini did not request a tool."
                )

                print(
                    "\nGemini response:"
                )

                print(
                    response.output_text
                )

                return

            # =================================================
            # STEP 2
            # GEMINI REQUESTED TOOL
            # =================================================

            print(
                "\n=== STEP 2: GEMINI REQUESTED TOOL ==="
            )

            print(
                f"Tool: {tool_call.name}"
            )

            print(
                f"Call ID: {tool_call.id}"
            )

            print(
                f"Arguments: {tool_call.arguments}"
            )

            # =================================================
            # VERIFY TOOL
            # =================================================

            if tool_call.name != "search_buses":

                print(
                    "\nUnexpected tool selected:"
                    f" {tool_call.name}"
                )

                return

            # =================================================
            # STEP 3
            # CALL MCP TOOL
            # =================================================

            print(
                "\n=== STEP 3: CALL MCP TOOL ==="
            )

            # Gemini-facing tool:
            #
            # search_buses
            #
            # MCP server tool:
            #
            # search_buses_tool

            mcp_tool_name = "search_buses_tool"

            result = await session.call_tool(
                mcp_tool_name,
                arguments=tool_call.arguments,
            )

            print(
                f"MCP tool: {mcp_tool_name}"
            )

            # =================================================
            # CHECK MCP ERROR
            # =================================================

            if result.is_error:

                print(
                    "\nMCP tool execution failed."
                )

                print(result)

                return

            # =================================================
            # STEP 4
            # EXTRACT MCP TOOL RESULT
            # =================================================

            print(
                "\n=== STEP 4: MCP TOOL RESULT ==="
            )

            # ------------------------------------------------
            # MCP can return structured content for a Python
            # list[dict] result.
            # ------------------------------------------------

            structured_content = getattr(
                result,
                "structured_content",
                None,
            )

            if structured_content is not None:

                print(
                    "Structured content:"
                )

                print(
                    json.dumps(
                        structured_content,
                        indent=2,
                        default=str,
                    )
                )

                tool_result_text = json.dumps(
                    structured_content,
                    default=str,
                )

            else:

                # ------------------------------------------------
                # Fall back to text content.
                # ------------------------------------------------

                tool_result_parts: list[str] = []

                for content in result.content:

                    if content.type == "text":

                        tool_result_parts.append(
                            content.text
                        )

                # ------------------------------------------------
                # If text content exists, combine it.
                # Otherwise send a valid JSON empty result.
                # ------------------------------------------------

                if tool_result_parts:

                    tool_result_text = "\n".join(
                        tool_result_parts
                    )

                else:

                    tool_result_text = "[]"

                print(
                    "Text content:"
                )

                print(
                    json.dumps(
                        tool_result_parts,
                        indent=2,
                    )
                )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Never send:
            #
            # {"type": "text", "text": ""}
            #
            # Gemini rejects empty text content.
            # ------------------------------------------------

            if not tool_result_text.strip():

                tool_result_text = "[]"

            print(
                "\nNormalized tool result:"
            )

            print(tool_result_text)

            # =================================================
            # STEP 5
            # SEND FUNCTION RESULT BACK TO GEMINI
            # =================================================

            print(
                "\n=== STEP 5: SEND TOOL RESULT BACK TO GEMINI ==="
            )

            if response.id is None:

                print(
                    "Interaction has no ID; "
                    "cannot continue."
                )

                return

            # ------------------------------------------------
            # FUNCTION RESULT
            # ------------------------------------------------

            function_result: interactions.FunctionResultStepParam = {
                "type": "function_result",
                "name": tool_call.name,
                "call_id": tool_call.id,
                "result": [
                    {
                        "type": "text",
                        "text": tool_result_text,
                    }
                ],
            }

            print(
                "\nFunction result sent to Gemini:"
            )

            print(
                json.dumps(
                    function_result,
                    indent=2,
                    default=str,
                )
            )

            # =================================================
            # CONTINUE SAME GEMINI INTERACTION
            # =================================================

            final_response = client.interactions.create(
                model=MODEL,
                previous_interaction_id=response.id,
                input=[
                    function_result
                ],
                tools=TOOLS,
            )

            # =================================================
            # STEP 6
            # FINAL GEMINI RESPONSE
            # =================================================

            print(
                "\n=== GEMINI FINAL RESPONSE ==="
            )

            print(
                final_response.output_text
            )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())