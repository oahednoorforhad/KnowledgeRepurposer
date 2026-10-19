from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_current_user
from app.repositories.profile_repo import get_profile, upsert_profile

router = APIRouter(prefix="/profile", tags=["profile"])

MAX_SAMPLE_POSTS_CHARS = 6000


@router.get("")
async def get_profile_route(user: dict = Depends(require_current_user)):
    profile = await get_profile(user["id"])
    if profile is None:
        return {}
    return profile


@router.put("")
async def upsert_profile_route(body: dict, user: dict = Depends(require_current_user)):
    allowed = {"name", "job_title", "niche", "tone", "linkedin_headline", "bio", "sample_posts"}
    fields = {k: v for k, v in body.items() if k in allowed}
    bad = [k for k, v in fields.items() if v is not None and not isinstance(v, str)]
    if bad:
        raise HTTPException(status_code=422, detail=f"{', '.join(bad)} must be text.")
    samples = fields.get("sample_posts")
    if samples is not None and len(samples) > MAX_SAMPLE_POSTS_CHARS:
        raise HTTPException(
            status_code=422,
            detail=f"sample_posts must be text of at most {MAX_SAMPLE_POSTS_CHARS} characters.",
        )
    updated = await upsert_profile(user["id"], fields)
    return updated
