import os

import asyncpg


pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        dsn = os.getenv("DATABASE_URL")
        if not dsn:
            raise RuntimeError("DATABASE_URL is not set. Use your Supabase pooler connection string.")
        # Supabase's transaction pooler (port 6543) can't keep prepared statements
        # across transactions, so asyncpg's statement cache must be off.
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10, statement_cache_size=0)
    return pool


async def close_pool() -> None:
    global pool
    if pool is not None:
        await pool.close()
        pool = None


async def acquire() -> asyncpg.Connection:
    p = await get_pool()
    return await p.acquire()


async def release(conn: asyncpg.Connection) -> None:
    p = pool
    if p is not None:
        await p.release(conn)
