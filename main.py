#!/usr/bin/env python3
"""Custom Crawler Scraper - CLI entry point."""

import argparse
import logging
import logging.handlers
from datetime import datetime
from pathlib import Path

from config.config import (
    DATABASE_PATH,
    OUTPUT_DIR,
    REPORTS_DIR,
    LOG_LEVEL,
    LOG_FORMAT,
    LOG_DIR,
    LOG_FILE,
    LOG_MAX_BYTES,
    LOG_BACKUP_COUNT,
)
from storage.sqlite_store import SQLiteStore
from scraper.sources.framework import ScraperFramework
from generator.html_generator import HTMLGenerator
from analyzer.report_generator import ReportGenerator

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging with rotating file handler."""
    # Ensure log directory exists
    Path(LOG_DIR).mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        Path(LOG_DIR) / LOG_FILE,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(LOG_LEVEL)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(LOG_LEVEL)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


def init_db(db_path: str = DATABASE_PATH) -> None:
    """Initialize the database."""
    logger.info(f"Initializing database at {db_path}...")
    SQLiteStore(db_path)
    logger.info("Database initialized successfully.")


def scrape(
    config_path: str = "config/sources.yaml",
    db_path: str = DATABASE_PATH,
) -> None:
    """Scrape data from all configured sources."""
    logger.info("Starting scrape operation...")
    framework = ScraperFramework(config_path=config_path, db_path=db_path)
    projects = framework.scrape_all()
    logger.info(f"Scraping complete. Total projects collected: {len(projects)}")


def generate(
    db_path: str = DATABASE_PATH,
    output_dir: str = OUTPUT_DIR,
    language: str = None,
) -> None:
    """Generate HTML page from stored data."""
    logger.info("Generating HTML page...")
    store = SQLiteStore(db_path)
    projects = store.get_all(language=language)

    if not projects:
        logger.warning("No projects found in database.")
        return

    Path(output_dir).mkdir(exist_ok=True)
    output_path = f"{output_dir}/index.html"

    generator = HTMLGenerator()
    generator.generate(projects, output_path)
    logger.info(f"HTML page generated: {output_path}")


def analyze(
    db_path: str = DATABASE_PATH,
    reports_dir: str = REPORTS_DIR,
    language: str = None,
) -> None:
    """Run trend analysis and generate report."""
    logger.info("Running trend analysis...")
    store = SQLiteStore(db_path)
    projects = store.get_all(language=language)

    if not projects:
        logger.warning("No projects found in database.")
        return

    Path(reports_dir).mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = f"{reports_dir}/{date_str}-report.md"

    generator = ReportGenerator()
    generator.generate(projects, report_path)
    logger.info(f"Report generated: {report_path}")


def report_only(
    db_path: str = DATABASE_PATH,
    reports_dir: str = REPORTS_DIR,
    language: str = None,
) -> None:
    """Generate report without re-scraping."""
    analyze(db_path, reports_dir, language)


def stats(db_path: str = DATABASE_PATH) -> None:
    """Display database statistics."""
    logger.info("Fetching database statistics...")
    store = SQLiteStore(db_path)
    stats_data = store.get_stats()

    print("\n=== Database Statistics ===")
    print(f"Total Projects: {stats_data['total_projects']}")
    print(f"Languages: {stats_data['language_count']}")
    print("\nProjects by Source:")
    for source, count in stats_data["by_source"].items():
        print(f"  - {source}: {count}")

    if stats_data["date_range"] and stats_data["date_range"][0]:
        print(
            f"\nDate Range: {stats_data['date_range'][0]} to {stats_data['date_range'][1]}"
        )

    print()


def _should_run_source(store, source_id: str, interval: int) -> bool:
    """Check if a source should run based on schedule_interval and last_run."""
    if interval <= 0:
        return False

    last_run_str = store.get_setting(f"last_run_{source_id}", "")
    if not last_run_str:
        return True

    try:
        from datetime import datetime

        last_run = datetime.fromisoformat(last_run_str)
        minutes_since = (datetime.now() - last_run).total_seconds() / 60
        return minutes_since >= interval
    except ValueError:
        return True


def _run_source_if_due(framework, store, source_id: str, interval: int) -> bool:
    """Run a single source if it's due. Returns True if ran."""
    if not _should_run_source(store, source_id, interval):
        return False

    try:
        logger.info(f"Running source: {source_id} (interval: {interval}min)")
        projects = framework.scrape_source(source_id)
        if projects:
            logger.info(f"  -> Got {len(projects)} projects from {source_id}")

        from datetime import datetime

        store.set_setting(f"last_run_{source_id}", datetime.now().isoformat())
        return True
    except Exception as e:
        logger.error(f"Failed to run {source_id}: {e}")
        return False


def _check_builtin_sources(framework, store, config_path) -> bool:
    """Check and run builtin sources from YAML config. Returns True if any ran."""
    ran_any = False
    try:
        import yaml

        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}

        for source_id, source_config in config.get("sources", {}).items():
            if not source_config.get("enabled", False):
                continue
            interval = source_config.get("schedule_interval", 0)
            if _run_source_if_due(framework, store, source_id, interval):
                ran_any = True
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}")

    return ran_any


