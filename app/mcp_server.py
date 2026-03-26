from datetime import datetime
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("JarvisTools", json_response=True)


@mcp.tool()
def get_time(timezone: str = "America/Los_Angeles") -> dict[str, str]:
    now = datetime.now(ZoneInfo(timezone))
    return {
        "timestamp": now.isoformat(),
        "friendly": now.strftime("%A, %B %d, %Y %I:%M %p %Z"),
    }


@mcp.tool()
def conversation_summary(summary: str = "") -> dict[str, str]:
    return {"summary": summary or "No conversation history yet."}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
