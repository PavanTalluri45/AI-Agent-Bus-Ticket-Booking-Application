import asyncio
import json
import sys
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bus_booking_ai_agent.config.gemini import client, MODEL


MAX_ITERATIONS = 5


class AgentState(TypedDict):
    user_message: str
    interaction_id: str

    tool_name: str
    tool_call_id: str
    tool_arguments: dict

    tool_result: str
    final_response: str

    iteration: int
    error: str


PROJECT_PACKAGE_ROOT = Path(__file__).resolve().parents[1]

SERVER_PATH = (
    PROJECT_PACKAGE_ROOT
    / "phase_03_mcp"
    / "server"
    / "mcp_server.py"
)


TOOLS = [
    {
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
                    "description": "Departure city.",
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
    },
    {
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
                    "description": "Schedule UUID.",
                },
            },
            "required": ["schedule_id"],
        },
    },
    {
        "type": "function",
        "name": "check_seat_availability",
        "description": (
            "Check available seats for a scheduled bus "
            "and a specific journey segment."
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
    },
]


async def call_mcp_tool(
    tool_name: str,
    arguments: dict,
) -> str:

    print("\n--- MCP CLIENT ---")

    print(f"Tool: {tool_name}")
    print(f"Arguments: {arguments}")

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
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

            elif tool_name == "get_bus_details":

                result = await session.call_tool(
                    "get_bus_details_tool",
                    arguments=arguments,
                )

            elif tool_name == "check_seat_availability":

                result = await session.call_tool(
                    "check_seat_availability_tool",
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

            return json.dumps([], default=str)


def llm_node(state: AgentState) -> AgentState:

    print("\n" + "=" * 60)
    print("--- LLM NODE ---")
    print("=" * 60)

    iteration = state["iteration"] + 1

    print(f"Iteration: {iteration}")

    try:

        if not state["interaction_id"]:

            response = client.interactions.create(
                model=MODEL,
                input=state["user_message"],
                tools=TOOLS,
            )

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
                previous_interaction_id=state[
                    "interaction_id"
                ],
                input=[function_result],
                tools=TOOLS,
            )

        steps = getattr(response, "steps", None) or []

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

            return {
                "user_message": state["user_message"],
                "interaction_id": getattr(response, "id", "") or "",

                "tool_name": tool_call.name,
                "tool_call_id": tool_call.id,
                "tool_arguments": tool_call.arguments,

                "tool_result": "",
                "final_response": "",

                "iteration": iteration,
                "error": "",
            }

        output_text = getattr(
            response,
            "output_text",
            None,
        )

        if not output_text:

            raise RuntimeError(
                "Gemini returned no final response."
            )

        print("Gemini produced final response.")

        return {
            "user_message": state["user_message"],
            "interaction_id": getattr(response, "id", "") or "",

            "tool_name": "",
            "tool_call_id": "",
            "tool_arguments": {},

            "tool_result": state["tool_result"],
            "final_response": output_text,

            "iteration": iteration,
            "error": "",
        }

    except Exception as error:

        print(f"LLM error: {error}")

        return {
            "user_message": state["user_message"],
            "interaction_id": state["interaction_id"],

            "tool_name": "",
            "tool_call_id": "",
            "tool_arguments": {},

            "tool_result": state["tool_result"],
            "final_response": "",

            "iteration": iteration,
            "error": str(error),
        }


def tool_node(state: AgentState) -> AgentState:

    print("\n" + "=" * 60)
    print("--- TOOL NODE ---")
    print("=" * 60)

    print(f"Tool: {state['tool_name']}")

    try:

        tool_result = asyncio.run(
            call_mcp_tool(
                tool_name=state["tool_name"],
                arguments=state["tool_arguments"],
            )
        )

        print("\nMCP tool execution completed.")

        return {
            "user_message": state["user_message"],
            "interaction_id": state["interaction_id"],

            "tool_name": state["tool_name"],
            "tool_call_id": state["tool_call_id"],
            "tool_arguments": state["tool_arguments"],

            "tool_result": tool_result,
            "final_response": "",

            "iteration": state["iteration"],
            "error": "",
        }

    except Exception as error:

        print(f"Tool error: {error}")

        return {
            "user_message": state["user_message"],
            "interaction_id": state["interaction_id"],

            "tool_name": state["tool_name"],
            "tool_call_id": state["tool_call_id"],
            "tool_arguments": state["tool_arguments"],

            "tool_result": "",
            "final_response": "",

            "iteration": state["iteration"],
            "error": str(error),
        }


def route_after_llm(
    state: AgentState,
) -> Literal["tool", "error", "end"]:

    if state["error"]:
        print("\nRouter decision: error")
        return "error"

    if state["tool_name"]:

        if state["iteration"] >= MAX_ITERATIONS:

            print(
                "\nMaximum iteration limit reached."
            )

            return "end"

        print("\nRouter decision: execute tool")

        return "tool"

    print("\nRouter decision: finish")

    return "end"


def route_after_tool(
    state: AgentState,
) -> Literal["llm", "error"]:

    if state["error"]:

        print("\nRouter decision: tool error")

        return "error"

    print("\nRouter decision: return to LLM")

    return "llm"


def error_node(state: AgentState) -> AgentState:

    print("\n" + "=" * 60)
    print("--- ERROR NODE ---")
    print("=" * 60)

    print(f"Error: {state['error']}")

    return {
        "user_message": state["user_message"],
        "interaction_id": state["interaction_id"],

        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},

        "tool_result": state["tool_result"],
        "final_response": (
            "The agent encountered an error: "
            f"{state['error']}"
        ),

        "iteration": state["iteration"],
        "error": state["error"],
    }


builder = StateGraph(AgentState)

builder.add_node("llm", llm_node)
builder.add_node("tool", tool_node)
builder.add_node("error", error_node)

builder.add_edge(START, "llm")

builder.add_conditional_edges(
    "llm",
    route_after_llm,
    {
        "tool": "tool",
        "error": "error",
        "end": END,
    },
)

builder.add_conditional_edges(
    "tool",
    route_after_tool,
    {
        "llm": "llm",
        "error": "error",
    },
)

builder.add_edge("error", END)

graph = builder.compile()


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

        "iteration": 0,
        "error": "",
    }

    print("=" * 60)
    print("INTEGRATED LANGGRAPH AGENT")
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