def _check_custom_sources(framework, store) -> bool:
    """Check and run custom sources from database. Returns True if any ran."""
    ran_any = False
    custom_sources = store.get_all_custom_sources()
    for source in custom_sources:
        if not source.get("enabled", False):
            continue
        name = source["name"]
        interval = source.get("schedule_interval", 0)
        if _run_source_if_due(framework, store, name, interval):
            ran_any = True
    return ran_any


def _regenerate_outputs(projects) -> None:
    """Regenerate HTML and report from projects."""
    logger.info("Regenerating outputs...")
    generator = HTMLGenerator()
    output_path = f"{OUTPUT_DIR}/index.html"
    Path(OUTPUT_DIR).mkdir(exist_ok=True)
    generator.generate(projects, output_path)
    logger.info(f"HTML generated: {output_path}")

    report_gen = ReportGenerator()
    date_str = datetime.now().strftime("%Y-%m-%d")
    report_path = f"{REPORTS_DIR}/{date_str}-report.md"
    Path(REPORTS_DIR).mkdir(exist_ok=True)
    report_gen.generate(projects, report_path)
    logger.info(f"Report generated: {report_path}")


def _run_scheduler_job(config_path, db_path) -> bool:
    """Run a single scheduler job cycle. Returns True if any source ran."""
    logger.info("=" * 50)
    logger.info("Checking sources for scheduled run...")

    try:
        framework = ScraperFramework(config_path=config_path, db_path=db_path)
        store = SQLiteStore(db_path)
        ran_any = False

        ran_any |= _check_builtin_sources(framework, store, config_path)
        ran_any |= _check_custom_sources(framework, store)

        if ran_any:
            projects = store.get_all()
            if projects:
                _regenerate_outputs(projects)
            logger.info("Job complete!")
        else:
            logger.info("No sources due for running")

        logger.info("=" * 50)

    except Exception as e:
        logger.error(f"Scheduled job failed: {e}", exc_info=True)

    return ran_any


def daemon(
    config_path: str = "config/sources.yaml",
    db_path: str = DATABASE_PATH,
    schedule_hour: int = 8,
    schedule_minute: int = 0,
) -> None:
    """Run as an interval-based scheduled background process.

    Checks each source's schedule_interval every minute and runs sources
    that are due for scraping (both builtin and custom).
    """
    import time

    logger.info("Starting interval-based daemon mode")

    # Run immediately on start
    logger.info("Running initial check...")
    _run_scheduler_job(config_path, db_path)

    # Check every minute
    while True:
        time.sleep(60)
        _run_scheduler_job(config_path, db_path)


def main():
    # Setup logging first
    setup_logging()

    parser = argparse.ArgumentParser(
        description="Custom Crawler Scraper - Multi-source trending project discovery"
    )
    parser.add_argument(
        "--scrape", action="store_true", help="Scrape data from all sources"
    )
    parser.add_argument("--generate", action="store_true", help="Generate HTML page")
    parser.add_argument(
        "--analyze", action="store_true", help="Run trend analysis and generate report"
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate report only (no scraping)"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Display database statistics"
    )
    parser.add_argument("--init-db", action="store_true", help="Initialize database")
    parser.add_argument(
        "--daemon", action="store_true", help="Run as scheduled background process"
    )
    parser.add_argument(
        "--admin", action="store_true", help="Start admin web interface server"
    )
    parser.add_argument(
        "--admin-port", type=int, default=5001, help="Admin server port (default: 5001)"
    )
    parser.add_argument("--language", type=str, help="Filter by programming language")
    parser.add_argument(
        "--config", type=str, default="config/sources.yaml", help="Config file path"
    )
    parser.add_argument(
        "--db", type=str, default=DATABASE_PATH, help="Database file path"
    )
    parser.add_argument(
        "--output", type=str, default=OUTPUT_DIR, help="Output directory"
    )
    parser.add_argument(
        "--reports", type=str, default=REPORTS_DIR, help="Reports directory"
    )

    args = parser.parse_args()

    if args.init_db:
        init_db(args.db)

    elif args.stats:
        stats(args.db)

    elif args.scrape:
        scrape(config_path=args.config, db_path=args.db)
        if args.generate:
            generate(db_path=args.db, output_dir=args.output, language=args.language)
        if args.analyze:
            analyze(db_path=args.db, reports_dir=args.reports, language=args.language)

    elif args.generate:
        generate(db_path=args.db, output_dir=args.output, language=args.language)

    elif args.analyze:
        analyze(db_path=args.db, reports_dir=args.reports, language=args.language)

    elif args.report:
        report_only(db_path=args.db, reports_dir=args.reports, language=args.language)

    elif args.admin:
        from admin_server import run_admin_server

        logger.info(f"Starting admin server on port {args.admin_port}...")
        run_admin_server(port=args.admin_port)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
