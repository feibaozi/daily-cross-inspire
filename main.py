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
from src.weekly import WeeklyCollector, WeeklyAISummarizer, is_sunday
from src.on_this_day import fetch_on_this_day

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")


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


def archive_articles(summarized, cache_db_path):
    weekly_collector = WeeklyCollector(cache_db_path=cache_db_path)
    for item in summarized:
        weekly_collector.archive_article(
            domain_name=item.domain_name,
            domain_icon=item.domain_icon,
            title=item.article.title,
            url=item.article.url,
            chinese_summary=item.chinese_summary,
        )
    logger.info(f"Archived {len(summarized)} articles for weekly review")


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

    timezone = schedule_config.get("timezone", "Asia/Shanghai")
    degrade_threshold = collection_config.get("degrade_threshold", 3)

    collector = RSSCollector(
        config=collection_config,
        cache_db_path=cache_config["db_path"],
        degrade_threshold=degrade_threshold,
    )

    if is_sunday(timezone):
        await run_weekly(settings, push_config, degrade_threshold)
        return

    logger.info(f"Loaded {len(domains_config)} domains from config")
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

    archive_articles(summarized, cache_config["db_path"])

    cross_connection = await summarizer.generate_cross_connection(picks)
    logger.info(f"Cross-connection: {cross_connection[:80]}...")

    on_this_day = await fetch_on_this_day()
    if on_this_day:
        cross_connection = (cross_connection or "") + "\n" + on_this_day

    health_report = collector.get_health_report()
    if health_report:
        degraded_count = sum(1 for h in health_report if h.degraded)
        logger.info(f"Health report: {len(health_report)} feeds tracked, {degraded_count} degraded")

    composer = Composer(timezone=timezone)
    markdown = composer.compose(summarized, health_report, degrade_threshold, cross_connection)

    logger.info("Generated markdown report:\n")
    print(markdown)
    print()

    await do_push(push_config, composer, markdown, summarized, health_report, degrade_threshold)


async def run_weekly(settings, push_config, degrade_threshold):
    logger.info("Sunday detected - generating weekly highlight instead of daily report")

    ai_config = settings["ai"]
    cache_config = settings["cache"]
    schedule_config = settings["schedule"]
    timezone = schedule_config.get("timezone", "Asia/Shanghai")

    weekly_collector = WeeklyCollector(cache_db_path=cache_config["db_path"])
    week_articles = weekly_collector.get_week_articles()

    if not week_articles:
        logger.error("No archived articles for weekly review. Aborting.")
        return

    logger.info(f"Found {len(week_articles)} articles from this week")

    weekly_summarizer = WeeklyAISummarizer(
        api_base=ai_config["api_base"],
        api_key=ai_config["api_key"],
        model=ai_config.get("model", "deepseek-chat"),
        max_tokens=1500,
        temperature=0.8,
    )
    weekly_content = await weekly_summarizer.generate_weekly(week_articles)

    composer = Composer(timezone=timezone)
    markdown = composer.compose_weekly(weekly_content, degrade_threshold=degrade_threshold)

    logger.info("Generated weekly highlight:\n")
    print(markdown)
    print()

    if push_config.get("feishu", {}).get("enabled"):
        webhook = push_config["feishu"]["webhook_url"]
        if webhook:
            logger.info("Pushing weekly to Feishu...")
            card = composer.compose_weekly_feishu_card(weekly_content, degrade_threshold=degrade_threshold)
            pusher = FeishuPusher(webhook_url=webhook)
            ok = await pusher.push(card)
            logger.info(f"  {'✅' if ok else '❌'} 飞书: {'成功' if ok else '失败'}")

    logger.info("=" * 50)
    logger.info("Weekly highlight completed!")
    logger.info("=" * 50)


async def do_push(push_config, composer, markdown, summarized, health_report, degrade_threshold):
    push_results = []

    if push_config.get("feishu", {}).get("enabled"):
        webhook = push_config["feishu"]["webhook_url"]
        if webhook:
            logger.info("Pushing to Feishu...")
            card = composer.compose_feishu_card(summarized, health_report, degrade_threshold)
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