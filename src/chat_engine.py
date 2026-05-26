import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

CHAT_SYSTEM_PROMPT = """你是"跨界灵感"的知识管家，一个博学、温暖、有趣的 AI 伙伴。

你的职责：
1. 回答用户关于已推送文章的任何问题
2. 用通俗语言解释复杂概念
3. 帮用户发现不同领域之间的联系
4. 推荐相关的延伸阅读方向

规则：
- 回答要简洁（200字以内），除非用户要求详细解释
- 优先引用用户最近 7 天读过的文章作为上下文
- 如果不确定，坦诚说"我不太确定"，不要编造
- 用中文回答
- 语气像朋友聊天，不要像百科全书"""


class ChatEngine:
    def __init__(self, ai_summarizer, cache_db_path: str = "data/cache.db"):
        self.ai_summarizer = ai_summarizer
        self.cache_db_path = cache_db_path
        self._init_db()

    def _init_db(self):
        import os
        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chat_history ("
            "  id INTEGER PRIMARY KEY AUTOINCREMENT,"
            "  role TEXT NOT NULL,"
            "  content TEXT NOT NULL,"
            "  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            ")"
        )
        conn.close()

    def _get_recent_articles(self, days: int = 7) -> str:
        conn = sqlite3.connect(self.cache_db_path)
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = conn.execute(
            "SELECT domain_name, domain_icon, title, chinese_summary "
            "FROM weekly_archive WHERE created_at >= ? ORDER BY created_at DESC LIMIT 10",
            (cutoff,)
        ).fetchall()
        conn.close()

        if not rows:
            return "（暂无近期阅读记录）"

        parts = []
        for row in rows:
            parts.append(f"[{row[1]} {row[0]}] {row[2]}\n摘要：{row[3][:200]}")
        return "\n\n".join(parts)

    def _get_chat_history(self, limit: int = 6) -> list[dict]:
        conn = sqlite3.connect(self.cache_db_path)
        rows = conn.execute(
            "SELECT role, content FROM chat_history ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def _save_message(self, role: str, content: str):
        conn = sqlite3.connect(self.cache_db_path)
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO chat_history (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, now)
        )
        conn.execute(
            "DELETE FROM chat_history WHERE id NOT IN "
            "(SELECT id FROM chat_history ORDER BY id DESC LIMIT 50)"
        )
        conn.commit()
        conn.close()

    async def chat(self, user_message: str) -> str:
        self._save_message("user", user_message)

        recent_articles = self._get_recent_articles()
        chat_history = self._get_chat_history()

        context = f"用户最近 7 天读过的文章：\n{recent_articles}\n\n---\n\n当前对话："
        messages = [
            {"role": "system", "content": CHAT_SYSTEM_PROMPT + "\n\n" + context}
        ]
        for msg in chat_history:
            messages.append(msg)

        messages.append({"role": "user", "content": user_message})

        try:
            import httpx
            payload = {
                "model": self.ai_summarizer.model,
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7,
            }
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    f"{self.ai_summarizer.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.ai_summarizer.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            reply = data["choices"][0]["message"]["content"].strip()
            self._save_message("assistant", reply)
            return reply

        except Exception as e:
            logger.error(f"Chat engine error: {e}")
            return "抱歉，我暂时无法回答。请稍后再试。"

    def clear_history(self):
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute("DELETE FROM chat_history")
        conn.commit()
        conn.close()
        logger.info("Chat history cleared")