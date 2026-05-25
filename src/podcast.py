import asyncio
import json
import logging
import os
import subprocess
from typing import Optional

from .ai_summarizer import SummarizedArticle

logger = logging.getLogger(__name__)

PODCAST_SCRIPT_PROMPT = """你是一位播客主持人，风格轻松有趣，像在和朋友聊天。

请把以下 3 篇跨界知识短文改写成一段 5 分钟的播客脚本。

要求：
1. 开头有简短的"欢迎收听今天的跨界灵感"
2. 每篇文章用"接下来我们来聊聊..."自然过渡
3. 口语化，多用"你知道吗""你想想看""这就有意思了"这类口语
4. 结尾用"明天见"收束
5. 总字数 800-1000 字（大约 5 分钟朗读时间）

输出纯文本，不要 Markdown 标记。"""


class PodcastGenerator:
    def __init__(self, ai_summarizer, output_dir: str = "site/audio"):
        self.ai_summarizer = ai_summarizer
        self.output_dir = output_dir

    async def generate_script(self, summarized: list[SummarizedArticle]) -> str:
        articles_text = "\n\n".join([
            f"[{item.domain_icon} {item.domain_name}]\n{item.chinese_summary}"
            for item in summarized
        ])

        user_prompt = f"以下是今天的 3 篇文章：\n\n{articles_text}\n\n请改写成播客脚本。"

        try:
            script = await self.ai_summarizer._call_ai(
                PODCAST_SCRIPT_PROMPT, user_prompt, max_tokens=1500
            )
            return script
        except Exception as e:
            logger.error(f"Podcast script generation failed: {e}")
            return ""

    async def generate_audio(self, script: str,
                             voice: str = "zh-CN-YunxiNeural",
                             output_filename: str = "daily.mp3") -> Optional[str]:
        os.makedirs(self.output_dir, exist_ok=True)
        output_path = os.path.join(self.output_dir, output_filename)

        try:
            proc = await asyncio.create_subprocess_exec(
                "edge-tts",
                "--voice", voice,
                "--text", script,
                "--write-media", output_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode == 0:
                logger.info(f"Podcast audio generated: {output_path}")
                return output_path
            else:
                logger.warning(f"edge-tts failed: {stderr.decode()}")
                return None
        except FileNotFoundError:
            logger.warning("edge-tts not installed, skipping audio generation")
            return None

    async def generate(self, summarized: list[SummarizedArticle],
                       date_str: str = "") -> Optional[str]:
        script = await self.generate_script(summarized)
        if not script:
            return None

        script_path = os.path.join(self.output_dir, "script.txt")
        os.makedirs(self.output_dir, exist_ok=True)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script)

        filename = f"podcast_{date_str.replace(' ', '_')}.mp3" if date_str else "daily.mp3"
        audio_path = await self.generate_audio(script, output_filename=filename)
        return audio_path