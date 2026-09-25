from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph


class AgentState(TypedDict):
    request_type: str
    result: str


def search_buses_tool(state: AgentState) -> AgentState:
    print("\n--- Search Buses Tool ---")

    return {
        "request_type": state["request_type"],
        "result": "Search buses tool executed.",
    }


def get_bus_details_tool(state: AgentState) -> AgentState:
    print("\n--- Get Bus Details Tool ---")

    return {
        "request_type": state["request_type"],
        "result": "Get bus details tool executed.",
    }


def route_request(
    state: AgentState,
) -> Literal["search_buses", "get_bus_details"]:
    print("\n--- Router ---")
    print(f"Request type: {state['request_type']}")

    if state["request_type"] == "search":
        return "search_buses"

    if state["request_type"] == "details":
        return "get_bus_details"

    raise ValueError(
        f"Unsupported request type: {state['request_type']}"
    )


builder = StateGraph(AgentState)

builder.add_node("search_buses", search_buses_tool)
builder.add_node("get_bus_details", get_bus_details_tool)

builder.add_conditional_edges(
    START,
    route_request,
    {
        "search_buses": "search_buses",
        "get_bus_details": "get_bus_details",
    },
)

builder.add_edge("search_buses", END)
builder.add_edge("get_bus_details", END)

graph = builder.compile()


if __name__ == "__main__":

    print("=" * 60)
    print("LANGGRAPH TOOL ROUTING")
    print("=" * 60)

    search_state: AgentState = {
        "request_type": "search",
        "result": "",
    }

    print("\nInitial state:")
    print(search_state)

    final_search_state = graph.invoke(search_state)

    print("\nFinal state:")
    print(final_search_state)

    print("\n" + "=" * 60)

    details_state: AgentState = {
        "request_type": "details",
        "result": "",
    }

    print("\nInitial state:")
    print(details_state)

    final_details_state = graph.invoke(details_state)

    print("\nFinal state:")
    print(final_details_state)