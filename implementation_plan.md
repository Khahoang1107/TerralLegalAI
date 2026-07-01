# 🏗️ Kế Hoạch Dự Án RAG Đất Đai — TerraLegalAI

> **Vai trò**: AI Engineer & Solution Architect  
> **Phạm vi**: Chatbot tư vấn thủ tục đất đai tỉnh Vĩnh Long (2 thủ tục chính)  
> **Ngày lập kế hoạch**: 30/06/2026

---

## 1. 🎯 Mục Tiêu Dự Án RAG

### Dự án giải quyết vấn đề gì?

Người dân gặp khó khăn khi tra cứu, hiểu và thực hiện các thủ tục hành chính đất đai vì:
- Văn bản pháp luật dài, phức tạp, ngôn ngữ hành chính khó hiểu
- Thủ tục thay đổi liên tục theo các Quyết định mới của UBND tỉnh
- Người dân không biết nộp hồ sơ ở đâu, cần giấy tờ gì, mất bao lâu
- Cán bộ tiếp dân phải trả lời lặp đi lặp lại các câu hỏi đơn giản

### Người dùng cuối là ai?

| Nhóm | Nhu cầu |
|------|---------|
| 🏠 Người dân tỉnh Vĩnh Long | Hỏi nhanh thủ tục, hồ sơ cần chuẩn bị |
| 🏢 Cán bộ địa chính xã/phường | Tra cứu quy định khi hướng dẫn dân |
| ⚖️ Công chứng viên, môi giới | Kiểm tra điều kiện, thời hạn, căn cứ pháp lý |
| 👨‍💻 Admin hệ thống | Quản lý tài liệu, giám sát chất lượng |

### Dữ liệu đầu vào là gì?

```
📂 Nhóm 1 — Văn bản pháp luật (PDF)
   ├── Luật Đất đai 2024
   ├── Nghị định 101/2024/NĐ-CP
   └── Các nghị định, thông tư hướng dẫn

📂 Nhóm 2 — Quyết định UBND Vĩnh Long (PDF/DOCX)
   ├── QĐ 1308/QĐ-UBND (27/06/2025)
   ├── QĐ 1085/QĐ-UBND (03/09/2025)
   ├── QĐ 1312/QĐ-UBND (27/06/2025)
   └── QĐ 1467/QĐ-UBND (30/09/2025)

📂 Nhóm 3 — Biểu mẫu, tờ khai (PDF/DOCX)
   ├── Đơn đăng ký biến động đất đai
   ├── Đơn đề nghị cấp GCN
   ├── Tờ khai lệ phí trước bạ
   └── Tờ khai thuế TNCN

📂 Nhóm 4 — Bộ câu hỏi kiểm thử (JSON/YAML)
   └── 50–100 cặp hỏi-đáp chuẩn (ground truth)
```

### Kết quả đầu ra mong muốn là gì?

- ✅ Chatbot trả lời **chính xác, có trích dẫn nguồn**
- ✅ Hướng dẫn **từng bước thực hiện thủ tục**
- ✅ Gợi ý **biểu mẫu, hồ sơ cần chuẩn bị**
- ✅ Trả lời **ngôn ngữ đời thường** của người dân
- ✅ Không bịa thông tin khi không có dữ liệu

---

## 2. 📚 Kiến Thức Nền Cần Biết

### RAG là gì?

**RAG (Retrieval-Augmented Generation)** = Truy xuất + Sinh văn bản

```
Câu hỏi của user
       ↓
[Retriever] → Tìm đoạn văn bản liên quan trong kho tài liệu
       ↓
[LLM] ← Nhận câu hỏi + đoạn context tìm được
       ↓
Câu trả lời chính xác, có dẫn nguồn
```

### Vì sao cần RAG thay vì chỉ dùng LLM thông thường?

| Vấn đề với LLM thuần | Giải pháp của RAG |
|----------------------|-------------------|
| Không biết QĐ 1085/2025 của Vĩnh Long | Tìm đúng văn bản trong kho lưu trữ |
| Hallucinate thông tin pháp lý | Chỉ sinh từ context đã truy xuất |
| Không cập nhật văn bản mới | Thêm tài liệu mới → hệ thống hiểu ngay |
| Không trích dẫn nguồn cụ thể | RAG biết context đến từ tài liệu nào |

### Các khái niệm cốt lõi

| Khái niệm | Giải thích |
|-----------|-----------|
| **Document** | File PDF/DOCX gốc được nạp vào hệ thống |
| **Chunking** | Chia tài liệu thành đoạn nhỏ (~500 token) để xử lý |
| **Embedding** | Chuyển text → vector số để so sánh ngữ nghĩa |
| **Vector Database** | DB lưu vector, cho phép tìm kiếm theo độ tương đồng |
| **Retrieval** | Tìm k chunk liên quan nhất với câu hỏi |
| **Reranking** | Sắp xếp lại kết quả retrieval theo độ liên quan thực sự |
| **Prompt** | Lệnh + context gửi cho LLM để sinh câu trả lời |
| **Context** | Các đoạn văn bản liên quan được đưa vào prompt |
| **Hallucination** | LLM bịa thông tin không có trong tài liệu |

