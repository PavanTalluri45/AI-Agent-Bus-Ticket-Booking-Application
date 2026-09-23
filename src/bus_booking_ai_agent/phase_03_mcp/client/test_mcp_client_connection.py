import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


SERVER_PATH = (
    Path(__file__).resolve().parents[1] / "server" / "mcp_server.py"
)


async def main():
    server_params = StdioServerParameters(
        command="uv",
        args=[
            "run",
            "python",
            str(SERVER_PATH),
        ],
    )

    print("Connecting to MCP server...")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            print("MCP connection established.")

            tools_result = await session.list_tools()

            print("\n=== AVAILABLE MCP TOOLS ===")

            for tool in tools_result.tools:
                print(f"- {tool.name}")
                print(f"  Description: {tool.description}")

            print("\n=== CALLING search_buses ===")

            result = await session.call_tool(
                "search_buses_tool",
                arguments={
                    "origin": "Hyderabad",
                    "destination": "Bangalore",
                    "travel_date": "2026-09-25",
                },
            )

            print("\n=== TOOL RESULT ===")
            print(result)


if __name__ == "__main__":
    asyncio.run(main())