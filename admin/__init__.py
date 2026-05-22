"""Admin blueprint for Custom Crawler Scraper."""

import os
from flask import Blueprint

# Get the path to the admin templates folder
ADMIN_TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
    template_folder=ADMIN_TEMPLATES_DIR,  # Explicitly set template folder
)

from admin import routes  # noqa: E402, F401
