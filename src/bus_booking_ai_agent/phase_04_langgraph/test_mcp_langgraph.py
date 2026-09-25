import asyncio
import json
import sys
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class AgentState(TypedDict):
    origin: str
    destination: str
    travel_date: str
    tool_result: str


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

# test_mcp_langgraph.py
#
# phase_04_langgraph/
#     test_mcp_langgraph.py
#
# parents[0] = phase_04_langgraph
# parents[1] = bus_booking_ai_agent
#
# Therefore:
# bus_booking_ai_agent/
#     phase_03_mcp/
#         server/
#             mcp_server.py

PROJECT_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

SERVER_PATH = (
    PROJECT_PACKAGE_ROOT
    / "phase_03_mcp"
    / "server"
    / "mcp_server.py"
)


# ---------------------------------------------------------
# MCP Client
# ---------------------------------------------------------

async def call_mcp_search_buses(
    origin: str,
    destination: str,
    travel_date: str,
) -> str:

    print(f"\nMCP Server path:")
    print(SERVER_PATH)

    if not SERVER_PATH.exists():
        raise FileNotFoundError(
            f"MCP server not found at: {SERVER_PATH}"
        )

    server_params = StdioServerParameters(
        # Use the same Python interpreter running this test.
        command=sys.executable,
        args=[
            str(SERVER_PATH),
        ],
        # Start the server from the project root.
        cwd=str(PROJECT_PACKAGE_ROOT.parent.parent),
    )

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            print("\nInitializing MCP session...")

            await session.initialize()

            print("MCP session initialized.")

            print("\nCalling search_buses_tool...")

            result = await session.call_tool(
                "search_buses_tool",
                arguments={
                    "origin": origin,
                    "destination": destination,
                    "travel_date": travel_date,
                },
            )

            print("MCP tool execution completed.")

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

            return json.dumps(
                [],
                default=str,
            )


# ---------------------------------------------------------
# LangGraph MCP Tool Node
# ---------------------------------------------------------

def mcp_tool_node(
    state: AgentState,
) -> AgentState:

    print("\n--- MCP Tool Node ---")

    print(
        f"Searching buses from "
        f"{state['origin']} to "
        f"{state['destination']} "
        f"on {state['travel_date']}"
    )

    tool_result = asyncio.run(
        call_mcp_search_buses(
            origin=state["origin"],
            destination=state["destination"],
            travel_date=state["travel_date"],
        )
    )

    return {
        "origin": state["origin"],
        "destination": state["destination"],
        "travel_date": state["travel_date"],
        "tool_result": tool_result,
    }


# ---------------------------------------------------------
# Build LangGraph
# ---------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node(
    "mcp_tool",
    mcp_tool_node,
)

builder.add_edge(
    START,
    "mcp_tool",
)

builder.add_edge(
    "mcp_tool",
    END,
)

graph = builder.compile()


# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("LANGGRAPH + MCP")
    print("=" * 60)

    print("\nMCP server:")
    print(SERVER_PATH)

    initial_state: AgentState = {
        "origin": "Hyderabad",
        "destination": "Bangalore",
        "travel_date": "2026-09-25",
        "tool_result": "",
    }

    print("\nInitial state:")
    print(initial_state)

    final_state = graph.invoke(
        initial_state
    )

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(final_state)