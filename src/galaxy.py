import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

from .reading_profile import NEARBY_DOMAIN_MAP

logger = logging.getLogger(__name__)


def export_galaxy_data(cache_db_path: str = "data/cache.db",
                       output_path: str = "site/galaxy_data.json") -> str:
    import os
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    conn = sqlite3.connect(cache_db_path)

    conn.execute(
        "CREATE TABLE IF NOT EXISTS preferences ("
        "  domain_name TEXT PRIMARY KEY,"
        "  likes INTEGER DEFAULT 0,"
        "  skips INTEGER DEFAULT 0,"
        "  deep_dives INTEGER DEFAULT 0,"
        "  last_interaction TEXT,"
        "  adjusted_weight REAL DEFAULT 0.0"
        ")"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS weekly_archive ("
        "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "  title TEXT, url TEXT, domain_name TEXT, domain_icon TEXT,"
        "  chinese_summary TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        ")"
    )

    prefs_rows = conn.execute(
        "SELECT domain_name, likes, skips, deep_dives FROM preferences"
    ).fetchall()

    archive_rows = conn.execute(
        "SELECT domain_name, domain_icon, title, created_at FROM weekly_archive "
        "ORDER BY created_at DESC"
    ).fetchall()

    conn.close()

    domain_stats = {}
    for row in prefs_rows:
        domain_stats[row[0]] = {
            "likes": row[1],
            "skips": row[2],
            "deep_dives": row[3],
            "reads": 0,
        }

    domain_icons = {}
    domain_read_count = {}
    for row in archive_rows:
        name = row[0]
        icon = row[1]
        domain_icons[name] = icon
        domain_read_count[name] = domain_read_count.get(name, 0) + 1

    for name, count in domain_read_count.items():
        if name in domain_stats:
            domain_stats[name]["reads"] = count
        else:
            domain_stats[name] = {"likes": 0, "skips": 0, "deep_dives": 0, "reads": count}

    all_domain_names = set(domain_stats.keys()) | set(domain_icons.keys())
    for name in all_domain_names:
        if name not in domain_icons:
            domain_icons[name] = "📚"

    nodes = []
    for name in all_domain_names:
        stats = domain_stats.get(name, {"likes": 0, "skips": 0, "deep_dives": 0, "reads": 0})
        score = stats["likes"] * 2 + stats["deep_dives"] * 3 + stats["reads"]
        nodes.append({
            "id": name,
            "icon": domain_icons.get(name, "📚"),
            "likes": stats["likes"],
            "skips": stats["skips"],
            "deep_dives": stats["deep_dives"],
            "reads": stats["reads"],
            "score": score,
        })

    links = []
    seen_links = set()
    for source, targets in NEARBY_DOMAIN_MAP.items():
        for target in targets:
            key = tuple(sorted([source, target]))
            if key not in seen_links and source in all_domain_names and target in all_domain_names:
                seen_links.add(key)
                links.append({"source": source, "target": target})

    data = {
        "nodes": nodes,
        "links": links,
        "updated_at": datetime.now().isoformat(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Galaxy data exported: {len(nodes)} nodes, {len(links)} links")
    return output_path