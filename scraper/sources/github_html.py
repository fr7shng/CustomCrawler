"""Custom Crawler HTML scraper."""

import re
import logging
from typing import List
from datetime import datetime

import requests

from .base import BaseSource
from .models import UnifiedProject
from . import register_source
from config.config import GITHUB_TRENDING_URL, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)


@register_source("github_html")
class GitHubHTMLSource(BaseSource):
    """Scrape Custom Crawler page directly via HTML."""

    def __init__(self, priority: int = 1):
        super().__init__("github_html", priority)

    def scrape(self) -> List[UnifiedProject]:
        """
        Scrape Custom Crawler page.

        Returns:
            List of UnifiedProject from Custom Crawler
        """
        projects = []

        try:
            response = requests.get(GITHUB_TRENDING_URL, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            if "rate limit" in response.text.lower() or response.status_code == 403:
                raise Exception("GitHub HTML endpoint blocked (rate limit or 403)")

            projects = self._parse_html(response.text)

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch GitHub HTML: {e}")
            raise

        return projects

    def _parse_html(self, html: str) -> List[UnifiedProject]:
        """Parse Custom Crawler HTML to extract projects."""
        projects = []

        # Find all articles
        article_pattern = re.compile(
            r'<article[^>]*class="Box-row"[^>]*>(.*?)</article>', re.DOTALL
        )

        # New pattern: find the repo link in h2 > a[href="/owner/repo"]
        repo_link_pattern = re.compile(
            r'<h2[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>.*?</h2>', re.DOTALL
        )

        # Stars pattern: "1,234 stars" or "1234 stars"
        star_pattern = re.compile(r"([\d,]+)\s+[Ss]tar")

        # Forks pattern
        fork_pattern = re.compile(r"([\d,]+)\s+[Ff]ork")

        # Language pattern
        lang_pattern = re.compile(
            r'<span[^>]*itemprop="programmingLanguage"[^>]*>([^<]+)</span>'
        )

        # Description pattern
        desc_pattern = re.compile(
            r'<p[^>]*class="[^"]*color-fg-muted[^"]*"[^>]*>([^<]+)</p>'
        )

        for article_match in article_pattern.finditer(html):
            article = article_match.group(1)

            # Find repo link in h2
            repo_match = repo_link_pattern.search(article)
            if not repo_match:
                continue

            repo_path = repo_match.group(1).strip()  # e.g. /zilliztech/claude-context
            if not repo_path.startswith("/"):
                continue

            parts = repo_path.split("/")
            if len(parts) < 3:  # /owner/repo
                continue

            author = parts[1]
            repo_name = parts[2]
            project_url = f"https://github.com/{author}/{repo_name}"

            # Extract stars
            stars_text = star_pattern.search(article)
            stars = int(stars_text.group(1).replace(",", "")) if stars_text else 0

            # Extract forks
            forks_text = fork_pattern.search(article)
            forks = int(forks_text.group(1).replace(",", "")) if forks_text else 0

            # Extract language
            lang_match = lang_pattern.search(article)
            language = lang_match.group(1).strip() if lang_match else ""

            # Extract description
            desc_match = desc_pattern.search(article)
            description = desc_match.group(1).strip() if desc_match else ""

            projects.append(
                UnifiedProject(
                    source=self.name,
                    project_name=f"{author}/{repo_name}",
                    project_url=project_url,
                    description=description,
                    author=author,
                    stars=stars,
                    forks=forks,
                    language=language,
                    category="trending",
                    scraped_at=datetime.now(),
                )
            )

        return projects
