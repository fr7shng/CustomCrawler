"""Markdown report generator."""

from datetime import datetime
from typing import List

from scraper.sources.models import UnifiedProject
from .dark_horse import DarkHorseDetector, DarkHorseProject
from .readme_scorer import ReadmeScorer
from .trend_analyzer import TrendAnalyzer, LanguageHeat


class ReportGenerator:
    """Generate Markdown analysis reports."""

    def __init__(self):
        self.dark_horse_detector = DarkHorseDetector()
        self.readme_scorer = ReadmeScorer()
        self.trend_analyzer = TrendAnalyzer()

    def generate(self, projects: List[UnifiedProject], output_path: str = None) -> str:
        """
        Generate a complete analysis report.

        Args:
            projects: List of UnifiedProject to analyze
            output_path: Optional path to write report file

        Returns:
            Report content as Markdown string
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_lines = [
            f"# Custom Crawler 分析报告 - {date_str}",
            "",
            "## 概览",
        ]

        dark_horses = self.dark_horse_detector.detect(projects)
        language_heats = self.trend_analyzer.analyze_languages(projects)

        report_lines.extend(
            [
                f"- 热门项目总数: {len(projects)}",
                f"- 黑马项目数: {len(dark_horses)}",
                f"- 语言数量: {len(language_heats)}",
                "",
            ]
        )

        report_lines.extend(self._generate_top_projects_section(projects))
        report_lines.extend(self._generate_dark_horse_section(dark_horses))
        report_lines.extend(self._generate_language_section(language_heats))

        report = "\n".join(report_lines)

        if output_path:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)

        return report

    def _generate_top_projects_section(
        self, projects: List[UnifiedProject]
    ) -> List[str]:
        """Generate Top 10 projects table."""
        lines = ["## 热门项目 Top 10（含 README 评分）", ""]

        scores = self.readme_scorer.score_all(projects)
        sorted_scores = sorted(scores, key=lambda x: x.project.stars, reverse=True)[:10]

        if sorted_scores:
            lines.append("| 排名 | 项目 | 语言 | Stars | README评分 | 描述 |")
            lines.append("|------|------|------|-------|------------|------|")

            for i, score in enumerate(sorted_scores, 1):
                p = score.project
                desc_preview = (
                    (p.description[:50] + "...")
                    if len(p.description) > 50
                    else p.description
                )
                desc_preview = desc_preview.replace("|", "\\|")
                lines.append(
                    f"| {i} | [{p.project_name}]({p.project_url}) | {p.language} | {p.stars} | {score.total_score} | {desc_preview} |"
                )

        lines.append("")
        return lines

    def _generate_dark_horse_section(
        self, dark_horses: List[DarkHorseProject]
    ) -> List[str]:
        """Generate dark horse projects table."""
        lines = ["## 黑马项目 🏃", ""]

        if dark_horses:
            lines.append("| 项目 | 语言 | Stars | 黑马评分 | 识别原因 |")
            lines.append("|------|------|-------|----------|----------|")

            for dh in dark_horses[:20]:
                p = dh.project
                reason_desc = DarkHorseDetector.reason_description(dh.reason)
                lines.append(
                    f"| [{p.project_name}]({p.project_url}) | {p.language} | {p.stars} | {dh.score:.2f} | {reason_desc} |"
                )
        else:
            lines.append("*暂无黑马项目数据（首次采集无法识别）*")

        lines.append("")
        return lines

    def _generate_language_section(
        self, language_heats: List[LanguageHeat]
    ) -> List[str]:
        """Generate language heat table."""
        lines = ["## 语言热度 📈", ""]

        if language_heats:
            lines.append("| 语言 | 项目数 | 总Stars | 平均Stars | 热度 |")
            lines.append("|------|--------|---------|-----------|------|")

            for heat in language_heats:
                lines.append(
                    f"| {heat.language} | {heat.project_count} | {heat.total_stars} | {heat.average_stars:.0f} | {heat.heat_level} |"
                )
        else:
            lines.append("*暂无语言数据*")

        lines.append("")
        return lines
