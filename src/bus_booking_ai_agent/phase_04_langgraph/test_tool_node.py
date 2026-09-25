from typing import TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    message: str
    tool_result: str


def get_bus_information() -> str:
    """
    Simple deterministic tool used to learn
    how a Tool Node executes a tool.
    """

    return "Bus information tool executed successfully."


def tool_node(state: AgentState) -> AgentState:
    print("\n--- Tool Node ---")
    print(f"Received state: {state}")

    result = get_bus_information()

    return {
        "message": state["message"],
        "tool_result": result,
    }


builder = StateGraph(AgentState)

builder.add_node("tool", tool_node)

builder.add_edge(START, "tool")
builder.add_edge("tool", END)

graph = builder.compile()


if __name__ == "__main__":

    initial_state: AgentState = {
        "message": "Find bus information",
        "tool_result": "",
    }

    print("=" * 60)
    print("LANGGRAPH TOOL NODE")
    print("=" * 60)

    print("\nInitial state:")
    print(initial_state)

    final_state = graph.invoke(initial_state)

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(final_state)