---

## 3. 🔄 Quy Trình Xây Dựng Hệ Thống RAG

### Luồng Indexing (Xử lý tài liệu — chạy 1 lần)

```
Step 1: Thu thập tài liệu
        PDF/DOCX từ 4 nhóm → /data/raw/

Step 2: Tiền xử lý dữ liệu
        ├── Extract text từ PDF (PyMuPDF / pdfplumber)
        ├── Làm sạch: bỏ header/footer, số trang
        ├── Nhận dạng cấu trúc: Điều, Khoản, Mục
        └── Gán metadata: tên văn bản, điều khoản, nhóm

Step 3: Chunking
        ├── Chunk size: 400–600 token
        ├── Overlap: 80–100 token
        ├── Chunk theo cấu trúc: 1 Điều = 1 chunk (ưu tiên)
        └── Giữ metadata trong mỗi chunk

Step 4: Tạo Embedding
        ├── Model: bge-m3 / multilingual-e5-large
        └── Output: vector 768/1024 chiều

Step 5: Lưu vào Vector Database
        ├── Qdrant / ChromaDB / Weaviate
        └── Mỗi record: {id, vector, metadata, text}
```

### Luồng Inference (Người dùng hỏi — real-time)

```
Step 6: Người dùng đặt câu hỏi
        "Sang tên sổ đỏ cần giấy tờ gì?"

Step 7: Query Expansion + Embedding câu hỏi
        → Chuyển câu hỏi thành vector

Step 8: Retrieval — Tìm top-K chunk liên quan
        ├── Dense retrieval (vector similarity)
        ├── Sparse retrieval (BM25 keyword)
        └── Hybrid = Dense + Sparse

Step 9: Reranking
        └── Cross-encoder reranker → chọn top-3 chunk tốt nhất

Step 10: Build Prompt
         ├── System prompt (hướng dẫn AI trả lời)
         ├── Context (3 chunk liên quan)
         └── Câu hỏi của user

Step 11: LLM sinh câu trả lời
         └── GPT-4o / Gemini 1.5 Pro / Qwen2.5

Step 12: Post-processing
         ├── Trích xuất nguồn tham chiếu
         ├── Format câu trả lời
         └── Confidence score

Step 13: Trả lời kèm nguồn tham chiếu
         └── Response + [Nguồn: QĐ 1085, Điều 3, Khoản 2]
```

---

## 4. 🏛️ Kiến Trúc Hệ Thống

### Sơ đồ kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────────────┐
│                        TERRALEGALAI SYSTEM                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐      ┌──────────────────────────────────────┐  │
│  │   FRONTEND   │      │           ADMIN PORTAL               │  │
│  │  (Next.js)   │      │  Upload docs / Manage / Monitor      │  │
│  └──────┬───────┘      └──────────────┬───────────────────────┘  │
│         │                             │                           │
│         ▼                             ▼                           │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                   BACKEND API (FastAPI)                   │    │
│  │  /chat  /upload  /documents  /evaluate  /history         │    │
│  └────┬──────────────────────────────────────────┬──────────┘    │
│       │                                          │               │
│       ▼                                          ▼               │
│  ┌────────────┐                       ┌─────────────────────┐   │
│  │  RAG ENGINE │                       │  DOC PROCESSOR      │   │
│  │            │                       │                     │   │
│  │ ┌────────┐ │                       │ PDF/DOCX Parser     │   │
│  │ │Retriever│ │                       │ Text Cleaner        │   │
│  │ └───┬────┘ │                       │ Chunker             │   │
│  │     │      │                       │ Metadata Extractor  │   │
│  │ ┌───▼────┐ │                       └─────────┬───────────┘   │
│  │ │Reranker│ │                                 │               │
│  │ └───┬────┘ │                                 ▼               │
│  │     │      │                       ┌─────────────────────┐   │
│  │ ┌───▼────┐ │                       │  EMBEDDING MODEL    │   │
│  │ │Prompt  │ │◄──── Context ─────────│  (bge-m3 / e5)      │   │
│  │ │Builder │ │                       └─────────┬───────────┘   │
│  │ └───┬────┘ │                                 │               │
│  │     │      │                                 ▼               │
│  │ ┌───▼────┐ │      ┌──────────────────────────────────────┐   │
│  │ │  LLM   │ │      │         VECTOR DATABASE              │   │
│  │ │(GPT-4o)│ │◄─────│  Qdrant  (chunks + embeddings)      │   │
│  │ └───┬────┘ │      └──────────────────────────────────────┘   │
│  └─────┼──────┘                                                  │
│        │                                                         │
│        ▼                                                         │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              DATABASES                                    │    │
│  │  PostgreSQL: users, documents, chat_history, feedback     │    │
│  │  Redis: session cache, rate limiting                      │    │
│  └──────────────────────────────────────────────────────────┘    │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │              EVALUATION MODULE                            │    │
│  │  RAGAS metrics: Faithfulness, Answer Relevancy,          │    │
│  │  Context Precision, Context Recall                        │    │
│  └──────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### Mô tả từng module

