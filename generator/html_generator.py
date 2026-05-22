"""HTML generator with client-side filtering and pagination."""

import json
import os
from typing import List, Generator

from scraper.sources.models import UnifiedProject
from config.config import ITEMS_PER_PAGE


class HTMLGenerator:
    """Generate static HTML pages with embedded JavaScript for filtering."""

    def __init__(self):
        """Initialize the generator with template."""
        template_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "templates", "index.html"
        )
        with open(template_path, "r", encoding="utf-8") as f:
            self.template = f.read()

    def generate(self, projects: List[UnifiedProject], output_path: str = None) -> str:
        """
        Generate HTML page with projects data embedded.

        Args:
            projects: List of UnifiedProject to display
            output_path: Optional path to write HTML file

        Returns:
            Generated HTML content
        """
        # Optimize: Use separators for smaller JSON
        projects_data = [p.to_dict() for p in projects]
        projects_json = json.dumps(projects_data, ensure_ascii=False, separators=(",", ":"))

        languages = sorted(set(p.language for p in projects if p.language))
        sources = sorted(set(p.source for p in projects if p.source))

        # Replace template placeholders
        html = self.template
        html = html.replace("{{PROJECTS_JSON}}", projects_json)
        html = html.replace("{{ITEMS_PER_PAGE}}", str(ITEMS_PER_PAGE))
        html = html.replace("{{SOURCE_NAV}}", self._generate_source_nav(sources))
        html = html.replace(
            "{{CATEGORY_ITEMS}}", self._generate_category_items(languages)
        )

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html)

        return html

    def _generate_category_items(self, languages: List[str]) -> str:
        """Generate category items for sidebar with expand functionality."""
        if not languages:
            return ""

        items = []
        display_limit = 12
        for lang in languages[:display_limit]:
            items.append(
                f'<span class="category-item" data-lang="{lang}">{lang}</span>'
            )
        if len(languages) > display_limit:
            remaining = languages[display_limit:]
            remaining_json = json.dumps(remaining, ensure_ascii=False, separators=(",", ":"))
            items.append(
                f'<span class="category-item more-btn category-more-btn" onclick="expandCategories(this, {remaining_json})">+{len(remaining)} 更多</span>'
            )
        return "".join(items)

    def _generate_source_nav(self, sources: List[str]) -> str:
        """Generate source navigation for sidebar based on actual data."""
        if not sources:
            return '<div class="side-nav-item active" data-source="">全部来源</div>'

        source_labels = {
            "github_html": "🐙 GitHub",
            "github_trending_api": "⚡ API",
            "hackernews": "📈 HackerNews",
            "reddit": "🤖 Reddit",
            "gitee": "🐱 Gitee",
            "juejin": "💎 掘金",
            "v2ex": "🌐 V2EX",
        }
        nav_items = ['<div class="side-nav-item active" data-source="">全部来源</div>']
        for source in sources:
            label = source_labels.get(source, source)
            nav_items.append(
                f'<div class="side-nav-item" data-source="{source}">{label}</div>'
            )
        return "".join(nav_items)
