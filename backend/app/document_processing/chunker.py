"""
TerraLegalAI — Document Chunker (v3 — Structure-Aware)
Chia tài liệu thủ tục hành chính đất đai thành chunks theo cấu trúc thực tế.

Cấu trúc tài liệu thực tế (phân tích từ OCR output):

  QĐ 1085 (Bộ thủ tục hành chính):
    ┌─ "8. Cap đổi Giấy chứng nhận..."    ← header thủ tục
    │   ├─ (1) Trình tự thực hiện          ← chunk 1
    │   │    ├─ Bước 1: ...
    │   │    ├─ Bước 2: ...
    │   │    └─ Bước 3: ...
    │   ├─ (2) Cách thức thực hiện         ← chunk 2
    │   ├─ (3) Thành phần, số lượng hồ sơ ← chunk 3
    │   ├─ (4) Thời hạn giải quyết         ← chunk 4
    │   ├─ (5) Đối tượng thực hiện         ← chunk 5
    │   ├─ (6) Cơ quan thực hiện           ← chunk 6
    │   ├─ (7) Kết quả thực hiện           ← chunk 7
    │   ├─ (8) Lệ phí                      ← chunk 8
    │   ├─ (9) Tên mẫu đơn                 ← chunk 9
    │   ├─ (10) Yêu cầu, điều kiện         ← chunk 10
    │   └─ (11) Căn cứ pháp lý             ← chunk 11
    └─ "12. Đăng ký biến động..."
         └─ (tương tự)

  QĐ 1467 (Quy trình nội bộ — dạng bảng):
    ┌─ "8. Cấp đổi GCN" (Mã TTHC: 1.012783.H61)
    │   ├─ 8.1  (cấp trên bản đồ chính quy)
    │   │   ├─ Bước 1: Tiếp nhận hồ sơ         ← chunk
    │   │   ├─ Bước 2: Kiểm tra hồ sơ          ← chunk
    │   │   ├─ Bước 3: Gửi phiếu tài chính     ← chunk
    │   │   ├─ Bước 4: Cấp GCN                 ← chunk
    │   │   ├─ Bước 5: Trả kết quả             ← chunk
    │   │   └─ Tổng thời gian: 05 ngày         ← chunk thoi_han
    │   └─ 8.2  (thay đổi kích thước)
    │       └─ (tương tự)
    └─ "12. Đăng ký biến động..."
        └─ (tương tự)

  Văn bản pháp luật (Luật, Nghị định):
    - Chunk theo Điều, fallback theo Khoản
"""
import re
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.document_processing.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)


# ── Map số mục → field_type & nhãn ──────────────────────────────────────────
SECTION_FIELD_MAP = {
    1:  "trinh_tu",
    2:  "cach_thuc",
    3:  "thanh_phan_ho_so",
    4:  "thoi_han",
    5:  "doi_tuong",
    6:  "co_quan",
    7:  "ket_qua",
    8:  "le_phi",
    9:  "mau_don",
    10: "dieu_kien",
    11: "can_cu_phap_ly",
}

SECTION_LABEL_MAP = {
    1:  "(1) Trình tự thực hiện",
    2:  "(2) Cách thức thực hiện",
    3:  "(3) Thành phần, số lượng hồ sơ",
    4:  "(4) Thời hạn giải quyết",
    5:  "(5) Đối tượng thực hiện",
    6:  "(6) Cơ quan thực hiện",
    7:  "(7) Kết quả thực hiện",
    8:  "(8) Lệ phí",
    9:  "(9) Tên mẫu đơn, mẫu tờ khai",
    10: "(10) Yêu cầu, điều kiện",
    11: "(11) Căn cứ pháp lý",
}

# Tên ngắn cho metadata
PROCEDURE_SHORTNAME_MAP = {
    "cap doi":            "cap_doi_gcn",
    "cấp đổi":           "cap_doi_gcn",
    "chuyển nhượng":     "chuyen_nhuong",
    "tang cho":          "tang_cho",
    "tặng cho":          "tang_cho",
    "thừa kế":           "thua_ke",
    "đăng ký biến động": "dang_ky_bien_dong",
    "dang ky bien dong": "dang_ky_bien_dong",
    "cho thuê":          "cho_thue",
}


