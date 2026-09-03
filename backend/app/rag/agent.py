"""
TerraLegalAI — Form Filling Agent
Handles extracting form fields from conversation history using LLM structured outputs.
"""
import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from backend.app.core.config import settings
from backend.app.core.form_flow import get_missing_fields, order_fields

logger = logging.getLogger(__name__)


# ─── Patterns nhận diện trường TỰ ĐỘNG ĐIỀN (không hỏi người dùng) ────────────
import unicodedata


# ─── Patterns nhận diện trường TỰ ĐỘNG ĐIỀN (không hỏi người dùng) ────────────
# Patterns dùng ký tự không dấu để tương thích với mọi cách nhập tên trường
# Sử dụng normalized (NFD stripped) tên trường trước khi match
_AUTO_FILL_NAME_PATTERNS_NORMALIZED: List[str] = [
    r"noi\s*nhan",          # Nơi nhận
    r"tinh.*noi\s*viet",    # Tỉnh (Nơi viết)
    r"noi\s*viet",          # Nơi viết
    r"^ngay$",              # Ngày
    r"^thang$",             # Tháng
    r"^nam$",               # Năm
    r"thoi\s*han",          # Thời hạn
    r"le\s*phi",            # Lệ phí
    r"co\s*quan\s*tiep\s*nhan",          # Cơ quan tiếp nhận
    r"co\s*quan\s*co\s*tham\s*quyen",   # Cơ quan có thẩm quyền
    r"can\s*cu\s*phap\s*ly",            # Căn cứ pháp lý
]

_AUTO_FILL_RE = re.compile(
    "|".join(f"(?:{p})" for p in _AUTO_FILL_NAME_PATTERNS_NORMALIZED),
    re.IGNORECASE,
)


def _normalize_no_diacritic(text: str) -> str:
    """Chuyển chuỗi Unicode có dấu thành không dấu, lowercase."""
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn").lower()


def is_auto_fill_field(field: Dict[str, Any]) -> bool:
    """
    Trả về True nếu trường này nên được tự động điền (không hỏi người dùng).
    Kiểm tra theo 2 cách:
      1. Có cờ is_auto_fill=True
      2. Mô tả chứa tag [TU_DONG_DIEN]
      3. Tên trường (sau khi normalize bỏ dấu) khớp với danh sách pattern
    """
    # Form mới luôn lưu value_source. Giá trị explicit này phải ưu tiên hơn
    # heuristic cũ theo tên (ví dụ "Ngày cấp" không được tự nhiên bị coi là
    # ngày tự động nếu admin đã chọn "Người dùng nhập").
    source = field.get("value_source")
    if source in {"ai_document", "current_date"}:
        return True
    if source == "user_input":
        return False
    if field.get("is_auto_fill"):
        return True
    description = field.get("description", "")
    if "[TU_DONG_DIEN]" in description:
        return True
    field_name = field.get("name", field.get("key", ""))
    normalized = _normalize_no_diacritic(field_name)
    return bool(_AUTO_FILL_RE.search(normalized))


# ─── Validator chất lượng dữ liệu inline ──────────────────────────────────────

# Từ khóa gợi ý người dùng đã nhầm — nhập tên tài liệu thay vì thông tin cá nhân
_DOC_KEYWORDS = re.compile(
    r"\b(bản\s*sao|cccd|cmnd|sổ\s*đỏ|giấy\s*chứng\s*nhận|hộ\s*khẩu|hợp\s*đồng|biên\s*lai|chứng\s*từ|tờ\s*khai)\b",
    re.IGNORECASE | re.UNICODE,
)

