"""Authentication utilities for admin server."""

import os
import hashlib
import secrets
import logging
from functools import wraps

from flask import session, redirect, flash

from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


def hash_password(password):
    """Hash password with SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def init_users_table(db_path):
    """Create users table if not exists."""
    store = SQLiteStore(db_path)
    conn = store._get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'admin',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()

    # Create default admin if no users exist
    cursor.execute("SELECT COUNT(*) FROM admin_users")
    if cursor.fetchone()[0] == 0:
        # SECURITY: Use strong default password from env or generate random
        default_password = os.environ.get("ADMIN_DEFAULT_PASSWORD")
        if default_password:
            password_to_use = default_password
        else:
            # Generate a random password and log it
            password_to_use = secrets.token_urlsafe(16)
            logger.warning(
                "=" * 60 + "\n"
                "SECURITY WARNING: No admin user exists!\n"
                "Generated temporary password for first login:\n"
                f"  Username: admin\n"
                f"  Password: {password_to_use}\n"
                "Please change the password immediately after login!\n"
                "=" * 60
            )

        cursor.execute(
            "INSERT INTO admin_users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", hash_password(password_to_use), "admin"),
        )
        conn.commit()


def login_required(f):
    """Decorator to require login."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/admin/login")
        return f(*args, **kwargs)

    return decorated_function
