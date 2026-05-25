from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import require_current_user
from app.repositories.profile_repo import get_profile, upsert_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("")
async def get_profile_route(user: dict = Depends(require_current_user)):
    profile = await get_profile(user["id"])
    if profile is None:
        return {}
    return profile


@router.put("")
async def upsert_profile_route(body: dict, user: dict = Depends(require_current_user)):
    allowed = {"name", "job_title", "niche", "tone", "linkedin_headline", "bio"}
    fields = {k: v for k, v in body.items() if k in allowed}
    updated = await upsert_profile(user["id"], fields)
    return updated
