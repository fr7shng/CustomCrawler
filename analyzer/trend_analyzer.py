"""Language trend analysis."""

import math
from typing import List, Dict
from dataclasses import dataclass

from scraper.sources.models import UnifiedProject


@dataclass
class LanguageHeat:
    """Language heat analysis result."""
    language: str
    project_count: int
    total_stars: int
    average_stars: float
    heat_score: float
    heat_level: str


class TrendAnalyzer:
    """Analyze programming language trends."""

    def analyze_languages(self, projects: List[UnifiedProject]) -> List[LanguageHeat]:
        """
        Analyze language popularity using composite heat formula.

        Formula: log(total_stars + 1) × 0.5 + project_count × 10 + average_stars × 0.1

        Heat levels:
        - 🔥 Hot: top 3
        - 📈 Stable: 4-6
        - 📉 General: 6+

        Args:
            projects: List of UnifiedProject to analyze

        Returns:
            List of LanguageHeat sorted by heat score descending
        """
        language_stats = self._aggregate_by_language(projects)
        heats = []

        for language, stats in language_stats.items():
            if not language:
                continue

            total_stars = stats["total_stars"]
            project_count = stats["count"]
            avg_stars = stats["avg_stars"]

            heat_score = (
                math.log(total_stars + 1) * 0.5 +
                project_count * 10 +
                avg_stars * 0.1
            )

            heats.append(LanguageHeat(
                language=language,
                project_count=project_count,
                total_stars=total_stars,
                average_stars=avg_stars,
                heat_score=heat_score,
                heat_level=""
            ))

        heats.sort(key=lambda x: x.heat_score, reverse=True)

        for i, heat in enumerate(heats):
            if i < 3:
                heat.heat_level = "🔥 热"
            elif i < 6:
                heat.heat_level = "📈 稳定"
            else:
                heat.heat_level = "📉 一般"

        return heats

    def _aggregate_by_language(self, projects: List[UnifiedProject]) -> Dict[str, Dict]:
        """Aggregate project stats by language."""
        stats = {}

        for project in projects:
            lang = project.language or "Unknown"
            if lang not in stats:
                stats[lang] = {"total_stars": 0, "count": 0, "stars_list": []}

            stats[lang]["total_stars"] += project.stars
            stats[lang]["count"] += 1
            stats[lang]["stars_list"].append(project.stars)

        for lang, data in stats.items():
            data["avg_stars"] = data["total_stars"] / data["count"] if data["count"] > 0 else 0

        return stats
