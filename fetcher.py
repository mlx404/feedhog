import asyncio
import html
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Optional

import fastfeedparser as ffp

from models import Article, CategoryConfig, FeedConfig, FeedData, FeedExtra


def _strip_html(text: str) -> str:
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _parse_date(entry) -> Optional[datetime]:
    for field in ["published_parsed", "updated_parsed", "created_parsed"]:
        if hasattr(entry, field) and getattr(entry, field):
            time_struct = getattr(entry, field)
            return datetime(*time_struct[:6], tzinfo=timezone.utc)

    for field in ["published", "updated", "created"]:
        if hasattr(entry, field) and getattr(entry, field):
            try:
                date_str = getattr(entry, field)
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                continue

    return None


def _fetch_feed_sync(feed: FeedConfig, category: str, now: datetime) -> list[Article]:
    articles = []
    cutoff = now - timedelta(days=feed.days)

    try:
        parsed = ffp.parse(feed.url)

        if not hasattr(parsed, "entries"):
            print(f"Warning: no entries in {feed.source}", file=sys.stderr)
            return articles

        for entry in parsed.entries:
            published = _parse_date(entry)
            if not published or published < cutoff:
                continue

            content = ""
            if hasattr(entry, "content") and entry.content:
                content = (
                    entry.content[0].get("value", "")
                    if isinstance(entry.content, list)
                    else str(entry.content)
                )
            elif hasattr(entry, "summary") and entry.summary:
                content = entry.summary
            elif hasattr(entry, "description") and entry.description:
                content = entry.description
            content = _strip_html(content)

            articles.append(
                Article(
                    title=entry.get("title", "Untitled"),
                    url=entry.get("link", ""),
                    content=content,
                    published=published,
                    published_timestamp=published.timestamp(),
                    source=feed.source,
                    category=category,
                    summarize=feed.summarize,
                    days=feed.days,
                    comments=entry.get("comments", "") or "" if FeedExtra.comments in feed.extras else "",
                    author=entry.get("author", "") or "" if FeedExtra.author in feed.extras else "",
                )
            )

        print(f"✓ {feed.source}: {len(articles)} articles")

    except Exception as e:
        print(f"✗ {feed.source}: {e}", file=sys.stderr)

    return articles


async def fetch_all(categories: list[CategoryConfig]) -> FeedData:
    now = datetime.now(timezone.utc)

    tasks = [
        asyncio.to_thread(_fetch_feed_sync, feed, cat.name, now)
        for cat in categories
        for feed in cat.feeds
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    articles = []
    for result in results:
        if isinstance(result, Exception):
            print(f"Feed fetch error: {result}", file=sys.stderr)
        else:
            articles.extend(result)

    articles.sort(key=lambda a: a.published_timestamp, reverse=True)

    return FeedData(
        generated_at=now,
        articles=articles,
        sources_order=[feed.source for cat in categories for feed in cat.feeds],
        categories_order=[cat.name for cat in categories],
    )