| Module | Chức năng |
|--------|-----------|
| **Frontend (Next.js)** | Giao diện chat, upload tài liệu, xem lịch sử |
| **Backend API (FastAPI)** | Xử lý request, orchestrate RAG pipeline |
| **Doc Processor** | Parse PDF/DOCX, clean text, chunk, extract metadata |
| **Embedding Model** | Chuyển text → vector (offline hoặc API) |
| **Vector Database (Qdrant)** | Lưu trữ và tìm kiếm vector theo semantic similarity |
| **Retriever** | Hybrid search: dense (vector) + sparse (BM25) |
| **Reranker** | Cross-encoder lọc lại top-K kết quả |
| **LLM** | Sinh câu trả lời từ context đã truy xuất |
| **PostgreSQL** | Lưu document metadata, chat history, user, feedback |
| **Redis** | Cache session, rate limit, temp storage |
| **Evaluation Module** | Đánh giá chất lượng RAG tự động bằng RAGAS |

---

## 5. 🔀 Luồng Hoạt Động Chi Tiết

### Luồng A: Upload & Indexing Tài Liệu

```
Admin upload PDF
    │
    ▼
POST /api/documents/upload
    │
    ▼
DocProcessor.parse()          ← PyMuPDF / pdfplumber
    │  extract text, clean
    ▼
DocumentChunker.chunk()       ← LangChain RecursiveCharacterSplitter
    │  chunk_size=500, overlap=80
    │  Ưu tiên: chunk theo Điều/Khoản
    ▼
MetadataExtractor.extract()   ← Nhận dạng: tên văn bản, điều khoản, nhóm
    │
    ▼
EmbeddingModel.encode()       ← bge-m3 batch encode
    │
    ▼
VectorDB.upsert()             ← Qdrant: lưu {id, vector, payload}
    │
    ▼
PostgreSQL: update documents table (status = indexed)
    │
    ▼
✅ Tài liệu sẵn sàng để truy vấn
```

### Luồng B: Chat Q&A

```
User: "Sang tên sổ đỏ cần giấy tờ gì?"
    │
    ▼
POST /api/chat
    │
    ├─── SessionManager: load chat history (Redis/PostgreSQL)
    │
    ▼
QueryPreprocessor
    │  ├── Detect intent: hỏi hồ sơ / trình tự / thời hạn / điều kiện
    │  ├── Expand query: "sang tên sổ đỏ" → "chuyển nhượng quyền sử dụng đất"
    │  └── Query rewrite nếu cần (LLM)
    │
    ▼
HybridRetriever.search(query, k=10)
    │  ├── Dense: vector similarity (Qdrant)
    │  └── Sparse: BM25 keyword match
    │
    ▼
Reranker.rerank(query, chunks, top_k=3)  ← Cross-encoder model
    │
    ▼
ContextBuilder.build()
    │  ├── Ghép 3 chunk thành context block
    │  └── Thêm metadata: [Nguồn: QĐ 1085, Điều 3]
    │
    ▼
PromptBuilder.build(system_prompt, context, history, question)
    │
    ▼
LLM.generate(prompt)          ← GPT-4o / Gemini 1.5 Pro
    │
    ▼
ResponseParser
    │  ├── Extract citations
    │  ├── Confidence check: nếu LLM nói "không tìm thấy" → fallback
    │  └── Format markdown response
    │
    ▼
PostgreSQL: lưu chat_history
    │
    ▼
✅ Response + [Nguồn: QĐ 1085/QĐ-UBND, Điều 3, Khoản 2]
```

---

## 6. 🛠️ Công Nghệ Đề Xuất

### Stack chính

| Layer | Công nghệ đề xuất | Lý do |
|-------|-------------------|-------|
| **Backend** | FastAPI (Python 3.11) | Async, type hints, OpenAPI tự động |
| **Frontend** | Next.js 14 + TypeScript | SSR, App Router, tối ưu SEO |
| **Vector DB** | **Qdrant** (self-hosted) | Hỗ trợ hybrid search, payload filter, miễn phí |
| **Embedding** | **bge-m3** (BAAI) | Tốt nhất cho tiếng Việt, multilingual, miễn phí |
| **Reranker** | bge-reranker-v2-m3 | Cùng family với embedding, cross-encoder |
| **LLM** | **GPT-4o** (chính) + Gemini 1.5 Flash (dự phòng) | GPT-4o tốt nhất cho tiếng Việt pháp lý |
| **RAG Framework** | **LangChain** + custom pipeline | Modular, nhiều tích hợp, cộng đồng lớn |
| **SQL Database** | PostgreSQL 15 | Mature, ACID, JSON support |
| **Cache** | Redis 7 | Session, rate limit, temp cache |
| **Task Queue** | Celery + Redis | Async document processing |
| **Evaluation** | RAGAS | Đánh giá RAG tự động |
| **Deployment** | Docker Compose → Kubernetes | Dev → Production |
| **Monitoring** | Langfuse + Grafana | Trace LLM calls, metrics |

