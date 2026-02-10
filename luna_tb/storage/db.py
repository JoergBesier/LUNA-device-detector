"""SQLite storage utilities and migrations."""
from __future__ import annotations

import datetime as dt
import logging
import pathlib
import sqlite3
from typing import Iterable

LOGGER = logging.getLogger(__name__)


class MigrationError(RuntimeError):
    """Raised when migrations fail."""


def get_connection(db_path: str | pathlib.Path) -> sqlite3.Connection:
    path_obj = pathlib.Path(db_path)
    conn = sqlite3.connect(path_obj)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: str | pathlib.Path, migrations_dir: str | pathlib.Path) -> None:
    """Initialize the database file and apply migrations."""
    path_obj = pathlib.Path(db_path)
    if path_obj.parent and not path_obj.parent.exists():
        path_obj.parent.mkdir(parents=True, exist_ok=True)

    with get_connection(path_obj) as conn:
        apply_migrations(conn, migrations_dir)


def apply_migrations(conn: sqlite3.Connection, migrations_dir: str | pathlib.Path) -> None:
    migrations_path = pathlib.Path(migrations_dir)
    if not migrations_path.exists():
        raise MigrationError(f"Missing migrations dir: {migrations_path}")

    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);"
    )

    applied = {
        row[0]
        for row in conn.execute("SELECT version FROM schema_migrations;").fetchall()
    }

    migration_files = sorted(
        p for p in migrations_path.iterdir() if p.is_file() and p.suffix == ".sql"
    )
    for migration in migration_files:
        version = migration.stem
        if version in applied:
            continue

        LOGGER.info("Applying migration %s", migration.name)
        sql = migration.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?);",
                (version, _utc_now()),
            )
            conn.commit()
        except sqlite3.DatabaseError as exc:
            conn.rollback()
            raise MigrationError(f"Failed migration {migration.name}: {exc}") from exc


def _utc_now() -> str:
    return dt.datetime.now(tz=dt.timezone.utc).isoformat()
