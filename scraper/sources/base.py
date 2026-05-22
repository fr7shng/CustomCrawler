"""Base class for all data sources."""

from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from .models import UnifiedProject


class BaseSource(ABC):
    """Abstract base class for all data sources."""

    def __init__(self, name: str, priority: int = 10):
        """
        Initialize the source.

        Args:
            name: Source identifier (e.g., 'github', 'hackernews')
            priority: Lower number = higher priority (checked first)
        """
        self.name = name
        self.priority = priority

    @abstractmethod
    def scrape(self) -> List[UnifiedProject]:
        """
        Scrape projects from this source.

        Returns:
            List of UnifiedProject objects
        """
        pass

    def normalize(self, raw_data: dict) -> UnifiedProject:
        """
        Normalize raw data to UnifiedProject format.
        Override in subclass if source has special normalization needs.

        Args:
            raw_data: Raw data dictionary from source

        Returns:
            UnifiedProject object
        """
        return UnifiedProject(
            source=self.name,
            project_name=raw_data.get("project_name", ""),
            project_url=raw_data.get("project_url", ""),
            description=raw_data.get("description", ""),
            author=raw_data.get("author", ""),
            stars=raw_data.get("stars", 0),
            forks=raw_data.get("forks", 0),
            language=raw_data.get("language", ""),
            category=raw_data.get("category", "trending"),
            scraped_at=datetime.now(),
        )
