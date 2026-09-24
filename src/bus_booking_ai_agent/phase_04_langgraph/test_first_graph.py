from typing import TypedDict

from langgraph.graph import END, START, StateGraph


# ============================================================
# State
# ============================================================

class AgentState(TypedDict):
    message: str


# ============================================================
# Node A
# ============================================================

def node_a(state: AgentState) -> AgentState:
    print("\n--- Node A ---")
    print(f"Received state: {state}")

    return {
        "message": state["message"] + " -> Node A"
    }


# ============================================================
# Node B
# ============================================================

def node_b(state: AgentState) -> AgentState:
    print("\n--- Node B ---")
    print(f"Received state: {state}")

    return {
        "message": state["message"] + " -> Node B"
    }


# ============================================================
# Build Graph
# ============================================================

builder = StateGraph(AgentState)

builder.add_node("node_a", node_a)
builder.add_node("node_b", node_b)

builder.add_edge(START, "node_a")
builder.add_edge("node_a", "node_b")
builder.add_edge("node_b", END)

graph = builder.compile()


# ============================================================
# Run Graph
# ============================================================

if __name__ == "__main__":

    initial_state: AgentState = {
        "message": "Start"
    }

    print("=" * 60)
    print("FIRST LANGGRAPH")
    print("=" * 60)

    print("\nInitial state:")
    print(initial_state)

    final_state = graph.invoke(initial_state)

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(final_state)