### Thư viện Python chính

```python
# RAG Core
langchain>=0.2.0
langchain-openai
langchain-community
qdrant-client

# Document Processing
pymupdf          # PDF parsing
python-docx      # DOCX parsing
pdfplumber       # Table extraction from PDF

# Embedding & Reranking
sentence-transformers   # bge-m3, reranker
FlagEmbedding           # BGE official library

# Evaluation
ragas
deepeval

# Backend
fastapi
uvicorn
celery
redis
sqlalchemy
alembic
pydantic-settings

# Monitoring
langfuse
```

---

## 7. 📋 Các Chức Năng Chính

### 7.1 Chức năng người dùng

| # | Chức năng | Mô tả |
|---|-----------|-------|
| F01 | **Chat hỏi đáp** | Nhập câu hỏi bằng ngôn ngữ tự nhiên |
| F02 | **Xem nguồn tham chiếu** | Mỗi câu trả lời có trích dẫn từ điều khoản cụ thể |
| F03 | **Lịch sử hội thoại** | Xem lại các cuộc hội thoại đã thực hiện |
| F04 | **Đánh giá câu trả lời** | 👍/👎 feedback để cải thiện hệ thống |
| F05 | **Gợi ý câu hỏi** | Hệ thống đề xuất câu hỏi liên quan |
| F06 | **Chọn thủ tục** | Filter theo: Chuyển nhượng / Cấp đổi GCN |

### 7.2 Chức năng Admin

| # | Chức năng | Mô tả |
|---|-----------|-------|
| A01 | **Upload tài liệu** | Upload PDF/DOCX, tự động index |
| A02 | **Quản lý tài liệu** | Xem, xóa, cập nhật tài liệu |
| A03 | **Theo dõi chất lượng** | Dashboard RAGAS metrics |
| A04 | **Xem nhật ký hệ thống** | Log retrieval, LLM calls, errors |
| A05 | **Quản lý bộ test** | Thêm/sửa cặp hỏi-đáp chuẩn |
| A06 | **Export báo cáo** | Xuất thống kê câu hỏi, chủ đề phổ biến |

---

## 8. ⚠️ Các Vấn Đề Kỹ Thuật Cần Xử Lý

### 8.1 Chunk size chọn bao nhiêu?

```
Chiến lược chunking cho văn bản pháp lý:

Cấp độ 1 (nhỏ) — Khoản, Điểm: 150–250 token
  → Dùng cho retrieval chính xác

Cấp độ 2 (trung) — Điều: 400–600 token  ← Khuyến nghị
  → Cân bằng giữa precision và context

Cấp độ 3 (lớn) — Chương/Mục: 800–1200 token
  → Dùng để cung cấp context rộng cho LLM

→ Chiến lược: Parent-Child Chunking
  - Retrieve bằng chunk nhỏ (Cấp 1/2)
  - Đưa vào LLM chunk lớn hơn (parent) để có đủ ngữ cảnh
```

### 8.2 Làm sao giảm hallucination?

```
1. Strict grounding prompt:
   "Chỉ trả lời dựa trên context được cung cấp.
    Nếu không có thông tin, trả lời: 'Tôi chưa tìm thấy thông tin này trong tài liệu.'"

2. Citation enforcement:
   → Yêu cầu LLM phải trích nguồn cụ thể cho mỗi thông tin

3. Faithfulness check (RAGAS):
   → Tự động kiểm tra câu trả lời có căn cứ trong context không

4. Temperature = 0 hoặc 0.1
   → Giảm sáng tạo, tăng độ chính xác

5. Fallback khi không tìm thấy:
   → "Câu hỏi của bạn nằm ngoài phạm vi tài liệu hiện tại.
      Vui lòng liên hệ Văn phòng Đăng ký Đất đai tỉnh Vĩnh Long."
```

### 8.3 Làm sao tìm đúng tài liệu liên quan?

```
Hybrid Retrieval Pipeline:

Dense Search (ngữ nghĩa):
  → bge-m3 embedding + Qdrant cosine similarity
  → Tốt cho: câu hỏi đời thường ≠ từ khoá trong văn bản

Sparse Search (từ khoá):
  → BM25 full-text search
  → Tốt cho: mã văn bản, số điều khoản cụ thể

Metadata Filtering:
  → Filter theo: nhóm thủ tục, loại văn bản, tỉnh

Query Expansion:
  → "sang tên sổ đỏ" → ["chuyển nhượng quyền sử dụng đất",
                          "đăng ký biến động", "Giấy chứng nhận"]

Cross-encoder Reranking:
  → Top 10 chunks → Reranker → Top 3 chunks
```

### 8.4 Làm sao trả lời có dẫn chứng?

