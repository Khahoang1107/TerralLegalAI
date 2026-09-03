"""
TerraLegalAI — Chat API Endpoints
POST /api/v1/chat           — Gửi câu hỏi, nhận câu trả lời RAG
POST /api/v1/messages/{id}/feedback — Gửi feedback 👍/👎
"""
import logging
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Depends, Request
import asyncio

from backend.app.core.config import settings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user
from backend.app.models.user import User
from backend.app.models.conversation import Conversation, Message
from backend.app.models.form_schema import FormSchema
from backend.app.core.form_flow import apply_flow_rules, get_missing_fields, order_fields
import uuid

router = APIRouter()
logger = logging.getLogger(__name__)


# ─── Request / Response schemas ───────────────────────────────────

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000, description="Câu hỏi của người dùng")
    conversation_id: Optional[str] = Field(None, description="ID cuộc hội thoại (để giữ context)")
    procedure_filter: Optional[str] = Field(
        None,
        description="Filter theo thủ tục: chuyen_nhuong | cap_doi | tang_cho | all",
        pattern="^(chuyen_nhuong|cap_doi|tang_cho|all)$",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "question": "Sang tên sổ đỏ cần giấy tờ gì?",
                "procedure_filter": "chuyen_nhuong",
            }
        }
    }


class CitationSchema(BaseModel):
    source_name: str
    article: str = ""
    clause: str = ""
    text_snippet: str = ""
    relevance_score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationSchema]
    confidence: float
    intent: str
    procedure_type: str
    conversation_id: Optional[str]
    message_id: Optional[str]
    latency_ms: int
    is_fallback: bool = False
    form_completed: bool = False
    form_id: Optional[str] = None
    collected_data: Optional[dict] = None


class FeedbackRequest(BaseModel):
    value: int = Field(..., description="1 = thumbs up, -1 = thumbs down", ge=-1, le=1)


# ─── Dependency: RAG Pipeline ─────────────────────────────────────

def get_rag_pipeline(request: Request):
    """
    Dependency injection cho RAG pipeline.
    Lấy pipeline singleton đã được khởi tạo từ app.state trong lifespan.
    """
    if not hasattr(request.app.state, "rag_pipeline"):
        raise HTTPException(status_code=500, detail="RAG Pipeline is not initialized")
    return request.app.state.rag_pipeline

def get_form_agent(request: Request):
    if not hasattr(request.app.state, "form_agent"):
        raise HTTPException(status_code=500, detail="Form Agent is not initialized")
    return request.app.state.form_agent


# ─── Helper ───────────────────────────────────────────────────────

