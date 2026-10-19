from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.auth import require_current_user
from app.repositories.generation_repo import (
    delete_generation,
    get_generation,
    list_generations,
    update_post,
    update_status,
)

router = APIRouter(prefix="/generations", tags=["generations"])


class StatusUpdate(BaseModel):
    status: str


class PostUpdate(BaseModel):
    generated_post: str = Field(min_length=1, max_length=10000)


@router.get("")
async def list_route(user: dict = Depends(require_current_user)):
    return await list_generations(user["id"])


@router.get("/{generation_id}")
async def get_route(generation_id: str, user: dict = Depends(require_current_user)):
    gen = await get_generation(generation_id, user["id"])
    if gen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")
    return gen


@router.patch("/{generation_id}")
async def patch_post_route(generation_id: str, body: PostUpdate, user: dict = Depends(require_current_user)):
    gen = await update_post(generation_id, user["id"], body.generated_post)
    if gen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")
    return gen


@router.patch("/{generation_id}/status")
async def patch_status_route(generation_id: str, body: StatusUpdate, user: dict = Depends(require_current_user)):
    if body.status not in ("draft", "published", "archived"):
        raise HTTPException(status_code=400, detail="Invalid status. Use: draft, published, archived")
    gen = await update_status(generation_id, user["id"], body.status)
    if gen is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")
    return gen


@router.delete("/{generation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_route(generation_id: str, user: dict = Depends(require_current_user)):
    deleted = await delete_generation(generation_id, user["id"])
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation not found")
