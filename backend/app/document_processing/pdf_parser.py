"""
TerraLegalAI — PDF Document Parser
Sử dụng PyMuPDF (fitz) để extract text từ PDF văn bản pháp luật tiếng Việt.
Hỗ trợ: cấu trúc Điều/Khoản/Điểm, metadata extraction, làm sạch text.
Tự động phát hiện PDF scan và fallback sang OCR (Tesseract).
"""
import re
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def is_scanned_pdf(file_path: str | Path, sample_pages: int = 3) -> bool:
    """
    Kiểm tra PDF có phải là ảnh scan không (không có text layer).
    
    Args:
        file_path: Đường dẫn file PDF
        sample_pages: Số trang để kiểm tra
        
    Returns:
        True nếu PDF là scan, False nếu có text layer
    """
    doc = fitz.open(str(file_path))
    total_chars = 0
    pages_checked = min(sample_pages, len(doc))
    for i in range(pages_checked):
        total_chars += len(doc[i].get_text().strip())
    doc.close()
    # Nếu trung bình < 50 ký tự/trang → là scan
    return (total_chars / max(pages_checked, 1)) < 50


@dataclass
class ParsedPage:
    page_number: int
    text: str
    is_empty: bool = False


@dataclass
class ParsedDocument:
    """Kết quả parse một file PDF."""
    file_path: str
    file_name: str
    total_pages: int
    full_text: str
    pages: list[ParsedPage] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
    # Detected structure
    detected_articles: list[str] = field(default_factory=list)  # Điều 1, Điều 2...
    detected_procedure_name: Optional[str] = None


