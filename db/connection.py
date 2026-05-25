import os

import asyncpg


pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        dsn = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/postgres")
        pool = await asyncpg.create_pool(dsn, min_size=2, max_size=10)
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
