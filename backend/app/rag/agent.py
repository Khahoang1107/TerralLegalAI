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
    value: str = Field(description="The extracted value, or empty if not provided")

class FormExtractionResult(BaseModel):
    extracted_fields: List[ExtractedField] = Field(description="List of fields successfully extracted from user messages")
    is_complete: bool = Field(description="True if all required fields are collected, False otherwise")
    assistant_reply: str = Field(description="The conversational response to ask the user for missing fields, or confirm completion")

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
        rag_context: str = ""
    ) -> FormExtractionResult:
        """
        Uses LLM to extract form fields from the conversation and decide the next step.
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
        # Tăng window lịch sử lên 12 tin nhắn để giữ ngữ cảnh tốt hơn
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-12:]])
        
        prompt = f"""Bạn là AI Agent chuyên hỗ trợ người dùng điền biểu mẫu thủ tục hành chính đất đai.
Nhiệm vụ của bạn là trích xuất thông tin người dùng cung cấp và điền vào biểu mẫu "{form_name}".

### CÁC TRƯỜNG THÔNG TIN CẦN THU THẬP (FIELDS):
{schema_text}

### KHO TRI THỨC PHÁP LÝ (RAG CONTEXT):
{rag_context if rag_context else "Không có thông tin bổ sung."}

### THÔNG TIN ĐÃ THU THẬP TRƯỚC ĐÓ:
{collected_data}

### LỊCH SỬ TRÒ CHUYỆN GẦN NHẤT:
{history_text}
user: {user_message}

### YÊU CẦU ĐẶC BIÊT VỀ ĐIỀN THÔNG TIN PHÁP LÝ:
1. Đối với các trường thông tin mang tính cá nhân (Họ tên, CMND, Địa chỉ, Số sổ đỏ...): Hãy hỏi Người dùng nếu còn thiếu.
2. Đối với các trường thông tin pháp lý (như Nơi nộp hồ sơ, Mức lệ phí, Thời hạn, Căn cứ pháp lý...): BẮT BUỘC TỰ ĐỘNG điền bằng cách tra cứu trong KHO TRI THỨC PHÁP LÝ (RAG CONTEXT). TUYỆT ĐỐI KHÔNG HỎI người dùng các thông tin này nếu bạn có thể tự trả lời dựa vào RAG CONTEXT.

### CÁC BƯỚC THỰC HIỆN:
1. Trích xuất các thông tin người dùng vừa cung cấp tương ứng với các trường trong biểu mẫu.
2. Tự động điền các trường pháp lý dựa trên KHO TRI THỨC PHÁP LÝ.
3. Kiểm tra xem ĐÃ ĐỦ các trường "Bắt buộc" (Required) chưa dựa trên 'THÔNG TIN ĐÃ THU THẬP TRƯỚC ĐÓ', dữ liệu vừa trích xuất và KHO TRI THỨC.
4. **Chuẩn hóa định dạng dữ liệu:**
   - Ngày tháng: Luôn chuyển sang dạng "dd/mm/yyyy" (VD: "mùng 3 tháng 7 năm 2026" → "03/07/2026").
   - Số CMND/CCCD: Chỉ giữ lại các chữ số, xóa dấu gạch nếu có.
   - Tên người: Viết hoa chữ cái đầu mỗi từ.
   - **Trường Kiểu "boolean" (ô tick ☑):** Khi hỏi người dùng, hãy đặt câu hỏi dạng Có/Không.
     Nếu người dùng trả lời "có", "yes", "đúng", "x", "rồi" → lưu value = "có".
     Nếu người dùng trả lời "không", "no", "chưa", "không phải" → lưu value = "không".
5. Sinh ra câu trả lời (assistant_reply): 
   - Nếu chưa đủ thông tin bắt buộc (chủ yếu là thông tin cá nhân): Hãy hỏi người dùng cung cấp 1-2 thông tin còn thiếu một cách lịch sự, tự nhiên.
   - Với trường **Kiểu boolean**: hỏi dạng "Bạn có [tên trường] không?" thay vì yêu cầu nhập văn bản.
   - Nếu đã đủ: Thông báo rằng biểu mẫu đã hoàn tất và sẵn sàng tải xuống. Đừng hỏi thêm.

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
                data = json.loads(response.text)
                return FormExtractionResult.model_validate(data)

        except Exception as e:
            logger.error(f"Error in FormAgent extraction: {e}", exc_info=True)
            return FormExtractionResult(
                extracted_fields=[],
                is_complete=False,
                assistant_reply="Xin lỗi, tôi đang gặp khó khăn trong việc xử lý thông tin. Bạn có thể cung cấp lại được không?"
            )
