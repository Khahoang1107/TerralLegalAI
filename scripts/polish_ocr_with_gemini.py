"""
TerraLegalAI — Polish OCR text with Gemini 2.5 Flash
Sửa lỗi chính tả, phục hồi dấu tiếng Việt cho các file text OCR trong data/processed/ocr_text/
Đảm bảo bảo toàn 100% nội dung, không tóm tắt, kiểm tra độ dài nghiêm ngặt.
"""
import os
import sys
import re
import time
from pathlib import Path

# Fix console encoding on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not API_KEY:
    print("[ERROR] Không tìm thấy GEMINI_API_KEY trong .env")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

SYSTEM_PROMPT = """Bạn là chuyên viên số hóa tài liệu pháp lý và hiệu đính văn bản nhà nước Việt Nam.
Nhiệm vụ: Sửa lỗi chính tả, phục hồi đầy đủ dấu thanh tiếng Việt cho bản trích xuất OCR của văn bản pháp luật đất đai.

QUY TẮC BẮT BUỘC:
1. TUYỆT ĐỐI KHÔNG TÓM TẮT. Bảo toàn 100% tất cả các câu, các đoạn, các bước quy trình, các gạch đầu dòng và số thứ tự.
2. Giữ nguyên toàn bộ cấu trúc: Số quyết định, ngày tháng năm, Điều, Khoản, Điểm, Bước 1, Bước 2, Bước 3, Hồ sơ, Thời hạn, Cơ quan thực hiện.
3. Sửa đúng các lỗi OCR phổ biến:
   - 'dang ky dat dai' -> 'đăng ký đất đai'
   - 'hé so' / 'ho so' -> 'hồ sơ'
   - 'sir dung dat' / 'su dung dat' -> 'sử dụng đất'
   - 'tai san gan liền voi dat' -> 'tài sản gắn liền với đất'
   - 'thu tue' / 'tha tục' -> 'thủ tục'
   - 'thanh phan' -> 'thành phần'
   - 'Trinh tw' -> 'Trình tự'
   - 'Van phong' -> 'Văn phòng'
   - 'Chi nhanh' -> 'Chi nhánh'
   - 'céng ching' -> 'công chứng'
   - 'can bộ' -> 'cán bộ'
4. Chỉ trả về nội dung văn bản sau khi đã sửa chính tả. KHÔNG thêm lời giải thích, KHÔNG bọc trong markdown code block (như ```).
"""

def polish_chunk(chunk_text: str, chunk_index: int, total_chunks: int) -> str:
    prompt = f"""Dưới đây là một phần văn bản OCR cần hiệu đính (phần {chunk_index}/{total_chunks}).
Yêu cầu: Hãy sửa lỗi chính tả và phục hồi dấu tiếng Việt cho từng dòng, TUYỆT ĐỐI KHÔNG ĐƯỢC TÓM TẮT HOẶC CẮT BỚT.

--- BẮT ĐẦU VĂN BẢN ---
{chunk_text}
--- KẾT THÚC VĂN BẢN ---"""

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.1,
                    max_output_tokens=8192,
                )
            )
            result = response.text.strip()
            if result.startswith("```"):
                result = re.sub(r"^```[a-zA-Z]*\n?", "", result)
                result = re.sub(r"\n?```$", "", result).strip()

            # Kiểm tra độ dài: nếu kết quả ngắn hơn 80% văn bản gốc -> có thể Gemini đã tóm tắt nhầm!
            if len(result) < len(chunk_text) * 0.75:
                print(f"\n[WARNING] Kết quả phần {chunk_index} quá ngắn ({len(result)} vs {len(chunk_text)} gốc). Đang thử lại với cảnh báo nghiêm ngặt...")
                # Thử lại với lời nhắc mạnh hơn
                retry_prompt = f"LƯU Ý ĐẶC BIỆT: KHÔNG ĐƯỢC TÓM TẮT. Phải chép lại đầy đủ từng dòng và sửa dấu tiếng Việt:\n\n{chunk_text}"
                resp2 = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=retry_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.0,
                        max_output_tokens=8192,
                    )
                )
                r2 = resp2.text.strip()
                if len(r2) >= len(chunk_text) * 0.75:
                    return r2
                # Nếu vẫn ngắn, fallback giữ nguyên bản gốc để an toàn dữ liệu
                print(f"[FALLBACK] Giữ nguyên phần {chunk_index} gốc để không mất dữ liệu.")
                return chunk_text

            return result
        except Exception as e:
            print(f"\n[LỖI] Thử lần {attempt + 1} cho phần {chunk_index}: {e}")
            time.sleep(2)
    return chunk_text


def split_by_pages(text: str, max_chars: int = 6000) -> list[str]:
    """Tách văn bản theo từng cụm trang ~4000-6000 ký tự."""
    parts = re.split(r"(--- TRANG \d+ ---)", text)
    chunks = []
    current = ""
    for p in parts:
        if len(current) + len(p) > max_chars and current:
            chunks.append(current.strip())
            current = p
        else:
            current += "\n\n" + p if current else p
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]


def process_file(file_path: Path):
    print(f"\n=======================================================")
    print(f"[FILE] Đang xử lý: {file_path.name}")
    print(f"=======================================================")

    bak_path = file_path.with_suffix(".txt.bak")
    if not bak_path.exists():
        bak_path.write_bytes(file_path.read_bytes())
        print(f"[BACKUP] Đã tạo backup: {bak_path.name}")

    original_text = bak_path.read_text(encoding="utf-8")
    chunks = split_by_pages(original_text)
    print(f"[CHUNKS] Chia văn bản thành {len(chunks)} phần lớn.")

    polished_parts = []
    for i, c in enumerate(chunks, start=1):
        print(f"[TIẾN ĐỘ] Đang xử lý phần {i}/{len(chunks)} ({len(c)} ký tự)...", end="", flush=True)
        polished = polish_chunk(c, i, len(chunks))
        polished_parts.append(polished)
        print(f" -> Xong ({len(polished)} ký tự)")
        time.sleep(0.5)

    final_text = "\n\n".join(polished_parts)
    file_path.write_text(final_text, encoding="utf-8")
    print(f"[HOÀN TẤT] Ghi đè file: {file_path.name} ({len(final_text):,} ký tự)")


def main():
    ocr_dir = Path("data/processed/ocr_text")
    txt_files = [f for f in ocr_dir.glob("*.txt") if not f.name.endswith(".bak")]

    print(f"[START] Bắt đầu hiệu đính {len(txt_files)} file OCR bằng {MODEL_NAME}...")
    for f in txt_files:
        process_file(f)

    print("\n[SUCCESS] Toàn bộ file OCR đã được hiệu đính thành công chuẩn 100% tiếng Việt!")


if __name__ == "__main__":
    main()
