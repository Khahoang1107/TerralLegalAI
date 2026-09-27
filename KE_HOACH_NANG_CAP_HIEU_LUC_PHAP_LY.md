# KẾ HOẠCH NÂNG CẤP HỆ THỐNG QUẢN LÝ HIỆU LỰC PHÁP LÝ PHỨC HỢP (TERRALEGALAI)
## Giải pháp xử lý: Một Quyết định bãi bỏ nhiều văn bản & Sửa đổi một phần điều khoản

---

## 1. Bản chất vấn đề trong thực tế pháp lý Đất đai

Trong thực tế ban hành văn bản hành chính và quy phạm pháp luật (điển hình như **Quyết định 4836/QĐ-UBND**):
1. **Quan hệ 1 - Nhiều (1-to-N Replacement):** Một Quyết định mới công bố bãi bỏ cùng lúc nhiều văn bản cũ (*QĐ 1085, QĐ 1467*).
2. **Bãi bỏ / Sửa đổi từng phần (Granular / Provision-level Amendment):** 
   * Bãi bỏ cụ thể một số thủ tục (ví dụ: *14 thủ tục tại QĐ 1308, 44 thủ tục tại QĐ 3035*), trong khi các thủ tục còn lại của QĐ 1308/3035 vẫn giữ nguyên hiệu lực.
   * Sửa đổi một số Điều/Khoản của Nghị định/Quyết định cũ (văn bản gốc vẫn còn hiệu lực 90%, chỉ có 10% điều khoản bị thay thế).

---

## 2. So sánh các phương án giải quyết

| Tiêu chí | Cách 1: Chọn đơn lẻ (Hiện tại) | Cách 2: Multi-select thủ công | Cách 3: AI Legal Graph & Auto-Impact (TỐI ƯU NHẤT) |
| :--- | :--- | :--- | :--- |
| **Thao tác người dùng** | Phải upload nhiều lần hoặc chỉ chọn được 1 file gốc. | Admin tự dò tìm và tích chọn nhiều checkbox. | **AI tự quét Điều khoản thi hành, gợi ý toàn bộ danh sách tác động.** |
| **Bãi bỏ nhiều văn bản** | Không hỗ trợ (chỉ chọn được 1). | Có hỗ trợ qua danh sách tích chọn. | **Tự động bãi bỏ đồng loạt tất cả các văn bản liên quan.** |
| **Sửa đổi từng Điều/Khoản** | Khó kiểm soát, dễ làm mất cả văn bản gốc. | Phải nhập tay Điều bị sửa. | **AI đối chiếu tự động, vô hiệu hóa đúng Điều bị sửa.** |
| **Giá trị học thuật luận văn** | Mức cơ bản (CRUD thông thường). | Mức khá. | **Mức xuất sắc: Mô hình hóa Đồ thị Hiệu lực Pháp lý (Legal Validity Knowledge Graph).** |

---

## 3. Thiết kế Giải pháp Tối ưu nhất (Cách 3: AI Legal Impact & Multi-Parent)

### A. Giao diện Upload Đa tầng (Multi-Impact Upload Interface)
Thay vì 1 ô dropdown đơn lẻ, khi chọn hoặc nhận diện là **Thay thế / Sửa đổi**:
1. **Khu vực 1: Văn bản bị thay thế toàn bộ (Full Repeal):**
   * Hiển thị danh sách thẻ (chips/checkboxes) các văn bản hiện có trong hệ thống.
   * AI tự động đọc Điều 4 và **tự động tích chọn sẵn** các văn bản bị bãi bỏ (ví dụ: `[x] Ban hành bộ TTHC (QĐ 1085)`, `[x] Quy trình nội bộ (QĐ 1467)`).
   * Admin có thể bấm dấu [x] để thêm hoặc bớt văn bản bất kỳ lúc nào.
2. **Khu vực 2: Văn bản bị sửa đổi/bãi bỏ một phần (Partial Amendment):**
   * Cho phép chọn văn bản gốc bị sửa đổi điều khoản.
   * Khi hoàn tất upload, hệ thống tự động sinh một bản **"Phân tích tác động điều khoản" (Provision Impact Analysis)**.

### B. Cơ sở dữ liệu & Vector Store (Backend Execution)
1. **Cập nhật quan hệ đa chiều trong `Document`:**
   * Lưu mảng JSONB: `related_documents = [{"document_id": "...", "relation": "replaces", "source_name": "..."}, ...]`
2. **Đồng bộ hàng loạt sang Qdrant:**
   * Khi bấm Tải lên, hệ thống chạy background task cập nhật nhãn `validity_status = "repealed"` cho **tất cả** các văn bản bị thay thế đã chọn.
3. **Bộ thẩm định Điều/Khoản (Provision Amendment Workflow):**
   * Cho phép Admin bấm "Xem & Xác nhận sửa đổi Điều khoản": AI trích xuất các câu như *"Sửa đổi Khoản 1 Điều 3..."* ➔ Đánh dấu đúng Chunk tương ứng của văn bản cũ là `amended`, trỏ link sang Chunk mới.

---

## 4. Kế hoạch triển khai cụ thể

* **Giai đoạn 1 (Làm ngay lập tức):**
  1. Nâng cấp Backend `documents.py`: Cho phép nhận mảng `parent_document_ids` (hỗ trợ bãi bỏ đồng thời nhiều văn bản).
  2. Nâng cấp Frontend `page.tsx`: Chuyển ô chọn văn bản gốc thành **Danh sách tích chọn đa văn bản (Multi-select Checklist)**, có AI tự động tích chọn sẵn các văn bản cũ.
* **Giai đoạn 2 (Tích hợp màn hình Thẩm định điều khoản):**
  1. Kích hoạt Modal "Thẩm định sửa đổi Điều/Khoản" để xử lý các trường hợp sửa đổi một phần.
  2. Kết nối bộ lọc RAG để AI trích dẫn văn bản mới kèm chú thích lịch sử sửa đổi.