```python
# Mỗi chunk lưu metadata đầy đủ:
{
  "text": "Hồ sơ chuyển nhượng quyền sử dụng đất gồm...",
  "source": "QĐ 1085/QĐ-UBND",
  "date": "03/09/2025",
  "article": "Điều 3",
  "clause": "Khoản 2",
  "group": "thu_tuc_chuyen_nhuong",
  "field": "thanh_phan_ho_so"
}

# Prompt yêu cầu format:
"Sau mỗi thông tin quan trọng, ghi [Nguồn: <tên văn bản>, <điều khoản>]"
```

### 8.5 Khi không tìm thấy thông tin thì xử lý thế nào?

```
Bước 1: Kiểm tra similarity score
   - Nếu top-1 score < 0.65 → câu hỏi ngoài phạm vi

Bước 2: LLM xác nhận không có context
   - Nếu LLM generate "không có thông tin" → trigger fallback

Bước 3: Fallback Response Template:
   "Xin lỗi, tôi chưa tìm thấy thông tin chính xác về '[câu hỏi]'
    trong cơ sở dữ liệu hiện tại.

    👉 Bạn có thể:
    - Liên hệ: Văn phòng Đăng ký Đất đai tỉnh Vĩnh Long
    - Điện thoại: [số điện thoại]
    - Hoặc thử đặt câu hỏi theo cách khác"

Bước 4: Log câu hỏi không trả lời được → cải thiện dữ liệu
```

### 8.6 Làm sao đánh giá chất lượng hệ thống RAG?

```
RAGAS Framework — 4 metrics chính:

1. Faithfulness (Độ trung thực)
   → Câu trả lời có căn cứ trong context không? [0-1]
   → Target: > 0.85

2. Answer Relevancy (Độ liên quan câu trả lời)
   → Câu trả lời có giải đáp đúng câu hỏi không? [0-1]
   → Target: > 0.80

3. Context Precision (Độ chính xác context)
   → Chunk được retrieve có thực sự liên quan không? [0-1]
   → Target: > 0.75

4. Context Recall (Độ đầy đủ context)
   → Chunk chứa đủ thông tin để trả lời không? [0-1]
   → Target: > 0.80

Bộ test: 50–100 cặp Q&A chuẩn (ground truth) tự xây dựng
Chạy evaluation: mỗi tuần hoặc sau mỗi lần cập nhật tài liệu
```

---

## 9. 🗄️ Database Schema

### PostgreSQL Schema

```sql
-- Quản lý tài liệu
CREATE TABLE documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(500) NOT NULL,
    file_path       VARCHAR(1000),
    group_type      VARCHAR(100), -- 'luat', 'quyet_dinh', 'bieu_mau', 'faq'
    procedure_type  VARCHAR(100), -- 'chuyen_nhuong', 'cap_doi', 'all'
    source_name     VARCHAR(500), -- "QĐ 1085/QĐ-UBND"
    issue_date      DATE,
    status          VARCHAR(50) DEFAULT 'pending', -- pending/indexing/indexed/error
    chunk_count     INTEGER,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Chunks đã được chunk và index
CREATE TABLE document_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id     UUID REFERENCES documents(id),
    chunk_index     INTEGER,
    text            TEXT NOT NULL,
    article         VARCHAR(200), -- "Điều 3"
    clause          VARCHAR(200), -- "Khoản 2"
    field_type      VARCHAR(100), -- "thanh_phan_ho_so", "thoi_han", etc.
    vector_id       VARCHAR(200), -- ID trong Qdrant
    token_count     INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Người dùng (optional, có thể anonymous)
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      VARCHAR(200) UNIQUE,
    user_type       VARCHAR(50) DEFAULT 'citizen', -- citizen/officer/admin
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Lịch sử hội thoại
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    title           VARCHAR(500),
    procedure_type  VARCHAR(100),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Tin nhắn
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    role            VARCHAR(20), -- 'user' / 'assistant'
    content         TEXT NOT NULL,
    intent          VARCHAR(200), -- detected intent
    retrieved_chunks JSONB, -- [{chunk_id, score, source}]
    citations       JSONB, -- [{source, article, clause}]
    confidence      FLOAT,
    latency_ms      INTEGER,
    feedback        SMALLINT, -- 1 (thumbs up) / -1 (thumbs down)
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Bộ câu hỏi kiểm thử
CREATE TABLE test_cases (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question        TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    procedure_group VARCHAR(100),
    intent          VARCHAR(200),
    source_doc      VARCHAR(500),
    field_type      VARCHAR(100),
    level           SMALLINT, -- 1/2/3/4 (mức độ câu hỏi)
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Kết quả đánh giá RAG
CREATE TABLE evaluation_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date        TIMESTAMP DEFAULT NOW(),
    faithfulness    FLOAT,
    answer_relevancy FLOAT,
    context_precision FLOAT,
    context_recall  FLOAT,
    total_questions INTEGER,
    notes           TEXT
);
```

### Qdrant Collection Schema

