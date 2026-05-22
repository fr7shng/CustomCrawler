"""HackerNews scraper."""

import logging
from typing import List
from datetime import datetime

import requests

from .base import BaseSource
from .models import UnifiedProject
from . import register_source
from config.config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


@register_source("hackernews")
class HackerNewsSource(BaseSource):
    """Scrape HackerNews top stories via Firebase API."""

    def __init__(self, priority: int = 3):
        super().__init__("hackernews", priority)
        self.api_url = "https://hacker-news.firebaseio.com/v0"
        self.top_count = 30

    def scrape(self) -> List[UnifiedProject]:
        """
        Scrape top stories from HackerNews.

        Returns:
            List of UnifiedProject from HackerNews
        """
        projects = []

        try:
            response = requests.get(
                f"{self.api_url}/topstories.json", timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            story_ids = response.json()[: self.top_count]

            for story_id in story_ids:
                story = self._fetch_story(story_id)
                if story:
                    projects.append(story)

        except requests.exceptions.RequestException as e:
            logger.error(f"HackerNews request failed: {e}")
            raise

        return projects

    def _fetch_story(self, story_id: int) -> UnifiedProject:
        """Fetch a single HackerNews story."""
        try:
            response = requests.get(
                f"{self.api_url}/item/{story_id}.json", timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            if not data or data.get("type") != "story":
                return None

            # HN items: text is only for Ask HN, title is always present
            title = data.get("title", "")
            text = data.get("text", "")
            description = text if text else ""  # Use text if available, else empty

            return UnifiedProject(
                source=self.name,
                project_name=title,
                project_url=data.get(
                    "url", f"https://news.ycombinator.com/item?id={story_id}"
                ),
                description=description,
                author=data.get("by", ""),
                stars=data.get("score", 0),
                forks=0,
                language="English",
                category="hot",
                scraped_at=datetime.now(),
            )
        except Exception as e:
            logger.warning(f"Failed to fetch story {story_id}: {e}")
            return None
