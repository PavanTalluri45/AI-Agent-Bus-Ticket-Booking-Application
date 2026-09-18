from mcp.server.mcpserver import MCPServer

from bus_booking_ai_agent.phase_03_mcp.tools.search_buses import (
    SearchBusesInput,
    search_buses,
)


mcp = MCPServer("Bus Booking MCP Server")


@mcp.tool()
def search_buses_tool(
    origin: str,
    destination: str,
    travel_date: str,
) -> list[dict]:
    """
    Search scheduled buses between an origin and destination
    for a specific travel date.
    """

    request = SearchBusesInput(
        origin=origin,
        destination=destination,
        travel_date=travel_date,
    )

    return search_buses(request)