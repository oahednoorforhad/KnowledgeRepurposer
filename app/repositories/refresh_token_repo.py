from db.connection import acquire, release


async def create_refresh_token(user_id: str, token_hash: str, expires_at) -> dict:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1::uuid, $2, $3) RETURNING *",
            user_id, token_hash, expires_at,
        )
        return dict(row)
    finally:
        await release(conn)


async def rotate_refresh_token(old_token_hash: str, new_token_hash: str, expires_at) -> dict | None:
    """Atomically revoke the old token (if still valid) and insert its replacement.

    The old row is kept (revoked) so a later replay of it is detected as reuse.
    Returns the new row, or None if the old token was not valid; of two concurrent
    rotations of the same token only one can win.
    """
    conn = await acquire()
    try:
        async with conn.transaction():
            old = await conn.fetchrow(
                "UPDATE refresh_tokens SET revoked_at = now() "
                "WHERE token_hash = $1 AND revoked_at IS NULL AND expires_at > now() RETURNING user_id",
                old_token_hash,
            )
            if old is None:
                return None
            row = await conn.fetchrow(
                "INSERT INTO refresh_tokens (user_id, token_hash, expires_at) VALUES ($1, $2, $3) RETURNING *",
                old["user_id"], new_token_hash, expires_at,
            )
            return dict(row)
    finally:
        await release(conn)


async def revoke_refresh_token(token_hash: str) -> bool:
    conn = await acquire()
    try:
        result = await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = $1",
            token_hash,
        )
        return "UPDATE 1" in result
    finally:
        await release(conn)


async def get_refresh_token_by_hash(token_hash: str) -> dict | None:
    """Return a refresh token row regardless of revoked/expired status."""
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM refresh_tokens WHERE token_hash = $1",
            token_hash,
        )
        return dict(row) if row else None
    finally:
        await release(conn)


async def revoke_all_refresh_tokens(user_id: str) -> int:
    conn = await acquire()
    try:
        result = await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = $1::uuid AND revoked_at IS NULL",
            user_id,
        )
        # result format is "UPDATE <count>"
        parts = result.split()
        return int(parts[1]) if len(parts) == 2 else 0
    finally:
        await release(conn)
