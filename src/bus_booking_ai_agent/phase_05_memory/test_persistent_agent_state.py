from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    user_message: str
    status: str
    iteration: int


def agent_node(state: AgentState) -> AgentState:
    return {
        **state,
        "status": "completed",
        "iteration": state["iteration"] + 1,
    }


def build_graph():
    builder = StateGraph(AgentState)

    builder.add_node("agent", agent_node)

    builder.add_edge(START, "agent")
    builder.add_edge("agent", END)

    checkpointer = MemorySaver()

    return builder.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    graph = build_graph()

    config: RunnableConfig = {
        "configurable": {
            "thread_id": "conversation-001",
        }
    }

    initial_state: AgentState = {
        "user_message": "Find buses from Hyderabad to Bangalore.",
        "status": "started",
        "iteration": 0,
    }

    result = graph.invoke(
        initial_state,
        config=config,
    )

    print("FIRST EXECUTION")
    print(result)

    saved_state = graph.get_state(config)

    print("\nSAVED STATE")
    print(saved_state.values)