_PHONE_RE = re.compile(r"^(0|\+84)[0-9]{8,10}$")

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def quick_validate_value(field: Dict[str, Any], value: str) -> bool:
    """
    Kiểm tra nhanh xem `value` có phù hợp với loại trường `field` không.
    Trả về True = hợp lệ, False = có vẻ sai.
    Chỉ validate các trường cá nhân rõ ràng, không validate trường auto-fill.
    """
    if not value or value == "__SKIPPED__":
        return True  # rỗng/bỏ qua → để flow xử lý riêng

    name = field.get("name", "").lower()
    field_type = field.get("type", "string")

    # Trường "địa chỉ": không được là tên tài liệu
    if "địa chỉ" in name:
        if _DOC_KEYWORDS.search(value):
            return False

    # Trường "số điện thoại": phải là dãy số đúng định dạng
    if "điện thoại" in name or "phone" in name:
        cleaned = value.replace(" ", "").replace("-", "")
        if not _PHONE_RE.match(cleaned):
            return False

    # Trường "email" / "hộp điện tử"
    if "email" in name or "hộp điện tử" in name or "thư điện tử" in name:
        if "@" in value and not _EMAIL_RE.match(value):
            return False

    # Trường "họ và tên": không được là tên tài liệu
    if "họ" in name and "tên" in name:
        if _DOC_KEYWORDS.search(value):
            return False

    # Trường kiểu boolean: chỉ chấp nhận các giá trị có/không tương đương
    if field_type == "boolean":
        normalized = value.lower().strip()
        BOOL_OK = {
            "có", "co", "yes", "true", "1", "x", "☑", "đúng", "rồi", "được",
            "không", "khong", "no", "false", "0", "☐", "sai", "chưa", "ko",
        }
        if normalized not in BOOL_OK:
            return False

    # Trường kiểu digit_group: chỉ chấp nhận chuỗi số (có thể có dấu chấm, gạch ngang)
    if field_type == "digit_group":
        cleaned = re.sub(r"[\s.\-/]", "", value)
        if cleaned and not cleaned.isdigit():
            return False

    if field_type == "choice":
        options = [str(option).strip().casefold() for option in field.get("options", [])]
        if options and value.strip().casefold() not in options:
            return False

    return True



def normalize_field_value(field: Dict[str, Any], value: str) -> str:
    """
    Chuẩn hóa giá trị trước khi lưu vào collected_data:
    - Boolean: chuyển về 'có' hoặc 'không'
    - Digit_group: giữ lại chỉ chữ số
    - String: giữ nguyên
    """
    if not value or value == "__SKIPPED__":
        return value

    field_type = field.get("type", "string")

    if field_type == "boolean":
        v = value.lower().strip()
        TRUE_SET = {"có", "co", "yes", "true", "1", "x", "☑", "đúng", "rồi", "được", "đồng ý", "ok"}
        FALSE_SET = {"không", "khong", "no", "false", "0", "☐", "sai", "chưa", "ko", "chưa có", "khong co"}
        if v in TRUE_SET:
            return "có"
        if v in FALSE_SET:
            return "không"
        # Nếu không nhận ra → giữ nguyên (sẽ bị reject bởi quick_validate_value)
        return value

    if field_type == "digit_group":
        # Chỉ giữ chữ số
        digits_only = re.sub(r"[^0-9]", "", value)
        return digits_only if digits_only else value

    return value


# ─── Data Models ──────────────────────────────────────────────────────────────

class ExtractedField(BaseModel):
    key: str = Field(description="The unique key of the field")
    value: str = Field(description="The extracted value, or empty string if not extractable")


class FormExtractionResult(BaseModel):
    extracted_fields: List[ExtractedField] = Field(description="List of fields to update in collected_data")
    is_complete: bool = Field(description="True ONLY if every single Required personal field now has a non-empty value. False otherwise.")
    assistant_reply: str = Field(description="The next conversational message to send to the user")
    next_field_key: Optional[str] = Field(default=None, description="The key of the field you are asking the user about in this turn (null if is_complete=true)")
    next_field_name: Optional[str] = Field(default=None, description="The human-readable name of the field you are asking about (null if is_complete=true)")


def get_friendly_name(field: Dict[str, Any]) -> str:
    """Helper: Return description (if available and not just instruction), else format name/key."""
    desc = field.get("description", "")
    if desc and not desc.startswith("Nhập thông tin"):
        return desc.replace(" [TU_DONG_DIEN]", "").strip()

    name = field.get("name")
    key = field.get("key", "?")
    if not name or name == key:
        if "_" in key:
            return key.replace("_", " ").capitalize()
        return key
    if name and "_" in name:
        return name.replace("_", " ").capitalize()
    return name

