# Báo cáo đóng góp cá nhân

## Thông tin

- Họ và tên: Cao Văn Cường
- Mã học viên: 2A202602493
- Nhóm: 22
- Repository: `taitottinhday/K4-L3A-RAG-Pipeline`
- Nhánh: `feature/data-indexing`
- Commit đối chiếu: `2e01fd5` — `feat: add data collection and indexing tasks`

## Phần việc đã thực hiện

| Module/deliverable       | Việc trực tiếp thực hiện                                                                      | File/commit                                  | Trạng thái |
| ------------------------ | --------------------------------------------------------------------------------------------- | -------------------------------------------- | ---------- |
| Task 1 — Legal data      | Khai báo nguồn tài liệu pháp lý, tải file, kiểm tra định dạng/kích thước và xử lý lỗi nguồn   | `src/task1_collect_legal_docs.py`, `2e01fd5` | Done       |
| Task 2 — News data       | Thu thập bài viết công khai và lưu JSON đủ `url`, `title`, `date_crawled`, `content_markdown` | `src/task2_crawl_news.py`, `2e01fd5`         | Done       |
| Task 3 — Standardization | Chuyển legal/news về Markdown, giữ `title`, `source`, `doc_type`, `url` và cấu trúc thư mục   | `src/task3_convert_markdown.py`, `2e01fd5`   | Done       |
| Task 4 — Chunk & index   | Load Markdown, chunk recursive, tạo embedding, ID ổn định và upsert ChromaDB cosine           | `src/task4_chunking_indexing.py`, `2e01fd5`  | Done       |

## Quyết định kỹ thuật quan trọng

1. **Quyết định:** Tách `data/landing/` và `data/standardized/`.  
   **Lý do/evidence:** Landing giữ nguyên file gốc để đối chiếu khi convert sai; downstream chỉ đọc Markdown đã chuẩn hóa với metadata thống nhất.  
   **Trade-off:** Tốn thêm dung lượng lưu trữ nhưng tăng khả năng truy vết nguồn và chạy lại pipeline.

2. **Quyết định:** Chunk recursive với `CHUNK_SIZE=500`, `CHUNK_OVERLAP=50`, ID ổn định và ChromaDB dùng upsert/cosine.  
   **Lý do/evidence:** Overlap giữ ngữ cảnh ở biên; ID theo document/chunk giúp chạy lại index không sinh bản sao.  
   **Trade-off:** Overlap làm tăng số vector; hash embedding mặc định tái lập và không tốn API nhưng semantic quality thấp hơn model chuyên dụng.

## Kiểm thử và kết quả

- Dữ liệu sau tích hợp: 3 PDF pháp lý, 5 JSON bài viết và 8 Markdown chuẩn hóa.
- Index tích hợp: 510 chunks từ 8 documents.
- `pytest tests/test_acceptance.py -q`: **5 passed**.
- `pytest tests/test_contracts.py -q`: **15 passed**.
- `pytest -q`: **20 passed** trên `main` sau khi merge ba phần.

## Điều còn hạn chế

- URL nguồn công khai có thể thay đổi hoặc chặn request; khi đó cần thay bằng nguồn chính thức tương đương.
- Chunk theo ký tự chưa hiểu hoàn toàn cấu trúc điều/khoản của văn bản pháp luật.
- Nếu có thêm thời gian, cải tiến đầu tiên là chunk theo heading pháp lý và A/B lại context recall/precision.

## Xác nhận đóng góp

Nội dung trên được đối chiếu với commit `2e01fd5`. Thành viên cần tự đọc lại, bổ sung MSSV và xác nhận trước khi nộp.

- Ngày: 20/09/2026
- Tên thành viên: Cao Văn Cường
