import asyncio
import logging
import os
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.collector import RSSCollector
from src.selector import DomainSelector
from src.ai_summarizer import AISummarizer
from src.composer import Composer
from src.pusher import FeishuPusher, DingTalkPusher, EmailPusher

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


def _resolve_env(value: str) -> str:
    pattern = re.compile(r"\$\{(\w+)\}")
    matches = pattern.findall(value)
    for var in matches:
        env_val = os.environ.get(var, "")
        if not env_val:
            logger.warning(f"Environment variable {var} is not set")
        value = value.replace(f"${{{var}}}", env_val)
    return value


def load_config() -> tuple[dict, dict]:
    base = Path(__file__).resolve().parent
    sources_path = base / "config" / "sources.yaml"
    settings_path = base / "config" / "settings.yaml"

    with open(sources_path, "r", encoding="utf-8") as f:
        sources = yaml.safe_load(f)

    with open(settings_path, "r", encoding="utf-8") as f:
        raw = f.read()
    for var_name in re.findall(r"\$\{(\w+)\}", raw):
        raw = raw.replace(f"${{{var_name}}}", os.environ.get(var_name, ""))
    settings = yaml.safe_load(raw)

    return sources, settings


async def run():
    logger.info("=" * 50)
    logger.info("DailyCrossInspire - 每日跨界灵感早报")
    logger.info("=" * 50)

    sources, settings = load_config()
    domains_config = sources["domains"]
    ai_config = settings["ai"]
    collection_config = settings["collection"]
    push_config = settings["push"]
    schedule_config = settings["schedule"]
    cache_config = settings["cache"]

    logger.info(f"Loaded {len(domains_config)} domains from config")

    collector = RSSCollector(
        config=collection_config,
        cache_db_path=cache_config["db_path"],
    )
    domains = await collector.collect_all(domains_config)

    domains_with_articles = [d for d in domains if d.articles]
    if not domains_with_articles:
        logger.error("No articles collected from any domain. Aborting.")
        return

    logger.info(f"{len(domains_with_articles)} domains have new articles")

    selector = DomainSelector(select_count=collection_config["select_count"])
    picks = selector.select(domains_with_articles)

    if not picks:
        logger.error("No articles selected. Aborting.")
        return

    logger.info(f"Summarizing {len(picks)} articles via AI...")
    summarizer = AISummarizer(
        api_base=ai_config["api_base"],
        api_key=ai_config["api_key"],
        model=ai_config.get("model", "deepseek-chat"),
        max_tokens=ai_config.get("max_tokens", 800),
        temperature=ai_config.get("temperature", 0.8),
    )
    summarized = await summarizer.summarize_batch(picks)

    composer = Composer(timezone=schedule_config.get("timezone", "Asia/Shanghai"))
    markdown = composer.compose(summarized)

    logger.info("Generated markdown report:\n")
    print(markdown)
    print()

    push_results = []

    if push_config.get("feishu", {}).get("enabled"):
        webhook = push_config["feishu"]["webhook_url"]
        if webhook:
            logger.info("Pushing to Feishu...")
            card = composer.compose_feishu_card(summarized)
            pusher = FeishuPusher(webhook_url=webhook)
            ok = await pusher.push(card)
            push_results.append(("飞书", ok))

    if push_config.get("dingtalk", {}).get("enabled"):
        webhook = push_config["dingtalk"]["webhook_url"]
        if webhook:
            logger.info("Pushing to DingTalk...")
            pusher = DingTalkPusher(webhook_url=webhook)
            ok = await pusher.push(markdown)
            push_results.append(("钉钉", ok))

    if push_config.get("email", {}).get("enabled"):
        email_cfg = push_config["email"]
        if all([email_cfg.get(k) for k in ["smtp_host", "sender", "password", "recipient"]]):
            logger.info("Pushing via email...")
            pusher = EmailPusher(
                smtp_host=email_cfg["smtp_host"],
                smtp_port=email_cfg.get("smtp_port", 587),
                sender=email_cfg["sender"],
                password=email_cfg["password"],
                recipient=email_cfg["recipient"],
            )
            ok = pusher.push(markdown)
            push_results.append(("邮件", ok))

    logger.info("=" * 50)
    if push_results:
        for channel, ok in push_results:
            status = "✅" if ok else "❌"
            logger.info(f"  {status} {channel}: {'成功' if ok else '失败'}")
    else:
        logger.info("  ℹ️ 未配置任何推送渠道，仅输出到控制台")
    logger.info("=" * 50)


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()