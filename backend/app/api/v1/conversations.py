from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime

from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation, Message
from backend.app.api.v1.chat import CitationSchema

router = APIRouter(prefix="/conversations")


class ConversationResponse(BaseModel):
    id: str
    title: str
    created_at: datetime
    
    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    citations: Optional[List[CitationSchema]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse]


class UpdateConversationRequest(BaseModel):
    title: str


@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy danh sách cuộc trò chuyện của user."""
    stmt = select(Conversation).where(Conversation.user_id == current_user.id).order_by(Conversation.created_at.desc())
    result = await db.execute(stmt)
    conversations = result.scalars().all()
    return conversations


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Lấy chi tiết một cuộc trò chuyện và tin nhắn."""
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    conversation = await db.scalar(stmt)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")
        
    msg_stmt = select(Message).where(Message.conversation_id == conversation_id).order_by(Message.created_at.asc())
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()
    
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        created_at=conversation.created_at,
        messages=messages
    )


@router.put("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Đổi tên cuộc trò chuyện."""
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    conversation = await db.scalar(stmt)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")
        
    conversation.title = payload.title
    await db.commit()
    await db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Xóa cuộc trò chuyện."""
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    conversation = await db.scalar(stmt)
    if not conversation:
        # DELETE is idempotent: an already removed conversation is the desired state.
        return
        
    await db.delete(conversation)
    await db.commit()

@router.get("/{conversation_id}/export-form")
async def export_conversation_form(
    conversation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Conversation).where(Conversation.id == conversation_id, Conversation.user_id == current_user.id)
    conversation = await db.scalar(stmt)
    if not conversation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy cuộc trò chuyện")
    
    if not conversation.state or not conversation.state.get("is_complete"):
        raise HTTPException(status_code=400, detail="Biểu mẫu chưa được điền hoàn tất")
        
    form_id = conversation.state.get("active_form_id")
    collected_data = conversation.state.get("collected_data", {})
    
    import os
    from docxtpl import DocxTemplate
    from fastapi.responses import FileResponse
    from backend.app.models.form_schema import FormSchema
    
    form = await db.scalar(select(FormSchema).where(FormSchema.id == form_id))
    if not form:
        raise HTTPException(status_code=404, detail="Không tìm thấy cấu trúc biểu mẫu gốc")
        
    template_path = f"backend/data/templates/{form_id}.docx"
    if not os.path.exists(template_path):
        template_path = "backend/data/templates/default.docx"
        if not os.path.exists(template_path):
            raise HTTPException(status_code=404, detail="Không tìm thấy mẫu DOCX")
            
    try:
        doc = DocxTemplate(template_path)
        doc.render(collected_data)
        output_dir = "backend/data/exports"
        os.makedirs(output_dir, exist_ok=True)
        output_path = f"{output_dir}/{form_id}_{conversation_id}.docx"
        doc.save(output_path)
        return FileResponse(
            output_path, 
            filename=f"BieuMau_{form.procedure_type}.docx", 
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi tạo file DOCX: {str(e)}")
