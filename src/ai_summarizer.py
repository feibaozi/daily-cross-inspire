from dataclasses import dataclass

from .collector import Article

SYSTEM_PROMPT = """你是一个博学的知识翻译官，擅长将任何领域的专业知识转化为通俗易懂的中文科普短文。

你的任务：
1. 阅读给定的文章标题和摘要，理解其核心内容
2. 用通俗易懂的中文总结核心发现/观点（300字以内）
3. 补充一个"为什么这很重要"的小段落（80字以内）
4. 用一个生活化的比喻或类比帮助读者理解
5. 结尾留一个引人深思的开放式问题

风格要求：
- 像在跟朋友喝咖啡聊天，口语化但不失严谨
- 如果涉及专业术语，用括号标注英文原文
- 语气充满好奇心，让读者感觉到"发现新大陆"的兴奋
- 不要使用"根据文章""研究表明"等机械表述，直接讲故事

输出格式：用 Markdown，不要包含代码块标记。"""

USER_PROMPT_TEMPLATE = """领域：{domain_name}
标题：{title}
原文摘要：{summary}

请按照上述风格，生成一篇早报短文。直接输出 Markdown 格式的内容："""


@dataclass
class SummarizedArticle:
    article: Article
    chinese_summary: str

    @property
    def domain_icon(self) -> str:
        return self.article.domain_icon

    @property
    def domain_name(self) -> str:
        return self.article.domain_name


class AISummarizer:
    def __init__(self, api_base: str, api_key: str, model: str = "deepseek-chat",
                 max_tokens: int = 800, temperature: float = 0.8):
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def summarize(self, article: Article) -> SummarizedArticle:
        import httpx

        user_prompt = USER_PROMPT_TEMPLATE.format(
            domain_name=article.domain_name,
            title=article.title,
            summary=article.clean_summary,
        )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        async with httpx.AsyncClient(timeout=60) as client:
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

        content = data["choices"][0]["message"]["content"].strip()
        return SummarizedArticle(article=article, chinese_summary=content)

    async def summarize_batch(self, picks: list) -> list[SummarizedArticle]:
        import asyncio

        tasks = []
        for domain, article in picks:
            tasks.append(self.summarize(article))

        results = await asyncio.gather(*tasks)
        return list(results)