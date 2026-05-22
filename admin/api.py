"""REST API routes for admin server."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from flask import Blueprint, jsonify

from storage.sqlite_store import SQLiteStore

# Create Blueprint for API routes
api_bp = Blueprint("api", __name__, url_prefix="")

DATABASE_PATH = os.path.join(PROJECT_ROOT, "custom_crawler.db")


@api_bp.route("/projects")
def list_projects():
    """Get all projects."""
    store = SQLiteStore(DATABASE_PATH)
    projects = store.get_all()
    return jsonify([p.to_dict() for p in projects])


@api_bp.route("/projects/<source>")
def projects_by_source(source):
    """Get projects by source."""
    store = SQLiteStore(DATABASE_PATH)
    projects = store.get_all(source=source)
    return jsonify([p.to_dict() for p in projects])


@api_bp.route("/stats")
def get_stats():
    """Get database statistics."""
    store = SQLiteStore(DATABASE_PATH)
    return jsonify(store.get_stats())
