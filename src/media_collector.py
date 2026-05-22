import asyncio
import logging
import subprocess
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MediaSource:
    url: str
    domain_name: str
    domain_icon: str
    type: str


async def fetch_youtube_captions(video_url: str) -> str:
    proc = await asyncio.create_subprocess_exec(
        "yt-dlp", "--skip-download", "--write-auto-subs", "--sub-lang", "en",
        "--convert-subs", "srt", "--print", "filename", "-o", "-",
        video_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.warning(f"yt-dlp failed for {video_url}: {stderr.decode()}")
        return ""
    return stdout.decode("utf-8", errors="replace")[:2000]


async def fetch_youtube_metadata(video_url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://www.youtube.com/oembed?url={video_url}&format=json"
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "title": data.get("title", ""),
                "description": (data.get("description", "") or "")[:500],
            }
    except Exception as e:
        logger.warning(f"Failed to fetch YouTube metadata: {e}")
        return {"title": "", "description": ""}


async def collect_youtube(sources: list[MediaSource]) -> list[dict]:
    results = []
    for src in sources:
        if src.type != "youtube":
            continue
        meta = await fetch_youtube_metadata(src.url)
        if not meta["title"]:
            continue
        results.append({
            "title": meta["title"],
            "url": src.url,
            "summary": meta["description"],
            "domain_name": src.domain_name,
            "domain_icon": src.domain_icon,
        })
        logger.info(f"YouTube: {meta['title'][:60]}")
    return results