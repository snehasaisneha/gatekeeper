"""Database migration runner for Gatekeeper.

Supports both SQLite and PostgreSQL.
"""

import argparse
import asyncio
from pathlib import Path

from gatekeeper.config import get_settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def get_db_info() -> tuple[str, str]:
    """Get database type and connection string.

    Returns:
        Tuple of (db_type, connection_string) where db_type is 'sqlite' or 'postgres'
    """
    settings = get_settings()
    db_url = settings.database_url

    if db_url.startswith("sqlite"):
        # Extract path from sqlite+aiosqlite:/// or sqlite:///
        if ":///" in db_url:
            db_path = db_url.split(":///", 1)[1]
            if db_path.startswith("./"):
                db_path = db_path[2:]
            return ("sqlite", db_path)
    elif db_url.startswith("postgresql") or db_url.startswith("postgres"):
        # Convert async URL to sync for migrations if needed
        conn_str = db_url.replace("postgresql+asyncpg://", "postgresql://")
        return ("postgres", conn_str)

    raise ValueError(f"Unsupported database URL: {db_url}")


async def run_sqlite_migrations(db_path: str, target: int | None = None) -> None:
    """Run migrations on SQLite database."""
    import aiosqlite

    print(f"Running migrations on SQLite: {db_path}")

    async with aiosqlite.connect(db_path) as db:
        # Get applied migrations
        try:
            cursor = await db.execute("SELECT name FROM _migrations")
            applied = {row[0] for row in await cursor.fetchall()}
        except aiosqlite.OperationalError:
            applied = set()

        # Get migration files
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            print("No migration files found.")
            return

        # Filter to target if specified
        if target is not None:
            prefix = f"{target:03d}_"
            migration_files = [f for f in migration_files if f.name.startswith(prefix)]
            if not migration_files:
                print(f"No migration found with number {target}")
                return

        # Apply pending migrations
        count = 0
        for mf in migration_files:
            if mf.name in applied:
                if target is not None:
                    print(f"Migration {mf.name} already applied.")
                continue

            print(f"Applying: {mf.name}")
            sql = mf.read_text()
            await db.executescript(sql)
            await db.execute("INSERT INTO _migrations (name) VALUES (?)", (mf.name,))
            await db.commit()
            count += 1

        if count == 0:
            print("All migrations already applied.")
        else:
            print(f"\nApplied {count} migration(s).")


def run_postgres_migrations(conn_str: str, target: int | None = None) -> None:
    """Run migrations on PostgreSQL database."""
    import psycopg2

    print("Running migrations on PostgreSQL")

    conn = psycopg2.connect(conn_str)
    conn.autocommit = False
    cur = conn.cursor()

    try:
        # Ensure _migrations table exists
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

        # Get applied migrations
        cur.execute("SELECT name FROM _migrations")
        applied = {row[0] for row in cur.fetchall()}

        # Get migration files
        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            print("No migration files found.")
            return

        # Filter to target if specified
        if target is not None:
            prefix = f"{target:03d}_"
            migration_files = [f for f in migration_files if f.name.startswith(prefix)]
            if not migration_files:
                print(f"No migration found with number {target}")
                return

        # Apply pending migrations
        count = 0
        for mf in migration_files:
            if mf.name in applied:
                if target is not None:
                    print(f"Migration {mf.name} already applied.")
                continue

            print(f"Applying: {mf.name}")
            sql = mf.read_text()

            # PostgreSQL compatibility: adjust SQLite-specific syntax
            sql = sql.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
            sql = sql.replace("BLOB", "BYTEA")

            cur.execute(sql)
            cur.execute("INSERT INTO _migrations (name) VALUES (%s)", (mf.name,))
            conn.commit()
            count += 1

        if count == 0:
            print("All migrations already applied.")
        else:
            print(f"\nApplied {count} migration(s).")

    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cur.close()
        conn.close()


async def run_migrations(target: int | None = None) -> None:
    """Run database migrations."""
    db_type, conn_str = get_db_info()

    if db_type == "sqlite":
        await run_sqlite_migrations(conn_str, target)
    else:
        run_postgres_migrations(conn_str, target)


async def show_status() -> None:
    """Show migration status."""
    db_type, conn_str = get_db_info()
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    if db_type == "sqlite":
        import aiosqlite

        if not Path(conn_str).exists():
            print(f"Database does not exist: {conn_str}")
            print("\nPending migrations:")
            for f in migration_files:
                print(f"  - {f.name}")
            return

        async with aiosqlite.connect(conn_str) as db:
            try:
                cursor = await db.execute("SELECT name FROM _migrations")
                applied = {row[0] for row in await cursor.fetchall()}
            except aiosqlite.OperationalError:
                applied = set()

            print("Migration status:")
            for f in migration_files:
                status = "✓" if f.name in applied else "○"
                print(f"  {status} {f.name}")
    else:
        import psycopg2

        conn = psycopg2.connect(conn_str)
        cur = conn.cursor()
        try:
            cur.execute("SELECT name FROM _migrations")
            applied = {row[0] for row in cur.fetchall()}
        except psycopg2.ProgrammingError:
            applied = set()
        finally:
            cur.close()
            conn.close()

        print("Migration status:")
        for f in migration_files:
            status = "✓" if f.name in applied else "○"
            print(f"  {status} {f.name}")


# Entry points for pyproject.toml scripts


def run_all() -> None:
    """Entry point for `uv run all-migrations`."""
    asyncio.run(run_migrations())


def run_single() -> None:
    """Entry point for `uv run migrations --n <number>`."""
    parser = argparse.ArgumentParser(description="Run a specific migration")
    parser.add_argument(
        "--n",
        type=int,
        required=True,
        help="Migration number to run (e.g., 1 for 001_init.sql)",
    )
    args = parser.parse_args()
    asyncio.run(run_migrations(target=args.n))


def main() -> None:
    """Main entry point for `python -m gatekeeper.db.migrate`."""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "status":
        asyncio.run(show_status())
    else:
        asyncio.run(run_migrations())


if __name__ == "__main__":
    main()
