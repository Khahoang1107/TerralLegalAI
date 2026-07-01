# Hướng Dẫn Chạy Dự Án TerraLegalAI

Tài liệu này hướng dẫn cách khởi chạy nhanh toàn bộ dự án (Frontend, Backend, Database) thông qua Docker. Đây là phương pháp đơn giản và ổn định nhất, không cần phải cài đặt thủ công môi trường Python hay Node.js.

---

## Bước 1: Yêu Cầu Bắt Buộc
Máy tính của bạn (hoặc máy chủ) **bắt buộc phải cài đặt Docker**:
- Tải và cài đặt **[Docker Desktop](https://www.docker.com/products/docker-desktop/)** (Nếu dùng Windows/Mac).
- Mở ứng dụng Docker Desktop lên và đợi đến khi biểu tượng phía góc dưới báo trạng thái **Engine running** (Màu xanh).

---

## Bước 2: Kiểm Tra File Môi Trường
Đảm bảo rằng trong thư mục gốc của dự án (nơi chứa file `docker-compose.yml`) đã có file **`.env`**.
- Nếu bạn thấy có file `.env.example` nhưng không có `.env` 👉 Hãy copy file `.env.example` và đổi tên bản sao đó thành `.env`.
- Mở file `.env` lên, điền các thông tin quan trọng như: `OPENAI_API_KEY` hoặc các mật khẩu/cấu hình cần thiết (nếu có).

---

## Bước 3: Khởi Động Dự Án
1. Mở **Terminal** (CMD, PowerShell, hoặc Terminal tích hợp trong VS Code).
2. Trỏ đường dẫn (dùng lệnh `cd`) vào đúng thư mục gốc của dự án.
3. Chạy lệnh sau:

```bash
docker-compose up -d --build
```

**Lệnh này sẽ tự động làm mọi việc:**
- Tải về và cấu hình PostgreSQL, Qdrant (Vector Database), Redis.
- Build và chạy API Backend (FastAPI).
- Build và chạy Giao diện Frontend (Next.js).

*(Lưu ý: Quá trình chạy lần đầu tiên có thể mất từ 5-10 phút để tải các thư viện. Các lần sau sẽ chạy lên ngay lập tức).*

---

## Bước 4: Truy Cập Ứng Dụng
Khi lệnh ở Bước 3 chạy xong và không báo lỗi, bạn mở trình duyệt web lên và truy cập vào các đường dẫn sau:

- 🌐 **Giao Diện Người Dùng (Frontend):** [http://localhost:3000](http://localhost:3000)
- ⚙️ **Giao Diện API Docs (Backend):** [http://localhost:8000/docs](http://localhost:8000/docs)
- 📊 **Quản lý Vector DB (Qdrant):** [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## 🛠 Các Câu Lệnh Hữu Ích Khác

- **Để dừng và tắt hoàn toàn dự án:**
  ```bash
  docker-compose down
  ```

- **Để xem log (Lịch sử chạy/Lỗi) nếu web không vào được:**
  ```bash
  docker-compose logs -f
  ```
  *(Muốn xem riêng log của backend: `docker-compose logs -f backend`)*

---

### 💡 Lưu Ý: Truy cập từ thiết bị khác (Mạng LAN/Wifi)
Nếu bạn chạy code trên Laptop nhưng muốn dùng điện thoại kết nối vào web:
1. Mở file `docker-compose.yml` lên.
2. Kéo xuống phần `frontend`, tìm biến môi trường:
   `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Thay chữ `localhost` bằng địa chỉ IP máy tính của bạn (Ví dụ: `NEXT_PUBLIC_API_URL=http://192.168.1.55:8000`).
4. Chạy lại lệnh: `docker-compose up -d --build`.
5. Dùng điện thoại truy cập vào: `http://192.168.1.55:3000` là được.
