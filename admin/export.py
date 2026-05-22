"""Data export service for CSV, JSON, and Markdown formats."""

import csv
import json
import io
import logging
from scraper.sources.models import UnifiedProject

logger = logging.getLogger(__name__)


class DataExporter:
    @staticmethod
    def to_json(projects, pretty=True):
        data = [p.to_dict() for p in projects]
        return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None)

    @staticmethod
    def to_csv(projects, fields=None):
        if not fields:
            fields = [
                "source",
                "project_name",
                "project_url",
                "description",
                "author",
                "stars",
                "forks",
                "language",
                "category",
                "scraped_at",
            ]
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(fields)
        for p in projects:
            row = [str(getattr(p, f, "")) for f in fields]
            writer.writerow(row)
        return output.getvalue()

    @staticmethod
    def to_markdown(projects, top_n=50):
        if not projects:
            return "暂无数据"
        lines = [
            f"# Custom Crawler 导出 ({len(projects)} 个项目)",
            "",
            "| 项目 | 语言 | Stars | 来源 |",
            "|------|------|-------|------|",
        ]
        for p in projects[:top_n]:
            desc = (
                (p.description[:60] + "...")
                if len(p.description) > 60
                else p.description
            )
            desc = desc.replace("|", "\\|")
            lines.append(
                f"| [{p.project_name}]({p.project_url}) | {p.language} | {p.stars} | {p.source} |"
            )
        return "\n".join(lines) + "\n"

    @staticmethod
    def to_txt(projects):
        lines = [f"Custom Crawler - 导出 ({len(projects)} 个项目)", "=" * 50, ""]
        for i, p in enumerate(projects, 1):
            lines.append(f"{i}. {p.project_name}")
            lines.append(f"   链接: {p.project_url}")
            lines.append(f"   语言: {p.language}  Stars: {p.stars}  来源: {p.source}")
            if p.description:
                lines.append(f"   描述: {p.description[:100]}")
            lines.append("")
        return "\n".join(lines)