class PDFParser:
    """
    Parser cho văn bản pháp luật đất đai tiếng Việt.
    
    Xử lý đặc biệt:
    - Loại bỏ header/footer lặp lại
    - Nhận dạng cấu trúc Điều/Khoản/Điểm
    - Normalize khoảng trắng và encoding tiếng Việt
    """

    # Regex nhận dạng cấu trúc pháp lý
    ARTICLE_PATTERN = re.compile(
        r"^(Điều\s+\d+[a-z]?[\.\:]?\s*.{0,100})$",
        re.MULTILINE | re.IGNORECASE
    )
    CLAUSE_PATTERN = re.compile(
        r"^\s*(\d+\.\s+.{0,200})$",
        re.MULTILINE
    )
    POINT_PATTERN = re.compile(
        r"^\s*([a-z]\)\s+.{0,200})$",
        re.MULTILINE
    )
    PROCEDURE_NAME_PATTERN = re.compile(
        r"(Thủ tục\s+.{10,150}?)(?:\n|\.)",
        re.IGNORECASE
    )

    # Patterns để loại bỏ header/footer thường gặp
    HEADER_FOOTER_PATTERNS = [
        re.compile(r"^\s*\d+\s*$", re.MULTILINE),          # Số trang đơn lẻ
        re.compile(r"Trang\s+\d+\s+/\s+\d+", re.IGNORECASE),
        re.compile(r"^\s*[-–—]+\s*$", re.MULTILINE),        # Đường kẻ
    ]

    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse một file PDF và trả về ParsedDocument.
        
        Args:
            file_path: Đường dẫn đến file PDF
            
        Returns:
            ParsedDocument với full_text, pages, metadata
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")
        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"File không phải PDF: {file_path}")

        logger.info(f"Đang parse: {file_path.name}")

        doc = fitz.open(str(file_path))
        pages = []
        all_text_parts = []

        import pytesseract
        from PIL import Image
        import io

        for page_num in range(len(doc)):
            page = doc[page_num]
            raw_text = page.get_text("text")
            cleaned = self._clean_page_text(raw_text)

            # OCR fallback for scanned pages
            if len(cleaned.strip()) < 20:
                logger.info(f"  Trang {page_num + 1} trống hoặc là ảnh scan, đang chạy OCR (Tesseract)...")
                try:
                    pix = page.get_pixmap(dpi=150)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    # Convert to grayscale to improve OCR slightly
                    img = img.convert('L')
                    ocr_text = pytesseract.image_to_string(img, lang="vie")
                    cleaned = self._clean_page_text(ocr_text)
                except Exception as e:
                    logger.error(f"  Lỗi OCR ở trang {page_num + 1}: {e}")

            parsed_page = ParsedPage(
                page_number=page_num + 1,
                text=cleaned,
                is_empty=len(cleaned.strip()) < 20,
            )
            pages.append(parsed_page)
            if not parsed_page.is_empty:
                all_text_parts.append(cleaned)

        doc.close()

        full_text = "\n\n".join(all_text_parts)
        full_text = self._normalize_whitespace(full_text)

        # Extract metadata và cấu trúc
        detected_articles = self._detect_articles(full_text)
        procedure_name = self._detect_procedure_name(full_text)

        result = ParsedDocument(
            file_path=str(file_path),
            file_name=file_path.name,
            total_pages=len(doc) if not doc.is_closed else len(pages),
            full_text=full_text,
            pages=pages,
            metadata={
                "file_size_bytes": file_path.stat().st_size,
                "file_name": file_path.name,
            },
            detected_articles=detected_articles,
            detected_procedure_name=procedure_name,
        )

        logger.info(
            f"✅ Parse xong: {file_path.name} | "
            f"{len(pages)} trang | "
            f"{len(detected_articles)} điều | "
            f"{len(full_text):,} ký tự"
        )
        return result

    def _clean_page_text(self, raw_text: str) -> str:
        """Làm sạch text một trang PDF."""
        # Xóa header/footer patterns
        for pattern in self.HEADER_FOOTER_PATTERNS:
            raw_text = pattern.sub("", raw_text)

        # Normalize dấu gạch ngang, nháy kép kiểu đặc biệt
        raw_text = raw_text.replace("\u2013", "-").replace("\u2014", "-")
        raw_text = raw_text.replace("\u201c", '"').replace("\u201d", '"')
        raw_text = raw_text.replace("\u2018", "'").replace("\u2019", "'")

        # Xóa ký tự không in được (trừ newline, tab)
        raw_text = re.sub(r"[^\S\n\t ]+", " ", raw_text)

        # Ghép dòng bị ngắt giữa chừng (word wrap)
        raw_text = re.sub(r"(\w)-\n(\w)", r"\1\2", raw_text)

        return raw_text.strip()

    def _normalize_whitespace(self, text: str) -> str:
        """Chuẩn hóa khoảng trắng trong toàn bộ văn bản."""
        # Giảm nhiều dòng trống liên tiếp xuống còn 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Xóa khoảng trắng cuối dòng
        text = re.sub(r" +\n", "\n", text)
        # Xóa khoảng trắng đầu dòng quá nhiều
        text = re.sub(r"^\s{4,}", "  ", text, flags=re.MULTILINE)
        return text.strip()

    def _detect_articles(self, text: str) -> list[str]:
        """Nhận dạng các Điều trong văn bản."""
        matches = self.ARTICLE_PATTERN.findall(text)
        # Deduplicate và clean
        seen = set()
        result = []
        for m in matches:
            m_clean = m.strip()
            if m_clean not in seen:
                seen.add(m_clean)
                result.append(m_clean)
        return result

    def _detect_procedure_name(self, text: str) -> Optional[str]:
        """Tìm tên thủ tục hành chính trong văn bản."""
        match = self.PROCEDURE_NAME_PATTERN.search(text)
        if match:
            return match.group(1).strip()
        return None


# ─── Quick test ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python pdf_parser.py <path_to_pdf>")
        sys.exit(1)

    parser = PDFParser()
    result = parser.parse(sys.argv[1])

    print(f"\n{'='*60}")
    print(f"File: {result.file_name}")
    print(f"Tổng trang: {result.total_pages}")
    print(f"Tổng ký tự: {len(result.full_text):,}")
    print(f"Số Điều phát hiện: {len(result.detected_articles)}")
    if result.detected_procedure_name:
        print(f"Tên thủ tục: {result.detected_procedure_name}")
    print(f"\n--- 500 ký tự đầu ---")
    print(result.full_text[:500])
    print(f"\n--- Các Điều phát hiện (10 đầu) ---")
    for a in result.detected_articles[:10]:
        print(f"  • {a}")
