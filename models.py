from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class FeedExtra(str, Enum):
    author = "author"
    comments = "comments"


class FeedConfig(BaseModel):
    url: str
    source: str
    summarize: bool = True
    days: int = 1
    extras: list[FeedExtra] = []


class CategoryConfig(BaseModel):
    name: str
    feeds: list[FeedConfig]


class Article(BaseModel):
    title: str
    url: str
    content: str
    published: datetime
    published_timestamp: float
    source: str
    category: str
    summarize: bool = True
    days: int = 1
    comments: str = ""
    author: str = ""


class FeedData(BaseModel):
    generated_at: datetime
    articles: list[Article]
    sources_order: list[str]
    categories_order: list[str] = []

    def articles_by_source(self) -> dict[str, list[Article]]:
        return {
            source: [a for a in self.articles if a.source == source]
            for source in self.sources_order
        }

    def articles_by_category(self) -> dict[str, dict[str, list[Article]]]:
        source_to_category = {a.source: a.category for a in self.articles}
        result: dict[str, dict[str, list[Article]]] = {cat: {} for cat in self.categories_order}
        for source in self.sources_order:
            cat = source_to_category.get(source, "")
            if cat not in result:
                result[cat] = {}
            result[cat][source] = [a for a in self.articles if a.source == source]
        return result


class BulletReference(BaseModel):
    number: int
    url: str
    title: str
    source: str


class Bullet(BaseModel):
    title: str
    text: str
    references: list[BulletReference]


class SummaryData(BaseModel):
    generated_at: datetime
    categories: dict[str, list[Bullet]]
