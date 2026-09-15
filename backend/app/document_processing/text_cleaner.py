"""
TerraLegalAI — Text Cleaner
Làm sạch và chuẩn hóa text từ văn bản pháp lý Việt Nam.
Xử lý: header/footer, số trang, OCR artifacts, ký tự lạ.
"""
import logging
import re
import unicodedata

logger = logging.getLogger(__name__)


class TextCleaner:
    """
    Làm sạch text từ PDF/DOCX văn bản pháp lý.
    Bao gồm: bỏ header/footer, số trang, ký tự đặc biệt OCR.
    """

    # Pattern nhận dạng header/footer văn bản pháp lý VN
    _PAGE_NUMBER_PATTERNS = [
        r"^\s*-\s*\d+\s*-\s*$",             # - 1 - hoặc - 12 -
        r"^\s*Trang\s+\d+\s*/\s*\d+\s*$",   # Trang 1/10
        r"^\s*\d+\s*$",                       # Số đứng một mình
    ]

    _HEADER_FOOTER_PATTERNS = [
        r"^ỦY BAN NHÂN DÂN.{0,50}$",
        r"^CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM",
        r"^Độc lập - Tự do - Hạnh phúc",
        r"^Vĩnh Long,\s+ngày\s+\d+",
        r"^Số:\s*\d+",
    ]

    _OCR_ARTIFACTS = {
        "ﬁ": "fi",
        "ﬀ": "ff",
        "ﬂ": "fl",
        "–": "-",
        "—": "-",
        "\u00a0": " ",    # non-breaking space
        "\u200b": "",     # zero-width space
        "\ufeff": "",     # BOM
        "…": "...",
    }

    # ── Sửa lỗi chính tả OCR phổ biến trong văn bản đất đai ─────────────────
    # Danh sách (sai, đúng) — cụm từ dài trước để tránh partial replace.
    # Chỉ sửa những lỗi chắc chắn, KHÔNG dùng spell-checker tự động
    # để tránh sửa nhầm mã TTHC, tên người, địa danh.
    _OCR_LEGAL_CORRECTIONS: list[tuple[str, str]] = [
        # ── giấy chứng nhận (nhân → nhận) ──────────────────────────────────
        ("giấy chứng nhân quyền sử dụng đất", "giấy chứng nhận quyền sử dụng đất"),
        ("Giấy chứng nhân quyền sử dụng đất", "Giấy chứng nhận quyền sử dụng đất"),
        ("giấy chứng nhân quyền", "giấy chứng nhận quyền"),
        ("Giấy chứng nhân quyền", "Giấy chứng nhận quyền"),
        ("giấy chứng nhân", "giấy chứng nhận"),

        # ── nhân dân / nhân dân ─────────────────────────────────────────────
        ("ủy ban nhân dan", "ủy ban nhân dân"),
        ("Ủy ban nhân dan", "Ủy ban nhân dân"),
        ("Ủy Ban Nhân Dan", "Ủy Ban Nhân Dân"),

        # ── đất / dat ───────────────────────────────────────────────────────
        ("quyền sử dụng dat", "quyền sử dụng đất"),
        ("quyền sở hữu dat",  "quyền sở hữu đất"),
        ("thu hồi dat",       "thu hồi đất"),
        ("sử dụng dat",       "sử dụng đất"),
        (" dat đai",          " đất đai"),
        (" dat\n",            " đất\n"),

        # ── chuyển nhượng ───────────────────────────────────────────────────
        ("chuyển nhương",  "chuyển nhượng"),
        ("Chuyển nhương",  "Chuyển nhượng"),
        ("Chuyển Nhương",  "Chuyển Nhượng"),

        # ── thừa kế ─────────────────────────────────────────────────────────
        ("thừa kể",  "thừa kế"),
        ("Thừa kể",  "Thừa kế"),
        ("thừa kê",  "thừa kế"),

        # ── tặng cho ────────────────────────────────────────────────────────
        ("tặng chô",  "tặng cho"),
        ("Tặng chô",  "Tặng cho"),

        # ── hồ sơ ───────────────────────────────────────────────────────────
        ("ho sơ",   "hồ sơ"),
        ("hồ so",   "hồ sơ"),
        ("Hồ so",   "Hồ sơ"),

        # ── thủ tục hành chính ──────────────────────────────────────────────
        ("thủ tuc hành chính",  "thủ tục hành chính"),
        ("thủ tuc",             "thủ tục"),
        ("thủ tục hanh chính",  "thủ tục hành chính"),
        ("thủ tục hành chinh",  "thủ tục hành chính"),

        # ── cơ quan ─────────────────────────────────────────────────────────
        ("co quan",  "cơ quan"),
        ("Co quan",  "Cơ quan"),

        # ── đăng ký ─────────────────────────────────────────────────────────
        ("dăng ký",  "đăng ký"),
        ("Dăng ký",  "Đăng ký"),
        ("đang ký",  "đăng ký"),
        ("Đang ký",  "Đăng ký"),

        # ── biến động ───────────────────────────────────────────────────────
        ("biến dộng",  "biến động"),
        ("Biến dộng",  "Biến động"),

        # ── thời hạn ────────────────────────────────────────────────────────
        ("thơi hạn",  "thời hạn"),
        ("thời han",  "thời hạn"),

        # ── địa chỉ / địa phương ────────────────────────────────────────────
        ("dia chỉ",    "địa chỉ"),
        ("dia phương", "địa phương"),
        ("Dia chỉ",    "Địa chỉ"),
    ]

    # ── Regex: ký tự rác không thuộc tiếng Việt/Latin/ASCII ─────────────────
    # Giữ lại: ASCII printable + Latin Extended (Việt) + combining diacritics
    # Loại bỏ: Private Use, CJK, Specials, Surrogates, v.v.
    _GARBAGE_CHAR_RE = re.compile(
        r"[^\u0000-\u007F"     # ASCII
        r"\u00C0-\u024F"       # Latin Extended (tiếng Âu)
        r"\u0300-\u036F"       # Combining diacritical marks
        r"\u1E00-\u1EFF"       # Latin Extended Additional (tiếng Việt)
        r"\s]",                # whitespace
        re.UNICODE,
    )

    # ── Regex: chuỗi ký tự ASCII rác ngắn kẹp giữa text tiếng Việt ──────────
    # OCR đôi khi tạo ra chuỗi như "<J'ng", "nscr,,", "<<J" xen vào giữa từ.
    # Pattern: ký tự non-word ASCII (<, >, ', ", `, ~, ^, \, |, {, }) liên tiếp
    # theo sau bởi 1-4 ký tự ASCII không phải chữ cái tiếng Việt.
    _OCR_INLINE_GARBAGE_RE = re.compile(
        r"[<>\'\"``~^\\|{}\[\]]{1,3}[A-Za-z0-9]{0,4}[,;:!?]{0,2}"
        r"(?=\s|[\u00C0-\u024F\u1E00-\u1EFF])",  # theo sau là space hoặc ký tự Việt
        re.UNICODE,
    )

    def clean(self, text: str, remove_headers: bool = True) -> str:
        """
        Làm sạch text toàn bộ.

        Pipeline (theo thứ tự):
          0. Normalize Unicode form NFC  (fix dấu tổ hợp)
          1. Fix encoding/OCR artifacts
          2. Xóa ký tự rác ngoài range tiếng Việt
          3. Normalize whitespace
          4. Xóa số trang
          5. Xóa header/footer lặp lại
          6. Normalize legal patterns
          7. Áp dụng corrections domain đất đai
          8. Final cleanup

        Args:
            text: Text thô từ PDF/DOCX
            remove_headers: Có bỏ header/footer không (mặc định True)

        Returns:
            Text đã được làm sạch
        """
        if not text:
            return ""

        # 0. Normalize Unicode form NFC (fix dấu tổ hợp → dựng sẵn)
        text = self._normalize_unicode_form(text)

        # 1. Normalize encoding artifacts
        text = self._fix_encoding(text)

        # 2. Xóa ký tự rác ngoài range tiếng Việt/Latin
        text = self._remove_garbage_chars(text)

        # 3. Normalize whitespace
        text = self._normalize_whitespace(text)

        # 4. Remove page numbers
        text = self._remove_page_numbers(text)

        # 5. Remove repeated headers/footers (nếu bật)
        if remove_headers:
            text = self._remove_headers(text)

        # 6. Normalize legal text patterns
        text = self._normalize_legal_patterns(text)

        # 7. Áp dụng corrections domain đất đai
        text = self._apply_legal_corrections(text)

        # 8. Final cleanup
        text = self._final_cleanup(text)

        return text.strip()

    # ── Core cleaning methods ────────────────────────────────────────────────

    def _normalize_unicode_form(self, text: str) -> str:
        """
        Chuẩn hóa Unicode sang dạng NFC (Normalization Form C).

        Tiếng Việt có thể encode theo 2 cách:
          - NFC: chữ + dấu = 1 ký tự dựng sẵn (e.g. ề = U+1EC1)
          - NFD: chữ + combining marks riêng (e.g. e + ◌̂ + ◌̀)
        OCR và copy-paste từ Word thường trộn 2 dạng, khiến search thất bại.
        """
        return unicodedata.normalize("NFC", text)

    def _fix_encoding(self, text: str) -> str:
        """Sửa OCR artifacts và encoding issues."""
        for old, new in self._OCR_ARTIFACTS.items():
            text = text.replace(old, new)
        return text

    def _remove_garbage_chars(self, text: str) -> str:
        """
        Xóa ký tự rác nằm ngoài range tiếng Việt/Latin/ASCII.

        Xử lý 2 loại rác:
        1. Ký tự ngoài range tiếng Việt/Latin (Private Use, CJK, v.v.)
           → thay bằng space để tránh ghép từ sai
        2. Chuỗi ASCII ngắn kiểu "<J'", "nscr,," kẹp giữa từ Việt
           → thay bằng space
        """
        # Layer 1: ký tự ngoài Unicode range Việt
        text = self._GARBAGE_CHAR_RE.sub(" ", text)
        # Layer 2: chuỗi ASCII rác xen giữa từ Việt
        text = self._OCR_INLINE_GARBAGE_RE.sub(" ", text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        """Chuẩn hóa khoảng trắng: tab → space, multiple spaces → single."""
        text = text.replace("\t", " ")
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text

    def _remove_page_numbers(self, text: str) -> str:
        """Xóa các dòng chỉ chứa số trang."""
        lines = text.split("\n")
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            is_page_num = any(
                re.match(p, stripped, re.IGNORECASE)
                for p in self._PAGE_NUMBER_PATTERNS
            )
            if not is_page_num:
                cleaned_lines.append(line)
        return "\n".join(cleaned_lines)

    def _remove_headers(self, text: str) -> str:
        """
        Xóa header/footer lặp lại trong văn bản.
        Phát hiện bằng pattern matching với văn bản hành chính VN.
        """
        lines = text.split("\n")
        cleaned_lines = []
        seen_headers: set[str] = set()

        for line in lines:
            stripped = line.strip()
            is_header = any(
                re.match(p, stripped, re.IGNORECASE)
                for p in self._HEADER_FOOTER_PATTERNS
            )
            if is_header:
                if stripped not in seen_headers:
                    seen_headers.add(stripped)
                    cleaned_lines.append(line)
                # else: bỏ qua header lặp lại
            else:
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)

    def _normalize_legal_patterns(self, text: str) -> str:
        """
        Chuẩn hóa patterns pháp lý để dễ chunk và tìm kiếm.
        VD: "Điều1." → "Điều 1." | "Khoản1)" → "Khoản 1)"
        """
        # Thêm space giữa "Điều/Khoản/Điểm" và số
        text = re.sub(r"(Điều|Khoản|Điểm|Mục|Chương)(\d+)", r"\1 \2", text)
        # Normalize bullet points
        text = re.sub(r"^[•●▪▸►]\s*", "- ", text, flags=re.MULTILINE)
        return text

    def _apply_legal_corrections(self, text: str) -> str:
        """
        Áp dụng corrections domain đất đai — sửa lỗi OCR phổ biến.

        Dùng simple string replace (không regex) để tránh side effects.
        Corrections được apply theo thứ tự: cụm dài trước, ngắn sau.
        """
        for wrong, right in self._OCR_LEGAL_CORRECTIONS:
            if wrong in text:
                text = text.replace(wrong, right)
        return text

    def _final_cleanup(self, text: str) -> str:
        """Dọn dẹp cuối: bỏ dòng trắng liên tiếp quá nhiều."""
        # Tối đa 2 dòng trắng liên tiếp
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    def get_stats(self, original: str, cleaned: str) -> dict:
        """Trả về thống kê trước và sau cleaning."""
        return {
            "original_chars": len(original),
            "cleaned_chars": len(cleaned),
            "original_lines": original.count("\n"),
            "cleaned_lines": cleaned.count("\n"),
            "reduction_pct": round((1 - len(cleaned) / max(len(original), 1)) * 100, 1),
        }
