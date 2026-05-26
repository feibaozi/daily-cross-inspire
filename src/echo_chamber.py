import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

VALID_EMOTIONS = ("inspired", "confused", "bored", "amazed", "curious")

EMOTION_LABELS = {
    "amazed": "🤯 震撼",
    "inspired": "💡 受启发",
    "confused": "🤔 困惑",
    "bored": "😴 无聊",
    "curious": "🔍 好奇",
}


class EchoChamberDetector:
    def __init__(self, cache_db_path: str = "data/cache.db"):
        self.cache_db_path = cache_db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS emotion_log ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  article_url TEXT,"
            "  domain_name TEXT,"
            "  emotion TEXT NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS echo_chamber_alerts ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  alert_type TEXT NOT NULL,"
            "  message TEXT NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.close()

    def record_emotion(self, article_url: str, domain_name: str, emotion: str):
        if emotion not in VALID_EMOTIONS:
            logger.warning(f"Unknown emotion: {emotion}")
            return

        conn = sqlite3.connect(self.cache_db_path)
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO emotion_log (article_url, domain_name, emotion, created_at) VALUES (?, ?, ?, ?)",
            (article_url, domain_name, emotion, now)
        )
        conn.commit()
        conn.close()
        logger.info(f"Emotion recorded: {emotion} on [{domain_name}]")

    def detect_echo_chamber(self, window_days: int = 7,
                             concentration_threshold: float = 0.6) -> Optional[str]:
        conn = sqlite3.connect(self.cache_db_path)
        cutoff = (datetime.now() - timedelta(days=window_days)).isoformat()

        feedback_rows = conn.execute(
            "SELECT domain_name, action FROM feedback_log WHERE created_at >= ?",
            (cutoff,)
        ).fetchall()

        emotion_rows = conn.execute(
            "SELECT domain_name, emotion FROM emotion_log WHERE created_at >= ?",
            (cutoff,)
        ).fetchall()

        conn.close()

        positive_actions = {}
        for row in feedback_rows:
            domain, action = row
            if action in ("like", "deep_dive"):
                positive_actions[domain] = positive_actions.get(domain, 0) + 1

        positive_emotions = {}
        for row in emotion_rows:
            domain, emotion = row
            if emotion in ("amazed", "inspired", "curious"):
                positive_emotions[domain] = positive_emotions.get(domain, 0) + 1

        all_positive = {}
        for domain, count in positive_actions.items():
            all_positive[domain] = all_positive.get(domain, 0) + count
        for domain, count in positive_emotions.items():
            all_positive[domain] = all_positive.get(domain, 0) + count

        total = sum(all_positive.values())
        if total < 5:
            return None

        sorted_domains = sorted(all_positive.items(), key=lambda x: x[1], reverse=True)
        top_domain, top_count = sorted_domains[0]
        concentration = top_count / total

        if concentration >= concentration_threshold:
            from .reading_profile import NEARBY_DOMAIN_MAP
            alternatives = NEARBY_DOMAIN_MAP.get(top_domain, [])

            alert_msg = (
                f"⚠️ 茧房警示：过去 {window_days} 天，你对「{top_domain}」的正面反馈占比 "
                f"{concentration:.0%}，你正在形成新的信息茧房！\n\n"
            )

            if alternatives:
                alt_str = "、".join(alternatives[:3])
                alert_msg += f"💡 建议明天探索：{alt_str}"
            else:
                alert_msg += "💡 建议明天尝试一个完全陌生的领域"

            self._save_alert("concentration", alert_msg)
            return alert_msg

        return None

    def _save_alert(self, alert_type: str, message: str):
        conn = sqlite3.connect(self.cache_db_path)
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO echo_chamber_alerts (alert_type, message, created_at) VALUES (?, ?, ?)",
            (alert_type, message, now)
        )
        conn.commit()
        conn.close()

    def get_emotion_stats(self, days: int = 30) -> dict:
        conn = sqlite3.connect(self.cache_db_path)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        rows = conn.execute(
            "SELECT emotion, COUNT(*) FROM emotion_log WHERE created_at >= ? GROUP BY emotion",
            (cutoff,)
        ).fetchall()

        domain_emotions = conn.execute(
            "SELECT domain_name, emotion, COUNT(*) FROM emotion_log WHERE created_at >= ? "
            "GROUP BY domain_name, emotion",
            (cutoff,)
        ).fetchall()

        conn.close()

        emotion_counts = {r[0]: r[1] for r in rows}

        domain_map = {}
        for row in domain_emotions:
            domain, emotion, count = row
            if domain not in domain_map:
                domain_map[domain] = {}
            domain_map[domain][emotion] = count

        return {
            "total": sum(emotion_counts.values()),
            "by_emotion": emotion_counts,
            "by_domain": domain_map,
        }

    def get_emotion_url(self, article_url: str, domain_name: str,
                         emotion: str) -> str:
        import base64
        payload = json.dumps({
            "url": article_url,
            "domain": domain_name,
            "emotion": emotion,
        })
        encoded = base64.urlsafe_b64encode(payload.encode()).decode()
        return f"https://feibaozi.github.io/daily-cross-inspire/emotion.html?d={encoded}"