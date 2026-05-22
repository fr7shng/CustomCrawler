"""Juejin (掘金) scraper."""

import logging
from typing import List
from datetime import datetime

import requests

from .base import BaseSource
from .models import UnifiedProject
from . import register_source
from config.config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


@register_source("juejin")
class JuejinSource(BaseSource):
    """Scrape hot articles from Juejin (Chinese tech community)."""

    def __init__(self, priority: int = 5):
        super().__init__("juejin", priority)
        # Juejin article rank API
        self.api_url = "https://api.juejin.cn/content_api/v1/content/article_rank"

    def scrape(self) -> List[UnifiedProject]:
        """
        Scrape hot articles from Juejin.

        Returns:
            List of UnifiedProject from Juejin hot list
        """
        projects = []

        try:
            # category_id: 1=all, 2=frontend, 3=backend, 4=Android, 5=iOS, 6=AI
            response = requests.get(
                self.api_url,
                params={"category_id": "1", "type": "hot"},
                headers={"Accept-Encoding": "gzip, deflate, br"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()
            # Handle response encoding
            response.encoding = "utf-8"
            data = response.json()

            if data.get("err_msg") == "success" and data.get("data"):
                for item in data["data"]:
                    project = self._parse_item(item)
                    if project:
                        projects.append(project)

        except requests.exceptions.RequestException as e:
            logger.error(f"Juejin API request failed: {e}")
        except Exception as e:
            logger.error(f"Failed to parse Juejin response: {e}")

        logger.info(f"Got {len(projects)} projects from Juejin")
        return projects

    def _parse_item(self, item: dict) -> UnifiedProject:
        """Parse Juejin article item to UnifiedProject."""
        try:
            content = item.get("content", {})
            counter = item.get("content_counter", {})

            return UnifiedProject(
                source=self.name,
                project_name=content.get("title", ""),
                project_url=f"https://juejin.cn/post/{content.get('content_id', '')}",
                description=content.get("brief", ""),
                author=item.get("author", {}).get("name", ""),
                stars=counter.get("hot_rank", 0) or counter.get("digg_count", 0),
                forks=counter.get("collect_count", 0),
                language="Chinese",
                category="hot",
                scraped_at=datetime.now(),
            )
        except Exception as e:
            logger.warning(f"Failed to parse Juejin item: {e}")
            return None
