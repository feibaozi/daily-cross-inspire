from datetime import datetime
from typing import Optional

from .ai_summarizer import SummarizedArticle
from .collector import FeedHealth


HEADER_TEMPLATE = """# ☕ 每日跨界灵感早报

> 今天带你闯入 3 个完全陌生的世界 🌍
> {date_str}

---

"""

ARTICLE_TEMPLATE = """## {icon} {domain_name}

{chinese_summary}

---

"""

HEALTH_WARNING_TEMPLATE = """## ⚠️ 源健康状态

> 以下 RSS 源已连续 {threshold} 天异常，已被自动降级跳过：

{degraded_list}

"""

HEALTH_OK_FOOTER = """## 📡 源健康状态

> 所有 {total} 个 RSS 源运行正常 ✅

"""

FOOTER_TEMPLATE = """📬 明天早上 8:00，继续探索新世界

---

*由 DailyCrossInspire 自动生成 · {date_str}*"""


WEEKLY_HEADER = """# 🏆 每周跨界精选

> 一周探索了 7 个新世界，今天来回顾最有价值的那一个 🌟
> {date_str}

---

"""


class Composer:
    def __init__(self, timezone: str = "Asia/Shanghai"):
        self.timezone = timezone

    def _format_date(self) -> str:
        from datetime import timezone as tz, timedelta

        offset_map = {
            "Asia/Shanghai": 8,
            "Asia/Tokyo": 9,
            "America/New_York": -5,
            "Europe/London": 1,
        }
        offset = offset_map.get(self.timezone, 8)
        now = datetime.now(tz.utc) + timedelta(hours=offset)
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        weekday = weekday_names[now.weekday()]
        return f"{now.year}年{now.month}月{now.day}日 星期{weekday}"

    @staticmethod
    def _build_health_section(health_report: list[FeedHealth],
                              degrade_threshold: int = 3) -> str:
        degraded = [h for h in health_report if h.degraded]
        total = len(health_report)

        if degraded:
            lines = []
            for h in degraded:
                lines.append(
                    f"- {h.domain_name}：`{h.feed_url[:50]}...` ({h.consecutive_failures}次连续失败)"
                )
            return HEALTH_WARNING_TEMPLATE.format(
                threshold=degrade_threshold,
                degraded_list="\n".join(lines),
            )
        elif total > 0:
            return HEALTH_OK_FOOTER.format(total=total)
        return ""

    def compose(self, summarized: list[SummarizedArticle],
                health_report: Optional[list[FeedHealth]] = None,
                degrade_threshold: int = 3,
                cross_connection: Optional[str] = None) -> str:
        date_str = self._format_date()
        parts = [HEADER_TEMPLATE.format(date_str=date_str)]

        for item in summarized:
            parts.append(
                ARTICLE_TEMPLATE.format(
                    icon=item.domain_icon,
                    domain_name=item.domain_name,
                    chinese_summary=item.chinese_summary,
                )
            )

        if cross_connection:
            parts.append(cross_connection)
            parts.append("\n---\n\n")

        if health_report:
            parts.append(self._build_health_section(health_report, degrade_threshold))
            parts.append("\n---\n\n")

        parts.append(FOOTER_TEMPLATE.format(date_str=date_str))
        return "".join(parts)

    def compose_feishu_card(self, summarized: list[SummarizedArticle],
                            health_report: Optional[list[FeedHealth]] = None,
                            degrade_threshold: int = 3) -> dict:
        markdown = self.compose(summarized, health_report, degrade_threshold)
        date_str = self._format_date()

        degraded = [h for h in (health_report or []) if h.degraded]
        health_note = "自动生成 · 每天早8:00推送"
        if degraded:
            health_note = f"自动生成 · {len(degraded)}个源异常"

        article_urls = [item.article.url for item in summarized]

        elements = [{"tag": "markdown", "content": markdown}]
        if article_urls:
            elements.append(self._build_actions(article_urls))
        elements.append({"tag": "hr"})
        elements.append({"tag": "note", "elements": [{"tag": "plain_text", "content": health_note}]})

        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"☕ 每日跨界灵感 · {date_str}"},
                    "template": "blue",
                },
                "elements": elements,
            },
        }

    @staticmethod
    def _build_actions(article_urls: list[str]) -> dict:
        buttons = []
        for i, url in enumerate(article_urls):
            buttons.append({
                "tag": "button",
                "text": {"tag": "plain_text", "content": f"🔗 阅读原文 {i + 1}"},
                "type": "default",
                "url": url,
            })
        return {"tag": "action", "actions": buttons}

    def compose_weekly(self, weekly_content: str,
                       health_report: Optional[list[FeedHealth]] = None,
                       degrade_threshold: int = 3) -> str:
        date_str = self._format_date()
        parts = [WEEKLY_HEADER.format(date_str=date_str)]
        parts.append(weekly_content)
        parts.append("\n---\n\n")

        if health_report:
            parts.append(self._build_health_section(health_report, degrade_threshold))
            parts.append("\n---\n\n")

        parts.append(FOOTER_TEMPLATE.format(date_str=date_str))
        return "".join(parts)

    def compose_weekly_feishu_card(self, weekly_content: str,
                                   health_report: Optional[list[FeedHealth]] = None,
                                   degrade_threshold: int = 3) -> dict:
        markdown = self.compose_weekly(weekly_content, health_report, degrade_threshold)
        date_str = self._format_date()
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"🏆 每周跨界精选 · {date_str}"},
                    "template": "blue",
                },
                "elements": [
                    {"tag": "markdown", "content": markdown},
                    {"tag": "hr"},
                    {"tag": "note", "elements": [{"tag": "plain_text", "content": "每周日推送 · 回顾本周知识旅程"}]},
                ],
            },
        }