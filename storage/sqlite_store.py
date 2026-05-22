"""SQLite storage layer for scraped projects."""

import sqlite3
import threading
from datetime import datetime
from typing import List, Optional

from scraper.sources.models import UnifiedProject


class SQLiteStore:
    """SQLite storage handler for UnifiedProject data."""

    _INSERT_SQL = """
        INSERT INTO projects (
            source, project_name, project_url, description,
            author, stars, forks, language, category, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source, project_url) DO UPDATE SET
            project_name = excluded.project_name,
            description = excluded.description,
            author = excluded.author,
            stars = excluded.stars,
            forks = excluded.forks,
            language = excluded.language,
            category = excluded.category,
            scraped_at = excluded.scraped_at
    """

    def __init__(self, db_path: str = "custom_crawler.db"):
        """
        Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()

    def __enter__(self):
        """Enter context manager, return self."""
        self._local.conn = sqlite3.connect(self.db_path)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager, close connection."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            delattr(self._local, "conn")
        return False

    def _get_connection(self) -> sqlite3.Connection:
        """Get a connection for current thread, creating one if needed."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self.db_path)
        return self._local.conn

    def close(self) -> None:
        """Close the database connection for current thread."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            delattr(self._local, "conn")

    def _init_db(self) -> None:
        """Initialize database schema."""
        # Create temporary connection for init (thread-safe)
        conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()

        # Check if migration needed BEFORE creating indexes
        # Old DBs have UNIQUE(source, project_name); migrate to UNIQUE(source, project_url)
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='projects' AND name='sqlite_autoindex_projects_1'"
        )
        old_autoindex = cursor.fetchone()
        needs_migration = old_autoindex is not None

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                project_name TEXT NOT NULL,
                project_url TEXT NOT NULL,
                description TEXT,
                author TEXT,
                stars INTEGER DEFAULT 0,
                forks INTEGER DEFAULT 0,
                language TEXT,
                category TEXT,
                scraped_at TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, project_url)
            )
        """)

        if needs_migration:
            import logging as _logging

            _logger = _logging.getLogger(__name__)
            _logger.info(
                "迁移旧数据库约束: UNIQUE(source,project_name) -> UNIQUE(source,project_url)"
            )
            cursor.execute("PRAGMA foreign_keys = OFF")
            cursor.execute("BEGIN TRANSACTION")
            cursor.execute("DROP INDEX IF EXISTS idx_source_name")
            cursor.execute("""
                CREATE TABLE projects_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    project_name TEXT NOT NULL,
                    project_url TEXT NOT NULL,
                    description TEXT,
                    author TEXT,
                    stars INTEGER DEFAULT 0,
                    forks INTEGER DEFAULT 0,
                    language TEXT,
                    category TEXT,
                    scraped_at TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(source, project_url)
                )
            """)
            cursor.execute("""
                INSERT INTO projects_new
                    (id, source, project_name, project_url, description,
                     author, stars, forks, language, category, scraped_at, created_at)
                SELECT id, source, project_name, project_url, description,
                       author, stars, forks, language, category, scraped_at, created_at
                FROM projects
                WHERE id IN (
                    SELECT MIN(id) FROM projects GROUP BY source, project_url
                )
            """)
            cursor.execute("DROP TABLE projects")
            cursor.execute("ALTER TABLE projects_new RENAME TO projects")
            cursor.execute("COMMIT")
            cursor.execute("PRAGMA foreign_keys = ON")

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_source ON projects(source)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_scraped_at ON projects(scraped_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_language ON projects(language)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_source_project_url ON projects(source, project_url)
        """)
        # Custom sources table for user-defined scrapers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                source_code TEXT NOT NULL,
                config_schema TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                schedule_interval INTEGER DEFAULT 0
            )
        """)
        # Settings table for API keys
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        # Audit log table for sensitive operations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                username TEXT,
                action TEXT NOT NULL,
                resource_type TEXT,
                resource_id INTEGER,
                details TEXT,
                ip_address TEXT
            )
        """)
        # Check if schedule_interval column exists, add if not
        cursor.execute("PRAGMA table_info(custom_sources)")
        columns = [row[1] for row in cursor.fetchall()]  # row[1] = column name
        if "schedule_interval" not in columns:
            try:
                cursor.execute(
                    "ALTER TABLE custom_sources ADD COLUMN schedule_interval INTEGER DEFAULT 0"
                )
            except sqlite3.OperationalError as e:
                if "duplicate column name" not in str(e).lower():
                    raise
        # Source health tracking table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS source_health (
                source_name TEXT PRIMARY KEY,
                last_success_at TIMESTAMP,
                last_failure_at TIMESTAMP,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_error_message TEXT,
                avg_response_time_ms INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scrape_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT NOT NULL,
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                status TEXT NOT NULL,
                projects_count INTEGER DEFAULT 0,
                error_message TEXT,
                response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scrape_logs_source ON scrape_logs(source_name)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scrape_logs_created ON scrape_logs(created_at)"
        )
        conn.commit()
        conn.close()

    def insert(self, project: UnifiedProject) -> int:
        """
        Insert a project into the database.

        Args:
            project: UnifiedProject to insert

        Returns:
            Row ID of inserted project, 0 if skipped (duplicate source+url)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            self._INSERT_SQL,
            (
                project.source,
                project.project_name,
                project.project_url,
                project.description,
                project.author,
                project.stars,
                project.forks,
                project.language,
                project.category,
                project.scraped_at.isoformat(),
            ),
        )
        row_id = cursor.lastrowid
        conn.commit()
        return row_id if row_id is not None else 0

    def insert_many(self, projects: List[UnifiedProject]) -> int:
        """
        Insert multiple projects into the database.
        On conflict (same source + project_url), UPDATE existing record.

        Args:
            projects: List of UnifiedProject objects

        Returns:
            Number of NEW projects inserted (excluding updated existing records)
        """
        if not projects:
            return 0
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM projects")
        before_count = cursor.fetchone()[0]

        data = [
            (
                p.source,
                p.project_name,
                p.project_url,
                p.description,
                p.author,
                p.stars,
                p.forks,
                p.language,
                p.category,
                p.scraped_at.isoformat(),
            )
            for p in projects
        ]
        cursor.executemany(
            self._INSERT_SQL,
            data,
        )
        conn.commit()

        cursor.execute("SELECT COUNT(*) FROM projects")
        after_count = cursor.fetchone()[0]
        inserted = after_count - before_count

        if inserted < len(projects):
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                f"insert_many: collected {len(projects)}, inserted {inserted}, updated {len(projects) - inserted}"
            )
        return inserted

    def batch_insert(
        self, projects: List[UnifiedProject], batch_size: int = 100
    ) -> int:
        """
        Batch insert projects with configurable batch size.

        Args:
            projects: List of UnifiedProject objects
            batch_size: Number of projects per batch (default 100)

        Returns:
            Total number of projects inserted
        """
        if not projects:
            return 0
        total = 0
        for i in range(0, len(projects), batch_size):
            batch = projects[i : i + batch_size]
            total += self.insert_many(batch)
        return total

    def get_all(
        self,
        source: Optional[str] = None,
        language: Optional[str] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = "DESC",
    ) -> List[UnifiedProject]:
        """
        Query projects from the database with pagination and search.

        Args:
            source: Filter by source
            language: Filter by language
            limit: Limit number of results
            offset: Offset for pagination
            search: Search keyword for project_name and description
            sort_by: Sort column (stars, scraped_at, project_name)
            sort_order: Sort order (ASC or DESC)

        Returns:
            List of UnifiedProject objects
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM projects WHERE 1=1"
        count_query = "SELECT COUNT(*) FROM projects WHERE 1=1"
        params = []
        count_params = []

        if source:
            query += " AND source = ?"
            count_query += " AND source = ?"
            params.append(source)
            count_params.append(source)

        if language:
            query += " AND language = ?"
            count_query += " AND language = ?"
            params.append(language)
            count_params.append(language)

        if search:
            search_pattern = f"%{search}%"
            query += " AND (project_name LIKE ? OR description LIKE ?)"
            count_query += " AND (project_name LIKE ? OR description LIKE ?)"
            params.extend([search_pattern, search_pattern])
            count_params.extend([search_pattern, search_pattern])

        # Sorting
        valid_sort_columns = {
            "stars": "stars",
            "scraped_at": "scraped_at",
            "project_name": "project_name",
            "created_at": "created_at",
        }
        sort_column = valid_sort_columns.get(sort_by, "scraped_at")
        sort_direction = "DESC" if sort_order.upper() == "DESC" else "ASC"
        query += f" ORDER BY {sort_column} {sort_direction}"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        if offset:
            query += " OFFSET ?"
            params.append(offset)

        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            UnifiedProject(
                id=row[0],
                source=row[1],
                project_name=row[2],
                project_url=row[3],
                description=row[4] or "",
                author=row[5] or "",
                stars=row[6],
                forks=row[7],
                language=row[8] or "",
                category=row[9],
                scraped_at=datetime.fromisoformat(row[10]),
            )
            for row in rows
        ]

    def get_count(
        self,
        source: Optional[str] = None,
        language: Optional[str] = None,
        search: Optional[str] = None,
    ) -> int:
        """
        Get total count of projects with filters.

        Args:
            source: Filter by source
            language: Filter by language
            search: Search keyword for project_name and description

        Returns:
            Total count
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        query = "SELECT COUNT(*) FROM projects WHERE 1=1"
        params = []

        if source:
            query += " AND source = ?"
            params.append(source)

        if language:
            query += " AND language = ?"
            params.append(language)

        if search:
            search_pattern = f"%{search}%"
            query += " AND (project_name LIKE ? OR description LIKE ?)"
            params.extend([search_pattern, search_pattern])

        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def get_stats(self) -> dict:
        """
        Get database statistics.

        Returns:
            Dictionary with stats
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM projects")
        total = cursor.fetchone()[0]

        cursor.execute("""
            SELECT source, COUNT(*) as count
            FROM projects
            GROUP BY source
        """)
        by_source = dict(cursor.fetchall())

        cursor.execute("""
            SELECT MIN(scraped_at), MAX(scraped_at)
            FROM projects
        """)
        date_range = cursor.fetchone()

        cursor.execute("SELECT COUNT(DISTINCT language) FROM projects")
        language_count = cursor.fetchone()[0]

        return {
            "total_projects": total,
            "by_source": by_source,
            "date_range": date_range,
            "language_count": language_count,
        }

    def get_by_id(self, project_id: int) -> Optional[UnifiedProject]:
        """Get a project by its ID."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return UnifiedProject(
            id=row[0],
            source=row[1],
            project_name=row[2],
            project_url=row[3],
            description=row[4] or "",
            author=row[5] or "",
            stars=row[6],
            forks=row[7],
            language=row[8] or "",
            category=row[9],
            scraped_at=datetime.fromisoformat(row[10]),
        )

    def update(self, project_id: int, **kwargs) -> bool:
        """Update a project. Returns True if successful."""
        conn = self._get_connection()
        cursor = conn.cursor()
        allowed_fields = ["description", "project_url", "stars", "language", "author"]
        updates = []
        values = []
        for field in allowed_fields:
            if field in kwargs:
                updates.append(f"{field} = ?")
                values.append(kwargs[field])
        if not updates:
            return False
        values.append(project_id)
        query = f"UPDATE projects SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        return cursor.rowcount > 0

    def delete(self, project_id: int) -> bool:
        """Delete a project by ID. Returns True if successful."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        conn.commit()
        return cursor.rowcount > 0

    def search(self, keyword: str) -> List[UnifiedProject]:
        """Search projects by name or description."""
        conn = self._get_connection()
        cursor = conn.cursor()
        pattern = f"%{keyword}%"
        cursor.execute(
            """
            SELECT * FROM projects
            WHERE project_name LIKE ? OR description LIKE ?
            ORDER BY scraped_at DESC
            """,
            (pattern, pattern),
        )
        rows = cursor.fetchall()
        return [
            UnifiedProject(
                id=row[0],
                source=row[1],
                project_name=row[2],
                project_url=row[3],
                description=row[4] or "",
                author=row[5] or "",
                stars=row[6],
                forks=row[7],
                language=row[8] or "",
                category=row[9],
                scraped_at=datetime.fromisoformat(row[10]),
            )
            for row in rows
        ]

    def get_languages(self) -> List[str]:
        """Get all unique languages."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT DISTINCT language FROM projects WHERE language IS NOT NULL AND language != '' ORDER BY language"
        )
        return [row[0] for row in cursor.fetchall()]

    def get_sources(self) -> List[str]:
        """Get all unique sources."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT source FROM projects ORDER BY source")
        return [row[0] for row in cursor.fetchall()]

    # ============ Custom Sources Management ============
    def save_custom_source(
        self,
        name: str,
        source_code: str,
        description: str = "",
        config_schema: str = "",
        schedule_interval: int = 0,
    ) -> int:
        """Save or update a custom source."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO custom_sources (name, source_code, description, config_schema, schedule_interval, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                source_code = excluded.source_code,
                description = excluded.description,
                config_schema = excluded.config_schema,
                schedule_interval = excluded.schedule_interval,
                updated_at = CURRENT_TIMESTAMP
        """,
            (name, source_code, description, config_schema, schedule_interval),
        )
        conn.commit()
        return cursor.lastrowid if cursor.lastrowid else 0

    def get_custom_source(self, name: str) -> Optional[dict]:
        """Get a custom source by name."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_sources WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "source_code": row[3],
            "config_schema": row[4],
            "enabled": row[5],
            "created_at": row[6],
            "updated_at": row[7],
            "schedule_interval": row[8] if len(row) > 8 else 0,
        }

    def get_all_custom_sources(self) -> List[dict]:
        """Get all custom sources."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM custom_sources ORDER BY name")
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "source_code": row[3],
                "config_schema": row[4],
                "enabled": row[5],
                "created_at": row[6],
                "updated_at": row[7],
                "schedule_interval": row[8] if len(row) > 8 else 0,
            }
            for row in rows
        ]

    def delete_custom_source(self, name: str) -> bool:
        """Delete a custom source."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM custom_sources WHERE name = ?", (name,))
        conn.commit()
        return cursor.rowcount > 0

    def toggle_custom_source(self, name: str, enabled: bool) -> bool:
        """Enable or disable a custom source."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE custom_sources SET enabled = ? WHERE name = ?",
            (1 if enabled else 0, name),
        )
        conn.commit()
        return cursor.rowcount > 0

    def update_custom_source_schedule(self, name: str, schedule_interval: int) -> bool:
        """Update schedule interval for a custom source."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE custom_sources SET schedule_interval = ? WHERE name = ?",
            (schedule_interval, name),
        )
        conn.commit()
        return cursor.rowcount > 0

    # ============ Settings Management ============
    def get_setting(self, key: str, default: str = "") -> str:
        """Get a setting value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Set a setting value."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """,
            (key, value),
        )
        conn.commit()

    # ============ Audit Log ============
    def add_audit_log(
        self,
        action: str,
        username: str = None,
        resource_type: str = None,
        resource_id: int = None,
        details: str = None,
        ip_address: str = None,
    ) -> None:
        """Add an audit log entry for sensitive operations."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_log (username, action, resource_type, resource_id, details, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (username, action, resource_type, resource_id, details, ip_address),
        )
        conn.commit()

    def get_audit_log(self, limit: int = 100) -> List[dict]:
        """Get recent audit log entries."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, timestamp, username, action, resource_type, resource_id, details, ip_address "
            "FROM audit_log ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "timestamp": row[1],
                "username": row[2],
                "action": row[3],
                "resource_type": row[4],
                "resource_id": row[5],
                "details": row[6],
                "ip_address": row[7],
            }
            for row in rows
        ]

    # ============ Source Health Management ============
    def update_source_health(
        self,
        source_name: str,
        success: bool,
        error_message: str = None,
        response_time_ms: int = None,
    ) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT success_count, failure_count FROM source_health WHERE source_name = ?",
            (source_name,),
        )
        row = cursor.fetchone()
        if row:
            success_count = row[0] + (1 if success else 0)
            failure_count = row[1] + (0 if success else 1)
            cursor.execute(
                """
                UPDATE source_health
                SET last_success_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE last_success_at END,
                    last_failure_at = CASE WHEN NOT ? THEN CURRENT_TIMESTAMP ELSE last_failure_at END,
                    success_count = ?,
                    failure_count = ?,
                    last_error_message = CASE WHEN NOT ? THEN ? ELSE last_error_message END,
                    avg_response_time_ms = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE source_name = ?
            """,
                (
                    success,
                    success,
                    success_count,
                    failure_count,
                    success,
                    error_message,
                    response_time_ms,
                    source_name,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO source_health
                (source_name, last_success_at, last_failure_at, success_count, failure_count,
                 last_error_message, avg_response_time_ms)
                VALUES (?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                        CASE WHEN NOT ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                        ?, ?, ?, ?)
            """,
                (
                    source_name,
                    success,
                    success,
                    1 if success else 0,
                    0 if success else 1,
                    error_message if not success else None,
                    response_time_ms,
                ),
            )
        conn.commit()

    def get_source_health(self, source_name: str) -> Optional[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT source_name, last_success_at, last_failure_at,
                   success_count, failure_count, last_error_message, avg_response_time_ms
            FROM source_health WHERE source_name = ?
        """,
            (source_name,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "source_name": row[0],
            "last_success_at": row[1],
            "last_failure_at": row[2],
            "success_count": row[3],
            "failure_count": row[4],
            "last_error_message": row[5],
            "avg_response_time_ms": row[6],
        }

    def get_all_source_health(self) -> List[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT source_name, last_success_at, last_failure_at,
                   success_count, failure_count, last_error_message, avg_response_time_ms
            FROM source_health ORDER BY source_name
        """)
        return [
            {
                "source_name": row[0],
                "last_success_at": row[1],
                "last_failure_at": row[2],
                "success_count": row[3],
                "failure_count": row[4],
                "last_error_message": row[5],
                "avg_response_time_ms": row[6],
            }
            for row in cursor.fetchall()
        ]

    # ============ Scrape Logs ============
    def add_scrape_log(
        self,
        source_name: str,
        status: str,
        projects_count: int = 0,
        error_message: str = None,
        response_time_ms: int = None,
    ) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO scrape_logs (source_name, status, projects_count, error_message, response_time_ms) VALUES (?, ?, ?, ?, ?)",
            (source_name, status, projects_count, error_message, response_time_ms),
        )
        conn.commit()
        return cursor.lastrowid

    def get_scrape_logs(
        self, source_name: str = None, limit: int = 50, offset: int = 0
    ) -> List[dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        query = "SELECT id, source_name, started_at, completed_at, status, projects_count, error_message, response_time_ms FROM scrape_logs WHERE 1=1"
        params = []
        if source_name:
            query += " AND source_name = ?"
            params.append(source_name)
        query += " ORDER BY started_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        return [
            {
                "id": r[0],
                "source_name": r[1],
                "started_at": r[2],
                "completed_at": r[3],
                "status": r[4],
                "projects_count": r[5],
                "error_message": r[6],
                "response_time_ms": r[7],
            }
            for r in cursor.fetchall()
        ]
