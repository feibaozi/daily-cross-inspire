import logging
from typing import Optional

from .preference import PreferenceEngine
from .ai_summarizer import AISummarizer

logger = logging.getLogger(__name__)

READING_PROFILE_PROMPT = """你是一位知识分析师，根据用户的阅读偏好数据，生成一份个人知识画像。

用户数据：
- 总互动次数：{total_interactions}
- 本周互动：{weekly_interactions}
- 最喜欢的领域：{top_domains}
- 经常跳过的领域：{skipped_domains}

请生成以下内容：
1. **你的知识DNA**（100字）：用比喻描述用户的阅读风格（如"你是一个在知识海洋中偏爱深海区域的探险家"）
2. **隐藏兴趣发现**（80字）：基于跳过模式，推测用户可能没意识到自己会感兴趣的领域
3. **下周推荐方向**（80字）：推荐 1-2 个邻近领域，说明为什么用户可能喜欢

风格：温暖、有洞察力、像朋友在聊天。用 Markdown 格式。"""

NEARBY_DOMAIN_MAP = {
    "量子物理": ["材料科学", "密码学", "认知神经科学"],
    "中世纪欧洲史": ["古代哲学", "考古学", "语言学"],
    "前卫建筑设计": ["材料科学", "城市人类学", "前卫艺术"],
    "认知神经科学": ["语言学", "演化生物学", "量子物理"],
    "海洋生物学": ["演化生物学", "气候科学", "古生物学"],
    "古代哲学": ["中世纪欧洲史", "语言学", "认知神经科学"],
    "演化生物学": ["海洋生物学", "古生物学", "认知神经科学"],
    "材料科学": ["量子物理", "前卫建筑设计", "机器人学"],
    "气候科学": ["海洋生物学", "古生物学", "天文学"],
    "语言学": ["认知神经科学", "古代哲学", "中世纪欧洲史"],
    "天文学": ["量子物理", "气候科学", "古生物学"],
    "考古学": ["中世纪欧洲史", "古生物学", "古代哲学"],
    "机器人学": ["材料科学", "认知神经科学", "量子物理"],
    "古生物学": ["演化生物学", "考古学", "气候科学"],
    "音乐学": ["认知神经科学", "语言学", "古代哲学"],
}


class ReadingProfiler:
    def __init__(self, preference_engine: PreferenceEngine,
                 ai_summarizer: Optional[AISummarizer] = None):
        self.preference_engine = preference_engine
        self.ai_summarizer = ai_summarizer

    def get_nearby_recommendations(self, top_domains: list[str]) -> list[str]:
        nearby = {}
        for domain in top_domains:
            for candidate in NEARBY_DOMAIN_MAP.get(domain, []):
                nearby[candidate] = nearby.get(candidate, 0) + 1

        sorted_nearby = sorted(nearby.items(), key=lambda x: x[1], reverse=True)
        return [d for d, _ in sorted_nearby[:3]]

    async def generate_profile(self) -> str:
        profile = self.preference_engine.get_reading_profile()

        if profile["total_interactions"] < 3:
            return "## 🧭 你的知识画像\n\n> 数据积累中...再读几天就能生成你的专属画像了！\n"

        top_names = [d["name"] for d in profile["top_domains"][:3]]
        skip_names = [d["name"] for d in profile["skipped_domains"][:3]]

        if not self.ai_summarizer:
            return self._generate_static_profile(profile, top_names, skip_names)

        user_prompt = READING_PROFILE_PROMPT.format(
            total_interactions=profile["total_interactions"],
            weekly_interactions=profile["weekly_interactions"],
            top_domains="、".join(top_names),
            skipped_domains="、".join(skip_names),
        )

        try:
            content = await self.ai_summarizer._call_ai(
                READING_PROFILE_PROMPT.split("\n")[0],
                user_prompt,
                max_tokens=600,
            )
            return content
        except Exception as e:
            logger.warning(f"AI profile generation failed: {e}")
            return self._generate_static_profile(profile, top_names, skip_names)

    def _generate_static_profile(self, profile: dict,
                                 top_names: list[str],
                                 skip_names: list[str]) -> str:
        recommendations = self.get_nearby_recommendations(top_names)

        parts = ["## 🧭 你的知识画像\n"]

        if top_names:
            parts.append(f"**你最喜欢的领域**：{'、'.join(top_names)}\n")

        if skip_names:
            parts.append(f"**你经常跳过的领域**：{'、'.join(skip_names)}\n")

        if recommendations:
            parts.append(f"**下周推荐探索**：{'、'.join(recommendations)}\n")
            parts.append("> 这些领域和你喜欢的领域有深层关联，你可能会惊喜！\n")

        parts.append(f"\n*累计互动 {profile['total_interactions']} 次 · 本周 {profile['weekly_interactions']} 次*\n")

        return "\n".join(parts)