import asyncio
import json
from datetime import datetime, timezone

import litellm

from models import Bullet, BulletReference, FeedData, SummaryData

RESPONSE_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "category_id": {
                "type": "integer",
                "description": "The numeric ID assigned to this category in the input.",
            },
            "category": {
                "type": "string",
                "description": "Category name using plain Unicode characters, no HTML entities.",
            },
            "bullets": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Short title (at most 2 words) using plain Unicode characters, no HTML entities (e.g. ü not &uuml;).",
                        },
                        "text": {
                            "type": "string",
                            "description": "Clean description using plain Unicode characters, no HTML entities (e.g. ü not &uuml;), no inline citation brackets like [1].",
                        },
                        "references": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "List of referenced article numbers.",
                        },
                    },
                    "required": ["title", "text", "references"],
                },
            },
        },
        "required": ["category_id", "category", "bullets"],
    },
}


def _build_prompt(
    base_prompt: str, feed_data: FeedData, category_names: list[str], max_items: int = 5, language: str = "English"
) -> tuple[str, dict[int, dict]]:
    prompt = base_prompt.replace("{max_items}", str(max_items)).replace("{language}", language)
    article_number = 1
    article_mapping: dict[int, dict] = {}

    by_category: dict[str, list] = {}
    for article in feed_data.articles:
        if not article.summarize:
            continue
        by_category.setdefault(article.category, []).append(article)

    for category_id, category in enumerate(category_names, start=1):
        articles = by_category.get(category, [])
        if not articles:
            continue
        prompt += f"\n## {category} [id:{category_id}]\n\n"
        for article in articles:
            prompt += f"[{article_number}] **{article.title}** ({article.source})\n"
            content = article.content.strip()
            if content:
                prompt += (content[:1000] + "...") if len(content) > 1000 else content
                prompt += "\n"
            prompt += "\n"
            article_mapping[article_number] = {
                "url": article.url,
                "title": article.title,
                "source": article.source,
            }
            article_number += 1

    return prompt, article_mapping


def _generate_sync(prompt: str, model: str) -> str:
    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "summary",
                "schema": RESPONSE_SCHEMA,
            },
        },
    )
    return response.choices[0].message.content


async def summarize(
    feed_data: FeedData, category_names: list[str], prompt_text: str, model: str, max_items_per_category: int = 5, language: str = "English"
) -> SummaryData:
    prompt, article_mapping = _build_prompt(prompt_text, feed_data, category_names, max_items=max_items_per_category, language=language)

    raw = await asyncio.to_thread(_generate_sync, prompt, model)

    summary_array = json.loads(raw)
    summary_array.sort(key=lambda item: item.get("category_id", 0))

    categories: dict[str, list[Bullet]] = {}
    for item in summary_array:
        bullets = []
        for b in item.get("bullets", []):
            refs = sorted(
                [
                    BulletReference(number=n, **article_mapping[n])
                    for n in b.get("references", [])
                    if n in article_mapping
                ],
                key=lambda r: r.source,
            )
            bullets.append(Bullet(title=b["title"], text=b["text"], references=refs))
        categories[item["category"]] = bullets[:max_items_per_category]

    return SummaryData(
        generated_at=datetime.now(timezone.utc),
        categories=categories,
    )
