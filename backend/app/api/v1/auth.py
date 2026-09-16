from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.database import get_db
from backend.app.core.security import create_access_token, get_current_user, hash_password, verify_password
from backend.app.models.user import User


router = APIRouter(prefix="/auth")


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    # Existing accounts are identified by email in the database.  The local
    # part (before @) is also accepted as the username displayed by the UI.
    email: str = Field(min_length=2, max_length=255)
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: str

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


def token_response(user: User) -> TokenResponse:
    token, expires_in = create_access_token(user.id, user.role)
    return TokenResponse(access_token=token, expires_in=expires_in, user=UserResponse.model_validate(user))


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_db)):
    email = payload.email.strip().lower()
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email đã được sử dụng")
    user = User(full_name=payload.full_name.strip(), email=email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return token_response(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    identifier = payload.email.strip().lower()
    user = await db.scalar(
        select(User).where(
            or_(
                func.lower(User.email) == identifier,
                func.lower(func.split_part(User.email, "@", 1)) == identifier,
            )
        )
    )
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Tên đăng nhập/email hoặc mật khẩu không chính xác")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tài khoản đã bị khóa")
    return token_response(user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the authenticated user's password after verifying the old one."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu hiện tại không chính xác")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu mới phải khác mật khẩu hiện tại")

    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()
    return {"message": "Đổi mật khẩu thành công"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
