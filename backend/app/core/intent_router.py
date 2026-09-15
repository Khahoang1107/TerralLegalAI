"""Deterministic high-level routing between legal Q&A and form filling."""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

import logging

logger = logging.getLogger(__name__)

ChatMode = Literal["rag", "form", "resume_form", "exit_form", "unknown"]
DigressionIntent = Literal["FILL", "ASK_LEGAL"]


def _plain(text: str) -> str:
    normalized = unicodedata.normalize("NFD", (text or "").casefold())
    normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", normalized.replace("đ", "d")).strip()


def detect_explicit_chat_mode(question: str) -> ChatMode:
    """Detect only explicit commands; ordinary form answers remain unknown."""
    text = _plain(question)

    resume_patterns = (
        "tiep tuc dien", "quay lai dien", "dien tiep", "tiep tuc ke khai",
        "quay lai ke khai", "tiep tuc bieu mau", "tiep tuc to khai",
    )
    if any(pattern in text for pattern in resume_patterns):
        return "resume_form"

    exit_patterns = (
        "dung dien", "thoat dien", "huy dien", "dung ke khai",
        "thoat ke khai", "khong dien nua", "bo bieu mau",
    )
    if any(pattern in text for pattern in exit_patterns):
        return "exit_form"

    rag_patterns = (
        "toi hoi quy trinh", "toi muon hoi quy trinh", "chi hoi quy trinh",
        "toi muon hoi thong tin", "toi dang hoi thong tin", "chuyen sang tra cuu",
        "toi muon tra cuu", "chi tra cuu", "khong phai dien bieu mau",
        "khong phai dien form", "hoi quy dinh", "hoi thu tuc",
    )
    if any(pattern in text for pattern in rag_patterns):
        return "rag"

    form_patterns = (
        "dien bieu mau", "dien form", "dien to khai", "dien don",
        "tao bieu mau", "tao to khai", "lap to khai", "ke khai bieu mau",
        "ke khai to khai", "hoan thien bieu mau",
    )
    if any(pattern in text for pattern in form_patterns):
        return "form"

    return "unknown"


def resolve_active_conversation_mode(saved_mode: str, explicit_mode: ChatMode) -> Literal["rag", "form"]:
    """Resolve one turn without discarding the active form or its answers."""
    if explicit_mode in {"rag", "exit_form"}:
        return "rag"
    if explicit_mode in {"form", "resume_form"}:
        return "form"
    return "rag" if saved_mode == "rag" else "form"


# ─── Digression detection (khi đang trong form) ───────────────────────────────

# Từ khóa pháp lý — nếu có trong câu → khả năng cao là ASK_LEGAL
_LEGAL_KEYWORDS = re.compile(
    r"\b(quy\s*định|quy\s*trình|thủ\s*tục|điều\s*khoản|luật|nghị\s*định|thông\s*tư|"
    r"hạn\s*mức|lệ\s*phí|phí|thời\s*hạn|bao\s*lâu|mất\s*bao\s*lâu|"
    r"cần\s*giấy\s*tờ|cần\s*chuẩn\s*bị|hồ\s*sơ\s*gồm|nộp\s*ở\s*đâu|"
    r"gửi\s*ở\s*đâu|nộp\s*tại\s*đâu|tại\s*sao|vì\s*sao|mục\s*đích|"
    r"giải\s*thích|cho\s*tôi\s*biết\s*về|tư\s*vấn|được\s*không|có\s*được\s*không)\b",
    re.IGNORECASE | re.UNICODE,
)

# Từ khóa rõ ràng là câu trả lời form (số, đơn vị, địa chỉ ngắn)
_FILL_PATTERNS = re.compile(
    r"^\s*[\d,.]+\s*(m2|mét|ha|đồng|vnd|ngày|tháng|năm|%)?\s*$"  # số đơn thuần
    r"|^\s*\d{1,2}/\d{1,2}/\d{4}\s*$"   # ngày tháng
    r"|^\s*\d{9,12}\s*$",               # số CMND/CCCD/SĐT
    re.IGNORECASE | re.UNICODE,
)


def detect_digression(
    user_message: str,
    current_field_name: str = "",
) -> DigressionIntent:
    """
    Phân loại ý định khi người dùng đang điền form:
    - FILL: Câu trả lời cho trường đang hỏi
    - ASK_LEGAL: Người dùng hỏi quy định / pháp lý / thủ tục

    Dùng heuristic nhanh trước, không tốn API call:
    - Câu ngắn (≤ 6 từ) hoặc khớp pattern số → FILL
    - Câu có dấu "?" hoặc từ khóa pháp lý → ASK_LEGAL
    - Trường hợp còn lại → FILL (mặc định an toàn)
    """
    text = user_message.strip()

    # Fast-path 1: Nếu câu là số / ngày tháng thuần → chắc chắn là câu trả lời form
    if _FILL_PATTERNS.match(text):
        return "FILL"

    # Fast-path 2: Câu rất ngắn (≤ 6 từ) và không có dấu hỏi → câu trả lời form
    word_count = len(text.split())
    has_question_mark = "?" in text

    if word_count <= 6 and not has_question_mark and not _LEGAL_KEYWORDS.search(text):
        return "FILL"

    # Fast-path 3: Có dấu hỏi HOẶC từ khóa pháp lý rõ ràng → hỏi luật
    if has_question_mark or _LEGAL_KEYWORDS.search(text):
        logger.debug(f"detect_digression → ASK_LEGAL for: '{text[:60]}'")
        return "ASK_LEGAL"

    # Mặc định: coi là câu trả lời form (an toàn hơn là gọi RAG nhầm)
    return "FILL"