```python
# Collection: land_law_chunks
{
  "id": "uuid",
  "vector": [0.12, -0.34, ...],  # 1024 dim (bge-m3)
  "payload": {
    "document_id": "uuid",
    "chunk_index": 3,
    "text": "Hồ sơ gồm: 1. Đơn đăng ký...",
    "source_name": "QĐ 1085/QĐ-UBND",
    "issue_date": "2025-09-03",
    "group_type": "quyet_dinh",
    "procedure_type": "chuyen_nhuong",
    "article": "Điều 3",
    "clause": "Khoản 2",
    "field_type": "thanh_phan_ho_so",
    "token_count": 450
  }
}
```

---

## 10. 🔌 API Endpoints

### Chat & Conversation

```
POST   /api/v1/chat                    # Gửi câu hỏi, nhận trả lời
GET    /api/v1/conversations           # Lấy danh sách cuộc hội thoại
GET    /api/v1/conversations/{id}      # Lấy chi tiết cuộc hội thoại
DELETE /api/v1/conversations/{id}      # Xóa cuộc hội thoại
POST   /api/v1/messages/{id}/feedback  # Gửi feedback (👍/👎)
```

### Document Management (Admin)

```
POST   /api/v1/documents/upload        # Upload tài liệu mới
GET    /api/v1/documents               # Danh sách tài liệu
GET    /api/v1/documents/{id}          # Chi tiết tài liệu
DELETE /api/v1/documents/{id}          # Xóa tài liệu + re-index
PUT    /api/v1/documents/{id}/reindex  # Tái index tài liệu
```

### Evaluation (Admin)

```
POST   /api/v1/evaluation/run          # Chạy đánh giá RAGAS
GET    /api/v1/evaluation/results      # Kết quả đánh giá
GET    /api/v1/evaluation/test-cases   # Danh sách test cases
POST   /api/v1/evaluation/test-cases   # Thêm test case mới
```

### Health & Monitoring

```
GET    /api/v1/health                  # Health check
GET    /api/v1/metrics                 # Prometheus metrics
GET    /api/v1/stats                   # Thống kê hệ thống
```

### Request/Response mẫu

```json
// POST /api/v1/chat
// Request:
{
  "question": "Sang tên sổ đỏ cần giấy tờ gì?",
  "conversation_id": "uuid-optional",
  "procedure_filter": "chuyen_nhuong"
}

// Response:
{
  "answer": "Để chuyển nhượng quyền sử dụng đất (sang tên sổ đỏ), bạn cần chuẩn bị hồ sơ gồm:\n\n1. **Đơn đăng ký biến động đất đai** (Mẫu số 09/ĐK)\n2. **Hợp đồng chuyển nhượng** đã được công chứng/chứng thực\n3. **Giấy chứng nhận** quyền sử dụng đất (bản gốc)\n...",
  "citations": [
    {
      "source": "QĐ 1085/QĐ-UBND ngày 03/09/2025",
      "article": "Điều 3",
      "clause": "Khoản 2, Điểm a",
      "text": "Thành phần hồ sơ...",
      "relevance_score": 0.92
    }
  ],
  "confidence": 0.89,
  "intent": "hoi_ho_so",
  "procedure_type": "chuyen_nhuong",
  "conversation_id": "uuid",
  "message_id": "uuid",
  "latency_ms": 1240
}
```

---

## 11. 📦 Danh Sách Module Cần Code

```
terralegal-ai/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── v1/
│   │   │   │   ├── chat.py          # Chat endpoints
│   │   │   │   ├── documents.py     # Document management
│   │   │   │   └── evaluation.py    # Evaluation endpoints
│   │   ├── core/
│   │   │   ├── config.py            # Settings, env vars
│   │   │   ├── database.py          # PostgreSQL connection
│   │   │   └── security.py          # Auth (nếu cần)
│   │   ├── rag/
│   │   │   ├── pipeline.py          # ⭐ RAG orchestrator chính
│   │   │   ├── retriever.py         # Hybrid retriever
│   │   │   ├── reranker.py          # Cross-encoder reranker
│   │   │   ├── prompt_builder.py    # System + context prompt
│   │   │   ├── llm_client.py        # OpenAI / Gemini client
│   │   │   └── response_parser.py   # Extract citations, format
│   │   ├── document_processing/
│   │   │   ├── pdf_parser.py        # PyMuPDF parser
│   │   │   ├── docx_parser.py       # python-docx parser
│   │   │   ├── text_cleaner.py      # Clean, normalize text
│   │   │   ├── chunker.py           # Semantic chunking
│   │   │   └── metadata_extractor.py # Extract Điều, Khoản, Nhóm
│   │   ├── embedding/
│   │   │   ├── embedding_model.py   # bge-m3 wrapper
│   │   │   └── vector_store.py      # Qdrant CRUD operations
│   │   ├── evaluation/
│   │   │   ├── ragas_evaluator.py   # RAGAS metrics
│   │   │   └── test_runner.py       # Chạy test cases
│   │   ├── models/
│   │   │   ├── document.py          # SQLAlchemy models
│   │   │   ├── conversation.py
│   │   │   └── evaluation.py
│   │   └── tasks/
│   │       └── indexing_tasks.py    # Celery tasks (async index)
│   ├── migrations/                  # Alembic DB migrations
│   ├── tests/
│   │   ├── test_retriever.py
│   │   ├── test_pipeline.py
│   │   └── test_api.py
│   └── Dockerfile
│
├── frontend/
│   ├── app/
│   │   ├── page.tsx                 # Chat interface chính
│   │   ├── admin/
│   │   │   ├── documents/page.tsx   # Quản lý tài liệu
│   │   │   └── evaluation/page.tsx  # Dashboard đánh giá
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ChatWindow.tsx           # Cửa sổ chat
│   │   ├── MessageBubble.tsx        # Tin nhắn + citations
│   │   ├── SourceCitation.tsx       # Hiển thị nguồn trích dẫn
│   │   ├── FeedbackButtons.tsx      # 👍/👎
│   │   ├── DocumentUploader.tsx     # Upload tài liệu
│   │   └── MetricsDashboard.tsx     # RAGAS dashboard
│   └── Dockerfile
│
├── scripts/
│   ├── ingest_documents.py          # ⭐ Script batch index tài liệu
│   ├── build_test_dataset.py        # Tạo bộ test Q&A
│   └── run_evaluation.py            # Chạy đánh giá định kỳ
│
├── data/
│   ├── raw/                         # Tài liệu gốc
│   ├── processed/                   # Text đã clean
│   └── test_cases/                  # Bộ Q&A kiểm thử
│       └── test_questions.json
│
├── docker-compose.yml               # Dev environment
├── docker-compose.prod.yml          # Production
└── .env.example
```

