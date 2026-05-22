"""Dark horse project detection algorithms."""

import statistics
from typing import List, Dict
from dataclasses import dataclass

from scraper.sources.models import UnifiedProject


@dataclass
class DarkHorseProject:
    """A dark horse project with detection details."""

    project: UnifiedProject
    score: float
    reason: str


class DarkHorseDetector:
    """Detect dark horse (黑马) projects using statistical methods."""

    def detect(self, projects: List[UnifiedProject]) -> List[DarkHorseProject]:
        """
        Detect dark horse projects from a list.

        Uses three independent methods:
        1. Standard deviation: stars > avg + 1.5*std
        2. Ranking: top 10% by stars
        3. Multiple average: stars > 3 * avg

        Args:
            projects: List of UnifiedProject to analyze

        Returns:
            List of DarkHorseProject with detection details
        """
        if not projects:
            return []

        stars_list = [p.stars for p in projects]
        if len(stars_list) < 3:
            return []

        avg_stars = statistics.mean(stars_list)
        std_stars = statistics.stdev(stars_list) if len(stars_list) > 1 else 0

        if std_stars == 0:
            return []

        sorted_by_stars = sorted(projects, key=lambda p: p.stars, reverse=True)
        top_10pct_index = max(0, int(len(sorted_by_stars) * 0.1) - 1)
        top_10pct_threshold = sorted_by_stars[top_10pct_index].stars

        dark_horses: Dict[str, DarkHorseProject] = {}

        for project in projects:
            if project.stars == 0:
                continue

            score = 0.0
            reason = None

            if project.stars > avg_stars + 1.5 * std_stars:
                score = (project.stars - avg_stars) / std_stars
                reason = "std_dev"

            if not reason and project.stars > avg_stars * 3:
                candidate_score = project.stars / avg_stars
                if not reason or candidate_score > score:
                    score = candidate_score
                    reason = "multiple_avg"

            if (
                top_10pct_threshold <= project.stars
                and project.stars > avg_stars
            ):
                candidate_score = project.stars / avg_stars
                if not reason or candidate_score > score:
                    score = candidate_score
                    reason = "rank_top_10pct"

            if reason:
                project_key = f"{project.source}:{project.project_name}"
                if (
                    project_key not in dark_horses
                    or dark_horses[project_key].score < score
                ):
                    dark_horses[project_key] = DarkHorseProject(
                        project=project, score=score, reason=reason
                    )

        result = sorted(dark_horses.values(), key=lambda x: x.score, reverse=True)
        return result

    @staticmethod
    def reason_description(reason: str) -> str:
        """Get human-readable description of detection reason."""
        descriptions = {
            "std_dev": "标准差异常",
            "rank_top_10pct": "排名前10%",
            "multiple_avg": "远超平均",
        }
        return descriptions.get(reason, reason)
