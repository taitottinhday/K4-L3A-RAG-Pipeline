# Individual contribution report

Mỗi thành viên copy template này thành:

```text
reports/<student-id>-<short-name>.md
```

Giới hạn khuyến nghị: 1 trang, không chép lại README hoặc mô tả lý thuyết chung. Báo cáo không phải một bài pipeline cá nhân; mục đích là ghi nhận ownership và bằng chứng đóng góp trong sản phẩm nhóm.

---

## Thông tin

- Họ và tên: Cao Văn Cường
- Mã học viên: 2A202602493
- Nhóm:22
- Repository/branch:feature/data-indexing

## Phần việc đã thực hiện

| Module/deliverable                  | Việc tôi trực tiếp làm                                                                                                                                                 | File/commit/PR                                                                | Trạng thái |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------- | ---------- |
| Task 1: thu thập tài liệu pháp luật | Khai báo 3 nguồn PDF chính thức, tải với timeout, kiểm tra chữ ký `%PDF-`, kích thước và bỏ qua file hợp lệ đã có để chạy lại an toàn.                                 | `src/task1_collect_legal_docs.py`; commit `2e01fd5`                           | Done       |
| Task 2: crawl tin/chính sách        | Crawl 5 URL công khai bằng `requests`, tách HTML thành nội dung đọc được, lưu JSON gồm URL, tiêu đề, thời điểm thu thập và Markdown; các lỗi được gom và báo rõ.       | `src/task2_crawl_news.py`; commit `2e01fd5`                                   | Done       |
| Task 3: chuẩn hóa dữ liệu           | Chuyển PDF/DOCX và JSON sang Markdown, gắn metadata nguồn, tiêu đề, loại tài liệu và URL; có fallback JSON cho tài liệu PDF không trích xuất đủ nội dung.              | `src/task3_convert_markdown.py`; commit `2e01fd5`                             | Done       |
| Task 4: chunking và indexing        | Đọc Markdown, giữ provenance, chia chunk recursive có `chunk_index`, tạo embedding theo provider cấu hình và upsert vào ChromaDB để chạy index lại không tạo ID trùng. | `src/task4_chunking_indexing.py`; commit `2e01fd5`; `tests/test_contracts.py` | Done       |

Chỉ kê khai công việc có thể đối chiếu bằng file, commit, pull request, test hoặc kết quả evaluation.

## Quyết định kỹ thuật quan trọng

Mô tả tối đa hai quyết định mà bạn trực tiếp tham gia:

1. **Quyết định:** Dùng metadata JSON trong đầu file Markdown để giữ provenance xuyên suốt pipeline.  
   **Lý do/evidence:** Task 3 ghi `source`, `title`, `doc_type`, `url`; Task 4 đọc lại metadata và đưa vào từng chunk, phù hợp schema trong `docs/MODULE_CONTRACTS.md`.  
   **Trade-off:** File Markdown có thêm phần header kỹ thuật, nhưng downstream không phải suy đoán nguồn từ tên file và citation có thể truy vết.

2. **Quyết định:** Dùng ID chunk ổn định theo dạng `<document-id>::chunk-<index>` và `upsert` khi ghi ChromaDB.  
   **Lý do/evidence:** Task 4 tạo ID từ đường dẫn tương đối và vị trí chunk, xóa ID stale rồi upsert; test contract kiểm tra ID duy nhất, metadata và `chunk_index`.  
   **Trade-off:** Thay đổi nội dung có thể làm thay đổi số chunk và cần xóa ID cũ, nhưng chạy lại pipeline không tích lũy bản ghi trùng.

## Kiểm thử và kết quả

- Test hoặc query tôi đã dùng: `pytest tests/test_contracts.py -q`, tập trung vào `test_chunk_documents_preserves_identity_and_metadata` và các kiểm tra chữ ký public API.
- Kết quả trước/sau nếu có: Chưa có kết quả runtime trong phiên này vì lệnh test được bỏ qua; cần chạy `pytest tests/test_contracts.py -q` trước buổi demo.
- Lỗi đã phát hiện và cách xử lý: Chưa ghi nhận lỗi trong phạm vi Task 1–4; các lỗi tải/crawl và provider embedding được xử lý bằng timeout, thông báo lỗi rõ ràng và fallback cấu hình.

## Điều còn hạn chế

- Một hạn chế cụ thể của phần tôi làm: Task 1–3 cần network và dữ liệu nguồn thực tế; test hiện tại chủ yếu kiểm tra contract/chunking, chưa phải integration test chạy toàn bộ download, crawl và ChromaDB.
- Nếu có thêm thời gian, thay đổi đầu tiên tôi sẽ thực hiện: Bổ sung fixture offline và integration test cho đường đi Task 1–4, bao gồm kiểm tra chạy index hai lần cho cùng dữ liệu.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc của mình và có thể giải thích hoặc chạy lại trong buổi demo.

- Ngày: 2026-09-20
- Tên thành viên: Cao Văn Cường