---

## 12. 🧪 Bộ Câu Hỏi Kiểm Thử (Test Dataset)

### Mẫu file test_questions.json

```json
[
  {
    "id": "TC001",
    "level": 1,
    "question": "Hồ sơ chuyển nhượng quyền sử dụng đất gồm những gì?",
    "procedure_group": "chuyen_nhuong",
    "intent": "hoi_ho_so",
    "expected_answer": "Hồ sơ gồm: 1. Đơn đăng ký biến động đất đai, nhà ở và tài sản khác gắn liền với đất (Mẫu số 09/ĐK); 2. Hợp đồng chuyển nhượng quyền sử dụng đất đã được công chứng hoặc chứng thực; 3. Giấy chứng nhận quyền sử dụng đất (bản gốc)...",
    "source": "QĐ 1085/QĐ-UBND, Điều 3, Khoản 2"
  },
  {
    "id": "TC002",
    "level": 2,
    "question": "Tôi muốn sang tên sổ đỏ thì làm sao?",
    "procedure_group": "chuyen_nhuong",
    "intent": "hoi_trinh_tu",
    "expected_answer": "Để sang tên sổ đỏ (chuyển nhượng quyền sử dụng đất), bạn thực hiện theo các bước sau: Bước 1: Công chứng hợp đồng chuyển nhượng...",
    "source": "QĐ 1085/QĐ-UBND"
  },
  {
    "id": "TC003",
    "level": 3,
    "question": "Thủ tục chuyển nhượng quyền sử dụng đất mất bao lâu?",
    "procedure_group": "chuyen_nhuong",
    "intent": "hoi_thoi_han",
    "expected_answer": "Thời hạn giải quyết là... ngày làm việc kể từ ngày nhận đủ hồ sơ hợp lệ.",
    "source": "QĐ 1085/QĐ-UBND, Điều 3, Khoản 5"
  },
  {
    "id": "TC004",
    "level": 4,
    "question": "Tôi muốn tặng cho đất cho con, đất đã có sổ đỏ, không tranh chấp, vậy cần chuẩn bị hồ sơ gì?",
    "procedure_group": "tang_cho",
    "intent": "hoi_ho_so_tinh_huong",
    "expected_answer": "Trường hợp tặng cho quyền sử dụng đất cho con, bạn cần chuẩn bị...",
    "source": "QĐ 1085/QĐ-UBND"
  },
  {
    "id": "TC005",
    "level": 1,
    "question": "Cấp đổi giấy chứng nhận nộp hồ sơ ở đâu?",
    "procedure_group": "cap_doi",
    "intent": "hoi_co_quan",
    "expected_answer": "Nộp hồ sơ tại Văn phòng Đăng ký Đất đai tỉnh Vĩnh Long hoặc Chi nhánh Văn phòng Đăng ký Đất đai cấp huyện.",
    "source": "QĐ 1312/QĐ-UBND"
  }
]
```

---

## 13. 🚀 Kế Hoạch Triển Khai Theo Giai Đoạn

### Phase 1 — MVP (Tuần 1–4)

**Mục tiêu**: Có chatbot hoạt động với 2 thủ tục chính

