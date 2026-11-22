"""
Database Connection & Session Management for DemandIQ
Supports both MySQL (Production/Interview standard) and SQLite (Local development zero-friction).
"""
import os
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
import config

_engine: Engine = None

def get_engine() -> Engine:
    """Creates and returns a singleton SQLAlchemy engine based on config."""
    global _engine
    if _engine is not None:
        return _engine

    if config.DB_TYPE == "mysql":
        connection_url = (
            f"mysql+pymysql://{config.MYSQL_USER}:{config.MYSQL_PASSWORD}"
            f"@{config.MYSQL_HOST}:{config.MYSQL_PORT}/{config.MYSQL_DATABASE}"
            f"?charset=utf8mb4"
        )
        try:
            _engine = create_engine(connection_url, pool_pre_ping=True, pool_recycle=3600)
            # Test connection
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as e:
            print(f"[WARN] Failed to connect to MySQL ({e}). Falling back to SQLite at {config.SQLITE_PATH}")
            connection_url = f"sqlite:///{config.SQLITE_PATH}"
            _engine = create_engine(connection_url, connect_args={"check_same_thread": False})
    else:
        # SQLite
        Path(config.SQLITE_PATH).parent.mkdir(parents=True, exist_ok=True)
        connection_url = f"sqlite:///{config.SQLITE_PATH}"
        _engine = create_engine(connection_url, connect_args={"check_same_thread": False})

    return _engine

def execute_sql_file(file_path: Path):
    """Executes all semicolon-separated statements in a SQL script file."""
    if not file_path.exists():
        raise FileNotFoundError(f"SQL file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    engine = get_engine()
    is_sqlite = "sqlite" in str(engine.url)

    # Clean comments and parse statements
    statements = []
    current_stmt = []
    for line in sql_content.splitlines():
        trimmed = line.strip()
        if trimmed.startswith("--") or not trimmed:
            continue
        current_stmt.append(line)
        if trimmed.endswith(";"):
            stmt_str = "\n".join(current_stmt).strip()
            # If SQLite, adjust MySQL specific types if any
            if is_sqlite:
                stmt_str = stmt_str.replace("AUTO_INCREMENT", "AUTOINCREMENT")
                stmt_str = stmt_str.replace("ENGINE=InnoDB", "")
                stmt_str = stmt_str.replace("DEFAULT CHARSET=utf8mb4", "")
            statements.append(stmt_str)
            current_stmt = []

    with engine.begin() as conn:
        for stmt in statements:
            if stmt and not stmt.isspace():
                try:
                    conn.execute(text(stmt))
                except Exception as err:
                    # Ignore table already exists or harmless warnings
                    if "already exists" not in str(err).lower() and "duplicate" not in str(err).lower():
                        print(f"[SQL Notice] Statement skipped or errored: {err}")

def init_db():
    """Initializes schema, staging, and analytics tables & views."""
    schema_file = config.DATABASE_DIR / "schema.sql"
    staging_file = config.DATABASE_DIR / "staging.sql"
    analytics_file = config.DATABASE_DIR / "analytics.sql"

    print("[DB] Initializing database tables and schemas...")
    if schema_file.exists():
        execute_sql_file(schema_file)
    if staging_file.exists():
        execute_sql_file(staging_file)
    if analytics_file.exists():
        execute_sql_file(analytics_file)
    print("[DB] Database initialization completed successfully.")

if __name__ == "__main__":
    init_db()
