"""
TerraLegalAI — Metadata Extractor
Nhận dạng và trích xuất metadata từ text văn bản pháp lý Việt Nam.
Xác định: tên Điều, số Khoản, Điểm, loại nội dung (field_type).
"""
import logging
import re
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ExtractedMetadata:
    """Metadata trích xuất từ một đoạn text."""
    article: str = ""       # VD: "Điều 3"
    clause: str = ""        # VD: "Khoản 2"
    point: str = ""         # VD: "Điểm a"
    section: str = ""       # VD: "Mục I" / "Chương II"
    field_type: str = ""    # Loại nội dung: thanh_phan_ho_so / thoi_han / ...
    procedure_type: str = ""  # Phát hiện loại thủ tục nếu có


# ─── Patterns nhận dạng cấu trúc văn bản pháp lý VN ─────────────

ARTICLE_PATTERN = re.compile(
    r"Điều\s+(\d+[a-zA-Z]?)\b[.\:]?",
    re.IGNORECASE | re.UNICODE,
)
CLAUSE_PATTERN = re.compile(
    r"(?:Khoản|khoản)\s+(\d+)\b[.\:]?",
    re.IGNORECASE | re.UNICODE,
)
POINT_PATTERN = re.compile(
    r"(?:Điểm|điểm)\s+([a-zA-Z])\b[.\)]?",
    re.IGNORECASE | re.UNICODE,
)
SECTION_PATTERN = re.compile(
    r"(?:Mục|Chương)\s+([IVXLCDM]+|\d+[a-zA-Z]?)\b",
    re.IGNORECASE | re.UNICODE,
)
NUMBERED_CLAUSE_PATTERN = re.compile(
    r"^\s*(\d+)\.\s+",  # VD: "1. Hồ sơ gồm:"
)

# ─── Field type detection keywords ───────────────────────────────

FIELD_TYPE_KEYWORDS: dict[str, list[str]] = {
    "thanh_phan_ho_so": [
        "thành phần hồ sơ", "hồ sơ gồm", "giấy tờ gồm", "tài liệu cần",
        "đơn đăng ký", "giấy chứng nhận", "hợp đồng", "bản sao",
        "chứng thực", "công chứng",
    ],
    "trinh_tu_thuc_hien": [
        "trình tự thực hiện", "các bước", "quy trình", "bước 1", "bước 2",
        "tiếp nhận hồ sơ", "thẩm định", "phê duyệt", "trả kết quả",
    ],
    "thoi_han": [
        "thời hạn", "thời gian giải quyết", "ngày làm việc", "ngày kể từ",
        "không quá", "tối đa", "trong vòng",
    ],
    "le_phi": [
        "lệ phí", "phí", "chi phí", "mức thu", "không thu phí",
        "miễn phí", "phí thẩm định",
    ],
    "dieu_kien": [
        "điều kiện", "yêu cầu", "đáp ứng", "không vi phạm", "không tranh chấp",
        "đủ điều kiện", "trường hợp",
    ],
    "co_quan_tiep_nhan": [
        "cơ quan tiếp nhận", "nộp hồ sơ tại", "văn phòng đăng ký",
        "ủy ban nhân dân", "chi nhánh", "bộ phận một cửa",
    ],
    "can_cu_phap_ly": [
        "căn cứ", "theo quy định", "luật đất đai", "nghị định", "quyết định",
        "thông tư", "theo điều", "quy định tại",
    ],
}

# ─── Procedure type detection ─────────────────────────────────────

PROCEDURE_KEYWORDS: dict[str, list[str]] = {
    "chuyen_nhuong": [
        "chuyển nhượng quyền sử dụng đất", "sang tên", "biến động",
        "đăng ký biến động", "hợp đồng chuyển nhượng",
    ],
    "tang_cho": [
        "tặng cho quyền sử dụng đất", "tặng cho", "thừa kế",
    ],
    "cap_doi": [
        "cấp đổi giấy chứng nhận", "cấp đổi gcn", "cấp đổi sổ",
        "giấy chứng nhận bị hỏng", "bị rách",
    ],
    "cap_moi": [
        "cấp lần đầu", "cấp giấy chứng nhận lần đầu", "chưa có sổ",
    ],
}


class MetadataExtractor:
    """
    Trích xuất metadata từ text đoạn văn bản pháp lý.
    Tự động nhận dạng: Điều, Khoản, Điểm, loại nội dung, loại thủ tục.
    """

    def extract(self, text: str, context: str = "") -> ExtractedMetadata:
        """
        Trích xuất metadata từ một đoạn text.

        Args:
            text: Nội dung chunk cần phân tích
            context: Text xung quanh (để cải thiện độ chính xác)

        Returns:
            ExtractedMetadata với article, clause, field_type, ...
        """
        combined = f"{context}\n{text}" if context else text

        article = self._extract_article(combined)
        clause = self._extract_clause(combined)
        point = self._extract_point(combined)
        section = self._extract_section(combined)
        field_type = self._detect_field_type(text)
        procedure_type = self._detect_procedure_type(text)

        return ExtractedMetadata(
            article=article,
            clause=clause,
            point=point,
            section=section,
            field_type=field_type,
            procedure_type=procedure_type,
        )

    def _extract_article(self, text: str) -> str:
        """Tìm tên Điều đầu tiên trong text."""
        match = ARTICLE_PATTERN.search(text)
        if match:
            return f"Điều {match.group(1)}"
        return ""

    def _extract_clause(self, text: str) -> str:
        """Tìm số Khoản đầu tiên trong text."""
        match = CLAUSE_PATTERN.search(text)
        if match:
            return f"Khoản {match.group(1)}"
        # Fallback: pattern số thứ tự đầu dòng "1. ..."
        match2 = NUMBERED_CLAUSE_PATTERN.search(text)
        if match2:
            return f"Khoản {match2.group(1)}"
        return ""

    def _extract_point(self, text: str) -> str:
        """Tìm Điểm (a, b, c...) trong text."""
        match = POINT_PATTERN.search(text)
        if match:
            return f"Điểm {match.group(1)}"
        return ""

    def _extract_section(self, text: str) -> str:
        """Tìm Mục hoặc Chương trong text."""
        match = SECTION_PATTERN.search(text)
        if match:
            return match.group(0)
        return ""

    def _detect_field_type(self, text: str) -> str:
        """
        Nhận dạng loại nội dung (field_type) dựa trên từ khoá.
        Trả về type có nhiều matches nhất.
        """
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for field_type, keywords in FIELD_TYPE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[field_type] = score
        if not scores:
            return "general"
        return max(scores, key=scores.get)

    def _detect_procedure_type(self, text: str) -> str:
        """
        Nhận dạng loại thủ tục trong text.
        Trả về type có nhiều matches nhất, hoặc "" nếu không rõ.
        """
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for proc_type, keywords in PROCEDURE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[proc_type] = score
        if not scores:
            return ""
        return max(scores, key=scores.get)
