import asyncio

from mcp import Client

from bus_booking_ai_agent.phase_03_mcp.server.mcp_server import mcp


async def main() -> None:
    async with Client(mcp) as client:

        print("Testing invalid journey segment...")

        result = await client.call_tool(
            "check_seat_availability_tool",
            {
                "schedule_id": "53220a90-ee01-5210-99e2-e0387975cccc",
                "boarding_stop_id": "2f1514d9-f73e-50a2-94ae-8b5ef444f1a9",
                "dropping_stop_id": "e59ba1c8-1798-5ee2-93d5-06db16def156",
            },
        )

        print("\nResult:")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())