from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from bus_booking_ai_agent.phase_03_mcp.tools.search_buses import (
    SearchBusesInput,
    search_buses,
)

from bus_booking_ai_agent.phase_03_mcp.tools.get_bus_details import (
    GetBusDetailsInput,
    get_bus_details,
)

from bus_booking_ai_agent.phase_03_mcp.tools.check_seat_availability import (
    CheckSeatAvailabilityInput,
    InvalidJourneySegmentError,
    check_seat_availability,
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


@mcp.tool()
def get_bus_details_tool(
    schedule_id: str,
) -> dict | None:
    """
    Get detailed information about a specific scheduled bus.
    """

    request = GetBusDetailsInput(
        schedule_id=schedule_id,
    )

    return get_bus_details(request)


@mcp.tool()
def check_seat_availability_tool(
    schedule_id: str,
    boarding_stop_id: str,
    dropping_stop_id: str,
) -> list[dict]:
    """
    Check available seats for a specific scheduled bus
    and journey segment.
    """

    request = CheckSeatAvailabilityInput(
        schedule_id=schedule_id,
        boarding_stop_id=boarding_stop_id,
        dropping_stop_id=dropping_stop_id,
    )

    try:
        return check_seat_availability(request)

    except InvalidJourneySegmentError as error:
        raise ToolError(str(error)) from error