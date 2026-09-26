from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.core.database import get_db
from backend.app.models.conversation import Message, Conversation
from backend.app.models.evaluation import EvaluationRun
from backend.app.models.document import Document, DocumentChunk
from datetime import datetime, timedelta, date

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

@router.get("/overview")
async def get_overview(db: AsyncSession = Depends(get_db)):
    # 1. Lấy thông tin từ EvaluationRun
    eval_stmt = select(EvaluationRun).order_by(EvaluationRun.created_at.desc()).limit(6)
    eval_res = await db.execute(eval_stmt)
    eval_runs = eval_res.scalars().all()
    eval_runs.reverse()  # Sắp xếp từ cũ nhất đến mới nhất (trong 6 tuần/lần gần nhất)

    if eval_runs:
        latest = eval_runs[-1]
        metrics = {
            "faithfulness": round((latest.faithfulness or 0) * 100, 1),
            "answer_relevancy": round((latest.answer_relevancy or 0) * 100, 1),
            "context_precision": round((latest.context_precision or 0) * 100, 1),
            "fallback_rate": round(100 - (latest.answer_relevancy or 0) * 100, 1) # Just a fallback proxy for now
        }
        
        # Calculate diffs (compare with previous run)
        if len(eval_runs) > 1:
            prev = eval_runs[-2]
            metrics["faithfulness_diff"] = round(((latest.faithfulness or 0) - (prev.faithfulness or 0)) * 100, 1)
            metrics["relevancy_diff"] = round(((latest.answer_relevancy or 0) - (prev.answer_relevancy or 0)) * 100, 1)
            metrics["precision_diff"] = round(((latest.context_precision or 0) - (prev.context_precision or 0)) * 100, 1)
        else:
            metrics["faithfulness_diff"] = 0
            metrics["relevancy_diff"] = 0
            metrics["precision_diff"] = 0
    else:
        metrics = {
            "faithfulness": 0, "answer_relevancy": 0, "context_precision": 0, "fallback_rate": 0,
            "faithfulness_diff": 0, "relevancy_diff": 0, "precision_diff": 0
        }

    chart_data = []
    for run in eval_runs:
        chart_data.append({
            "label": run.created_at.strftime("Tuần %W") if run.created_at else "Run",
            "faithfulness": round((run.faithfulness or 0) * 100),
            "relevancy": round((run.answer_relevancy or 0) * 100)
        })

    # 2. Lấy thông tin Data Stats
    total_indexed_docs = await db.scalar(select(func.count(Document.id)).where(Document.status == "indexed"))
    total_chunks = await db.scalar(select(func.count(DocumentChunk.id)))
    
    today_start = datetime.combine(date.today(), datetime.min.time())
    questions_today = await db.scalar(select(func.count(Message.id)).where(Message.role == "user", Message.created_at >= today_start))
    
    up = await db.scalar(select(func.count(Message.id)).where(Message.feedback == 1, Message.created_at >= today_start))
    down = await db.scalar(select(func.count(Message.id)).where(Message.feedback == -1, Message.created_at >= today_start))
    total_feedback_today = (up or 0) + (down or 0)
    positive_feedback_pct = int(round((up / total_feedback_today) * 100)) if total_feedback_today > 0 else 0
    
    data_stats = {
        "indexed_docs": total_indexed_docs or 0,
        "total_chunks": total_chunks or 0,
        "questions_today": questions_today or 0,
        "positive_feedback_pct": positive_feedback_pct
    }

    # 3. Needs attention (Low confidence or fallback questions)
    attention_stmt = (
        select(Message.id, Message.content, Message.confidence, Message.created_at, Message.conversation_id, Message.intent, Message.is_fallback)
        .where((Message.is_fallback == True) | (Message.confidence < 0.6))
        .where(Message.role == 'assistant')
        .order_by(Message.created_at.desc())
        .limit(10)
    )
    attention_res = await db.execute(attention_stmt)
    
    needs_attention = []
    for msg in attention_res.fetchall():
        user_msg = await db.scalar(
            select(Message.content)
            .where(Message.conversation_id == msg.conversation_id, Message.role == 'user', Message.created_at <= msg.created_at)
            .order_by(Message.created_at.desc()).limit(1)
        )
        conf_pct = int(round((msg.confidence or 0) * 100)) if msg.confidence is not None else 0
        needs_attention.append({
            "id": str(msg.id),
            "question": user_msg or 'Không rõ câu hỏi',
            "answer": msg.content or '',
            "confidence": conf_pct,
            "is_fallback": bool(msg.is_fallback),
            "intent": msg.intent or 'Hỏi đáp chung',
            "conversation_id": str(msg.conversation_id),
            "created_at": msg.created_at.strftime("%H:%M %d/%m/%Y") if msg.created_at else ""
        })

    return {
        "metrics": metrics,
        "chart_data": chart_data,
        "data_stats": data_stats,
        "needs_attention": needs_attention
    }
