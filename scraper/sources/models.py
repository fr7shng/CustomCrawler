"""Unified data model for scraped projects."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class UnifiedProject:
    """Unified project model across all data sources."""

    source: str
    project_name: str
    project_url: str
    description: str
    author: str
    stars: int
    forks: int
    language: str
    category: str
    scraped_at: datetime
    id: Optional[int] = None  # Database ID, optional

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "source": self.source,
            "project_name": self.project_name,
            "project_url": self.project_url,
            "description": self.description,
            "author": self.author,
            "stars": self.stars,
            "forks": self.forks,
            "language": self.language,
            "category": self.category,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UnifiedProject":
        """Create from dictionary."""
        scraped_at = data["scraped_at"]
        if isinstance(scraped_at, str):
            scraped_at = datetime.fromisoformat(scraped_at)
        return cls(
            source=data["source"],
            project_name=data["project_name"],
            project_url=data["project_url"],
            description=data["description"],
            author=data["author"],
            stars=data["stars"],
            forks=data["forks"],
            language=data["language"],
            category=data["category"],
            scraped_at=scraped_at,
        )
