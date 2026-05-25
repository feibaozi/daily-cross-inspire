import logging
from typing import Optional

from .ai_summarizer import AISummarizer, SummarizedArticle

logger = logging.getLogger(__name__)

DEEP_DIVE_PROMPT = """你是一位博学的知识导师，用户对某篇文章产生了浓厚兴趣，想要深入了解。

请基于这篇文章的内容，生成一份深度解读：

1. **背景知识**（200字）：这个领域为什么研究这个问题？历史上有什么关键转折？
2. **核心原理**（200字）：用最通俗的语言解释核心机制，就像在教一个聪明的门外汉
3. **未来影响**（150字）：这个发现/技术未来 5-10 年可能怎么改变我们的生活？
4. **延伸阅读建议**：推荐 2-3 个相关关键词，用户可以自行搜索了解更多

风格：深度但不枯燥，像一个充满热情的大学教授在办公室和你一对一聊天。用 Markdown。"""

TAGGING_PROMPT = """你是一个知识分类专家。请为以下文章摘要生成 3 个标签。

标签要求：
- 每个标签 2-4 个字
- 从不同维度分类（如：方法论、应用场景、基础理论、跨领域概念）
- 优先选择能体现"跨界性"的标签

输出格式：只输出 3 个标签，用逗号分隔，不要其他内容。
例如：复杂系统,涌现现象,网络理论"""


class DeepDiveGenerator:
    def __init__(self, ai_summarizer: AISummarizer):
        self.ai_summarizer = ai_summarizer

    async def generate(self, article: SummarizedArticle) -> str:
        user_prompt = f"""领域：{article.domain_name}
标题：{article.article.title}
摘要：{article.chinese_summary}

请生成深度解读。"""

        try:
            content = await self.ai_summarizer._call_ai(
                DEEP_DIVE_PROMPT, user_prompt, max_tokens=1000
            )
            return content
        except Exception as e:
            logger.error(f"Deep dive generation failed: {e}")
            return ""

    async def generate_batch(self, summarized: list[SummarizedArticle]) -> list[str]:
        import asyncio
        tasks = [self.generate(item) for item in summarized]
        return await asyncio.gather(*tasks)


class AutoTagger:
    def __init__(self, ai_summarizer: AISummarizer):
        self.ai_summarizer = ai_summarizer

    async def tag(self, article: SummarizedArticle) -> list[str]:
        user_prompt = f"""领域：{article.domain_name}
标题：{article.article.title}
摘要：{article.chinese_summary[:500]}

请生成 3 个标签。"""

        try:
            content = await self.ai_summarizer._call_ai(
                TAGGING_PROMPT, user_prompt, max_tokens=50
            )
            tags = [t.strip() for t in content.split(",") if t.strip()]
            return tags[:3]
        except Exception as e:
            logger.error(f"Auto-tagging failed: {e}")
            return []

    async def tag_batch(self, summarized: list[SummarizedArticle]) -> list[list[str]]:
        import asyncio
        tasks = [self.tag(item) for item in summarized]
        return await asyncio.gather(*tasks)