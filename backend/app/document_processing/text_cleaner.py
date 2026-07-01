"""
TerraLegalAI — Text Cleaner
Làm sạch và chuẩn hóa text từ văn bản pháp lý Việt Nam.
Xử lý: header/footer, số trang, OCR artifacts, ký tự lạ.
"""
import logging
import re

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

    def clean(self, text: str, remove_headers: bool = True) -> str:
        """
        Làm sạch text toàn bộ.

        Args:
            text: Text thô từ PDF/DOCX
            remove_headers: Có bỏ header/footer không (mặc định True)

        Returns:
            Text đã được làm sạch
        """
        if not text:
            return ""

        # 1. Normalize encoding artifacts
        text = self._fix_encoding(text)

        # 2. Normalize whitespace
        text = self._normalize_whitespace(text)

        # 3. Remove page numbers
        text = self._remove_page_numbers(text)

        # 4. Remove repeated headers/footers (nếu bật)
        if remove_headers:
            text = self._remove_headers(text)

        # 5. Normalize legal text patterns
        text = self._normalize_legal_patterns(text)

        # 6. Final cleanup
        text = self._final_cleanup(text)

        return text.strip()

    def _fix_encoding(self, text: str) -> str:
        """Sửa OCR artifacts và encoding issues."""
        for old, new in self._OCR_ARTIFACTS.items():
            text = text.replace(old, new)
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
        # Track các header đã thấy (loại bỏ từ lần thứ 2 trở đi)
        seen_headers = set()

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
