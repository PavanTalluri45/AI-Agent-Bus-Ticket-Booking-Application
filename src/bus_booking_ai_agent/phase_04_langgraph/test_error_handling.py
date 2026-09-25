from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    request: str
    tool_result: str
    error: str
    status: str


# ---------------------------------------------------------
# Tool
# ---------------------------------------------------------

def bus_search_tool(
    state: AgentState,
) -> AgentState:

    print("\n--- TOOL NODE ---")

    try:
        request = state["request"]

        print(f"Tool received request: {request}")

        # Deliberately simulate a tool failure
        # for this learning exercise.
        if "invalid" in request.lower():
            raise ValueError(
                "Invalid bus search request."
            )

        return {
            "request": request,
            "tool_result": "Bus search completed successfully.",
            "error": "",
            "status": "success",
        }

    except Exception as error:

        return {
            "request": state["request"],
            "tool_result": "",
            "error": str(error),
            "status": "error",
        }


# ---------------------------------------------------------
# Error Handler
# ---------------------------------------------------------

def error_handler(
    state: AgentState,
) -> AgentState:

    print("\n--- ERROR HANDLER ---")

    print(
        f"Error received: {state['error']}"
    )

    return {
        "request": state["request"],
        "tool_result": "",
        "error": state["error"],
        "status": "handled",
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
    }


# ---------------------------------------------------------
# Router
# ---------------------------------------------------------

def route_after_tool(
    state: AgentState,
) -> str:

    if state["status"] == "error":
        return "error"

    return "success"


# ---------------------------------------------------------
# Build Graph
# ---------------------------------------------------------

builder = StateGraph(AgentState)

builder.add_node(
    "tool",
    bus_search_tool,
)

builder.add_node(
    "error_handler",
    error_handler,
)

builder.add_node(
    "success_handler",
    success_handler,
)

builder.add_edge(
    START,
    "tool",
)

builder.add_conditional_edges(
    "tool",
    route_after_tool,
    {
        "error": "error_handler",
        "success": "success_handler",
    },
)

builder.add_edge(
    "error_handler",
    END,
)

builder.add_edge(
    "success_handler",
    END,
)

graph = builder.compile()


# ---------------------------------------------------------
# Test
# ---------------------------------------------------------

if __name__ == "__main__":

    print("=" * 60)
    print("LANGGRAPH ERROR HANDLING")
    print("=" * 60)

    # -----------------------------------------------------
    # Successful request
    # -----------------------------------------------------

    success_state: AgentState = {
        "request": "Find buses from Hyderabad to Bangalore.",
        "tool_result": "",
        "error": "",
        "status": "pending",
    }

    print("\n" + "=" * 60)
    print("TEST 1: SUCCESS")
    print("=" * 60)

    final_success_state = graph.invoke(
        success_state
    )

    print("\nFinal state:")
    print(final_success_state)

    # -----------------------------------------------------
    # Failed request
    # -----------------------------------------------------

    error_state: AgentState = {
        "request": "Invalid bus search request.",
        "tool_result": "",
        "error": "",
        "status": "pending",
    }

    print("\n" + "=" * 60)
    print("TEST 2: ERROR")
    print("=" * 60)

    final_error_state = graph.invoke(
        error_state
    )

    print("\nFinal state:")
    print(final_error_state)