from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
    get_valid_refresh_token,
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
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class AuthResponse(BaseModel):
    token: str
    user_id: str
    refresh_token: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class LogoutResponse(BaseModel):
    message: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: AuthRequest, request: Request):
    allowed, retry_after = check_auth_rate_limit(request.client.host, "register")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many registration attempts. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    hashed = hash_password(body.password)
    user = await create_user(body.email, hashed)
    user_id = str(user["id"])

    token = create_jwt(user_id)

    raw_refresh = create_refresh_token_value()
    refresh_hash = hash_refresh_token(raw_refresh)
    refresh_expiry = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
    await create_refresh_token(user_id, refresh_hash, refresh_expiry)

    return AuthResponse(token=token, user_id=user_id, refresh_token=raw_refresh)


@router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest, request: Request):
    allowed, retry_after = check_auth_rate_limit(request.client.host, "login")
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Retry after {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    user = await get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    user_id = str(user["id"])

    token = create_jwt(user_id)

    raw_refresh = create_refresh_token_value()
    refresh_hash = hash_refresh_token(raw_refresh)
    refresh_expiry = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
    await create_refresh_token(user_id, refresh_hash, refresh_expiry)

    return AuthResponse(token=token, user_id=user_id, refresh_token=raw_refresh)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(body: RefreshRequest):
    token_hash = hash_refresh_token(body.refresh_token)
    valid = await get_valid_refresh_token(token_hash)
    if valid:
        user_id = str(valid["user_id"])
        new_access = create_jwt(user_id)
        new_raw_refresh = create_refresh_token_value()
        new_hash = hash_refresh_token(new_raw_refresh)
        new_expiry = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
        await rotate_refresh_token(token_hash, new_hash, new_expiry)
        return AuthResponse(token=new_access, user_id=user_id, refresh_token=new_raw_refresh)

    existing = await get_refresh_token_by_hash(token_hash)
    if existing:
        await revoke_all_refresh_tokens(str(existing["user_id"]))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token reused. All sessions have been revoked.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid refresh token.",
    )


@router.post("/logout", response_model=LogoutResponse)
async def logout(body: LogoutRequest, current_user: dict = Depends(require_current_user)):
    token_hash = hash_refresh_token(body.refresh_token)
    await revoke_refresh_token(token_hash)
    return LogoutResponse(message="Logged out successfully")


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
