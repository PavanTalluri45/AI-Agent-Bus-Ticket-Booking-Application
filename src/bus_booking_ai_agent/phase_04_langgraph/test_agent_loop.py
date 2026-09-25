import asyncio
import json
import sys
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bus_booking_ai_agent.config.gemini import client, MODEL


class AgentState(TypedDict):
    user_message: str
    interaction_id: str
    tool_name: str
    tool_call_id: str
    tool_arguments: dict
    tool_result: str
    final_response: str


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

PROJECT_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

SERVER_PATH = (
    PROJECT_PACKAGE_ROOT
    / "phase_03_mcp"
    / "server"
    / "mcp_server.py"
)


# ---------------------------------------------------------
# Gemini Tools
# ---------------------------------------------------------

TOOLS = [
    {
        "type": "function",
        "name": "search_buses",
        "description": (
            "Search scheduled buses between an origin "
            "and destination for a specific travel date."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "string",
                    "description": "Departure city.",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination city.",
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
    },
]


# ---------------------------------------------------------
# MCP Client
# ---------------------------------------------------------

async def call_mcp_tool(
    tool_name: str,
    arguments: dict,
) -> str:

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[
            str(SERVER_PATH),
        ],
        cwd=str(PROJECT_PACKAGE_ROOT.parent.parent),
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            await session.initialize()

            if tool_name == "search_buses":

                result = await session.call_tool(
                    "search_buses_tool",
                    arguments=arguments,
                )

            else:
                raise ValueError(
                    f"Unsupported tool: {tool_name}"
                )

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

            return json.dumps([])


# ---------------------------------------------------------
# LLM Node
# ---------------------------------------------------------

def llm_node(
    state: AgentState,
) -> AgentState:

    print("\n--- LLM NODE ---")

    # -----------------------------------------------------
    # First LLM call
    # -----------------------------------------------------

    if not state["interaction_id"]:

        response = client.interactions.create(
            model=MODEL,
            input=state["user_message"],
            tools=TOOLS,
        )

    # -----------------------------------------------------
    # Continue the same Gemini interaction after a tool
    # -----------------------------------------------------

    else:

        function_result = {
            "type": "function_result",
            "name": state["tool_name"],
            "call_id": state["tool_call_id"],
            "result": [
                {
                    "type": "text",
                    "text": state["tool_result"],
                }
            ],
        }

        response = client.interactions.create(
            model=MODEL,
            previous_interaction_id=state["interaction_id"],
            input=[
                function_result,
            ],
            tools=TOOLS,
        )

    # -----------------------------------------------------
    # Check whether Gemini requested a tool
    # -----------------------------------------------------

    steps = getattr(
        response,
        "steps",
        None,
    ) or []

    tool_calls = [
        step
        for step in steps
        if step.type == "function_call"
    ]

    if tool_calls:

        tool_call = tool_calls[0]

        print(
            f"Gemini selected tool: "
            f"{tool_call.name}"
        )

        print(
            f"Tool arguments: "
            f"{tool_call.arguments}"
        )

        # Gemini already gives us a Python dict.
        tool_arguments = tool_call.arguments

        return {
            "user_message": state["user_message"],
            "interaction_id": getattr(response, "id", "") or "",
            "tool_name": tool_call.name,
            "tool_call_id": tool_call.id,
            "tool_arguments": tool_arguments,
            "tool_result": "",
            "final_response": "",
        }

    # -----------------------------------------------------
    # Gemini produced a final answer
    # -----------------------------------------------------

    output_text = getattr(
        response,
        "output_text",
        None,
    )

    return {
        "user_message": state["user_message"],
        "interaction_id": getattr(response, "id", "") or "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": state["tool_result"],
        "final_response": output_text or "",
    }


# ---------------------------------------------------------
# Tool Node
# ---------------------------------------------------------

def tool_node(
    state: AgentState,
) -> AgentState:

    print("\n--- TOOL NODE ---")

    print(
        f"Executing tool: "
        f"{state['tool_name']}"
    )

    print(
        f"Arguments: "
        f"{state['tool_arguments']}"
    )

    tool_result = asyncio.run(
        call_mcp_tool(
            tool_name=state["tool_name"],
            arguments=state["tool_arguments"],
        )
    )

    print(
        "MCP tool execution completed."
    )

    return {
        "user_message": state["user_message"],
        "interaction_id": state["interaction_id"],
        "tool_name": state["tool_name"],
        "tool_call_id": state["tool_call_id"],
        "tool_arguments": state["tool_arguments"],
        "tool_result": tool_result,
        "final_response": "",
    }


# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

def route_after_llm(
    state: AgentState,
) -> str:

    if state["tool_name"]:

        print(
            "\nRouter decision: "
            "execute tool"
        )

        return "tool"

    print(
        "\nRouter decision: "
        "finish"
    )

    return "end"


# ---------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node(
    "llm",
    llm_node,
)

builder.add_node(
    "tool",
    tool_node,
)

builder.add_edge(
    START,
    "llm",
)

builder.add_conditional_edges(
    "llm",
    route_after_llm,
    {
        "tool": "tool",
        "end": END,
    },
)

builder.add_edge(
    "tool",
    "llm",
)

graph = builder.compile()


# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":

    initial_state: AgentState = {
        "user_message": (
            "Find buses from Hyderabad to Bangalore "
            "on 2026-09-25."
        ),
        "interaction_id": "",
        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},
        "tool_result": "",
        "final_response": "",
    }

    print("=" * 60)
    print("LANGGRAPH AGENT LOOP")
    print("=" * 60)

    print("\nInitial state:")
    print(initial_state)

    final_state = graph.invoke(
        initial_state
    )

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(final_state)

    print("\n" + "=" * 60)
    print("FINAL RESPONSE")
    print("=" * 60)

    print(final_state["final_response"])