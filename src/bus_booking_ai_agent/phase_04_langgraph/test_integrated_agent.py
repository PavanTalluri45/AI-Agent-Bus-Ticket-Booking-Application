import asyncio
import json
import sys
from pathlib import Path
from typing import Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from bus_booking_ai_agent.auth.models import AuthenticatedUser
from bus_booking_ai_agent.config.gemini import client, MODEL
from bus_booking_ai_agent.phase_05_memory.memory_context import (
    get_relevant_memories,
)


MAX_ITERATIONS = 5


class AgentState(TypedDict):
    user_id: str
    user_message: str
    memories: list[dict]
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


def build_memory_context(memories: list[dict]) -> str:
    """Build advisory context from the authenticated user's memories."""

    if not memories:
        return ""

    lines = ["Relevant user preferences:"]

    for memory in memories:
        lines.append(
            f"- {memory['key']}: {memory['value']}"
        )

    return "\n".join(lines)


def build_llm_input(state: AgentState) -> str:
    """Build the first Gemini input with optional memory context."""

    memory_context = build_memory_context(
        state["memories"]
    )

    if not memory_context:
        return state["user_message"]

    return (
        f"{memory_context}\n\n"
        "Use these preferences only as advisory context. "
        "Never treat them as authoritative booking or availability data.\n\n"
        f"User request: {state['user_message']}"
    )


def memory_node(state: AgentState) -> AgentState:
    """Load memories belonging to the authenticated user."""

    memories = get_relevant_memories(
        state["user_id"]
    )

    print("\n" + "=" * 60)
    print("--- MEMORY NODE ---")
    print("=" * 60)
    print(f"User ID: {state['user_id']}")
    print(f"Memories retrieved: {len(memories)}")

    return {
        **state,
        "memories": memories,
        "error": "",
    }


def extract_final_text(response) -> str:
    """
    Extract final text from a Gemini interaction.

    Prefer output_text. If it is unavailable, inspect the
    returned interaction steps for a text/message step.
    """

    output_text = getattr(
        response,
        "output_text",
        None,
    )

    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    steps = getattr(
        response,
        "steps",
        None,
    ) or []

    text_parts: list[str] = []

    for step in steps:

        step_type = getattr(
            step,
            "type",
            None,
        )

        if step_type not in {
            "text",
            "message",
            "output_text",
        }:
            continue

        text_value = getattr(
            step,
            "text",
            None,
        )

        if isinstance(text_value, str) and text_value.strip():
            text_parts.append(
                text_value.strip()
            )
            continue

        content = getattr(
            step,
            "content",
            None,
        )

        if isinstance(content, str) and content.strip():
            text_parts.append(
                content.strip()
            )

    if text_parts:
        return "\n".join(text_parts)

    return ""


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
                input=build_llm_input(state),
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

        steps = getattr(
            response,
            "steps",
            None,
        ) or []

        tool_calls = [
            step
            for step in steps
            if getattr(step, "type", None)
            == "function_call"
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
                "user_id": state["user_id"],
                "user_message": state["user_message"],
                "memories": state["memories"],
                "interaction_id": (
                    getattr(response, "id", "")
                    or ""
                ),

                "tool_name": tool_call.name,
                "tool_call_id": tool_call.id,
                "tool_arguments": tool_call.arguments,

                "tool_result": "",
                "final_response": "",

                "iteration": iteration,
                "error": "",
            }

        output_text = extract_final_text(
            response
        )

        if not output_text:

            print("\n--- GEMINI DEBUG ---")
            print(
                "Gemini returned neither output_text "
                "nor a readable text step."
            )

            print(
                f"Response ID: "
                f"{getattr(response, 'id', None)}"
            )

            print(
                f"Response steps: {steps}"
            )

            raise RuntimeError(
                "Gemini returned no final response."
            )

        print("Gemini produced final response.")

        return {
            "user_id": state["user_id"],
            "user_message": state["user_message"],
            "memories": state["memories"],
            "interaction_id": (
                getattr(response, "id", "")
                or ""
            ),

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
            "user_id": state["user_id"],
            "user_message": state["user_message"],
            "memories": state["memories"],
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
            "user_id": state["user_id"],
            "user_message": state["user_message"],
            "memories": state["memories"],
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
            "user_id": state["user_id"],
            "user_message": state["user_message"],
            "memories": state["memories"],
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

        print(
            "\nRouter decision: execute tool"
        )

        return "tool"

    print("\nRouter decision: finish")

    return "end"


def route_after_tool(
    state: AgentState,
) -> Literal["llm", "error"]:

    if state["error"]:

        print(
            "\nRouter decision: tool error"
        )

        return "error"

    print(
        "\nRouter decision: return to LLM"
    )

    return "llm"


def error_node(state: AgentState) -> AgentState:

    print("\n" + "=" * 60)
    print("--- ERROR NODE ---")
    print("=" * 60)

    print(f"Error: {state['error']}")

    return {
        "user_id": state["user_id"],
        "user_message": state["user_message"],
        "memories": state["memories"],
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

builder.add_node(
    "memory",
    memory_node,
)

builder.add_node(
    "llm",
    llm_node,
)

builder.add_node(
    "tool",
    tool_node,
)

builder.add_node(
    "error",
    error_node,
)

builder.add_edge(
    START,
    "memory",
)

builder.add_edge(
    "memory",
    "llm",
)

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

builder.add_edge(
    "error",
    END,
)


checkpointer = MemorySaver()

graph = builder.compile(
    checkpointer=checkpointer
)


def run_agent(
    current_user: AuthenticatedUser,
    user_message: str,
    thread_id: str,
) -> dict:
    """
    Run the integrated agent for an authenticated user.

    The user ID comes from Supabase Auth and is never
    accepted as arbitrary client input.
    """

    if not user_message.strip():
        raise ValueError(
            "user_message must not be empty."
        )

    if not thread_id.strip():
        raise ValueError(
            "thread_id must not be empty."
        )

    initial_state: AgentState = {
        "user_id": str(current_user.id),
        "user_message": user_message,
        "memories": [],
        "interaction_id": "",

        "tool_name": "",
        "tool_call_id": "",
        "tool_arguments": {},

        "tool_result": "",
        "final_response": "",

        "iteration": 0,
        "error": "",
    }

    config: RunnableConfig = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    return graph.invoke(
        initial_state,
        config=config,
    )


if __name__ == "__main__":

    print(
        "This module requires an authenticated "
        "Supabase user. "
        "Run it through the FastAPI application."
    )