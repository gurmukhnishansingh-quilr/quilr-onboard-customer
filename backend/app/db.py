import sqlite3
from typing import Iterator

from .config import settings


def init_db() -> None:
    conn = sqlite3.connect(settings.database_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS instances (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                region TEXT,
                base_url TEXT,
                status TEXT,
                pg_host TEXT,
                pg_port TEXT,
                pg_user TEXT,
                pg_password TEXT,
                neo4j_host TEXT,
                neo4j_port TEXT,
                neo4j_user TEXT,
                neo4j_password TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                department TEXT,
                vendor TEXT,
                contact_email TEXT,
                comment TEXT,
                instance_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(instance_id) REFERENCES instances(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tenant_cache (
                instance_id TEXT NOT NULL,
                match_value TEXT NOT NULL,
                tenant_id TEXT,
                tenant_name TEXT,
                subscriber TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (instance_id, match_value)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS internal_user_cache (
                instance_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                subscriber TEXT NOT NULL,
                user_id TEXT NOT NULL,
                name TEXT,
                email TEXT,
                account_type TEXT,
                fetched_at TEXT NOT NULL,
                PRIMARY KEY (instance_id, tenant_id, subscriber, user_id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS customer_comments (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                comment TEXT NOT NULL,
                author_email TEXT,
                author_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_settings (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL UNIQUE,
                theme TEXT DEFAULT 'dark',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_instance_columns(conn)
        _ensure_customer_columns(conn)
        _ensure_customer_comment_columns(conn)
        _ensure_internal_user_cache_columns(conn)
        conn.commit()
    finally:
        conn.close()


def _ensure_instance_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(instances)").fetchall()}
    columns = {
        "pg_host": "pg_host TEXT",
        "pg_port": "pg_port TEXT",
        "pg_user": "pg_user TEXT",
        "pg_password": "pg_password TEXT",
        "neo4j_host": "neo4j_host TEXT",
        "neo4j_port": "neo4j_port TEXT",
        "neo4j_user": "neo4j_user TEXT",
        "neo4j_password": "neo4j_password TEXT",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE instances ADD COLUMN {ddl}")


def _ensure_customer_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(customers)").fetchall()}
    columns = {
        "first_name": "first_name TEXT",
        "last_name": "last_name TEXT",
        "department": "department TEXT",
        "vendor": "vendor TEXT",
        "comment": "comment TEXT",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE customers ADD COLUMN {ddl}")


def _ensure_customer_comment_columns(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(customer_comments)").fetchall()}
    columns = {
        "author_email": "author_email TEXT",
        "author_name": "author_name TEXT",
        "tenant_id": "tenant_id TEXT",
    }
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE customer_comments ADD COLUMN {ddl}")


def _ensure_internal_user_cache_columns(conn: sqlite3.Connection) -> None:
    existing = {
        row[1] for row in conn.execute("PRAGMA table_info(internal_user_cache)").fetchall()
    }
    if "account_type" not in existing:
        conn.execute("ALTER TABLE internal_user_cache ADD COLUMN account_type TEXT")
        conn.execute(
            "UPDATE internal_user_cache SET account_type = 'credentials' "
            "WHERE account_type IS NULL OR account_type = ''"
        )


def get_db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.database_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