| Tuần | Công việc | Deliverable |
|------|-----------|-------------|
| 1 | Thu thập & chuẩn bị tài liệu 4 nhóm | `/data/raw/` đầy đủ |
| 1 | Thiết lập môi trường dev (Docker) | `docker-compose.yml` |
| 2 | Xây dựng Document Processor | `pdf_parser.py`, `chunker.py` |
| 2 | Setup Qdrant + bge-m3 embedding | Vector DB chạy được |
| 3 | Xây dựng RAG Pipeline cơ bản | `pipeline.py` hoạt động |
| 3 | Xây dựng Backend API (FastAPI) | `/api/v1/chat` endpoint |
| 4 | Xây dựng Frontend Chat UI (Next.js) | Giao diện chat cơ bản |
| 4 | Tích hợp End-to-End, demo nội bộ | Demo MVP |

**KPI Phase 1**: Trả lời đúng > 70% test cases Mức 1 & 2

---

### Phase 2 — Cải Thiện Retrieval (Tuần 5–7)

**Mục tiêu**: Tăng độ chính xác retrieval

| Tuần | Công việc |
|------|-----------|
| 5 | Thêm Hybrid Search (BM25 + Dense) |
| 5 | Thêm Cross-encoder Reranker |
| 6 | Query Expansion (LLM-based) |
| 6 | Parent-Child Chunking strategy |
| 7 | Metadata filtering theo nhóm thủ tục |
| 7 | Cải thiện System Prompt, citation extraction |

**KPI Phase 2**: Trả lời đúng > 85% test cases; Faithfulness > 0.85

---

### Phase 3 — Đánh Giá & Monitoring (Tuần 8–9)

**Mục tiêu**: Đảm bảo chất lượng và quan sát được hệ thống

| Tuần | Công việc |
|------|-----------|
| 8 | Tích hợp RAGAS evaluation pipeline |
| 8 | Xây dựng Admin Dashboard (metrics, logs) |
| 9 | Tích hợp Langfuse (LLM observability) |
| 9 | Xây dựng bộ 50–100 test cases đầy đủ |
| 9 | Fallback handling & error cases |

**KPI Phase 3**: Có dashboard real-time; chạy evaluation tự động

---

### Phase 4 — Triển Khai Thực Tế (Tuần 10–12)

**Mục tiêu**: Production-ready, bàn giao

| Tuần | Công việc |
|------|-----------|
| 10 | Security: Auth, rate limiting, input validation |
| 10 | Performance: Caching, async processing |
| 11 | Staging deployment, UAT với cán bộ địa chính |
| 11 | Thu thập feedback, fix bugs |
| 12 | Production deployment (Docker/K8s) |
| 12 | Bàn giao, training người dùng |

**KPI Phase 4**: Uptime > 99%; Response time < 3s; CSAT > 4/5

---

## 14. 📖 Checklist Kiến Thức Cần Học

### 🔴 Bắt buộc (Core RAG)
- [ ] Hiểu embedding và vector similarity (cosine, dot product)
- [ ] Hiểu cách hoạt động của Transformer / BERT
- [ ] RAG architecture (indexing pipeline + inference pipeline)
- [ ] Langchain: Document loaders, Text splitters, Retrievers, Chains
- [ ] Qdrant: collection, upsert, search, payload filter
- [ ] Prompt engineering cho pháp lý tiếng Việt
- [ ] FastAPI: async endpoints, dependency injection, background tasks

### 🟡 Quan trọng (Quality & Ops)
- [ ] Hybrid search: BM25 + Dense fusion (Reciprocal Rank Fusion)
- [ ] Cross-encoder reranking (bge-reranker)
- [ ] RAGAS metrics và cách đánh giá RAG
- [ ] Celery + Redis cho async task processing
- [ ] PostgreSQL với SQLAlchemy + Alembic migrations
- [ ] Docker Compose cho local dev

### 🟢 Nâng cao (Production)
- [ ] Langfuse / LangSmith cho LLM observability
- [ ] Kubernetes deployment
- [ ] Grafana + Prometheus monitoring
- [ ] A/B testing cho RAG configs
- [ ] Fine-tuning embedding model cho tiếng Việt pháp lý

---

## 15. 🗺️ Roadmap Tổng Quan

```
Tháng 1 (Tuần 1–4): 🏗️ MVP
├── ✅ Chuẩn bị dữ liệu
├── ✅ Document processing pipeline
├── ✅ Basic RAG (dense only)
├── ✅ REST API
└── ✅ Chat UI cơ bản

Tháng 2 (Tuần 5–9): 🔧 Improve & Monitor
├── ✅ Hybrid search + Reranker
├── ✅ Query expansion
├── ✅ RAGAS evaluation
└── ✅ Admin dashboard

Tháng 3 (Tuần 10–12): 🚀 Production
├── ✅ Security & Performance
├── ✅ UAT & Feedback
├── ✅ Production deployment
└── ✅ Handover & Training
```

---

> **📌 Ghi chú quan trọng**:
> - Bắt đầu thu thập và làm sạch tài liệu **ngay từ tuần 1** — đây là bước quan trọng nhất
> - Xây dựng bộ test cases **song song** với việc build hệ thống
> - Ưu tiên chất lượng retrieval trước, UI/UX sau
> - Luôn test với câu hỏi thực tế của người dân, không chỉ câu hỏi kỹ thuật

