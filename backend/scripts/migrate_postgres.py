"""Apply versioned SQL migrations to the configured Supabase PostgreSQL DB."""
import asyncio
import os
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


async def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    dsn = os.environ.get("SUPABASE_DB_URL")
    if not dsn:
        raise SystemExit("SUPABASE_DB_URL is required")
    migration_dir = Path(__file__).resolve().parents[1] / "migrations"
    conn = await asyncpg.connect(dsn, command_timeout=60)
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        for path in sorted(migration_dir.glob("*.sql")):
            version = path.stem
            applied = await conn.fetchval("SELECT 1 FROM public.schema_migrations WHERE version=$1", version)
            if applied:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute("INSERT INTO public.schema_migrations(version) VALUES($1)", version)
            print(f"Applied {version}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
