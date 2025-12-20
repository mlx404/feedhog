import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.requests import Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config import load_config, load_prompt
from fetcher import fetch_all
from state import state
from summarizer import summarize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=HERE / "templates")
config = load_config()


async def refresh() -> None:
    logger.info("Starting feed refresh...")
    try:
        categories = config.categories
        if not categories:
            logger.warning("No categories configured in config.yaml")
            return

        prompt = load_prompt()
        feed_data = await fetch_all(categories)
        state.feeds = feed_data
        total_feeds = sum(len(c.feeds) for c in categories)
        logger.info(f"Fetched {len(feed_data.articles)} articles from {total_feeds} feeds")

        summary_data = await summarize(
            feed_data, [cat.name for cat in categories], prompt, config.model,
            max_items_per_category=config.summary_items_per_category,
            language=config.language,
        )
        state.summaries = summary_data
        logger.info("Summaries generated")

    except Exception:
        logger.exception("Feed refresh failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(refresh, "interval", hours=config.refresh_interval_hours)
    scheduler.start()
    asyncio.create_task(refresh())
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "feeds": state.feeds,
            "summaries": state.summaries,
        },
    )
