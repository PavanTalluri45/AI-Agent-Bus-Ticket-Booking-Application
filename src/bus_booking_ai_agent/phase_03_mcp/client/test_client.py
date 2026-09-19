import asyncio

from mcp import Client

from bus_booking_ai_agent.phase_03_mcp.server.mcp_server import mcp


async def main() -> None:
    async with Client(mcp) as client:

        # Discover available MCP tools
        tools = await client.list_tools()

        print("Available MCP tools:")

        for tool in tools.tools:
            print(f"- {tool.name}")

        # ---------------------------------------------------------
        # 1. Search Buses
        # ---------------------------------------------------------

        search_result = await client.call_tool(
            "search_buses_tool",
            {
                "origin": "Hyderabad",
                "destination": "Bangalore",
                "travel_date": "2026-09-20",
            },
        )

        print("\nSearch Buses Result:")
        print(search_result)

        # ---------------------------------------------------------
        # 2. Get Bus Details
        # ---------------------------------------------------------

        details_result = await client.call_tool(
            "get_bus_details_tool",
            {
                "schedule_id": "53220a90-ee01-5210-99e2-e0387975cccc",
            },
        )

        print("\nBus Details Result:")
        print(details_result)

        # ---------------------------------------------------------
        # 3. Check Seat Availability
        # ---------------------------------------------------------

        availability_result = await client.call_tool(
            "check_seat_availability_tool",
            {
                "schedule_id": "53220a90-ee01-5210-99e2-e0387975cccc",
                "boarding_stop_id": "e59ba1c8-1798-5ee2-93d5-06db16def156",
                "dropping_stop_id": "2f1514d9-f73e-50a2-94ae-8b5ef444f1a9",
            },
        )

        print("\nSeat Availability Result:")
        print(availability_result)


if __name__ == "__main__":
    asyncio.run(main())