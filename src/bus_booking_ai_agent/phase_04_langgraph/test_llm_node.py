from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from bus_booking_ai_agent.config.gemini import client, MODEL


class AgentState(TypedDict):
    message: str
    response: str


def llm_node(state: AgentState) -> AgentState:
    print("\n--- LLM Node ---")
    print(f"Input message: {state['message']}")

    response = client.interactions.create(
        model=MODEL,
        input=state["message"],
    )

    output_text = getattr(response, "output_text", None)

    if not output_text:
        raise RuntimeError("Gemini returned no text response.")

    return {
        "message": state["message"],
        "response": output_text,
    }


builder = StateGraph(AgentState)

builder.add_node("llm", llm_node)

builder.add_edge(START, "llm")
builder.add_edge("llm", END)

graph = builder.compile()


if __name__ == "__main__":

    initial_state: AgentState = {
        "message": "What information do I need to book a bus ticket?",
        "response": "",
    }

    print("=" * 60)
    print("LANGGRAPH LLM NODE")
    print("=" * 60)

    print("\nInitial state:")
    print(initial_state)

    final_state = graph.invoke(initial_state)

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(final_state)