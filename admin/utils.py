"""Utility functions for admin server."""

import os

import yaml

from storage.sqlite_store import SQLiteStore
from generator.html_generator import HTMLGenerator


OUTPUT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_sources_config():
    """Load sources configuration from YAML."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "sources.yaml",
    )
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except Exception:
        return {"sources": {}}


def save_sources_config(config):
    """Save sources configuration to YAML."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "sources.yaml",
    )
    with open(config_path, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)


def regenerate_frontend(db_path):
    """Regenerate the frontend HTML from current database."""
    try:
        store = SQLiteStore(db_path)
        projects = store.get_all()
        if projects:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            output_path = os.path.join(OUTPUT_DIR, "index.html")
            generator = HTMLGenerator()
            generator.generate(projects, output_path)
            return True, len(projects)
        return True, 0
    except Exception as e:
        return False, str(e)


def _mask_api_key(api_key: str) -> str:
    """Mask API key for display, showing only first and last 4 characters."""
    if not api_key or len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def _clean_llm_artifacts(code: str) -> str:
    """Remove common LLM output artifacts from generated code."""
    lines = code.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        leading = len(line) - len(line.lstrip(" "))

        # Skip bare single-char artifact lines
        if stripped in ("n", "r", "t", "s", "x"):
            continue

        # Strip leading 'n' artifact from lines that look like Python code
        if stripped.startswith("n") and len(stripped) > 1:
            after = stripped[1:]
            if after and (after[0].isalpha() or after[0] in "@_"):
                line = " " * leading + after

        cleaned.append(line)
    return "\n".join(cleaned)
