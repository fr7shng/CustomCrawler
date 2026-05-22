"""Custom Crawler API scraper (third-party API)."""

import logging
from typing import List
from datetime import datetime

import requests

from .base import BaseSource
from .models import UnifiedProject
from . import register_source
from config.config import REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


@register_source("github_trending_api")
class GitHubTrendingAPISource(BaseSource):
    """Scrape via Custom Crawler API (third-party)."""

    def __init__(self, priority: int = 2):
        super().__init__("github_trending_api", priority)
        self.api_url = "https://github-trending-api.onrender.com"

    def scrape(self) -> List[UnifiedProject]:
        """
        Scrape Custom Crawler via third-party API.

        Returns:
            List of UnifiedProject from API
        """
        projects = []

        try:
            response = requests.get(
                f"{self.api_url}/repositories", timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()

            if isinstance(data, list):
                for item in data:
                    projects.append(self._parse_item(item))

        except requests.exceptions.RequestException as e:
            logger.error(f"Custom Crawler API request failed: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to parse Custom Crawler API response: {e}")
            raise

        return projects

    def _parse_item(self, item: dict) -> UnifiedProject:
        """Parse API response item to UnifiedProject."""
        return UnifiedProject(
            source=self.name,
            project_name=item.get("full_name", item.get("name", "")),
            project_url=item.get("html_url", ""),
            description=item.get("description", ""),
            author=item.get("owner", {}).get("login", "")
            if isinstance(item.get("owner"), dict)
            else "",
            stars=item.get("stargazers_count", 0),
            forks=item.get("forks_count", 0),
            language=item.get("language", ""),
            category="trending",
            scraped_at=datetime.now(),
        )
