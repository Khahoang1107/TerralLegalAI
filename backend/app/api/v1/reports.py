from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.conversation import Message, Conversation
from datetime import datetime, timedelta

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get("/stats")
async def get_report_stats(db: AsyncSession = Depends(get_db)):
    # 1. Phản hồi người dùng (feedback_stats)
    stmt = select(
        func.count(Message.id).filter(Message.feedback == 1).label('up'),
        func.count(Message.id).filter(Message.feedback == -1).label('down')
    )
    res = await db.execute(stmt)
    up, down = res.fetchone()
    total_feedback = (up or 0) + (down or 0)
    
    if total_feedback > 0:
        up_pct = int(round((up / total_feedback) * 100))
        down_pct = int(round((down / total_feedback) * 100))
    else:
        up_pct, down_pct = 0, 0

    # 2. Chủ đề được hỏi nhiều (topic_stats)
    # Lấy 30 ngày gần nhất
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    topic_stmt = (
        select(Conversation.procedure_type, func.count(Conversation.id).label('total'))
        .where(Conversation.created_at >= thirty_days_ago)
        .where(Conversation.procedure_type.isnot(None))
        .group_by(Conversation.procedure_type)
        .order_by(func.count(Conversation.id).desc())
        .limit(3)
    )
    topic_res = await db.execute(topic_stmt)
    topics = topic_res.fetchall()
    
    total_convs = sum(t.total for t in topics)
    
    topic_stats = []
    # Map procedure type to display name
    proc_map = {
        'chuyen_nhuong': 'Chuyển nhượng đất',
        'cap_doi': 'Cấp đổi Giấy chứng nhận',
        'all': 'Khác / Tổng hợp',
        'khac': 'Khác'
    }
    for t in topics:
        pct = int(round((t.total / total_convs) * 100)) if total_convs > 0 else 0
        topic_stats.append({
            'name': proc_map.get(t.procedure_type, t.procedure_type),
            'percentage': pct
        })

    # 3. Câu hỏi fallback gần đây (fallback_logs)
    fallback_stmt = (
        select(Message.content, Message.confidence, Message.created_at, Message.conversation_id)
        .where(Message.is_fallback == True)
        .where(Message.role == 'assistant')
        .order_by(Message.created_at.desc())
        .limit(5)
    )
    fallback_res = await db.execute(fallback_stmt)
    
    fallback_logs = []
    for msg in fallback_res.fetchall():
        # Tìm câu hỏi của user trước đó trong cùng conversation
        user_msg_stmt = (
            select(Message.content)
            .where(Message.conversation_id == msg.conversation_id)
            .where(Message.role == 'user')
            .where(Message.created_at <= msg.created_at)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        user_msg_res = await db.execute(user_msg_stmt)
        user_q = user_msg_res.scalar()
        
        fallback_logs.append({
            'question': user_q or 'Không rõ',
            'time': msg.created_at.strftime('%H:%M'),
            'reason': f"Không tìm thấy ngữ cảnh đủ tin cậy · similarity {round(msg.confidence or 0, 2)}"
        })

    return {
        "feedback_stats": {
            "total": total_feedback,
            "up_pct": up_pct,
            "down_pct": down_pct
        },
        "topic_stats": topic_stats,
        "fallback_logs": fallback_logs
    }
