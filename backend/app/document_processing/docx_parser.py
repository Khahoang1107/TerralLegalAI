"""
TerraLegalAI — DOCX Parser (v2 — Table-Aware)
Parse file DOCX giữ nguyên thứ tự xuất hiện của đoạn văn và bảng.

Cải tiến so với v1:
- Duyệt theo thứ tự xuất hiện thực tế (paragraph XEN KẼ table), không tách rời
- Bảng được giữ nguyên cấu trúc → Markdown table (không flatten thành chuỗi phẳng)
- Phát hiện loại bảng từ tiêu đề/nội dung (hồ sơ / trình tự / lệ phí / điều kiện)
- Backward compatible: full_text vẫn xuất ra để các code cũ không bị vỡ
"""
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# ── Nhận dạng loại bảng ──────────────────────────────────────────
TABLE_TYPE_KEYWORDS: dict[str, list[str]] = {
    "ho_so": [
        "thành phần hồ sơ", "giấy tờ", "hồ sơ gồm", "danh mục hồ sơ",
        "bản chính", "bản sao", "hồ sơ nộp", "tài liệu cần",
    ],
    "trinh_tu": [
        "trình tự", "bước", "tiếp nhận hồ sơ", "thẩm định",
        "trả kết quả", "quy trình", "các bước thực hiện",
    ],
    "le_phi": [
        "lệ phí", "phí", "mức thu", "chi phí", "không thu phí",
        "miễn phí", "phí thẩm định",
    ],
    "dieu_kien": [
        "điều kiện", "yêu cầu", "trường hợp", "đáp ứng",
    ],
    "thoi_han": [
        "thời hạn", "ngày làm việc", "ngày kể từ", "thời gian giải quyết",
    ],
    "can_cu_phap_ly": [
        "căn cứ pháp lý", "văn bản pháp luật", "cơ sở pháp lý",
        "theo quy định tại", "luật", "nghị định",
    ],
}


def _detect_table_type(context_before: str, header_row: list[str], first_data_rows: list[list[str]]) -> str:
    """Phát hiện loại bảng dựa trên tiêu đề bảng và nội dung."""
    combined = " ".join([
        context_before,
        " ".join(header_row),
        " ".join(c for row in first_data_rows[:3] for c in row),
    ]).lower()

    for table_type, keywords in TABLE_TYPE_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return table_type
    return "general"


def _table_to_markdown(headers: list[str], rows: list[list[str]]) -> str:
    """Convert bảng (headers + rows) thành Markdown table."""
    # Chuẩn hóa: đảm bảo tất cả hàng có cùng số cột
    n_cols = max(len(headers), max((len(r) for r in rows), default=0))
    if n_cols == 0:
        return ""

    def pad_row(r: list[str], n: int) -> list[str]:
        r = [c.replace("|", "｜").replace("\n", " ").strip() for c in r]
        return r + [""] * (n - len(r))

    lines = []
    if any(h.strip() for h in headers):
        padded_h = pad_row(headers, n_cols)
        lines.append("| " + " | ".join(padded_h) + " |")
        lines.append("|" + "|".join([" --- "] * n_cols) + "|")
    else:
        # Không có header rõ ràng — dùng hàng đầu tiên làm header nếu có
        if rows:
            first = pad_row(rows[0], n_cols)
            lines.append("| " + " | ".join(first) + " |")
            lines.append("|" + "|".join([" --- "] * n_cols) + "|")
            rows = rows[1:]

    for row in rows:
        padded = pad_row(row, n_cols)
        lines.append("| " + " | ".join(padded) + " |")

    return "\n".join(lines)


# ── Data classes ─────────────────────────────────────────────────

@dataclass
class ParsedTable:
    """Một bảng được parse từ DOCX, giữ nguyên cấu trúc."""
    table_index: int
    headers: list[str]              # Hàng tiêu đề (hàng đầu hoặc hàng có kiểu bold)
    rows: list[list[str]]           # Các hàng dữ liệu
    context_before: str             # Đoạn văn ngay trước bảng (thường là tiêu đề)
    table_type: str                 # "ho_so" | "trinh_tu" | "le_phi" | "general" | ...
    markdown_repr: str              # Markdown table để đưa vào LLM


@dataclass
class ParsedParagraph:
    """Một đoạn văn thông thường."""
    text: str
    is_heading: bool = False
    heading_level: int = 0          # 1 = Heading 1, 2 = Heading 2, v.v.


