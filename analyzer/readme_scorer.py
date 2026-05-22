"""README quality scoring based on metadata."""

import re
from typing import List
from dataclasses import dataclass

from scraper.sources.models import UnifiedProject


@dataclass
class ReadmeScore:
    """README quality score with breakdown."""
    project: UnifiedProject
    total_score: int
    breakdown: dict


class ReadmeScorer:
    """Score README quality based on project metadata (no HTTP requests)."""

    TECHNICAL_KEYWORDS = [
        "python", "javascript", "typescript", "java", "go", "rust", "c++", "c#",
        "react", "vue", "angular", "node", "django", "flask", "fastapi",
        "api", "rest", "graphql", "grpc",
        "docker", "kubernetes", "aws", "azure", "gcp",
        "machine learning", "deep learning", "ai", "ml",
        "database", "sql", "nosql", "redis", "mongodb", "postgresql",
        "github", "gitlab", "cicd", "devops",
        "cli", "tool", "library", "framework"
    ]

    def score(self, project: UnifiedProject) -> ReadmeScore:
        """
        Score a project's README quality based on metadata.

        Scoring dimensions:
        - Base score: 10
        - Description completeness: 0-20 (>50 chars +10, >100 chars +20)
        - Technical keywords: 0-15
        - Hot bonus: 0-15 (based on stars)
        - Description quality: 0-10 (code, links, blank lines)

        Args:
            project: UnifiedProject to score

        Returns:
            ReadmeScore with total and breakdown
        """
        breakdown = {}

        total = 10
        breakdown["base"] = 10

        desc = project.description or ""
        desc_len = len(desc)

        if desc_len > 100:
            desc_score = 20
        elif desc_len > 50:
            desc_score = 10
        else:
            desc_score = 0
        total += desc_score
        breakdown["description_length"] = desc_score

        keyword_score = self._score_keywords(desc)
        total += keyword_score
        breakdown["keywords"] = keyword_score

        hot_score = self._score_hot_bonus(project.stars)
        total += hot_score
        breakdown["hot_bonus"] = hot_score

        quality_score = self._score_description_quality(desc)
        total += quality_score
        breakdown["quality"] = quality_score

        return ReadmeScore(
            project=project,
            total_score=total,
            breakdown=breakdown
        )

    def score_all(self, projects: List[UnifiedProject]) -> List[ReadmeScore]:
        """Score multiple projects."""
        return [self.score(p) for p in projects]

    def _score_keywords(self, description: str) -> int:
        """Score based on technical keywords."""
        if not description:
            return 0

        desc_lower = description.lower()
        matches = sum(1 for kw in self.TECHNICAL_KEYWORDS if kw in desc_lower)
        return min(15, matches * 3)

    def _score_hot_bonus(self, stars: int) -> int:
        """Score based on star count."""
        if stars > 100000:
            return 15
        elif stars > 50000:
            return 10
        elif stars > 10000:
            return 5
        return 0

    def _score_description_quality(self, description: str) -> int:
        """Score based on description formatting quality."""
        if not description:
            return 0

        score = 0

        if re.search(r'`[^`]+`|\bcode\b', description, re.IGNORECASE):
            score += 3

        if re.search(r'https?://|www\.', description):
            score += 4

        if '\n\n' in description or '\n' in description:
            score += 3

        return min(10, score)
