from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from backend.app.core.database import get_db
from backend.app.models.user import User
from backend.app.api.v1.auth import get_current_user

router = APIRouter()

class UserResponse(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": True}

class UserUpdateRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None

@router.get("", response_model=List[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lấy danh sách tất cả người dùng (Chỉ Admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
        
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    
    # Chuyển đổi định dạng ngày giờ cho pydantic response
    response_users = []
    for user in users:
        response_users.append(
            UserResponse(
                id=user.id,
                full_name=user.full_name,
                email=user.email,
                role=user.role,
                is_active=user.is_active,
                created_at=user.created_at.isoformat() if user.created_at else ""
            )
        )
    return response_users

@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    payload: UserUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cập nhật thông tin người dùng (Chỉ Admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
        
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
        
    if payload.role is not None:
        if payload.role not in ["citizen", "admin"]:
            raise HTTPException(status_code=400, detail="Vai trò không hợp lệ")
        user.role = payload.role
        
    if payload.is_active is not None:
        user.is_active = payload.is_active
        
    await db.commit()
    
    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at.isoformat() if user.created_at else ""
    )

@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Xóa người dùng (Chỉ Admin)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Không có quyền truy cập")
        
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Không thể tự xóa tài khoản của chính mình")
        
    user = await db.scalar(select(User).where(User.id == user_id))
    if not user:
        raise HTTPException(status_code=404, detail="Không tìm thấy người dùng")
        
    # NOTE: Dữ liệu liên quan (conversations, documents, forms, reports) 
    # nên được cascade delete hoặc xử lý theo nghiệp vụ nếu có khóa ngoại.
    
    await db.delete(user)
    await db.commit()
    return {"detail": "Đã xóa người dùng thành công"}