async def _load_chat_history(
    db: AsyncSession, conversation_id: str, max_messages: int = 20
) -> list[dict]:
    """
    Load lịch sử chat gần nhất của một conversation để đưa vào LLM.
    Load từ cuối lên (ORDER BY DESC, LIMIT n) rồi đảo lại để đảm bảo lấy đúng n tin nhắn MỚI NHẤT.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(max_messages)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    # Đảo lại để có thứ tự tăng dần (cũ → mới)
    return [{"role": m.role, "content": m.content} for m in reversed(messages)]


# ─── Endpoints ────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    req: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Gửi câu hỏi và nhận câu trả lời từ RAG pipeline.

    - Câu hỏi được tìm kiếm trong kho tài liệu đất đai Vĩnh Long
    - Trả lời kèm trích dẫn nguồn cụ thể (điều, khoản, văn bản)
    - Hỗ trợ filter theo loại thủ tục
    - Giữ context hội thoại (multi-turn conversation)
    """
    logger.info(f"Chat request from user {current_user.id}: '{request.question[:80]}'")

    try:
        # 1. Manage Conversation
        conv_record = None
        conversation_id = request.conversation_id
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            title = request.question[:50] + "..." if len(request.question) > 50 else request.question
            new_conv = Conversation(
                id=conversation_id,
                user_id=current_user.id,
                title=title,
                procedure_type=request.procedure_filter,
            )
            db.add(new_conv)
            await db.flush()  # flush để lấy ID trước khi add message
            conv_record = new_conv
        else:
            # Verify ownership
            stmt = select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == current_user.id
            )
            existing_conv = await db.scalar(stmt)
            if not existing_conv:
                raise HTTPException(status_code=404, detail="Không tìm thấy cuộc trò chuyện")
            conv_record = existing_conv

        # Detect form intent
        is_form_intent = False
        active_form = None
        collected_data = {}
        flow_state: dict = {}
        last_asked_field = None  # {"key": ..., "name": ...} — field asked in previous turn
        invalid_fields: list = []  # field keys where collected value is invalid
        result = None  # FormExtractionResult — only set in form path

        if conv_record.state and conv_record.state.get("active_form_id"):
            is_form_intent = True
            form_id = conv_record.state["active_form_id"]
            collected_data = conv_record.state.get("collected_data", {})
            flow_state = conv_record.state.get("flow_state", {})
            last_asked_field = conv_record.state.get("last_asked_field")  # may be None
            invalid_fields = conv_record.state.get("invalid_fields", [])  # persisted from prev turn
            active_form = await db.scalar(select(FormSchema).where(FormSchema.id == form_id))

            # ── Nếu form đã hoàn thành trước đó, trả về hướng dẫn xem biểu mẫu ──
            if conv_record.state.get("is_complete") and active_form:
                chat_history = await _load_chat_history(db, conversation_id)
                user_msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role="user",
                    content=request.question,
                )
                db.add(user_msg)
                
                answer_text = "Biểu mẫu của bạn đã hoàn thành! Bạn có thể nhấn nút **\"Xem & Chỉnh sửa biểu mẫu\"** phía trên để xem lại và tải xuống."
                assistant_msg = Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role="assistant",
                    content=answer_text,
                    intent="form_filling",
                )
                db.add(assistant_msg)
                await db.commit()
                
                return ChatResponse(
                    answer=answer_text,
                    citations=[],
                    confidence=1.0,
                    intent="form_filling",
                    procedure_type=active_form.procedure_type,
                    conversation_id=conversation_id,
                    message_id=assistant_msg.id,
                    latency_ms=0,
                    is_fallback=False,
                    form_completed=True,
                    form_id=str(active_form.id),
                    collected_data=collected_data,
                )
            # ─────────────────────────────────────────────────────────────────────
        else:
            # LLM Intent Router: Lấy danh sách biểu mẫu và tự động map câu hỏi
            forms_result = await db.execute(select(FormSchema).where(FormSchema.is_active == True))
            available_forms = forms_result.scalars().all()
            
            if available_forms:
                from google import genai
                from google.genai import types
                from backend.app.core.config import settings
                import json
                
                form_list_str = "\n".join([f"- ID: {f.id} | Tên: {f.name} | Loại thủ tục: {f.procedure_type}" for f in available_forms])
                router_prompt = f"""Phân tích câu hỏi của người dùng và xác định xem họ có muốn ĐIỀN BIỂU MẪU hay không.
Danh sách các biểu mẫu hiện có:
{form_list_str}

Câu hỏi người dùng: "{request.question}"

Yêu cầu:
- Nếu người dùng muốn điền một biểu mẫu có trong danh sách, hãy trả về JSON: {{"intent": "form", "form_id": "<id_của_biểu_mẫu>"}}
- Nếu không (chỉ hỏi thông tin, hỏi luật), hãy trả về JSON: {{"intent": "rag", "form_id": null}}
"""
                try:
                    router_client = genai.Client(api_key=settings.gemini_api_key)
                    router_resp = await router_client.aio.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=router_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=0.0
                        )
                    )
                    router_data = json.loads(router_resp.text)
                    if router_data.get("intent") == "form" and router_data.get("form_id"):
                        selected_id = router_data.get("form_id")
                        active_form = next((f for f in available_forms if str(f.id) == str(selected_id)), None)
                        if active_form:
                            is_form_intent = True
                            conv_record.state = {"active_form_id": str(active_form.id), "collected_data": {}, "flow_state": {}}
                            flag_modified(conv_record, "state")
                            await db.flush()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).error(f"Lỗi khi route intent: {e}")

        # 2. Load lịch sử hội thoại (cho multi-turn context)
        chat_history = await _load_chat_history(db, conversation_id)

        # 3. Save User Message
        user_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="user",
            content=request.question,
        )
        db.add(user_msg)
        await db.commit()

        # 4. Route intent
        answer_text = ""
        citations = []
        retrieved_chunks = []
        confidence = 1.0
        intent_val = ""
        procedure_val = request.procedure_filter or ""
        latency_ms = 0
        is_fallback = False

        if is_form_intent and active_form:
            import time
            start_time = time.time()
            
            # Tích hợp RAG Context lấy kiến thức luật để tự điền biểu mẫu
            rag_context = ""
            try:
                pipeline = get_rag_pipeline(req)
                
                def get_rag_context_sync():
                    query_vector = pipeline.embedding_model.encode_single(active_form.name + " " + active_form.procedure_type)
                    search_proc_type = active_form.procedure_type
                    if search_proc_type in ["chuyen_nhuong", "tang_cho"]:
                        search_proc_type = [search_proc_type, "dang_ky_bien_dong"]
                        
                    raw_results = pipeline.vector_store.search(
                        query_vector=query_vector,
                        top_k=3,
                        procedure_type=search_proc_type,
                        score_threshold=0.6,
                    )
                    return "\n\n".join([r["text"] for r in (raw_results or [])])
                
                rag_context = await asyncio.to_thread(get_rag_context_sync)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Lỗi khi lấy RAG context cho biểu mẫu: {e}")

            agent = get_form_agent(req)
            result = await agent.run_extraction(
                form_name=active_form.name,
                form_fields=active_form.fields,
                collected_data=collected_data,
                chat_history=chat_history,
                user_message=request.question,
                rag_context=rag_context,
                last_asked_field=last_asked_field,
                invalid_fields=invalid_fields,
            )
            
            # ── UPDATE collected_data + DATA QUALITY VALIDATION ────────────────
            from backend.app.rag.agent import is_auto_fill_field, quick_validate_value, get_friendly_name, normalize_field_value
            field_map: dict = {f.get("key", ""): f for f in (active_form.fields or [])}
            new_invalid_fields: list = []

            for extracted in result.extracted_fields:
                if not extracted.value:
                    continue
                if extracted.value == "__SKIPPED__":
                    collected_data[extracted.key] = "__SKIPPED__"
                    continue

                field_def = field_map.get(extracted.key, {})
                # Chuẩn hóa giá trị trước khi validate (boolean → có/không, digit → chỏ số)
                normalized_value = normalize_field_value(field_def, extracted.value)
                # Chỉ validate trường cá nhân (không validate trường tự điền)
                if not is_auto_fill_field(field_def):
                    if not quick_validate_value(field_def, normalized_value):
                        # Giá trị sai kiểu → KHÔNG lưu, đánh dấu invalid để hỏi lại
                        logger.warning(
                            f"Invalid value for '{extracted.key}' ({field_def.get('name', '?')}): "
                            f"'{extracted.value}' (normalized: '{normalized_value}') — removing from collected_data"
                        )
                        # Xóa khỏi collected_data nếu đã tồn tại
                        collected_data.pop(extracted.key, None)
                        new_invalid_fields.append(extracted.key)
                        continue

                collected_data[extracted.key] = normalized_value

            # Deterministic flow: applies/reopens dependent branches and settles
            # one-of groups.  The provenance lets a later parent answer reopen
            # only values skipped automatically, never a user's explicit skip.
            flow_state = apply_flow_rules(active_form.fields or [], collected_data, flow_state)

            # Kết hợp invalid_fields cũ (chưa được hỏi lại) với mới phát hiện
            # Loại bỏ khỏi invalid_fields những key vừa được điền thành công
            successfully_filled = {e.key for e in result.extracted_fields if e.key in collected_data and collected_data[e.key] != "__SKIPPED__"}
            persisted_invalid = [k for k in invalid_fields if k not in successfully_filled]
            invalid_fields = list(set(persisted_invalid + new_invalid_fields))
            # ─────────────────────────────────────────────────────────────────────

            # ── GROUND-TRUTH COMPLETION CHECK (không tin hoàn toàn vào LLM) ──────
            # Dùng is_auto_fill_field() thay vì check chuỗi [TU_DONG_DIEN] — chính xác hơn
            personal_fields = order_fields([
                f for f in (active_form.fields or [])
                if not is_auto_fill_field(f)
            ])
            
            # 1. Tính toán missing_fields thực sự (sau khi đã chạy cascade logic)
            missing_fields = get_missing_fields(personal_fields, collected_data)
            
            invalid_missing = [f for f in missing_fields if f.get("key") in invalid_fields]
            
            # 2. Đánh giá lại is_complete
            # Form hoàn thành khi không còn field nào trong missing_fields VÀ không có invalid_fields
            all_personal_filled = len(missing_fields) == 0 and not invalid_fields
            
            if all_personal_filled:
                logger.info("Ground-truth check: all personal fields filled → forcing is_complete=True")
                from backend.app.rag.agent import FormExtractionResult
                result = FormExtractionResult(
                    extracted_fields=result.extracted_fields,
                    is_complete=True,
                    assistant_reply="Dạ, tôi đã thu thập đủ thông tin cần thiết để hoàn thiện biểu mẫu. Biểu mẫu của bạn đã sẵn sàng để xem và tải xuống.",
                    next_field_key=None,
                    next_field_name=None,
                )
            else:
                # LLM nói xong nhưng thực tế chưa đủ, HOẶC LLM chưa xong nhưng hỏi sai trường
                next_field = (invalid_missing or missing_fields)[0] if missing_fields else None
                missing_names = [get_friendly_name(f) for f in missing_fields]
                
                # Kiểm tra xem LLM có đang hỏi đúng trường không (tránh trường hợp LLM hỏi vào trường đã bị SKIP bởi logic ở trên)
                llm_asked_valid_field = result.next_field_key in [f.get("key") for f in missing_fields]
                
                if result.is_complete or not llm_asked_valid_field:
                    if result.is_complete:
                        logger.warning(f"LLM claimed complete but missing: {missing_names} → forcing is_complete=False")
                    else:
                        logger.warning(f"LLM asked for invalid/skipped field {result.next_field_key}, overriding...")
                        
                    from backend.app.rag.agent import FormExtractionResult, get_friendly_name
                    next_reply = result.assistant_reply
                    if next_field:
                        field_name = get_friendly_name(next_field)
                        next_reply = f"Bạn vui lòng cung cấp thông tin **{field_name}** để tôi tiếp tục điền biểu mẫu nhé?"
                    
                    result = FormExtractionResult(
                        extracted_fields=result.extracted_fields,
                        is_complete=False,
                        assistant_reply=next_reply,
                        next_field_key=next_field.get("key") if next_field else None,
                        next_field_name=next_field.get("name") if next_field else None,
                    )
            # ─────────────────────────────────────────────────────────────────────

            # Lưu last_asked_field để lượt sau biết trường nào vừa được hỏi
            new_last_asked = None
            if not result.is_complete and result.next_field_key:
                new_last_asked = {
                    "key": result.next_field_key,
                    "name": result.next_field_name or result.next_field_key,
                }

            # save state — bao gồm invalid_fields để lượt sau biết trường nào cần hỏi lại
            conv_record.state = {
                "active_form_id": str(active_form.id),
                "collected_data": collected_data,
                "is_complete": result.is_complete,
                "last_asked_field": new_last_asked,
                "invalid_fields": invalid_fields,  # MỚI: trường có dữ liệu không hợp lệ
                "flow_state": flow_state,
            }
            flag_modified(conv_record, "state")
            await db.commit()

            answer_text = result.assistant_reply
            intent_val = "form_filling"
            procedure_val = active_form.procedure_type
            latency_ms = int((time.time() - start_time) * 1000)
        else:
            # 4. Call RAG Pipeline
            pipeline = get_rag_pipeline(req)
            rag_response = await asyncio.to_thread(
                pipeline.query,
                question=request.question,
                procedure_filter=request.procedure_filter,
                chat_history=chat_history,
            )
            answer_text = rag_response.answer
            intent_val = rag_response.intent
            procedure_val = rag_response.procedure_type
            confidence = rag_response.confidence
            latency_ms = rag_response.latency_ms
            is_fallback = rag_response.is_fallback
            retrieved_chunks = [
                # Qdrant / reranker can return numpy.float32. PostgreSQL JSONB
                # only accepts native JSON values, so normalise before persisting.
                {"text": c.text[:200], "score": float(c.score), "source_name": c.source_name}
                for c in rag_response.retrieved_chunks
            ]
            citations = [
                CitationSchema(
                    source_name=c.source_name,
                    article=c.article,
                    clause=c.clause,
                    text_snippet=c.text_snippet,
                    relevance_score=c.relevance_score,
                )
                for c in rag_response.citations
            ]

        # 5. Save Assistant Message (đầy đủ metadata)
        assistant_msg = Message(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            role="assistant",
            content=answer_text,
            intent=intent_val,
            retrieved_chunks=retrieved_chunks,
            citations=[c.model_dump(mode="json") for c in citations],
            confidence=confidence,
            latency_ms=latency_ms,
            is_fallback=is_fallback,
        )
        db.add(assistant_msg)
        await db.commit()

        return ChatResponse(
            answer=answer_text,
            citations=citations,
            confidence=confidence,
            intent=intent_val,
            procedure_type=procedure_val,
            conversation_id=conversation_id,
            message_id=assistant_msg.id,
            latency_ms=latency_ms,
            is_fallback=is_fallback,
            form_completed=(result.is_complete if result is not None else False) if is_form_intent else False,
            form_id=str(active_form.id) if (is_form_intent and active_form) else None,
            collected_data=conv_record.state.get("collected_data") if is_form_intent else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat error: {e}", exc_info=True)
        
        # Xử lý riêng lỗi hết credits từ Gemini API
        if "429" in str(e) and "RESOURCE_EXHAUSTED" in str(e):
            raise HTTPException(
                status_code=429,
                detail="Hệ thống AI đang tạm hết hạn mức (credits). Vui lòng cấu hình lại API Key hoặc liên hệ quản trị viên."
            )
            
        raise HTTPException(
            status_code=500,
            detail=f"Lỗi xử lý câu hỏi: {str(e)}",
        )


@router.post("/messages/{message_id}/feedback", status_code=200)
async def submit_feedback(
    message_id: str,
    payload: FeedbackRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Gửi feedback 👍 (value=1) hoặc 👎 (value=-1) cho một tin nhắn.
    Chỉ có thể feedback tin nhắn của assistant trong conversation của mình.
    """
    stmt = (
        select(Message)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Message.id == message_id,
            Message.role == "assistant",
            Conversation.user_id == current_user.id,
        )
    )
    message = await db.scalar(stmt)
    if not message:
        raise HTTPException(status_code=404, detail="Không tìm thấy tin nhắn")

    message.feedback = payload.value
    await db.commit()
    return {"message_id": message_id, "feedback": payload.value, "status": "saved"}


@router.get("/chat/suggestions")
async def get_suggestions(procedure: Optional[str] = None):
    """Gợi ý câu hỏi phổ biến theo loại thủ tục."""
    suggestions = {
        "chuyen_nhuong": [
            "Hồ sơ chuyển nhượng quyền sử dụng đất gồm những gì?",
            "Chuyển nhượng đất mất bao lâu?",
            "Nộp hồ sơ chuyển nhượng ở đâu?",
            "Điều kiện để chuyển nhượng quyền sử dụng đất là gì?",
            "Tôi bán đất cho người khác thì thủ tục thế nào?",
        ],
        "cap_doi": [
            "Cấp đổi Giấy chứng nhận cần giấy tờ gì?",
            "Sổ đỏ bị rách thì làm thủ tục gì?",
            "Cấp đổi sổ đỏ mất bao lâu?",
            "Nộp hồ sơ cấp đổi GCN ở đâu?",
            "Lệ phí cấp đổi Giấy chứng nhận là bao nhiêu?",
        ],
        "all": [
            "Sang tên sổ đỏ cần giấy tờ gì?",
            "Ba mẹ cho tôi đất thì cần làm thủ tục gì?",
            "Sổ đỏ bị hỏng thì xin cấp đổi thế nào?",
            "Chuyển nhượng đất mất bao lâu?",
            "Nộp hồ sơ đất đai ở đâu tại Vĩnh Long?",
        ],
    }
    key = procedure if procedure in suggestions else "all"
    return {"suggestions": suggestions[key]}
