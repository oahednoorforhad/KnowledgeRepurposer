import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth import (
    REFRESH_TOKEN_EXPIRY_DAYS,
    create_jwt,
    create_refresh_token_value,
    hash_password,
    hash_refresh_token,
    require_current_user,
    verify_password,
)
from app.repositories.refresh_token_repo import (
    create_refresh_token,
    get_refresh_token_by_hash,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.repositories.user_repo import create_user, get_user_by_email, update_user_password
from app.services.rate_limiter import check_auth_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v):
        # Non-strings fall through to EmailStr validation (422) instead of a 500.
        return v.strip().lower() if isinstance(v, str) else v


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


def _enforce_auth_rate_limit(request: Request, endpoint: str) -> None:
    ip = request.client.host if request.client else "unknown"
    allowed, retry_after = check_auth_rate_limit(ip, endpoint)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many {endpoint} attempts. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )


def _refresh_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)


def _set_auth_cookies(response: Response, user_id: str, raw_refresh: str) -> dict:
    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    common = {"httponly": True, "samesite": "lax", "secure": secure, "path": "/"}
    response.set_cookie(key="access_token", value=create_jwt(user_id), **common)
    response.set_cookie(
        key="refresh_token",
        value=raw_refresh,
        max_age=REFRESH_TOKEN_EXPIRY_DAYS * 24 * 3600,
        **common,
    )
    return {"message": "success", "user_id": user_id}


async def _start_session(response: Response, user_id: str) -> dict:
    raw_refresh = create_refresh_token_value()
    await create_refresh_token(user_id, hash_refresh_token(raw_refresh), _refresh_expiry())
    return _set_auth_cookies(response, user_id, raw_refresh)


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: AuthRequest, request: Request, response: Response):
    _enforce_auth_rate_limit(request, "register")
    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = await create_user(body.email, hash_password(body.password))
    return await _start_session(response, str(user["id"]))


@router.post("/login")
async def login(body: AuthRequest, request: Request, response: Response):
    _enforce_auth_rate_limit(request, "login")
    user = await get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return await _start_session(response, str(user["id"]))


@router.post("/refresh")
async def refresh(request: Request, response: Response):
    raw_refresh_token = request.cookies.get("refresh_token")
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing.",
        )
    token_hash = hash_refresh_token(raw_refresh_token)
    new_raw_refresh = create_refresh_token_value()
    rotated = await rotate_refresh_token(token_hash, hash_refresh_token(new_raw_refresh), _refresh_expiry())
    if rotated:
        return _set_auth_cookies(response, str(rotated["user_id"]), new_raw_refresh)

    # Only a token that was explicitly revoked (rotated or logged out) counts as reuse;
    # a merely expired token must not nuke the user's other sessions.
    existing = await get_refresh_token_by_hash(token_hash)
    if existing and existing["revoked_at"] is not None:
        await revoke_all_refresh_tokens(str(existing["user_id"]))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reused. All sessions have been revoked.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token.",
    )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    current_user: dict = Depends(require_current_user),
):
    raw_refresh_token = request.cookies.get("refresh_token")
    if raw_refresh_token:
        token_hash = hash_refresh_token(raw_refresh_token)
        await revoke_refresh_token(token_hash)
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "success"}


@router.post("/change-password")
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(require_current_user),
):
    user_id = str(current_user["id"])
    if not verify_password(body.current_password, current_user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )
    hashed = hash_password(body.new_password)
    await update_user_password(user_id, hashed)
    await revoke_all_refresh_tokens(user_id)
    return {"message": "Password changed successfully"}