@dataclass
class ParsedDocument:
    """Kết quả parse một file DOCX (v2 — Table-Aware).

    Backward-compatible: ``full_text`` và ``tables`` vẫn xuất ra.
    ``segments`` chứa thứ tự xuất hiện thực tế (paragraph xen kẽ table).
    """
    file_path: str
    full_text: str
    total_paragraphs: int = 0
    tables: list[list[list[str]]] = field(default_factory=list)     # raw rows (cũ)
    parsed_tables: list[ParsedTable] = field(default_factory=list)   # structured (mới)
    segments: list[Union[ParsedParagraph, ParsedTable]] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ── Parser ───────────────────────────────────────────────────────

class DOCXParser:
    """
    Parser cho file DOCX dùng python-docx.
    Duyệt body theo thứ tự thực tế để giữ đúng vị trí bảng so với đoạn văn.
    """

    # Namespace XML của OOXML
    _W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

    def parse(self, file_path: str | Path) -> ParsedDocument:
        """
        Parse file DOCX thành ParsedDocument với cấu trúc bảng nguyên vẹn.

        Args:
            file_path: Đường dẫn file DOCX

        Returns:
            ParsedDocument với segments (thứ tự thực), full_text (backward compat)
        """
        try:
            from docx import Document as DocxDocument
            from docx.oxml.ns import qn
        except ImportError:
            raise RuntimeError("Cần cài python-docx: pip install python-docx")

        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File không tồn tại: {file_path}")

        logger.info(f"Parsing DOCX (table-aware): {file_path.name}")
        doc = DocxDocument(str(file_path))

        segments: list[Union[ParsedParagraph, ParsedTable]] = []
        table_index = 0
        para_count = 0
        raw_tables_data: list[list[list[str]]] = []
        parsed_tables: list[ParsedTable] = []

        # Lấy context của đoạn văn ngay trước bảng
        last_para_text = ""

        # Duyệt body.xml theo thứ tự xuất hiện thực tế
        body = doc.element.body
        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

            # ── Paragraph ────────────────────────────────────────
            if tag == "p":
                # Dùng api chuẩn để lấy text + style
                para_obj = self._find_para_object(doc, child)
                if para_obj is not None:
                    text = para_obj.text.strip()
                    style_name = para_obj.style.name if para_obj.style else ""
                else:
                    text = self._extract_text_from_element(child)

                if not text:
                    continue

                is_heading = False
                heading_level = 0
                if para_obj is not None:
                    style_name = para_obj.style.name if para_obj.style else ""
                    if "Heading" in style_name:
                        is_heading = True
                        try:
                            heading_level = int(style_name.replace("Heading", "").strip())
                        except ValueError:
                            heading_level = 1
                    elif style_name.startswith("Title"):
                        is_heading = True
                        heading_level = 0

                para_seg = ParsedParagraph(
                    text=text,
                    is_heading=is_heading,
                    heading_level=heading_level,
                )
                segments.append(para_seg)
                last_para_text = text
                para_count += 1

            # ── Table ─────────────────────────────────────────────
            elif tag == "tbl":
                tbl_obj = self._find_table_object(doc, child)

                if tbl_obj is not None:
                    raw_rows = self._extract_table_rows(tbl_obj)
                else:
                    raw_rows = self._extract_raw_table_rows(child)

                if not raw_rows:
                    continue

                raw_tables_data.append(raw_rows)

                # Phát hiện header: hàng đầu thường là tiêu đề
                headers = raw_rows[0] if raw_rows else []
                data_rows = raw_rows[1:] if len(raw_rows) > 1 else raw_rows

                # Detect loại bảng
                tbl_type = _detect_table_type(last_para_text, headers, data_rows[:3])

                # Tạo Markdown
                markdown = _table_to_markdown(headers, data_rows)

                parsed_tbl = ParsedTable(
                    table_index=table_index,
                    headers=headers,
                    rows=data_rows,
                    context_before=last_para_text,
                    table_type=tbl_type,
                    markdown_repr=markdown,
                )
                parsed_tables.append(parsed_tbl)
                segments.append(parsed_tbl)
                table_index += 1

        # Tổng hợp full_text (backward compat): paragraph + Markdown bảng
        text_parts: list[str] = []
        for seg in segments:
            if isinstance(seg, ParsedParagraph):
                if seg.is_heading:
                    text_parts.append(f"\n\n{seg.text}\n")
                else:
                    text_parts.append(seg.text)
            else:  # ParsedTable
                label = f"[Bảng: {seg.table_type}]" if seg.table_type != "general" else "[Bảng]"
                if seg.context_before:
                    text_parts.append(f"\n{label}\n{seg.markdown_repr}\n")
                else:
                    text_parts.append(f"\n{label}\n{seg.markdown_repr}\n")

        full_text = self._clean_text("\n".join(text_parts))

        logger.info(
            f"DOCX parsed (v2): {para_count} đoạn văn, {table_index} bảng, "
            f"{len(segments)} segments, {len(full_text):,} ký tự"
        )

        return ParsedDocument(
            file_path=str(file_path),
            full_text=full_text,
            total_paragraphs=para_count,
            tables=raw_tables_data,
            parsed_tables=parsed_tables,
            segments=segments,
            metadata={
                "filename": file_path.name,
                "file_size": file_path.stat().st_size,
                "table_count": table_index,
                "segment_count": len(segments),
            },
        )

    # ── Helpers ──────────────────────────────────────────────────

    def _find_para_object(self, doc, xml_element):
        """Tìm paragraph object tương ứng với xml element trong doc.paragraphs."""
        try:
            for p in doc.paragraphs:
                if p._element is xml_element:
                    return p
        except Exception:
            pass
        return None

    def _find_table_object(self, doc, xml_element):
        """Tìm table object tương ứng với xml element trong doc.tables."""
        try:
            for t in doc.tables:
                if t._element is xml_element:
                    return t
        except Exception:
            pass
        return None

    def _extract_table_rows(self, table) -> list[list[str]]:
        """Extract rows từ table object của python-docx."""
        rows = []
        seen_coords: set[tuple[int, int]] = set()
        for ri, row in enumerate(table.rows):
            row_cells = []
            for ci, cell in enumerate(row.cells):
                # Bỏ qua merged cells (python-docx lặp lại)
                coord = (ri, ci)
                if coord not in seen_coords:
                    seen_coords.add(coord)
                    row_cells.append(cell.text.strip())
            if any(c for c in row_cells):
                rows.append(row_cells)
        return rows

    def _extract_text_from_element(self, element) -> str:
        """Fallback: extract text thô từ XML element."""
        texts = []
        for t in element.iter():
            tag = t.tag.split("}")[-1] if "}" in t.tag else t.tag
            if tag == "t" and t.text:
                texts.append(t.text)
        return "".join(texts).strip()

    def _extract_raw_table_rows(self, tbl_element) -> list[list[str]]:
        """Fallback: extract rows từ XML table element trực tiếp."""
        rows = []
        for tr in tbl_element:
            tag = tr.tag.split("}")[-1] if "}" in tr.tag else tr.tag
            if tag != "tr":
                continue
            cells = []
            for tc in tr:
                cell_tag = tc.tag.split("}")[-1] if "}" in tc.tag else tc.tag
                if cell_tag == "tc":
                    cell_text = self._extract_text_from_element(tc)
                    cells.append(cell_text)
            if any(c for c in cells):
                rows.append(cells)
        return rows

    def _clean_text(self, text: str) -> str:
        """Làm sạch text: bỏ khoảng trắng thừa, normalize."""
        # Loại bỏ dòng trắng liên tiếp (giữ tối đa 2 dòng trắng)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Loại bỏ khoảng trắng thừa trong cùng một dòng
        text = re.sub(r"[ \t]+", " ", text)
        # Trim từng dòng
        lines = [line.strip() for line in text.split("\n")]
        return "\n".join(lines).strip()


# ── Quick test ───────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if len(sys.argv) < 2:
        print("Usage: python docx_parser.py <path_to_docx>")
        sys.exit(1)

    parser = DOCXParser()
    result = parser.parse(sys.argv[1])

    print(f"\n{'='*60}")
    print(f"File: {result.metadata.get('filename')}")
    print(f"Đoạn văn: {result.total_paragraphs}")
    print(f"Bảng: {result.metadata.get('table_count')}")
    print(f"Segments: {result.metadata.get('segment_count')}")
    print(f"Ký tự: {len(result.full_text):,}")

    print(f"\n--- Segments theo thứ tự ---")
    for i, seg in enumerate(result.segments[:10]):
        if isinstance(seg, ParsedParagraph):
            print(f"  [{i}] PARA: {seg.text[:60]}...")
        else:
            print(f"  [{i}] TABLE ({seg.table_type}): {len(seg.rows)} hàng")
            print(f"       Context: {seg.context_before[:50]}...")
            print(f"       Markdown (4 dòng đầu):")
            for line in seg.markdown_repr.split("\n")[:4]:
                print(f"         {line}")
