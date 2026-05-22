"""Admin server - entry point for starting the Flask application."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from admin.app import create_app

# Create Flask app
app = create_app()

DATABASE_PATH = app.config["DATABASE_PATH"]


def run_admin_server(host: str = "0.0.0.0", port: int = 5001):
    """Run the admin server (called by main.py)."""
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    print("Starting admin server on http://0.0.0.0:5001/admin/")
    print("Check server logs for generated default password if first login")
    app.run(host="0.0.0.0", port=5001, debug=False)
