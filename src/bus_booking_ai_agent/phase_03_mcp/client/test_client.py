import asyncio

from mcp import Client

from bus_booking_ai_agent.phase_03_mcp.server.mcp_server import mcp


async def main() -> None:
    async with Client(mcp) as client:

        tools = await client.list_tools()

        print("Available MCP tools:")

        for tool in tools.tools:
            print(f"- {tool.name}")

        result = await client.call_tool(
            "search_buses_tool",
            {
                "origin": "Hyderabad",
                "destination": "Bangalore",
                "travel_date": "2026-09-20",
            },
        )

        print("\nTool result:")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())