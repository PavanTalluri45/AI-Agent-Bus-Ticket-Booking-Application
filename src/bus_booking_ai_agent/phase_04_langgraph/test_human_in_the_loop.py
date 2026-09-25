from typing import Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class AgentState(TypedDict):
    request: str
    action: str
    approval: str
    status: str


def prepare_action(state: AgentState) -> AgentState:
    print("\n--- PREPARE ACTION ---")

    action = "Book the selected bus seat."

    print(f"Request: {state['request']}")
    print(f"Prepared action: {action}")

    return {
        "request": state["request"],
        "action": action,
        "approval": "",
        "status": "awaiting_approval",
    }


def human_approval(state: AgentState) -> AgentState:
    print("\n--- HUMAN APPROVAL ---")
    print(f"Action requiring approval: {state['action']}")

    decision = interrupt(
        {
            "message": "Do you approve this action?",
            "action": state["action"],
        }
    )

    return {
        "request": state["request"],
        "action": state["action"],
        "approval": str(decision),
        "status": "approved" if decision == "yes" else "rejected",
    }


def route_after_approval(
    state: AgentState,
) -> Literal["approved", "rejected"]:

    if state["approval"] == "yes":
        return "approved"

    return "rejected"


def approved_node(state: AgentState) -> AgentState:
    print("\n--- APPROVED ---")
    print("Human approved the action.")

    return {
        "request": state["request"],
        "action": state["action"],
        "approval": state["approval"],
        "status": "approved",
    }


def rejected_node(state: AgentState) -> AgentState:
    print("\n--- REJECTED ---")
    print("Human rejected the action.")

    return {
        "request": state["request"],
        "action": state["action"],
        "approval": state["approval"],
        "status": "rejected",
    }


builder = StateGraph(AgentState)

builder.add_node("prepare_action", prepare_action)
builder.add_node("human_approval", human_approval)
builder.add_node("approved", approved_node)
builder.add_node("rejected", rejected_node)

builder.add_edge(START, "prepare_action")
builder.add_edge("prepare_action", "human_approval")

builder.add_conditional_edges(
    "human_approval",
    route_after_approval,
    {
        "approved": "approved",
        "rejected": "rejected",
    },
)

builder.add_edge("approved", END)
builder.add_edge("rejected", END)

checkpointer = MemorySaver()

graph = builder.compile(
    checkpointer=checkpointer
)


if __name__ == "__main__":

    initial_state: AgentState = {
        "request": "Book a bus seat.",
        "action": "",
        "approval": "",
        "status": "pending",
    }

    config: RunnableConfig = {
        "configurable": {
            "thread_id": "hitl-learning-01"
        }
    }

    print("=" * 60)
    print("LANGGRAPH HUMAN-IN-THE-LOOP")
    print("=" * 60)

    print("\nStarting graph...")

    result = graph.invoke(
        initial_state,
        config=config,
    )

    print("\n" + "=" * 60)
    print("GRAPH PAUSED")
    print("=" * 60)

    print(result)