"""Admin server - legacy entry point that delegates to admin.server."""

from admin.server import app, run_admin_server, DATABASE_PATH

__all__ = ["app", "run_admin_server", "DATABASE_PATH"]
