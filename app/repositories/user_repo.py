from db.connection import acquire, release


async def create_user(email: str, hashed_password: str) -> dict:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            "INSERT INTO users (email, hashed_password) VALUES ($1, $2) RETURNING id, email, created_at",
            email, hashed_password,
        )
        return dict(row)
    finally:
        await release(conn)


async def get_user_by_email(email: str) -> dict | None:
    conn = await acquire()
    try:
        row = await conn.fetchrow("SELECT id, email, hashed_password, created_at FROM users WHERE LOWER(email) = LOWER($1)", email)
        return dict(row) if row else None
    finally:
        await release(conn)


async def get_user_by_id(user_id: str) -> dict | None:
    conn = await acquire()
    try:
        row = await conn.fetchrow("SELECT id, email, created_at FROM users WHERE id = $1::uuid", user_id)
        return dict(row) if row else None
    finally:
        await release(conn)
