from dataclasses import dataclass

from models import FeedData, SummaryData


@dataclass
class AppState:
    feeds: FeedData | None = None
    summaries: SummaryData | None = None


state = AppState()