@dataclass
class DocumentChunk:
    """Một chunk văn bản kèm đầy đủ metadata."""
    chunk_id:        str
    text:            str
    token_estimate:  int
    source_file:     str
    source_name:     str
    group_type:      str
    procedure_type:  str
    procedure_name:  str  = ""
    section_number:  int  = 0    # 1-11 với QĐ 1085
    step_number:     int  = 0    # Bước N với QĐ 1467
    article:         str  = ""   # "Điều 3" với Luật/NĐ
    clause:          str  = ""   # "Khoản 1"
    field_type:      str  = "general"
    chunk_index:     int  = 0
    validity_status: str  = "active"


@dataclass
class ChunkingConfig:
    chunk_size:        int       = 600
    chunk_overlap:     int       = 80
    min_chunk_size:    int       = 60
    fallback_separators: list[str] = field(default_factory=lambda: [
        "\n\n", "\n", ". ", " ", "",
    ])


class DocumentChunker:
    """
    Structure-aware chunker cho tài liệu thủ tục hành chính đất đai.

    Chiến lược theo từng loại tài liệu:
    - QĐ 1085 → chunk theo mục (1)-(11), mỗi mục = 1 chunk
    - QĐ 1467 → chunk theo Bước, prefix tên thủ tục
    - Luật/NĐ → chunk theo Điều/Khoản
    - Khác     → RecursiveCharacterTextSplitter

    Mỗi chunk có prefix context để LLM biết ngữ cảnh:
        [Thủ tục: Cấp đổi GCN]
        [Mục: (3) Thành phần, số lượng hồ sơ]
        ...nội dung...
    """

    # ── Regex ────────────────────────────────────────────────────────────────

    # QĐ 1085: mục đánh số (1)-(11)
    # Ví dụ: "(1) Trinh tw thực hiện", "(3) Thanh phan"
    SECTION_RE = re.compile(
        r"^\s*\((\d{1,2})\)\s+(.{3,})",
        re.MULTILINE,
    )

    # Tên thủ tục: "8. Cap đổi..." hoặc "12. Dang ky..."
    # Chỉ bắt đầu dòng, số từ 1-30
    PROC_HEADER_RE = re.compile(
        r"(?:^|\n)\s*(\d{1,2})\.\s+([A-ZĐÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬÉÈẺẼẸÊẾỀỂỄỆÍÌỈĨỊÓÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢÚÙỦŨỤƯỨỪỬỮỰÝỲỶỸỴ"
        r"a-zđáàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ"
        r"A-Z]{1}.{9,200}?)(?:\n|$)",
        re.MULTILINE,
    )

    # QĐ 1467: sub-section "8.1", "8.2", "12.1"
    SUB_PROC_RE = re.compile(
        r"(?:^|\n)\s*(\d{1,2}\.\d)\s+(.{10,200}?)(?:\n|$)",
        re.MULTILINE,
    )

    # Bước N trong QĐ 1467 (dạng bảng OCR có thể bị lỗi)
    BUOC_RE = re.compile(
        r"(?:^|(?<=\n))\s*B(?:ư|u)\s*[oơ]\s*[cC]\s+(\d+)\s*[|\-–]?\s*",
        re.MULTILINE | re.IGNORECASE,
    )
    BUOC_ANY_RE = re.compile(
        r"B\s*[uư]\s*[oơ]\s*c\s+\d+",
        re.IGNORECASE,
    )

    # Thời gian giải quyết tổng
    TOTAL_TIME_RE = re.compile(
        r"T[oổ]ng\s+th[oờ]i\s+gian\s+gi[aả]i\s+quy[eế]t\s+TTHC[^\n]*\n(.{3,80})",
        re.IGNORECASE,
    )

    # Điều (văn bản pháp luật)
    ARTICLE_RE = re.compile(
        r"(?:^|\n)(Đi[eề]u\s+\d+[a-zđ]?\.?\s+.{0,120})",
        re.MULTILINE | re.IGNORECASE,
    )

    # ─────────────────────────────────────────────────────────────────────────
    def __init__(self, config: ChunkingConfig = None):
        self.config = config or ChunkingConfig()
        self._cleaner = TextCleaner()
        self._fallback_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            length_function=self._estimate_tokens,
            separators=self.config.fallback_separators,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def chunk(
        self,
        text: str,
        source_file: str,
        source_name: str,
        group_type: str,
        procedure_type: str = "all",
    ) -> list[DocumentChunk]:
        """Entry point: làm sạch text → nhận dạng cấu trúc → chọn chiến lược → chunk."""
        if not text or len(text.strip()) < self.config.min_chunk_size:
            logger.warning(f"Text quá ngắn để chunk: {source_file}")
            return []

        # ── Bước 0: Làm sạch text trước khi chunk ────────────────────────────
        # TextCleaner xử lý: NFC normalization, garbage chars, header/footer,
        # corrections domain đất đai, số trang, whitespace.
        text = self._cleaner.clean(text)
        if len(text.strip()) < self.config.min_chunk_size:
            logger.warning(f"Text quá ngắn sau khi clean: {source_file}")
            return []

        doc_type = self._detect_doc_type(text, source_name)
        logger.info(f"'{source_file}': doc_type={doc_type}")

        if doc_type == "quyet_dinh_tthc":
            chunks = self._chunk_quyet_dinh_tthc(
                text, source_file, source_name, group_type, procedure_type
            )
        elif doc_type == "quy_trinh_noi_bo":
            chunks = self._chunk_quy_trinh_noi_bo(
                text, source_file, source_name, group_type, procedure_type
            )
        elif doc_type == "luat_nghi_dinh":
            chunks = self._chunk_luat(
                text, source_file, source_name, group_type, procedure_type
            )
        else:
            chunks = self._chunk_fallback(
                text, source_file, source_name, group_type, procedure_type
            )

        for i, c in enumerate(chunks):
            c.chunk_index = i

        logger.info(
            f"  → {len(chunks)} chunks | "
            f"avg {sum(c.token_estimate for c in chunks) // max(len(chunks), 1)} tokens"
        )
        return chunks

    # ─────────────────────────────────────────────────────────────────────────
    # Detection
    # ─────────────────────────────────────────────────────────────────────────

    def _detect_doc_type(self, text: str, source_name: str) -> str:
        """
        Nhận dạng loại tài liệu.

        Ưu tiên:
        1. Có mục (1)-(11) → quyet_dinh_tthc  (QĐ 1085)
        2. Có dạng bảng Bước + sub-section X.Y → quy_trinh_noi_bo  (QĐ 1467)
        3. Có Điều X → luat_nghi_dinh
        4. unknown → fallback
        """
        text_lower = text.lower()
        src_lower  = source_name.lower()

        # Đếm mục (1)-(11) — đây là marker mạnh nhất cho QĐ 1085
        section_matches = [
            m for m in self.SECTION_RE.finditer(text)
            if 1 <= int(m.group(1)) <= 11
        ]
        n_sections = len(section_matches)

        # Đếm Bước
        n_buoc = len(self.BUOC_ANY_RE.findall(text))

        # Đếm sub-section X.Y (8.1, 8.2, 12.1...)
        n_subsec = len(self.SUB_PROC_RE.findall(text))

        logger.debug(
            f"  detect: sections={n_sections}, buoc={n_buoc}, subsec={n_subsec}"
        )

        # QĐ 1085: nhiều mục (1)-(11) → ưu tiên hàng đầu
        if n_sections >= 4:
            return "quyet_dinh_tthc"

        # QĐ 1467: có bảng Bước, sub-section X.Y, hoặc tên file chứa 1467
        if n_buoc >= 3 or n_subsec >= 2 or "1467" in src_lower:
            return "quy_trinh_noi_bo"

        # Luật / Nghị định
        if (
            self.ARTICLE_RE.search(text)
            or any(k in src_lower for k in ["luật", "luat", "nghị định", "nghi dinh", "thông tư"])
        ):
            return "luat_nghi_dinh"

        return "unknown"

    # ─────────────────────────────────────────────────────────────────────────
    # Strategy 1: QĐ 1085 — chunk theo mục (1)-(11)
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_quyet_dinh_tthc(
        self, text, source_file, source_name, group_type, procedure_type
    ) -> list[DocumentChunk]:
        """
        Chunk QĐ 1085 theo cấu trúc (1)-(11).

        Bước:
        1. Tách thành các khối thủ tục (theo "N. Tên thủ tục")
        2. Trong mỗi thủ tục, tách theo mục (1)-(11)
        3. Mỗi mục = 1 chunk, có prefix [Thủ tục] + [Mục]
        """
        chunks = []
        procedure_blocks = self._split_by_procedure_header(text)

        for proc_name, proc_type_key, proc_text in procedure_blocks:
            section_blocks = self._split_by_numbered_sections(proc_text)

            if not section_blocks:
                # Không tìm được (1)-(11) → fallback chunk toàn bộ
                fallback = self._chunk_fallback(
                    proc_text, source_file, source_name, group_type, procedure_type
                )
                for c in fallback:
                    c.procedure_name = proc_name
                chunks.extend(fallback)
                continue

            for sec_num, sec_text in section_blocks:
                if self._estimate_tokens(sec_text) < 1:
                    continue

                # Mục quá lớn → chia tiếp (giữ ngữ nghĩa, không cắt ngang Bước)
                if self._estimate_tokens(sec_text) > self.config.chunk_size * 2:
                    sub_texts = self._split_section_by_buoc_or_fallback(sec_text)
                else:
                    sub_texts = [sec_text]

                for sub_text in sub_texts:
                    sub_text = sub_text.strip()
                    if len(sub_text) < self.config.min_chunk_size:
                        continue

                    full_text = self._make_prefix(proc_name, sec_num) + sub_text

                    chunks.append(DocumentChunk(
                        chunk_id       = str(uuid.uuid4()),
                        text           = full_text,
                        token_estimate = self._estimate_tokens(full_text),
                        source_file    = source_file,
                        source_name    = source_name,
                        group_type     = group_type,
                        procedure_type = proc_type_key or procedure_type,
                        procedure_name = proc_name,
                        section_number = sec_num,
                        field_type     = SECTION_FIELD_MAP.get(sec_num, "general"),
                    ))

        return chunks

    def _split_by_procedure_header(self, text: str) -> list[tuple[str, str, str]]:
        """
        Tách text thành các khối thủ tục theo header "N. Tên thủ tục".

        Trả về: [(proc_name, proc_type_key, proc_text), ...]
        """
        matches = list(self.PROC_HEADER_RE.finditer(text))

        # Lọc: chỉ giữ những header có số từ 1-30 và tên đủ dài
        matches = [
            m for m in matches
            if int(m.group(1)) <= 30 and len(m.group(2).strip()) > 15
        ]

        if not matches:
            return [("Thủ tục đất đai", "all", text)]

        blocks = []
        for i, m in enumerate(matches):
            raw_name = re.sub(r"\s+", " ", m.group(2)).strip()[:200]
            proc_name = raw_name
            proc_type_key = self._guess_procedure_type(raw_name)
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            proc_text = text[start:end].strip()
            if len(proc_text) > 100:
                blocks.append((proc_name, proc_type_key, proc_text))

        return blocks if blocks else [("Thủ tục đất đai", "all", text)]

    def _split_by_numbered_sections(self, text: str) -> list[tuple[int, str]]:
        """
        Tách text thành các mục (1)-(11).
        Trả về: [(số_mục, nội_dung_mục), ...]
        """
        matches = [
            m for m in self.SECTION_RE.finditer(text)
            if 1 <= int(m.group(1)) <= 11
        ]

        if not matches:
            return []

        sections = []
        for i, m in enumerate(matches):
            sec_num = int(m.group(1))
            start   = m.start()
            end     = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sec_text = text[start:end].strip()
            if len(sec_text) >= self.config.min_chunk_size:
                sections.append((sec_num, sec_text))

        return sections

    def _split_section_by_buoc_or_fallback(self, text: str) -> list[str]:
        """
        Chia mục (1) Trình tự (thường rất dài) theo Bước 1/2/3.
        Fallback về RecursiveCharacterTextSplitter nếu không có Bước.
        """
        # Tách theo "Bước N:"
        buoc_pattern = re.compile(
            r"(B(?:ư|u)[oơ]c\s+\d+\s*:)",
            re.IGNORECASE,
        )
        parts = buoc_pattern.split(text)

        if len(parts) <= 1:
            return self._fallback_splitter.split_text(text)

        # Ghép lại: [prefix, "Bước 1:", nội_dung_1, "Bước 2:", nội_dung_2, ...]
        chunks = []
        if parts[0].strip():
            chunks.append(parts[0].strip())

        i = 1
        while i < len(parts) - 1:
            header  = parts[i]
            content = parts[i + 1] if i + 1 < len(parts) else ""
            combined = (header + content).strip()
            if len(combined) >= self.config.min_chunk_size:
                chunks.append(combined)
            i += 2

        return chunks if chunks else self._fallback_splitter.split_text(text)

    def _make_prefix(self, proc_name: str, sec_num: int) -> str:
        """Tạo context prefix cho chunk."""
        label = SECTION_LABEL_MAP.get(sec_num, f"({sec_num})")
        return f"[Thủ tục: {proc_name}]\n[Mục: {label}]\n"

    def _guess_procedure_type(self, proc_name: str) -> str:
        """Đoán procedure_type từ tên thủ tục."""
        name_lower = proc_name.lower()
        for keyword, ptype in PROCEDURE_SHORTNAME_MAP.items():
            if keyword in name_lower:
                return ptype
        return "all"

    # ─────────────────────────────────────────────────────────────────────────
    # Strategy 2: QĐ 1467 — chunk theo Bước (dạng bảng)
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_quy_trinh_noi_bo(
        self, text, source_file, source_name, group_type, procedure_type
    ) -> list[DocumentChunk]:
        """
        Chunk QĐ 1467 theo từng Bước trong mỗi sub-procedure.

        Cấu trúc:
          8.1 (trường hợp bản đồ chính quy)
            Bước 1 → chunk
            Bước 2 → chunk
            Tổng thời gian → chunk (field_type=thoi_han)
          8.2 (trường hợp thay đổi kích thước)
            Bước 1 → chunk
            ...
        """
        chunks = []

        # Ưu tiên tách theo sub-section (8.1, 8.2, 12.1...)
        sub_blocks = self._split_by_sub_procedure(text)

        for parent_name, sub_name, sub_text in sub_blocks:
            proc_display = f"{parent_name} — {sub_name}" if sub_name else parent_name

            # Tách các Bước
            step_blocks = self._split_by_buoc_table(sub_text)

            if not step_blocks:
                # Không tìm được Bước → 1 chunk cho cả sub-procedure
                sub_text_clean = sub_text.strip()
                if len(sub_text_clean) >= self.config.min_chunk_size:
                    full_text = f"[Thủ tục: {proc_display}]\n{sub_text_clean}"
                    chunks.append(DocumentChunk(
                        chunk_id       = str(uuid.uuid4()),
                        text           = full_text,
                        token_estimate = self._estimate_tokens(full_text),
                        source_file    = source_file,
                        source_name    = source_name,
                        group_type     = group_type,
                        procedure_type = self._guess_procedure_type(parent_name),
                        procedure_name = proc_display,
                        field_type     = "trinh_tu",
                    ))
                continue

            for step_num, step_content in step_blocks:
                step_content = step_content.strip()
                if len(step_content) < self.config.min_chunk_size:
                    continue

                full_text = (
                    f"[Thủ tục: {proc_display}]\n"
                    f"[Bước {step_num}]\n"
                    f"{step_content}"
                )
                chunks.append(DocumentChunk(
                    chunk_id       = str(uuid.uuid4()),
                    text           = full_text,
                    token_estimate = self._estimate_tokens(full_text),
                    source_file    = source_file,
                    source_name    = source_name,
                    group_type     = group_type,
                    procedure_type = self._guess_procedure_type(parent_name),
                    procedure_name = proc_display,
                    step_number    = step_num,
                    field_type     = "trinh_tu",
                ))

            # Chunk thời gian tổng
            time_match = self.TOTAL_TIME_RE.search(sub_text)
            if time_match:
                time_val  = time_match.group(1).strip()
                time_text = (
                    f"[Thủ tục: {proc_display}]\n"
                    f"[Mục: (4) Thời hạn giải quyết]\n"
                    f"Tổng thời gian giải quyết TTHC: {time_val}"
                )
                chunks.append(DocumentChunk(
                    chunk_id       = str(uuid.uuid4()),
                    text           = time_text,
                    token_estimate = self._estimate_tokens(time_text),
                    source_file    = source_file,
                    source_name    = source_name,
                    group_type     = group_type,
                    procedure_type = self._guess_procedure_type(parent_name),
                    procedure_name = proc_display,
                    section_number = 4,
                    field_type     = "thoi_han",
                ))

        return chunks

    def _split_by_sub_procedure(
        self, text: str
    ) -> list[tuple[str, str, str]]:
        """
        Tách text thành các sub-procedure: 8.1, 8.2, 12.1, 12.2...

        Trả về: [(parent_proc_name, sub_name, sub_text), ...]
        """
        # Tìm parent procedure headers trước (N. Tên thủ tục)
        parent_matches = list(self.PROC_HEADER_RE.finditer(text))
        parent_matches = [
            m for m in parent_matches
            if int(m.group(1)) <= 30 and len(m.group(2).strip()) > 15
        ]

        # Tìm sub-section headers (N.M Tên trường hợp)
        sub_matches = list(self.SUB_PROC_RE.finditer(text))

        if not sub_matches:
            # Không có sub-section → dùng parent hoặc toàn bộ
            if parent_matches:
                blocks = []
                for i, m in enumerate(parent_matches):
                    pname = re.sub(r"\s+", " ", m.group(2)).strip()[:200]
                    start = m.start()
                    end   = parent_matches[i + 1].start() if i + 1 < len(parent_matches) else len(text)
                    blocks.append((pname, "", text[start:end].strip()))
                return blocks
            return [("Quy trình nội bộ đất đai", "", text)]

        # Build map: sub_section_key → parent_name
        # Ví dụ: "8.1" → "Cấp đổi Giấy chứng nhận"
        parent_map: dict[str, str] = {}
        for pm in parent_matches:
            p_num  = int(pm.group(1))
            p_name = re.sub(r"\s+", " ", pm.group(2)).strip()[:200]
            parent_map[str(p_num)] = p_name

        blocks = []
        for i, sm in enumerate(sub_matches):
            sub_key  = sm.group(1)         # "8.1"
            sub_desc = re.sub(r"\s+", " ", sm.group(2)).strip()[:150]
            parent_num = sub_key.split(".")[0]
            parent_name = parent_map.get(parent_num, f"Thủ tục {parent_num}")

            start = sm.start()
            end   = sub_matches[i + 1].start() if i + 1 < len(sub_matches) else len(text)
            sub_text = text[start:end].strip()

            if len(sub_text) >= self.config.min_chunk_size:
                blocks.append((parent_name, sub_desc, sub_text))

        return blocks if blocks else [("Quy trình nội bộ", "", text)]

    def _split_by_buoc_table(self, text: str) -> list[tuple[int, str]]:
        """
        Tách text dạng bảng QĐ 1467 theo Bước 1, 2, 3...
        Xử lý nhiều cách viết do OCR: "Bước", "Buoc", "Bướóc"...
        """
        buoc_re = re.compile(
            r"B\s*[uưU]\s*[oơO]\s*[cC]\s+(\d+)",
            re.IGNORECASE,
        )
        matches = list(buoc_re.finditer(text))

        if not matches:
            return []

        steps = []
        for i, m in enumerate(matches):
            step_num = int(m.group(1))
            start    = m.start()
            end      = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            step_text = text[start:end].strip()

            # Bỏ qua những mục quá ngắn (header noise)
            if len(step_text) >= self.config.min_chunk_size:
                steps.append((step_num, step_text))

        return steps

    # ─────────────────────────────────────────────────────────────────────────
    # Strategy 3: Luật / Nghị định — chunk theo Điều
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_luat(
        self, text, source_file, source_name, group_type, procedure_type
    ) -> list[DocumentChunk]:
        """Chunk văn bản pháp luật theo Điều. Nếu Điều dài → split theo Khoản."""
        chunks = []
        matches = list(self.ARTICLE_RE.finditer(text))

        if not matches:
            return self._chunk_fallback(
                text, source_file, source_name, group_type, procedure_type
            )

        for i, m in enumerate(matches):
            art_header = m.group(1).strip()
            # Trích số điều: "Điều 3" → "Điều 3"
            art_num_match = re.search(r"Đi[eề]u\s+\d+", art_header, re.IGNORECASE)
            art_label     = art_num_match.group(0) if art_num_match else art_header

            start    = m.start()
            end      = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            art_text = text[start:end].strip()

            if len(art_text) < self.config.min_chunk_size:
                continue

            # Nếu điều quá dài → chunk theo Khoản
            if self._estimate_tokens(art_text) > self.config.chunk_size * 2:
                sub_texts = self._split_by_khoan(art_text)
            else:
                sub_texts = [art_text]

            for sub in sub_texts:
                sub = sub.strip()
                if len(sub) < self.config.min_chunk_size:
                    continue

                # Thêm prefix [Văn bản] + [Điều] để LLM biết chunk từ luật nào
                full_text = (
                    f"[Văn bản: {source_name}]\n"
                    f"[{art_label}]\n"
                    f"{sub}"
                )
                clause_match = re.match(r"\s*(\d+[a-zđ]?)\.\s", sub, re.IGNORECASE)
                clause_label = f"Khoản {clause_match.group(1)}" if clause_match else ""
                chunks.append(DocumentChunk(
                    chunk_id       = str(uuid.uuid4()),
                    text           = full_text,
                    token_estimate = self._estimate_tokens(full_text),
                    source_file    = source_file,
                    source_name    = source_name,
                    group_type     = group_type,
                    procedure_type = procedure_type,
                    article        = art_label,
                    clause         = clause_label,
                    field_type     = "can_cu_phap_ly",
                ))

        return chunks

    def _split_by_khoan(self, article_text: str) -> list[str]:
        """Chia Điều dài theo Khoản (1., 2., 3.)."""
        khoan_re = re.compile(r"^\s*(\d+)\.\s", re.MULTILINE)
        matches  = list(khoan_re.finditer(article_text))
        if not matches:
            return self._fallback_splitter.split_text(article_text)

        parts = []
        for i, m in enumerate(matches):
            start = m.start()
            end   = matches[i + 1].start() if i + 1 < len(matches) else len(article_text)
            k_text = article_text[start:end].strip()
            if len(k_text) >= self.config.min_chunk_size:
                parts.append(k_text)

        return parts if parts else [article_text]

    # ─────────────────────────────────────────────────────────────────────────
    # Fallback
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_fallback(
        self, text, source_file, source_name, group_type, procedure_type
    ) -> list[DocumentChunk]:
        """Fallback: RecursiveCharacterTextSplitter."""
        raw = self._fallback_splitter.split_text(text)
        return [
            DocumentChunk(
                chunk_id       = str(uuid.uuid4()),
                text           = c.strip(),
                token_estimate = self._estimate_tokens(c),
                source_file    = source_file,
                source_name    = source_name,
                group_type     = group_type,
                procedure_type = procedure_type,
                field_type     = "general",
            )
            for c in raw
            if len(c.strip()) >= self.config.min_chunk_size
        ]

    # ─────────────────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────────────────

    def _estimate_tokens(self, text: str) -> int:
        """Ước tính token: tiếng Việt ≈ 1.5 ký tự/token."""
        return max(1, int(len(text) / 1.5))
