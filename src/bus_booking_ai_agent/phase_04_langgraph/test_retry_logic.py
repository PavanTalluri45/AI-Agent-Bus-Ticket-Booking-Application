from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


MAX_RETRIES = 2


class AgentState(TypedDict):
    request: str
    tool_result: str
    error: str
    status: str
    retry_count: int


# ---------------------------------------------------------
# Tool
# ---------------------------------------------------------

def bus_search_tool(
    state: AgentState,
) -> AgentState:

    print(
        f"\n--- TOOL NODE "
        f"(Attempt {state['retry_count'] + 1}) ---"
    )

    retry_count = state["retry_count"]

    # Simulate a temporary failure on the first attempt.
    if retry_count == 0:

        print("Tool failed: temporary database connection error.")

        return {
            "request": state["request"],
            "tool_result": "",
            "error": "Temporary database connection error.",
            "status": "error",
            "retry_count": retry_count + 1,
        }

    # Succeeds on the second attempt.
    print("Tool executed successfully.")

    return {
        "request": state["request"],
        "tool_result": "Bus search completed successfully.",
        "error": "",
        "status": "success",
        "retry_count": retry_count,
    }


# ---------------------------------------------------------
# Success Handler
# ---------------------------------------------------------

def success_handler(
    state: AgentState,
) -> AgentState:

    print("\n--- SUCCESS HANDLER ---")

    print(
        f"Tool result: {state['tool_result']}"
    )

    return {
        "request": state["request"],
        "tool_result": state["tool_result"],
        "error": "",
        "status": "completed",
        "retry_count": state["retry_count"],
    }


# ---------------------------------------------------------
# Error Handler
# ---------------------------------------------------------

def error_handler(
    state: AgentState,
) -> AgentState:

    print("\n--- ERROR HANDLER ---")

    print(
        f"Final error: {state['error']}"
    )

    return {
        "request": state["request"],
        "tool_result": "",
        "error": state["error"],
        "status": "failed",
        "retry_count": state["retry_count"],
    }


# ---------------------------------------------------------
# Router after Tool
# ---------------------------------------------------------

def route_after_tool(
    state: AgentState,
) -> Literal["success", "retry", "error"]:

    if state["status"] == "success":
        return "success"

    if state["retry_count"] < MAX_RETRIES:
        return "retry"

    return "error"


# ---------------------------------------------------------
# Build Graph
# ---------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node(
    "tool",
    bus_search_tool,
)

builder.add_node(
    "success_handler",
    success_handler,
)

builder.add_node(
    "error_handler",
    error_handler,
)

builder.add_edge(
    START,
    "tool",
)

builder.add_conditional_edges(
    "tool",
    route_after_tool,
    {
        "success": "success_handler",
        "retry": "tool",
        "error": "error_handler",
    },
)

builder.add_edge(
    "success_handler",
    END,
)

builder.add_edge(
    "error_handler",
    END,
)

graph = builder.compile()


# ---------------------------------------------------------
# Run
# ---------------------------------------------------------

if __name__ == "__main__":

    initial_state: AgentState = {
        "request": "Find buses from Hyderabad to Bangalore.",
        "tool_result": "",
        "error": "",
        "status": "pending",
        "retry_count": 0,
    }

    print("=" * 60)
    print("LANGGRAPH RETRY LOGIC")
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