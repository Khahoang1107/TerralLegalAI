"""
TerraLegalAI — Form Filling Agent
Handles extracting form fields from conversation history using LLM structured outputs.
"""
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from backend.app.core.config import settings

logger = logging.getLogger(__name__)

class ExtractedField(BaseModel):
    key: str = Field(description="The unique key of the field")
    value: str = Field(description="The extracted value, or empty string if not extractable")

class FormExtractionResult(BaseModel):
    extracted_fields: List[ExtractedField] = Field(description="List of fields to update in collected_data")
    is_complete: bool = Field(description="True ONLY if every single Required field now has a non-empty value. False otherwise.")
    assistant_reply: str = Field(description="The next conversational message to send to the user")
    next_field_key: Optional[str] = Field(default=None, description="The key of the field you are asking the user about in this turn (null if is_complete=true)")
    next_field_name: Optional[str] = Field(default=None, description="The human-readable name of the field you are asking about (null if is_complete=true)")

class FormAgent:
    def __init__(self):
        self.client = genai.Client(api_key=settings.gemini_api_key)
        self.model = settings.gemini_model

    async def run_extraction(
        self,
        form_name: str,
        form_fields: List[Dict[str, Any]],
        collected_data: Dict[str, str],
        chat_history: List[Dict[str, str]],
        user_message: str,
        rag_context: str = "",
        last_asked_field: Optional[Dict[str, str]] = None,
    ) -> FormExtractionResult:
        """
        Uses LLM to extract form fields from the conversation and decide the next step.
        last_asked_field: {"key": "field_9002", "name": "Số CMND/CCCD"} — the field we asked in the PREVIOUS turn.
        """
        schema_desc = []
        for f in form_fields:
            req = "Bắt buộc" if f.get("required") else "Tùy chọn"
            desc = f.get("description", "")
            field_type = f.get("type", "string")
            schema_desc.append(
                f"- {f.get('name', f.get('key', '?'))} "
                f"(Key: {f.get('key', '')}, Kiểu: {field_type}, {req}): {desc}"
            )

        schema_text = "\n".join(schema_desc)
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-16:]])
        
        # Build collected_data display with field names for clarity
        field_key_to_name = {f.get("key", ""): f.get("name", f.get("key", "")) for f in form_fields}
        collected_display = "\n".join([
            f"  - {field_key_to_name.get(k, k)} (key={k}): {v}"
            for k, v in collected_data.items()
        ]) or "  (Chua co du lieu nao)"

        # Separate: personal fields (ask user) vs legal/auto fields (auto-fill)
        auto_fill_fields = [
            f for f in form_fields
            if "[TU_DONG_DIEN]" in f.get("description", "") or not f.get("required", True)
        ]
        personal_fields = [
            f for f in form_fields
            if f not in auto_fill_fields
        ]
        auto_fill_display = "\n".join([
            f"  - {f.get('name', f.get('key','?'))} (key={f.get('key','')}): Tu dong dien bang RAG, KHONG hoi nguoi dung"
            for f in auto_fill_fields
        ]) or "  (Khong co)"

        # Determine missing PERSONAL required fields only
        missing_required = [
            f for f in personal_fields
            if f.get("required") and not collected_data.get(f.get("key", ""))
        ]
        missing_display = "\n".join([
            f"  - {f.get('name', f.get('key', '?'))} (key={f.get('key', '')})"
            for f in missing_required
        ]) or "  (Khong con truong bat buoc nao con thieu - co the hoan thanh!)"


        last_asked_str = ""
        if last_asked_field and last_asked_field.get("key"):
            last_asked_str = f"""
### TRƯỜNG BẠN VỪA HỎI TRONG LƯỢT TRƯỚC:
Key: {last_asked_field['key']}
Tên: {last_asked_field.get('name', '')}
→ Tin nhắn cuối của người dùng là CÂU TRẢ LỜI cho trường này.
→ BẮT BUỘC phải trích xuất câu trả lời đó và gán vào key "{last_asked_field['key']}", NGAY CẢ KHI giá trị đó đã xuất hiện ở trường khác trong collected_data.
"""
        else:
            last_asked_str = "\n### TRƯỜNG BẠN VỪA HỎI TRONG LƯỢT TRƯỚC: (không có — đây là lượt đầu tiên)\n"

        import datetime
        today = datetime.date.today()
        today_str = f"{today.day:02d}/{today.month:02d}/{today.year}"
        day_str = str(today.day)
        month_str = str(today.month)
        year_str = str(today.year)

        prompt = f"""Bạn là AI Agent chuyên hỗ trợ người dùng điền biểu mẫu thủ tục hành chính đất đai.
Nhiệm vụ của bạn là thu thập thông tin từ người dùng để hoàn thiện biểu mẫu "{form_name}".

### CÁC TRƯỜNG THÔNG TIN CẦN THU THẬP:
{schema_text}

### KHO TRI THỨC PHÁP LÝ (để tự điền các trường pháp lý):
{rag_context if rag_context else "Không có thông tin bổ sung."}

### THÔNG TIN ĐÃ THU THẬP (KHÔNG được hỏi lại các trường này):
{collected_display}

### CÁC TRƯỜNG TỰ ĐỘNG ĐIỀN (TUYỆT ĐỐI KHÔNG HỎI NGƯỜI DÙNG - tự điền bằng RAG hoặc suy luận):
{auto_fill_display}

### CÁC TRƯỜNG CÁ NHÂN CÒN THIẾU (CHỈ hỏi từ danh sách này, không hỏi gì khác):
{missing_display}

{last_asked_str}

### LỊCH SỬ TRÒ CHUYỆN:
{history_text}
user: {user_message}

---
### QUY TRÌNH XỬ LÝ (thực hiện theo đúng thứ tự):

**BƯỚC 1 — GÁN CÂU TRẢ LỜI VỪA NHẬN:**
Nếu có "TRƯỜNG BẠN VỪA HỎI TRONG LƯỢT TRƯỚC", hãy:
- Lấy nội dung tin nhắn cuối của người dùng (user: {user_message})
- Gán nguyên vẹn vào key đó trong extracted_fields
- Giữ nguyên giá trị người dùng cung cấp (không rút gọn, không cắt bỏ chữ)
- KHÔNG quan tâm dữ liệu đó có giống trường khác hay không

**BƯỚC 2 — TỰ ĐỘNG ĐIỀN TRƯỜNG PHÁP LÝ (không hỏi người dùng):**
Chỉ đối với các trường có chứa [TU_DONG_DIEN] trong mô tả (như Nơi nhận, Lệ phí...), hãy tự động trích xuất thông tin từ KHO TRI THỨC để điền.
- Nếu không tìm thấy thông tin trong KHO TRI THỨC, TUYỆT ĐỐI KHÔNG điền "Theo quy định". Hãy trả về chuỗi rỗng "" hoặc không đưa trường đó vào extracted_fields.
- TUYỆT ĐỐI KHÔNG tự động điền các trường CÁ NHÂN (các trường không có chữ [TU_DONG_DIEN]). Nếu thiếu trường cá nhân, phải để trống để hệ thống biết mà hỏi tiếp.

**BƯỚC 3 — TỰ ĐỘNG SUY LUẬN CÁC TRƯỜNG ĐẶC BIỆT:**
- Trường "Ngày" → điền "{day_str}"
- Trường "Tháng" → điền "{month_str}"  
- Trường "Năm" → điền "{year_str}"
- Trường "Tỉnh (Nơi viết)" hoặc tương tự → lấy tỉnh/thành từ trường Địa chỉ đã thu thập (nếu có) để điền, KHÔNG hỏi người dùng.

**BƯỚC 4 — KIỂM TRA HOÀN THÀNH:**
Sau khi tổng hợp tất cả dữ liệu (bao gồm collected_data cũ + các trường vừa gán ở Bước 1 + các trường tự điền ở Bước 2, Bước 3):
- Nếu ĐÃ ĐẦY ĐỦ tất cả các trường "Bắt buộc" → set is_complete = true, next_field_key = null
- Nếu VẪN CÒN trường "Bắt buộc" CHƯA CÓ DỮ LIỆU (không tính các trường bạn vừa tự điền) → set is_complete = false, chọn 1 trường CÁ NHÂN còn thiếu để hỏi, set next_field_key và next_field_name cho trường đó.

**BƯỚC 5 — SINH CÂU TRẢ LỜI (assistant_reply):**
- Nếu người dùng ĐẶT CÂU HỎI (ví dụ: "gửi đi đâu?", "tại sao cần thông tin này?"), bạn PHẢI TRẢ LỜI câu hỏi đó ngắn gọn dựa vào KHO TRI THỨC. Sau khi trả lời, mới tiếp tục hỏi thông tin.
- Nếu is_complete = false: Hỏi đúng 1 câu về trường CÁ NHÂN bạn chọn ở Bước 4 (ghép sau câu trả lời nếu có), lịch sự và tự nhiên. 
  → TUYỆT ĐỐI KHÔNG HỎI các trường đã có trong collected_data.
  → TUYỆT ĐỐI KHÔNG HỎI các trường pháp lý (Nơi nhận hồ sơ, Thời hạn, Lệ phí...) hoặc các trường suy luận (Ngày, Tháng, Năm, Tỉnh). Bạn tự điền chúng, cấm hỏi người dùng.
- Nếu is_complete = true: Nói "Dạ, tôi đã thu thập đủ thông tin cần thiết. Biểu mẫu của bạn đã sẵn sàng để xem và tải xuống."
- **QUAN TRỌNG**: is_complete và nội dung assistant_reply PHẢI nhất quán với nhau. Nếu is_complete=false thì KHÔNG được nói "đã đủ" hay "sẵn sàng tải xuống".

**QUY TẮC TRƯỜNG ĐẶC BIỆT:**
- Trường kiểu "boolean": hỏi dạng "Bạn có [tên trường] không?". Nhận "có/yes/đúng/rồi" → lưu "có"; "không/no/chưa" → lưu "không".
- Trường "Tùy chọn" mà người dùng nói "không có" / "bỏ qua" → lưu "__SKIPPED__" và hỏi trường tiếp theo.
- Trường "Bắt buộc" mà người dùng nói "không có" → lưu "" (rỗng) và giải thích đây là bắt buộc theo pháp luật.

Phản hồi phải tuân thủ JSON schema được yêu cầu.
"""

        try:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=FormExtractionResult,
                temperature=0.1,
            )
            
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )
            
            if hasattr(response, "parsed") and response.parsed is not None:
                return response.parsed
            else:
                import json
                text = response.text
                if text.startswith("```json"):
                    text = text[7:]
                elif text.startswith("```"):
                    text = text[3:]
                if text.endswith("```"):
                    text = text[:-3]
                text = text.strip()
                data = json.loads(text)
                return FormExtractionResult.model_validate(data)

        except Exception as e:
            logger.error(f"Error in FormAgent extraction: {e}", exc_info=True)
            return FormExtractionResult(
                extracted_fields=[],
                is_complete=False,
                assistant_reply="Xin lỗi, tôi đang gặp khó khăn trong việc xử lý thông tin. Bạn có thể cung cấp lại được không?",
                next_field_key=None,
                next_field_name=None,
            )
