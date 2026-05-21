from datetime import datetime
from .ai_summarizer import SummarizedArticle


HEADER_TEMPLATE = """# ☕ 每日跨界灵感早报

> 今天带你闯入 3 个完全陌生的世界 🌍
> {date_str}

---

"""

ARTICLE_TEMPLATE = """## {icon} {domain_name}

{chinese_summary}

---

"""

FOOTER_TEMPLATE = """📬 明天早上 8:00，继续探索新世界

---

*由 DailyCrossInspire 自动生成 · {date_str}*"""


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

    def compose(self, summarized: list[SummarizedArticle]) -> str:
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

        parts.append(FOOTER_TEMPLATE.format(date_str=date_str))
        return "".join(parts)

    def compose_feishu_card(self, summarized: list[SummarizedArticle]) -> dict:
        markdown = self.compose(summarized)
        date_str = self._format_date()
        return {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": f"☕ 每日跨界灵感 · {date_str}"},
                    "template": "blue",
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": markdown,
                    },
                    {
                        "tag": "hr",
                    },
                    {
                        "tag": "note",
                        "elements": [
                            {
                                "tag": "plain_text",
                                "content": "自动生成 · 每天早8:00推送",
                            }
                        ],
                    },
                ],
            },
        }