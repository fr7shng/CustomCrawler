"""Flask app factory for admin server."""

import os
import sys
from flask import Flask, redirect, send_from_directory

from admin import bp
from admin.api import api_bp
from admin.auth import init_users_table
from admin.utils import OUTPUT_DIR
from storage.sqlite_store import SQLiteStore

# Project root setup
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


def create_app():
    """Create and configure the Flask application."""
    template_path = os.path.join(PROJECT_ROOT, "admin", "templates")
    app = Flask(__name__, template_folder=template_path)
    app.config["SECRET_KEY"] = os.environ.get(
        "FLASK_SECRET_KEY", os.urandom(32).hex()
    )
    app.config["TEMPLATES_AUTO_RELOAD"] = True

    DATABASE_PATH = os.path.join(PROJECT_ROOT, "custom_crawler.db")
    app.config["DATABASE_PATH"] = DATABASE_PATH
    app.config["PROJECT_ROOT"] = PROJECT_ROOT

    # Initialize users table
    init_users_table(DATABASE_PATH)

    # Register admin Blueprint (all /admin/* routes)
    app.register_blueprint(bp)

    # Register REST API routes
    app.register_blueprint(api_bp)

    # Static file serving routes
    _register_static_routes(app, OUTPUT_DIR)

    return app


def _register_static_routes(app, output_dir):
    """Register routes for serving static files."""

    @app.route("/")
    def root():
        """Serve index.html from root path or redirect to admin if not found."""
        try:
            return send_from_directory(output_dir, "index.html")
        except FileNotFoundError:
            return redirect("/admin/")

    @app.route("/output/")
    def output_index():
        """Serve the generated frontend HTML."""
        return send_from_directory(output_dir, "index.html")

    @app.route("/output/<path:filename>")
    def output_static(filename):
        """Serve static files from output directory."""
        return send_from_directory(output_dir, filename)

    @app.route("/index.html")
    def root_index():
        """Serve index.html from root path."""
        return send_from_directory(output_dir, "index.html")
