import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Article:
    title: str
    url: str
    summary: str
    domain_name: str
    domain_icon: str
    domain_weight: int
    source_feed: str
    published: Optional[datetime] = None

    @property
    def clean_summary(self) -> str:
        text = BeautifulSoup(self.summary, "html.parser").get_text(separator=" ", strip=True)
        return text[:1500]

    @property
    def is_fresh(self) -> bool:
        if self.published is None:
            return True
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        if self.published.tzinfo is None:
            self.published = self.published.replace(tzinfo=timezone.utc)
        return self.published >= cutoff


@dataclass
class Domain:
    name: str
    feeds: list[str]
    weight: int
    icon: str = ""
    articles: list[Article] = field(default_factory=list)


class RSSCollector:
    def __init__(self, config: dict, cache_db_path: str = "data/cache.db"):
        self.timeout = config.get("request_timeout", 15)
        self.max_per_feed = config.get("max_articles_per_feed", 5)
        self.min_length = config.get("min_article_length", 200)
        self.user_agent = config.get("user_agent", "DailyCrossInspire/1.0")
        self.lookback_days = config.get("lookback_days", 7)
        self.cache_db_path = cache_db_path
        self._seen_urls: set[str] = set()
        self._load_seen_urls()

    def _load_seen_urls(self):
        import sqlite3
        import os

        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS seen_articles (url TEXT PRIMARY KEY, seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        )
        rows = conn.execute("SELECT url FROM seen_articles").fetchall()
        self._seen_urls = {row[0] for row in rows}
        conn.close()
        logger.info(f"Loaded {len(self._seen_urls)} cached URLs from history")

    def _mark_seen(self, url: str):
        import sqlite3

        self._seen_urls.add(url)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            "INSERT OR IGNORE INTO seen_articles (url) VALUES (?)", (url,)
        )
        conn.commit()
        conn.close()

    def _cleanup_old_cache(self):
        import sqlite3

        cutoff = (datetime.now() - timedelta(days=30)).isoformat()
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute("DELETE FROM seen_articles WHERE seen_at < ?", (cutoff,))
        conn.commit()
        conn.close()

    async def _fetch_feed(self, client: httpx.AsyncClient, feed_url: str) -> list[dict]:
        try:
            response = await client.get(feed_url, follow_redirects=True)
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            articles = []
            for entry in feed.entries[: self.max_per_feed]:
                title = entry.get("title", "").strip()
                url = entry.get("link", "").strip()
                if not title or not url or url in self._seen_urls:
                    continue
                summary = entry.get("summary", "") or entry.get("description", "") or ""
                if len(summary) < self.min_length:
                    continue
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                articles.append({
                    "title": title,
                    "url": url,
                    "summary": summary,
                    "published": published,
                })
            logger.debug(f"Fetched {len(articles)} new articles from {feed_url}")
            return articles
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} from {feed_url}")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch {feed_url}: {e}")
            return []

    async def collect_from_domain(self, domain: dict) -> Domain:
        domain_obj = Domain(
            name=domain["name"],
            feeds=domain["feeds"],
            weight=domain.get("weight", 5),
            icon=domain.get("icon", ""),
        )

        async with httpx.AsyncClient(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent},
            limits=httpx.Limits(max_connections=10),
        ) as client:
            tasks = [self._fetch_feed(client, feed_url) for feed_url in domain_obj.feeds]
            results = await asyncio.gather(*tasks)

        seen_in_batch: set[str] = set()
        for feed_url, entries in zip(domain_obj.feeds, results):
            for entry in entries:
                if entry["url"] in seen_in_batch:
                    continue
                seen_in_batch.add(entry["url"])
                article = Article(
                    title=entry["title"],
                    url=entry["url"],
                    summary=entry["summary"],
                    domain_name=domain_obj.name,
                    domain_icon=domain_obj.icon,
                    domain_weight=domain_obj.weight,
                    source_feed=feed_url,
                    published=entry.get("published"),
                )
                if article.is_fresh:
                    domain_obj.articles.append(article)
                    self._mark_seen(entry["url"])

        logger.info(
            f"[{domain_obj.icon} {domain_obj.name}] collected {len(domain_obj.articles)} articles"
        )
        return domain_obj

    async def collect_all(self, domains_config: list[dict]) -> list[Domain]:
        logger.info(f"Starting collection from {len(domains_config)} domains...")
        tasks = [self.collect_from_domain(d) for d in domains_config]
        domains = await asyncio.gather(*tasks)
        total = sum(len(d.articles) for d in domains)
        logger.info(f"Collection complete: {total} total articles from {len(domains)} domains")
        self._cleanup_old_cache()
        return list(domains)