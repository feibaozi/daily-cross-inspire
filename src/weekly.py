from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

WEEKLY_SYSTEM_PROMPT = """你是一位博学的知识编辑，负责策划每周知识精选特刊。

你的任务：
1. 阅读本周推送过的所有文章摘要（包括标题、领域）
2. 评选出"本周最佳"——最有启发、最让人眼前一亮的文章
3. 为"本周最佳"撰写深度解读（500-600字），比日常早报更深入
4. 如果你发现两篇看似无关的文章之间存在奇妙的关联，简要描述这个"跨界连接"（200字以内）
5. 为本周的阅读体验做一句话总结

风格要求：
- 比日常早报更深度、更精致
- 加入你作为知识编辑的"个人推荐理由"
- 跨界连接部分要有发现感："你绝对想不到，A 领域的发现竟然和 B 领域的研究..."

输出格式：用 Markdown，不要用代码块包裹。"""

WEEKLY_USER_PROMPT_TEMPLATE = """以下是本周（周一至周日）推送过的所有文章摘要：

{articles_summary}

请按照要求，生成本周精选特刊。"""


@dataclass
class WeeklyHighlight:
    best_article: dict
    deep_analysis: str
    cross_connection: str
    week_summary: str


def is_sunday(timezone_str: str = "Asia/Shanghai") -> bool:
    offset_map = {"Asia/Shanghai": 8, "Asia/Tokyo": 9, "America/New_York": -5, "Europe/London": 1}
    offset = offset_map.get(timezone_str, 8)
    now = datetime.now(timezone.utc) + timedelta(hours=offset)
    return now.weekday() == 6


class WeeklyCollector:
    def __init__(self, cache_db_path: str = "data/cache.db"):
        self.cache_db_path = cache_db_path

    def get_week_articles(self) -> list[dict]:
        import sqlite3

        cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()

        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS weekly_archive ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT, url TEXT, domain_name TEXT, domain_icon TEXT,"
            "  chinese_summary TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        rows = conn.execute(
            "SELECT title, url, domain_name, domain_icon, chinese_summary "
            "FROM weekly_archive WHERE created_at >= ? ORDER BY created_at",
            (cutoff,)
        ).fetchall()
        conn.close()

        return [
            {
                "title": row[0],
                "url": row[1],
                "domain_name": row[2],
                "domain_icon": row[3],
                "chinese_summary": row[4],
            }
            for row in rows
        ]

    def archive_article(self, domain_name: str, domain_icon: str,
                        title: str, url: str, chinese_summary: str):
        import sqlite3
        import os

        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS weekly_archive ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  title TEXT, url TEXT, domain_name TEXT, domain_icon TEXT,"
            "  chinese_summary TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.execute(
            "INSERT INTO weekly_archive (title, url, domain_name, domain_icon, chinese_summary) VALUES (?, ?, ?, ?, ?)",
            (title, url, domain_name, domain_icon, chinese_summary)
        )
        conn.commit()
        conn.close()


class WeeklyAISummarizer:
    def __init__(self, api_base: str, api_key: str, model: str = "deepseek-chat",
                 max_tokens: int = 1500, temperature: float = 0.8):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def generate_weekly(self, articles: list[dict]) -> str:
        import httpx

        summaries = []
        for i, art in enumerate(articles, 1):
            summary_text = art.get("chinese_summary", "")[:300]
            summaries.append(
                f"{i}. [{art.get('domain_icon', '')} {art.get('domain_name', '')}] "
                f"{art.get('title', '')}\n   {summary_text}"
            )

        user_prompt = WEEKLY_USER_PROMPT_TEMPLATE.format(
            articles_summary="\n\n".join(summaries)
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": WEEKLY_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        return data["choices"][0]["message"]["content"].strip()