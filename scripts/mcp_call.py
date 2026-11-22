"""Call one MCP tool from the terminal, through the real MCP protocol.

    uv run python scripts/mcp_call.py --list
    uv run python scripts/mcp_call.py warehouse run_query '{"sql": "SELECT 1"}'
    uv run python scripts/mcp_call.py knowledge search_knowledge '{"query": "net revenue", "k": 3}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os

os.environ.setdefault("FASTMCP_LOG_LEVEL", "WARNING")

from fastmcp import Client

from agent.config import load_mcp_config


async def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("server", nargs="?")
    p.add_argument("tool", nargs="?")
    p.add_argument("args", nargs="?", default="{}", help="JSON object of tool arguments")
    p.add_argument("--list", action="store_true", help="list every tool on every server")
    a = p.parse_args()

    async with Client(load_mcp_config()) as client:
        if a.list or not a.tool:
            for t in await client.list_tools():
                ro = t.annotations.readOnlyHint if t.annotations else None
                print(f"{t.name:<32} readOnly={ro}  {(t.description or '').splitlines()[0]}")
            return
        r = await client.call_tool(f"{a.server}_{a.tool}", json.loads(a.args), raise_on_error=False)
        if r.is_error:
            print("ERROR:", r.content[0].text if r.content else "unknown")
        else:
            print(json.dumps(r.structured_content, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())
