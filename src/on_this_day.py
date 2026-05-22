import logging
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)


async def fetch_on_this_day() -> str:
    try:
        month = datetime.now().month
        day = datetime.now().day

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.wikimedia.org/feed/v1/wikipedia/en/onthisday/events/{month}/{day}",
                headers={
                    "User-Agent": "DailyCrossInspire/1.0",
                    "Accept": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        events = data.get("events", [])
        if not events:
            return ""

        event = events[0]
        year = event.get("year", "")
        text = event.get("text", "")

        text = text.replace("<b>", "**").replace("</b>", "**")
        text = text.replace("<i>", "*").replace("</i>", "*")
        text = text.replace("<a href=", "[").replace("</a>", "]")

        import re
        text = re.sub(r'\[[^]]*?title="([^"]*)"[^\]]*\]', r'\1', text)

        return f"## 📅 历史上的今天\n\n> **{year}年{month}月{day}日** — {text}\n"

    except Exception as e:
        logger.warning(f"Failed to fetch on-this-day: {e}")
        return ""