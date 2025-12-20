from pathlib import Path

import yaml
from pydantic import BaseModel
from models import CategoryConfig


class AppConfig(BaseModel):
    refresh_interval_hours: int = 3
    summary_items_per_category: int = 5
    language: str = "English"
    model: str
    categories: list[CategoryConfig] = []


def load_config(path: Path = Path("config.yaml")) -> AppConfig:
    with open(path) as f:
        data = yaml.safe_load(f)
    return AppConfig(**(data or {}))


def load_prompt(path: Path = Path("prompt.txt")) -> str:
    return path.read_text(encoding="utf-8")
