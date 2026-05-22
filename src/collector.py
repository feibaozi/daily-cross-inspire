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
class FeedHealth:
    feed_url: str
    domain_name: str
    consecutive_failures: int
    total_fetches: int
    total_failures: int
    last_success: Optional[str]
    degraded: bool


@dataclass
class Domain:
    name: str
    feeds: list[str]
    weight: int
    icon: str = ""
    articles: list[Article] = field(default_factory=list)


class RSSCollector:
    def __init__(self, config: dict, cache_db_path: str = "data/cache.db",
                 degrade_threshold: int = 3):
        self.timeout = config.get("request_timeout", 15)
        self.max_per_feed = config.get("max_articles_per_feed", 5)
        self.min_length = config.get("min_article_length", 200)
        self.user_agent = config.get("user_agent", "DailyCrossInspire/1.0")
        self.lookback_days = config.get("lookback_days", 7)
        self.cache_db_path = cache_db_path
        self.degrade_threshold = degrade_threshold
        self._seen_urls: set[str] = set()
        self._feed_statuses: dict[str, bool] = {}
        self._feed_article_counts: dict[str, int] = {}
        self._load_seen_urls()
        self._init_health_db()

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

    def _init_health_db(self):
        import sqlite3
        import os

        os.makedirs(os.path.dirname(self.cache_db_path), exist_ok=True)
        conn = sqlite3.connect(self.cache_db_path)
        conn.execute(
            """CREATE TABLE IF NOT EXISTS feed_health (
                feed_url TEXT PRIMARY KEY,
                domain_name TEXT NOT NULL,
                consecutive_failures INTEGER DEFAULT 0,
                total_fetches INTEGER DEFAULT 0,
                total_failures INTEGER DEFAULT 0,
                last_success TEXT,
                last_check TEXT,
                degraded INTEGER DEFAULT 0
            )"""
        )
        conn.close()

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

    def _record_feed_status(self, feed_url: str, domain_name: str,
                            success: bool, article_count: int = 0):
        import sqlite3

        conn = sqlite3.connect(self.cache_db_path)
        now = datetime.now().isoformat()

        existing = conn.execute(
            "SELECT consecutive_failures, total_fetches, total_failures FROM feed_health WHERE feed_url = ?",
            (feed_url,)
        ).fetchone()

        if existing is None:
            if success:
                conn.execute(
                    "INSERT INTO feed_health (feed_url, domain_name, consecutive_failures, total_fetches, total_failures, last_success, last_check, degraded) VALUES (?, ?, 0, 1, 0, ?, ?, 0)",
                    (feed_url, domain_name, now, now)
                )
            else:
                conn.execute(
                    "INSERT INTO feed_health (feed_url, domain_name, consecutive_failures, total_fetches, total_failures, last_check, degraded) VALUES (?, ?, 1, 1, 1, ?, 0)",
                    (feed_url, domain_name, now)
                )
        else:
            cons_fails, total_fetches, total_fails = existing
            total_fetches += 1
            if success:
                cons_fails = 0
                degraded = 0
                conn.execute(
                    "UPDATE feed_health SET consecutive_failures=0, total_fetches=?, total_failures=?, last_success=?, last_check=?, degraded=0 WHERE feed_url=?",
                    (total_fetches, total_fails, now, now, feed_url)
                )
            else:
                cons_fails += 1
                total_fails += 1
                degraded = 1 if cons_fails >= self.degrade_threshold else 0
                conn.execute(
                    "UPDATE feed_health SET consecutive_failures=?, total_fetches=?, total_failures=?, last_check=?, degraded=? WHERE feed_url=?",
                    (cons_fails, total_fetches, total_fails, now, degraded, feed_url)
                )

        conn.commit()
        conn.close()

    def get_health_report(self) -> list[FeedHealth]:
        import sqlite3

        conn = sqlite3.connect(self.cache_db_path)
        rows = conn.execute(
            "SELECT feed_url, domain_name, consecutive_failures, total_fetches, total_failures, last_success, degraded FROM feed_health ORDER BY degraded DESC, consecutive_failures DESC"
        ).fetchall()
        conn.close()

        report = []
        for row in rows:
            report.append(FeedHealth(
                feed_url=row[0],
                domain_name=row[1],
                consecutive_failures=row[2],
                total_fetches=row[3],
                total_failures=row[4],
                last_success=row[5],
                degraded=bool(row[6]),
            ))
        return report

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
            self._feed_statuses[feed_url] = True
            self._feed_article_counts[feed_url] = len(articles)
            return articles
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP {e.response.status_code} from {feed_url}")
            self._feed_statuses[feed_url] = False
            self._feed_article_counts[feed_url] = 0
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch {feed_url}: {e}")
            self._feed_statuses[feed_url] = False
            self._feed_article_counts[feed_url] = 0
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
            status = self._feed_statuses.get(feed_url, False)
            count = self._feed_article_counts.get(feed_url, 0)
            self._record_feed_status(feed_url, domain_obj.name, status, count)

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
        self._feed_statuses.clear()
        self._feed_article_counts.clear()

        tasks = [self.collect_from_domain(d) for d in domains_config]
        domains = await asyncio.gather(*tasks)
        total = sum(len(d.articles) for d in domains)
        logger.info(f"Collection complete: {total} total articles from {len(domains)} domains")
        self._cleanup_old_cache()
        return list(domains)