from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Dict, Any

from backend.app.core.database import get_db
from backend.app.models.setting import SystemSetting
from pydantic import BaseModel

router = APIRouter(prefix="/settings", tags=["Settings"])

class SettingUpdate(BaseModel):
    value: str
    description: str | None = None

@router.get("/")
async def get_all_settings(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SystemSetting))
    settings = result.scalars().all()
    return [{"key": s.key, "value": s.value, "description": s.description} for s in settings]

@router.get("/{key}")
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalars().first()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": setting.key, "value": setting.value, "description": setting.description}

@router.put("/{key}")
async def update_setting(key: str, payload: SettingUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalars().first()
    
    if setting:
        setting.value = payload.value
        if payload.description is not None:
            setting.description = payload.description
    else:
        setting = SystemSetting(key=key, value=payload.value, description=payload.description)
        db.add(setting)
        
    await db.commit()
    return {"message": "Setting updated successfully"}