# ─── Form Agent ───────────────────────────────────────────────────────────────

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
        invalid_fields: Optional[List[str]] = None,
    ) -> FormExtractionResult:
        """
        Uses LLM to extract form fields from the conversation and decide the next step.

        Args:
            last_asked_field: {\"key\": \"field_9002\", \"name\": \"Số CMND/CCCD\"} — field asked in PREVIOUS turn.
            invalid_fields: list of field keys where previously collected data was detected as invalid.
        """
        invalid_fields = invalid_fields or []

        # ── Phân loại trường tự động vs cá nhân ──────────────────────────────
        auto_fill_fields = [f for f in form_fields if is_auto_fill_field(f)]
        personal_fields = [f for f in form_fields if not is_auto_fill_field(f)]

        # Backend and AI share the same Admin/PDF ordering rule.
        personal_fields = order_fields(personal_fields)

        # ── Build schema description ──────────────────────────────────────────
        schema_desc = []
        for f in personal_fields:
            req = "Bắt buộc" if f.get("required") else "Tùy chọn"
            desc = f.get("description", "")
            section_name = f.get("section_name")
            field_type = f.get("type", "string")
            choices = f"; lựa chọn: {' | '.join(f.get('options', []))}" if field_type == "choice" else ""
            schema_desc.append(
                f"- {get_friendly_name(f)} "
                f"(Key: {f.get('key', '')}, Kiểu: {field_type}, {req}{choices}"
                f"{', Cụm: ' + section_name if section_name else ''}): {desc}"
            )

        schema_text = "\n".join(schema_desc) or "  (Không có trường cá nhân nào)"
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-16:]])

        # ── Build collected_data display ──────────────────────────────────────
        field_key_to_name = {f.get("key", ""): get_friendly_name(f) for f in form_fields}
        collected_display = "\n".join([
            f"  - {field_key_to_name.get(k, k)} (key={k}): {v}"
            for k, v in collected_data.items()
        ]) or "  (Chưa có dữ liệu nào)"

        # ── Auto-fill fields display ──────────────────────────────────────────
        auto_fill_display = "\n".join([
            f"  - {get_friendly_name(f)} (key={f.get('key', '')}): Tự động điền bằng RAG, KHÔNG hỏi người dùng"
            for f in auto_fill_fields
        ]) or "  (Không có)"

        # ── Missing personal fields (Required and Optional) ────────────────────
        # Includes one representative when an entire require_one_of_group is
        # unanswered, even if a user has skipped every individual alternative.
        missing_personal = get_missing_fields(personal_fields, collected_data)

        # Ưu tiên invalid fields lên đầu danh sách missing
        invalid_set = set(invalid_fields)
        missing_sorted = (
            [f for f in missing_personal if f.get("key") in invalid_set] +
            [f for f in missing_personal if f.get("key") not in invalid_set]
        )
        missing_display_lines = []
        if missing_sorted:
            # CHỈ ĐƯA 1 TRƯỜNG ĐẦU TIÊN VÀO DANH SÁCH ĐỂ BẮT BUỘC LLM PHẢI HỎI ĐÚNG THỨ TỰ
            f = missing_sorted[0]
            req_text = "Bắt buộc" if f.get("required") else "Tùy chọn"
            
            grp = f.get("require_one_of_group")
            if grp:
                all_group_fields = [gf for gf in personal_fields if gf.get("require_one_of_group") == grp]
                unskipped_group_fields = [gf for gf in all_group_fields if collected_data.get(gf.get("key", "")) != "__SKIPPED__"]
                names = " HOẶC ".join([get_friendly_name(gf) for gf in all_group_fields])
                
                if len(unskipped_group_fields) > 1:
                    req_text = f"Bắt buộc chọn 1 trong nhóm: {names}. Bạn CÓ THỂ hỏi gộp (VD: Bạn có A hoặc B không?), hoặc nếu người dùng không có trường này, HÃY CHO PHÉP lưu '__SKIPPED__' để tiếp tục hỏi trường kia."
                else:
                    req_text = f"Bắt buộc (Đại diện cho nhóm {names}. Các lựa chọn kia người dùng đã bỏ qua, nên BẮT BUỘC phải cung cấp trường này HOẶC người dùng có thể đổi ý cung cấp trường đã bỏ qua. Hãy giải thích rõ cho người dùng hiểu. Nếu người dùng đổi ý cung cấp trường kia, HÃY gán vào đúng key của trường kia!)"
            
            line = f"  - {get_friendly_name(f)} (key={f.get('key', '')}, {req_text})"
            if f.get("key") in invalid_set:
                line += " ← ⚠️ DỮ LIỆU CŨ KHÔNG HỢP LỆ, CẦN HỎI LẠI TRƯỚC TIÊN"
            line += " <--- (BẮT BUỘC HỎI TRƯỜNG NÀY TIẾP THEO TRONG LƯỢT NÀY)"
            missing_display_lines.append(line)
        missing_display = "\n".join(missing_display_lines) or "  (Không còn trường cá nhân nào thiếu — có thể hoàn thành!)"

        # ── Invalid fields notice ─────────────────────────────────────────────
        invalid_display = ""
        if invalid_fields:
            invalid_names = [field_key_to_name.get(k, k) for k in invalid_fields]
            invalid_display = f"""
### ⚠️ CÁC TRƯỜNG CÓ DỮ LIỆU KHÔNG HỢP LỆ (cần hỏi lại):
{chr(10).join(f"  - {n} (key={k})" for k, n in zip(invalid_fields, invalid_names))}
→ Các trường này đã bị XÓA khỏi collected_data vì dữ liệu không phù hợp với loại trường.
→ Hãy ưu tiên hỏi lại các trường này TRƯỚC.
"""

        # ── Last asked field hint ─────────────────────────────────────────────
        if last_asked_field and last_asked_field.get("key"):
            last_asked_str = f"""
### TRƯỜNG BẠN VỪA HỎI TRONG LƯỢT TRƯỚC:
Key: {last_asked_field['key']}
Tên: {last_asked_field.get('name', '')}
→ Tin nhắn cuối của người dùng là CÂU TRẢ LỜI cho trường này.
→ BẮT BUỘC phải trích xuất câu trả lời đó và gán vào key "{last_asked_field['key']}", NGAY CẢ KHI giá trị đó đã xuất hiện ở trường khác trong collected_data.
→ NHƯNG: nếu câu trả lời của người dùng rõ ràng KHÔNG phù hợp với loại trường (ví dụ: nhập tên tài liệu vào trường Địa chỉ, nhập chữ vào trường Số điện thoại), hãy KHÔNG gán, và hỏi lại lịch sự.
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

### CÁC TRƯỜNG CÁ NHÂN CẦN THU THẬP (chỉ hỏi những trường này):
{schema_text}

### KHO TRI THỨC PHÁP LÝ (để tự điền các trường pháp lý):
{rag_context if rag_context else "Không có thông tin bổ sung."}

### THÔNG TIN ĐÃ THU THẬP (KHÔNG được hỏi lại các trường này trừ khi được đánh dấu ⚠️):
{collected_display}

### CÁC TRƯỜNG TỰ ĐỘNG ĐIỀN (TUYỆT ĐỐI KHÔNG HỎI NGƯỜI DÙNG - tự điền bằng RAG hoặc suy luận):
{auto_fill_display}

### CÁC TRƯỜNG CÁ NHÂN CÒN THIẾU (CHỈ hỏi từ danh sách này, không hỏi gì khác):
{missing_display}
{invalid_display}
{last_asked_str}

### LỊCH SỬ TRÒ CHUYỆN:
{history_text}
user: {user_message}

---
### QUY TRÌNH XỬ LÝ (thực hiện theo đúng thứ tự):

**BƯỚC 0 — KIỂM TRA CHẤT LƯỢNG CÂU TRẢ LỜI (nếu có trường vừa hỏi):**
Nếu có "TRƯỜNG BẠN VỪA HỎI TRONG LƯỢT TRƯỚC", trước khi gán hãy kiểm tra:
- Trường "Địa chỉ": câu trả lời PHẢI là địa chỉ thực (xã/phường, quận/huyện, tỉnh/thành). Nếu người dùng nhập tên tài liệu (bản sao, CCCD, sổ đỏ...) hoặc số điện thoại → KHÔNG gán, hỏi lại: "Bạn vui lòng cung cấp địa chỉ cụ thể (số nhà, xã/phường, quận/huyện, tỉnh) nhé?"
- Trường "Số điện thoại": PHẢI là dãy số, bắt đầu bằng 0 hoặc +84, dài 10-11 chữ số. Nếu không phải → KHÔNG gán, hỏi lại.
- Trường "Họ và tên": PHẢI là tên người (chữ cái, có thể có dấu). Nếu là tên tài liệu hay số → KHÔNG gán, hỏi lại.
- Trường "Hộp điện tử" / Email: nếu người dùng cung cấp, phải có định dạng email (chứa @). Nếu họ nói "không có" → lưu "__SKIPPED__".
- Các trường khác: dùng nhận thức thông thường để xét xem câu trả lời có phù hợp không.

**BƯỚC 1 — GÁN CÂU TRẢ LỜI VỪA NHẬN (nếu qua được Bước 0):**
Nếu có "TRƯỜNG BẠN VỪA HỎI TRONG LƯỢT TRƯỚC" và câu trả lời hợp lệ:
- Từ nội dung tin nhắn của người dùng (user: {user_message}), HÃY TRÍCH XUẤT THÔNG TIN CỐT LÕI VÀ CHÍNH XÁC NHẤT để gán vào key đó trong `extracted_fields`.
- Tuyệt đối KHÔNG bê nguyên toàn bộ câu nói của người dùng. CHỈ LẤY GIÁ TRỊ CỐT LÕI.
  + Ví dụ: Người dùng nói "diện tích : 1000m2" -> CHỈ LẤY "1000m2".
  + Ví dụ: Người dùng nói "Lần chứng nhận đầu tiên: không phải" -> CHỈ LẤY "không".
  + Ví dụ: Người dùng nói "tôi sinh ngày 01/01/1990" -> CHỈ LẤY "01/01/1990".
- Riêng với trường "Địa chỉ", phải giữ nguyên tên đường, phường, xã đầy đủ, không được viết tắt (VD: "Phường A, Quận B" chứ không phải "A, B").
- ĐẶC BIỆT: Nếu trường đang hỏi liên quan đến "Năm" (ví dụ: Năm, Kỳ tính thuế...) và người dùng trả lời là "năm nay", "hiện tại", hãy tự động chuyển đổi giá trị đó thành năm hiện tại là "{year_str}".

**BƯỚC 2 — TỰ ĐỘNG ĐIỀN TRƯỜNG PHÁP LÝ (không hỏi người dùng):**
Chỉ đối với các trường trong danh sách "CÁC TRƯỜNG TỰ ĐỘNG ĐIỀN", hãy tự động trích xuất thông tin từ KHO TRI THỨC để điền.
- Nếu không tìm thấy thông tin trong KHO TRI THỨC, TUYỆT ĐỐI KHÔNG điền "Theo quy định". Hãy trả về chuỗi rỗng "" hoặc không đưa trường đó vào extracted_fields.
- TUYỆT ĐỐI KHÔNG tự động điền các trường CÁ NHÂN. Nếu thiếu trường cá nhân, phải để trống để hỏi tiếp.

**BƯỚC 3 — TỰ ĐỘNG SUY LUẬN CÁC TRƯỜNG ĐẶC BIỆT:**
- Trường "Ngày" → điền "{day_str}"
- Trường "Tháng" → điền "{month_str}"
- Trường "Năm" → điền "{year_str}"
- Trường "Tỉnh (Nơi viết)" hoặc tương tự → lấy tỉnh/thành từ trường Địa chỉ đã thu thập (nếu có) để điền, KHÔNG hỏi người dùng.

**BƯỚC 4 — KIỂM TRA HOÀN THÀNH:**
Sau khi tổng hợp tất cả dữ liệu (bao gồm collected_data cũ + các trường vừa gán ở Bước 1 + các trường tự điền ở Bước 2, Bước 3):
- Nếu ĐÃ ĐẦY ĐỦ tất cả các trường CÁ NHÂN (cả Bắt buộc và Tùy chọn đều đã có dữ liệu hoặc "__SKIPPED__") → set is_complete = true, next_field_key = null, next_field_name = null
- Nếu VẪN CÒN trường CÁ NHÂN CHƯA CÓ DỮ LIỆU → set is_complete = false. BẠN BẮT BUỘC PHẢI CHỌN TRƯỜNG ĐẦU TIÊN (trên cùng) trong danh sách "CÁC TRƯỜNG CÁ NHÂN CÒN THIẾU" để hỏi, KHÔNG ĐƯỢC CHỌN TRƯỜNG BÊN DƯỚI. Đặt next_field_key và next_field_name bằng thông tin của trường đầu tiên đó.
- QUAN TRỌNG: is_complete chỉ quan tâm đến trường CÁ NHÂN. Các trường tự động điền KHÔNG ảnh hưởng đến is_complete.

**BƯỚC 5 — SINH CÂU TRẢ LỜI (assistant_reply):**
- Nếu Bước 0 phát hiện câu trả lời không hợp lệ: hỏi lại trường đó với hướng dẫn cụ thể.
- Nếu người dùng đặt câu hỏi (ví dụ: "gửi đi đâu?", "tại sao cần thông tin này?"), PHẢI TRẢ LỜI câu hỏi đó ngắn gọn dựa vào KHO TRI THỨC. Sau khi trả lời, mới tiếp tục hỏi thông tin.
- Nếu is_complete = false: Hỏi đúng 1 câu về trường CÁ NHÂN bạn chọn ở Bước 4 (ghép sau câu trả lời nếu có). Đặt câu hỏi một cách TỰ NHIÊN, NGẮN GỌN và TRỰC TIẾP như người thật, DỰA VÀO NGỮ CẢNH VÀ KIỂU DỮ LIỆU CỦA TRƯỜNG ĐÓ. 
  + Ví dụ nếu hỏi về số, tiền, hoặc diện tích ("Số", "Diện tích", "Hạn mức"), hãy dùng "số mấy", "bao nhiêu", "là bao nhiêu". (VD: "Diện tích đất sử dụng đúng mục đích là bao nhiêu mét vuông ạ?")
  + Nếu hỏi về năm ("Năm cấp", "Kỳ tính thuế"), hãy dùng "năm nào", "năm bao nhiêu". (VD: "Kỳ tính thuế là năm bao nhiêu ạ?")
  + Nếu hỏi về ngày tháng ("Ngày sinh", "Ngày cấp"), hãy dùng "ngày mấy", "ngày bao nhiêu". (VD: "Ngày cấp CMND là ngày mấy ạ?")
  + TUYỆT ĐỐI TRÁNH cách hỏi máy móc như "Bạn vui lòng cung cấp thông tin [Tên trường]". Hãy linh hoạt biến tấu câu hỏi cho giống ngữ điệu của một tư vấn viên thực thụ.
- Nếu trường bạn chuẩn bị hỏi là "Tùy chọn" (không bắt buộc), HÃY THÔNG BÁO RÕ CHO NGƯỜI DÙNG RẰNG TRƯỜNG NÀY LÀ KHÔNG BẮT BUỘC, họ có thể trả lời "không có" hoặc "bỏ qua". Tuyệt đối không được nói là bắt buộc.
  → TUYỆT ĐỐI KHÔNG HỎI các trường đã có trong collected_data (trừ trường bị đánh dấu ⚠️).
  → TUYỆT ĐỐI KHÔNG HỎI các trường pháp lý / tự động điền. Bạn tự điền chúng, cấm hỏi người dùng.
  → TUYỆT ĐỐI CHỈ HỎI DUY NHẤT 1 TRƯỜNG MỖI LƯỢT. Không hỏi 2 trường cùng lúc dù bất kỳ lý do gì.
  → NẾU người dùng vừa trả lời "không có" cho một trường Bắt buộc, bạn PHẢI tiếp tục hỏi lại chính trường đó, KHÔNG được chuyển sang hỏi trường khác.
- Nếu is_complete = true: Nói "Dạ, tôi đã thu thập đủ thông tin cần thiết. Biểu mẫu của bạn đã sẵn sàng để xem và tải xuống."
- QUAN TRỌNG: is_complete và nội dung assistant_reply PHẢI nhất quán với nhau. Nếu is_complete=false thì KHÔNG được nói "đã đủ" hay "sẵn sàng tải xuống".

**QUY TẮC TRƯỜNG ĐẶC BIỆT:**
- Trường kiểu "boolean": hỏi dạng "Bạn có [tên trường] không?". Nhận "có/yes/đúng/rồi" → lưu "có"; "không/no/chưa" → lưu "không".
- Trường "Tùy chọn": Nếu bạn đã hỏi và người dùng nói "không có" / "bỏ qua" → lưu "__SKIPPED__" và hỏi trường tiếp theo. TUYỆT ĐỐI KHÔNG TỰ Ý gán "__SKIPPED__" cho trường "Tùy chọn" nếu bạn CHƯA HỎI người dùng về trường đó!
- Trường "Bắt buộc" mà người dùng nói "không có" → lưu "" (rỗng), giải thích đây là bắt buộc, và BẮT BUỘC YÊU CẦU họ cung cấp lại. TUY NHIÊN, CÓ 2 NGOẠI LỆ ĐƯỢC PHÉP LƯU "__SKIPPED__": (1) Nếu trường có ghi chú "Bắt buộc chọn 1 trong nhóm...", bạn PHẢI lưu "__SKIPPED__" để hệ thống chuyển sang hỏi trường thay thế cùng nhóm. (2) Nếu trường là các thành phần phụ của địa chỉ (như "Số nhà", "Đường/phố", "Tổ/thôn", "Ngõ/hẻm", "Tòa nhà") và người dùng khẳng định "không có", BẠN PHẢI lưu "__SKIPPED__" và đi tiếp.
- GỘP HỎI ĐỊA CHỈ: Nếu các trường tiếp theo cần hỏi là một chuỗi các thành phần địa chỉ (Số nhà, Đường, Tổ, Phường, Quận, Tỉnh), BẠN KHÔNG ĐƯỢC HỎI LẮT NHẮT TỪNG TRƯỜNG. Hãy hỏi gộp: "Bạn vui lòng cung cấp địa chỉ đầy đủ (số nhà, đường, tổ/thôn, phường/xã, quận/huyện, tỉnh/thành) của [Tên người/Nơi chốn] nhé." Khi người dùng trả lời 1 địa chỉ dài, hãy TỰ ĐỘNG BÓC TÁCH và gán TẤT CẢ các thành phần đó vào các key tương ứng trong `extracted_fields` cùng 1 lượt.
- Khi hỏi thông tin về CON NGƯỜI (ví dụ: tên người sử dụng đất, người chuyển nhượng, v.v.), TUYỆT ĐỐI KHÔNG DÙNG "là gì". Hãy dùng "là ai" hoặc "vui lòng cho biết họ và tên của...".
- ĐỊNH DẠNG NGÀY THÁNG: Nếu trường đang hỏi liên quan đến ngày, tháng, năm (ví dụ: Ngày sinh, Ngày cấp, Ngày hợp đồng, ...), hãy LUÔN LUÔN tự động chuyển đổi câu trả lời của người dùng về đúng định dạng chuẩn `DD/MM/YYYY` (Ví dụ: "ngày 22 tháng 12 năm 1999" -> "22/12/1999") trước khi gán vào `extracted_fields`.
- SUY LUẬN BỎ QUA (SKIP LOGIC): Nếu câu trả lời của người dùng HOẶC dữ liệu đã có cho thấy một/nhiều trường khác không còn ý nghĩa (Ví dụ: chọn "Lần đầu" = Có thì "Bổ sung lần thứ" bị vô hiệu; "Không có đại lý thuế" thì các trường mã số/tên/địa chỉ đại lý thuế cũng vô hiệu), hãy TỰ ĐỘNG GÁN giá trị "__SKIPPED__" cho các trường không cần thiết đó và đưa vào `extracted_fields` để không bao giờ hỏi chúng.

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
                result = response.parsed
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
                result = FormExtractionResult.model_validate(data)

            # ── Post-process: fix logical inconsistencies ─────────────────────
            # Rule 1: is_complete=True 但 next_field_key không null → fix
            if result.is_complete and result.next_field_key:
                logger.warning(
                    f"LLM returned is_complete=True but next_field_key='{result.next_field_key}' — fixing"
                )
                result = FormExtractionResult(
                    extracted_fields=result.extracted_fields,
                    is_complete=True,
                    assistant_reply=result.assistant_reply,
                    next_field_key=None,
                    next_field_name=None,
                )

            # Rule 2: is_complete=False nhưng assistant_reply chứa "sẵn sàng tải xuống" → fix reply
            if not result.is_complete and (
                "sẵn sàng tải xuống" in result.assistant_reply
                or "đã đủ thông tin" in result.assistant_reply
            ):
                logger.warning("LLM reply inconsistent with is_complete=False — truncating misleading text")
                # Giữ reply nhưng xóa phần misleading
                cleaned = result.assistant_reply
                for phrase in ["Biểu mẫu của bạn đã sẵn sàng", "sẵn sàng để xem và tải xuống", "đã đủ thông tin"]:
                    cleaned = cleaned.replace(phrase, "")
                result = FormExtractionResult(
                    extracted_fields=result.extracted_fields,
                    is_complete=False,
                    assistant_reply=cleaned.strip() or "Xin lỗi, tôi cần thu thập thêm thông tin.",
                    next_field_key=result.next_field_key,
                    next_field_name=result.next_field_name,
                )

            return result

        except Exception as e:
            logger.error(f"Error in FormAgent extraction: {e}", exc_info=True)
            return FormExtractionResult(
                extracted_fields=[],
                is_complete=False,
                assistant_reply="Xin lỗi, tôi đang gặp khó khăn trong việc xử lý thông tin. Bạn có thể cung cấp lại được không?",
                next_field_key=None,
                next_field_name=None,
            )
