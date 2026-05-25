import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class PreferenceEngine:
    def __init__(self, cache_db_path: str = "data/cache.db"):
        self.cache_db_path = cache_db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
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
            "CREATE TABLE IF NOT EXISTS feedback_log ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  article_url TEXT,"
            "  domain_name TEXT,"
            "  action TEXT NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.close()

    def record_feedback(self, article_url: str, domain_name: str, action: str):
        if action not in ("like", "skip", "deep_dive"):
            logger.warning(f"Unknown feedback action: {action}")
            return

        conn = sqlite3.connect(self.cache_db_path)
        now = datetime.now().isoformat()

        conn.execute(
            "INSERT INTO feedback_log (article_url, domain_name, action, created_at) VALUES (?, ?, ?, ?)",
            (article_url, domain_name, action, now)
        )

        row = conn.execute(
            "SELECT likes, skips, deep_dives FROM preferences WHERE domain_name = ?",
            (domain_name,)
        ).fetchone()

        if row is None:
            likes = skips = deep_dives = 0
        else:
            likes, skips, deep_dives = row

        if action == "like":
            likes += 1
        elif action == "skip":
            skips += 1
        elif action == "deep_dive":
            deep_dives += 1

        conn.execute(
            "INSERT OR REPLACE INTO preferences (domain_name, likes, skips, deep_dives, last_interaction, adjusted_weight) "
            "VALUES (?, ?, ?, ?, ?, COALESCE((SELECT adjusted_weight FROM preferences WHERE domain_name = ?), 0.0))",
            (domain_name, likes, skips, deep_dives, now, domain_name)
        )
        conn.commit()
        conn.close()
        logger.info(f"Feedback recorded: {action} on [{domain_name}]")

    def get_adjusted_weights(self, base_weights: dict[str, int],
                             decay_days: int = 30) -> dict[str, float]:
        conn = sqlite3.connect(self.cache_db_path)
        rows = conn.execute(
            "SELECT domain_name, likes, skips, deep_dives, last_interaction FROM preferences"
        ).fetchall()
        conn.close()

        prefs = {}
        for row in rows:
            prefs[row[0]] = {
                "likes": row[1],
                "skips": row[2],
                "deep_dives": row[3],
                "last_interaction": row[4],
            }

        adjusted = {}
        for domain_name, base_weight in base_weights.items():
            inv_base = 1.0 / max(base_weight, 1)

            if domain_name not in prefs:
                adjusted[domain_name] = inv_base
                continue

            p = prefs[domain_name]
            score = p["likes"] * 2.0 + p["deep_dives"] * 3.0 - p["skips"] * 1.5

            if p["last_interaction"]:
                try:
                    last = datetime.fromisoformat(p["last_interaction"])
                    days_ago = (datetime.now() - last).days
                    recency = max(0.1, 1.0 - (days_ago / decay_days))
                except (ValueError, TypeError):
                    recency = 1.0
            else:
                recency = 1.0

            adjusted[domain_name] = inv_base * (1.0 + score * 0.3) * recency

        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted

    def get_reading_profile(self) -> dict:
        conn = sqlite3.connect(self.cache_db_path)
        prefs = conn.execute(
            "SELECT domain_name, likes, skips, deep_dives, last_interaction FROM preferences "
            "ORDER BY likes + deep_dives DESC"
        ).fetchall()

        total_feedback = conn.execute(
            "SELECT COUNT(*) FROM feedback_log"
        ).fetchone()[0]

        recent_count = conn.execute(
            "SELECT COUNT(*) FROM feedback_log WHERE created_at >= ?",
            ((datetime.now() - timedelta(days=7)).isoformat(),)
        ).fetchone()[0]

        top_domains = conn.execute(
            "SELECT domain_name, likes + deep_dives as score FROM preferences "
            "ORDER BY score DESC LIMIT 5"
        ).fetchall()

        skipped_domains = conn.execute(
            "SELECT domain_name, skips FROM preferences "
            "WHERE skips > 0 ORDER BY skips DESC LIMIT 3"
        ).fetchall()

        conn.close()

        return {
            "total_interactions": total_feedback,
            "weekly_interactions": recent_count,
            "top_domains": [{"name": r[0], "score": r[1]} for r in top_domains],
            "skipped_domains": [{"name": r[0], "skips": r[1]} for r in skipped_domains],
            "domain_preferences": [
                {
                    "name": r[0],
                    "likes": r[1],
                    "skips": r[2],
                    "deep_dives": r[3],
                }
                for r in prefs
            ],
        }

    def get_feedback_url(self, article_url: str, domain_name: str,
                         action: str) -> str:
        import base64
        payload = json.dumps({
            "url": article_url,
            "domain": domain_name,
            "action": action,
        })
        encoded = base64.urlsafe_b64encode(payload.encode()).decode()
        return f"https://feibaozi.github.io/daily-cross-inspire/feedback.html?d={encoded}"