"""Multi-source scraping framework orchestrator."""

import logging
import random
import time
from typing import List, Optional

import requests
import yaml

from config.config import MAX_RETRIES, REQUEST_DELAY_MAX, REQUEST_DELAY_MIN
from storage.sqlite_store import SQLiteStore

from . import SOURCE_REGISTRY
from .base import BaseSource
from .models import UnifiedProject
from .translator import Translator

logger = logging.getLogger(__name__)


class ScraperFramework:
    """Orchestrates scraping from multiple sources with priority and fallback."""

    def __init__(
        self,
        config_path: str = "config/sources.yaml",
        db_path: str = "custom_crawler.db",
    ):
        """
        Initialize the scraper framework.

        Args:
            config_path: Path to sources.yaml configuration
            db_path: Path to SQLite database
        """
        self.config_path = config_path
        self.db = SQLiteStore(db_path)
        self.sources: List[BaseSource] = []
        self.translator: Optional[Translator] = None
        self.translation_enabled = False
        self._load_config()

    def _load_config(self) -> None:
        """Load source configuration from YAML and database."""
        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            # Load translation config
            translation_config = config.get("translation", {})
            self.translation_enabled = translation_config.get("enabled", False)
            if self.translation_enabled:
                self.translator = Translator()

            # Load builtin sources from YAML
            for source_id, source_config in config.get("sources", {}).items():
                if not source_config.get("enabled", False):
                    continue

                source = self._create_source(source_id, source_config)
                if source:
                    self.sources.append(source)

        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
        except Exception as e:
            logger.error(f"Error loading config: {e}")

        # Load custom sources from database (always try, even if YAML is missing)
        self._load_custom_sources()

        self.sources.sort(key=lambda s: s.priority)
        logger.info(f"Loaded {len(self.sources)} enabled sources")
        if self.translation_enabled:
            logger.info("Translation enabled (English -> Chinese)")

    def _load_custom_sources(self) -> None:
        """Load enabled custom sources from database into SOURCE_REGISTRY."""
        try:
            custom_sources = self.db.get_all_custom_sources()
            for source in custom_sources:
                if not source.get("enabled", False):
                    continue

                name = source["name"]
                source_code = source.get("source_code", "")

                if not source_code:
                    continue

                try:
                    # Only compile and exec if not already registered
                    if name not in SOURCE_REGISTRY:
                        # Create safe execution environment
                        import builtins

                        safe_globals = {
                            "__builtins__": {
                                k: v
                                for k, v in builtins.__dict__.items()
                                if k
                                not in {
                                    "eval",
                                    "exec",
                                    "compile",
                                    "open",
                                    "input",
                                    "__import__",
                                    "exit",
                                    "quit",
                                    "help",
                                }
                            }
                        }
                        # Allow __import__ for from...import statements
                        safe_globals["__builtins__"]["__import__"] = __import__

                        # Inject common modules
                        import datetime
                        import json
                        import re

                        import requests
                        from lxml import html as lxml_html

                        safe_globals["requests"] = requests
                        safe_globals["datetime"] = datetime
                        safe_globals["json"] = json
                        safe_globals["re"] = re
                        safe_globals["html"] = lxml_html

                        # Inject scraper modules
                        from scraper.sources import base as sources_base
                        from scraper.sources import models as sources_models
                        from scraper.sources import register_source

                        safe_globals["BaseSource"] = sources_base.BaseSource
                        safe_globals["UnifiedProject"] = sources_models.UnifiedProject
                        safe_globals["register_source"] = register_source

                        # Compile and execute
                        compiled = compile(
                            source_code, f"<custom_source_{name}>", "exec"
                        )
                        exec(compiled, safe_globals)

                    # Check if registered and instantiate
                    if name in SOURCE_REGISTRY:
                        source_class = SOURCE_REGISTRY[name]
                        instance = source_class(priority=10)
                        self.sources.append(instance)
                        logger.info(f"Loaded custom source: {name}")
                    else:
                        logger.warning(f"Custom source {name} did not register itself")

                except Exception as e:
                    logger.error(f"Failed to load custom source {name}: {e}")

        except Exception as e:
            logger.error(f"Error loading custom sources: {e}")

    def _create_source(self, source_id: str, config: dict) -> Optional[BaseSource]:
        """Create a source instance based on configuration using registry."""
        source_class = SOURCE_REGISTRY.get(source_id)
        if source_class is None:
            logger.warning(f"Unknown source: {source_id}")
            return None
        priority = config.get("priority", 10)
        return source_class(priority=priority)

    def _retry_request(self, func, *args, **kwargs):
        """Execute a function with retry logic.

        Connection errors (network unreachable, DNS failure) are not retried.
        Timeout and HTTP server errors are retried up to MAX_RETRIES times.
        """
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except (
                requests.exceptions.ConnectionError,
                requests.exceptions.URLRequired,
                requests.exceptions.InvalidURL,
                requests.exceptions.MissingSchema,
            ) as e:
                logger.warning(f"网络连接不可达，不重试: {e}")
                raise
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    delay = REQUEST_DELAY_MIN + random.random() * (
                        REQUEST_DELAY_MAX - REQUEST_DELAY_MIN
                    )
                    logger.warning(
                        f"Request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {MAX_RETRIES} attempts failed: {e}")
        raise last_exception

    def scrape_source(self, source_name: str) -> List[UnifiedProject]:
        """Scrape from a single source by name.

        Args:
            source_name: Name of the source to scrape

        Returns:
            List of scraped UnifiedProject objects
        """
        source = None
        for s in self.sources:
            if s.name == source_name:
                source = s
                break

        if not source:
            logger.warning(f"Source not found: {source_name}")
            return []

        try:
            logger.info(f"Scraping from {source.name}...")
            projects = self._retry_request(source.scrape)
            if projects:
                if self.translation_enabled and self.translator:
                    projects = self._translate_projects(projects)
                self.db.insert_many(projects)
                logger.debug(f"  -> Got {len(projects)} projects from {source.name}")
                return projects
        except Exception as e:
            logger.error(f"Failed to scrape {source.name}: {e}")

        return []

    def scrape_all(self) -> List[UnifiedProject]:
        """
        Scrape from all enabled sources in priority order.

        Returns:
            List of all scraped UnifiedProject objects
        """
        all_projects = []

        for source in self.sources:
            try:
                projects = self.scrape_source(source.name)
                if projects:
                    all_projects.extend(projects)
            except Exception as e:
                logger.error(f"Failed to scrape {source.name}: {e}")
                continue

            time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        return all_projects

    def _translate_projects(
        self, projects: List[UnifiedProject]
    ) -> List[UnifiedProject]:
        """Translate English project names and descriptions to Chinese."""
        translated_count = 0
        for project in projects:
            # Translate project name (title) - show both English and Chinese
            if project.project_name and Translator.should_translate(
                project.project_name
            ):
                translated = self.translator.translate(project.project_name)
                if translated != project.project_name:
                    # Format: "English → 中文"
                    project.project_name = f"{project.project_name} → {translated}"
                    translated_count += 1

            # Translate description - show both English and Chinese
            if project.description and Translator.should_translate(project.description):
                translated = self.translator.translate(project.description)
                if translated != project.description:
                    project.description = f"{project.description} → {translated}"
                    translated_count += 1

        if translated_count > 0:
            logger.info(f"  -> Translated {translated_count} English items to Chinese")
        return projects
