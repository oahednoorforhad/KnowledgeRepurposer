from db.connection import acquire, release


async def upsert_profile(user_id: str, fields: dict) -> dict:
    conn = await acquire()
    try:
        row = await conn.fetchrow(
            """
            INSERT INTO user_profiles (user_id, name, job_title, niche, tone, linkedin_headline, bio, sample_posts, updated_at)
            VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, now())
            ON CONFLICT (user_id)
            DO UPDATE SET
                name = EXCLUDED.name,
                job_title = EXCLUDED.job_title,
                niche = EXCLUDED.niche,
                tone = EXCLUDED.tone,
                linkedin_headline = EXCLUDED.linkedin_headline,
                bio = EXCLUDED.bio,
                sample_posts = EXCLUDED.sample_posts,
                updated_at = now()
            RETURNING *
            """,
            user_id,
            fields.get("name"),
            fields.get("job_title"),
            fields.get("niche"),
            fields.get("tone"),
            fields.get("linkedin_headline"),
            fields.get("bio"),
            fields.get("sample_posts"),
        )
        return dict(row)
    finally:
        await release(conn)


async def get_profile(user_id: str) -> dict | None:
    conn = await acquire()
    try:
        row = await conn.fetchrow("SELECT * FROM user_profiles WHERE user_id = $1::uuid", user_id)
        return dict(row) if row else None
    finally:
        await release(conn)
