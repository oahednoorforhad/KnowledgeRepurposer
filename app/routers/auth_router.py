from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.auth import create_jwt, hash_password, require_current_user, verify_password
from app.repositories.user_repo import create_user, get_user_by_email

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


class LogoutResponse(BaseModel):
    message: str


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(body: AuthRequest):
    existing = await get_user_by_email(body.email)
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    hashed = hash_password(body.password)
    user = await create_user(body.email, hashed)
    token = create_jwt(str(user["id"]))
    return AuthResponse(token=token, user_id=str(user["id"]))


@router.post("/login", response_model=AuthResponse)
async def login(body: AuthRequest):
    user = await get_user_by_email(body.email)
    if not user or not verify_password(body.password, user["hashed_password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_jwt(str(user["id"]))
    return AuthResponse(token=token, user_id=str(user["id"]))


@router.post("/logout", response_model=LogoutResponse)
async def logout(current_user: dict = Depends(require_current_user)):
    return LogoutResponse(message="Logged out successfully")
