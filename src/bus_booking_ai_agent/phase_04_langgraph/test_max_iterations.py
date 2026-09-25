from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


MAX_ITERATIONS = 3


class AgentState(TypedDict):
    request: str
    iteration: int
    result: str
    status: str


def agent_node(state: AgentState) -> AgentState:
    iteration = state["iteration"] + 1

    print(f"\n--- AGENT ITERATION {iteration} ---")

    print(f"Request: {state['request']}")

    return {
        "request": state["request"],
        "iteration": iteration,
        "result": f"Agent completed iteration {iteration}.",
        "status": "running",
    }


def route_after_agent(
    state: AgentState,
) -> Literal["continue", "stop"]:
    if state["iteration"] >= MAX_ITERATIONS:
        print("\nMaximum iteration limit reached.")
        return "stop"

    print("\nIteration limit not reached. Continuing...")
    return "continue"


builder = StateGraph(AgentState)

builder.add_node("agent", agent_node)

builder.add_edge(START, "agent")

builder.add_conditional_edges(
    "agent",
    route_after_agent,
    {
        "continue": "agent",
        "stop": END,
    },
)

graph = builder.compile()


if __name__ == "__main__":

    initial_state: AgentState = {
        "request": "Find buses from Hyderabad to Bangalore.",
        "iteration": 0,
        "result": "",
        "status": "pending",
    }

    print("=" * 60)
    print("LANGGRAPH MAXIMUM ITERATIONS")
    print("=" * 60)

    print("\nInitial state:")
    print(initial_state)

    final_state = graph.invoke(initial_state)

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(final_state)