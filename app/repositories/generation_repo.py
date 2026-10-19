from db.connection import acquire, release


async def create_generation(
    user_id: str,
    source_url: str | None,
    source_type: str,
    raw_content: str | None,
    creative_direction: str | None,
    generated_post: str,
    model_used: str | None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    estimated_cost_usd: float | None = None,
) -> dict:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO generations (user_id, source_url, source_type, raw_content, creative_direction, generated_post, model_used, input_tokens, output_tokens, estimated_cost_usd)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING *
            """,
            user_id, source_url, source_type, raw_content, creative_direction, generated_post, model_used,
            input_tokens, output_tokens, estimated_cost_usd,
        )
        return dict(row)
    finally:
        await release(conn)


async def list_generations(user_id: str) -> list[dict]:
    conn = await acquire()
    try:
        rows = await conn.fetch(
            "SELECT * FROM generations WHERE user_id = $1::uuid ORDER BY created_at DESC",
            user_id,
        )
        return [dict(r) for r in rows]
    finally:
        await release(conn)


async def get_generation(generation_id: str, user_id: str) -> dict | None:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            "SELECT * FROM generations WHERE id = $1::uuid AND user_id = $2::uuid",
            generation_id, user_id,
        )
        return dict(row) if row else None
    finally:
        await release(conn)


async def update_status(generation_id: str, user_id: str, status: str) -> dict | None:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            "UPDATE generations SET status = $3 WHERE id = $1::uuid AND user_id = $2::uuid RETURNING *",
            generation_id, user_id, status,
        )
        return dict(row) if row else None
    finally:
        await release(conn)


async def update_post(generation_id: str, user_id: str, generated_post: str) -> dict | None:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            "UPDATE generations SET generated_post = $3 WHERE id = $1::uuid AND user_id = $2::uuid RETURNING *",
            generation_id, user_id, generated_post,
        )
        return dict(row) if row else None
    finally:
        await release(conn)


async def delete_generation(generation_id: str, user_id: str) -> bool:
    conn = await acquire()
    try:
        result = await conn.execute(
            "DELETE FROM generations WHERE id = $1::uuid AND user_id = $2::uuid",
            generation_id, user_id,
        )
        return "DELETE 1" in result
    finally:
        await release(conn)
