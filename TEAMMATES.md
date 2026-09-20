# Thành viên và phân công

Nhóm có ba thành viên. Mỗi người làm việc bằng tài khoản Git của chính mình trên một nhánh riêng, chịu trách nhiệm đọc code, tạo thay đổi có ý nghĩa, chạy test và ghi commit/PR vào báo cáo cá nhân trong `reports/`.

## Bảng thành viên

| Họ và tên | Mã học viên | Vai trò | Nhánh đề xuất | Phạm vi sở hữu |
| --- | --- | --- | --- | --- |
| Cần điền | Cần điền | Data & Indexing | `feature/data-indexing` | Task 1–4, corpus landing/standardized và kiểm tra index |
| Cần điền | Cần điền | Retrieval & Fusion | `feature/retrieval-fusion` | Task 5–9, dense/BM25/RRF/fallback và contract test |
| Lê Văn Tài | 2A202602464 | Generation, UI & Evaluation | `feature/generation-evaluation` | Task 10, Streamlit, golden dataset, evaluation, báo cáo và tích hợp cuối |

## Phần 1 — Data & Indexing

**File sở hữu:**

- `src/task1_collect_legal_docs.py`
- `src/task2_crawl_news.py`
- `src/task3_convert_markdown.py`
- `src/task4_chunking_indexing.py`
- `data/landing/`
- `data/standardized/`

**Công việc phải thực hiện:**

1. Đối chiếu nguồn công khai, metadata và nội dung mẫu.
2. Kiểm tra chạy lại crawl/convert không tạo bản sao.
3. Kiểm tra chunk ID ổn định và upsert không nhân đôi index.
4. Ghi số document, Markdown và chunk vào báo cáo cá nhân.

**Lệnh kiểm tra:**

```powershell
python -m src.task1_collect_legal_docs
python -m src.task2_crawl_news
python -m src.task3_convert_markdown
python -m src.task4_chunking_indexing
python -m pytest tests/test_acceptance.py -q
```

## Phần 2 — Retrieval & Fusion

**File sở hữu:**

- `src/task5_semantic_search.py`
- `src/task6_lexical_search.py`
- `src/task7_reranking.py`
- `src/task8_pageindex_vectorless.py`
- `src/task9_retrieval_pipeline.py`
- `tests/test_contracts.py` khi bổ sung test cho phần retrieval

**Công việc phải thực hiện:**

1. Xác nhận dense và BM25 dùng cùng corpus, kết quả unique và sort giảm dần.
2. Kiểm tra RRF dùng rank từ 1, không mutate input và chỉ được gọi một lần.
3. Kiểm tra fallback dùng cosine dense gốc, không dùng điểm RRF.
4. Ghi kết quả một query trong domain và một query ngoài domain vào báo cáo.

**Lệnh kiểm tra:**

```powershell
python -m src.task5_semantic_search
python -m src.task6_lexical_search
python -m src.task7_reranking
python -m src.task9_retrieval_pipeline
python -m pytest tests/test_contracts.py -q
```

## Phần 3 — Generation, UI & Evaluation

**File sở hữu:**

- `src/task10_generation.py`
- `app.py`
- `src/evaluate_pipeline.py`
- `group_project/evaluation/golden_dataset.json`
- `group_project/evaluation/RESULT.md`
- `reports/RESULT.md`
- `README.md`

**Công việc phải thực hiện:**

1. Kiểm tra citation map đúng `sources`, safe refusal và provider dispatch.
2. Kiểm tra UI hiển thị answer, title/source, retrieval method và score.
3. Chạy dense-only và hybrid + RRF trên cùng 15 golden cases.
4. Phân tích bốn metric, ba worst performers và chạy tích hợp cuối.

**Lệnh kiểm tra:**

```powershell
python -m src.task10_generation
python -m src.evaluate_pipeline
python -m pytest -q
python -m streamlit run app.py
```

## Quy tắc bằng chứng đóng góp

1. Không commit lại file không thay đổi hoặc chỉ sửa khoảng trắng để tạo lịch sử.
2. Mỗi thành viên sử dụng tài khoản Git của chính mình và tạo thay đổi có thể giải thích khi demo.
3. Mỗi nhánh cần ít nhất một thay đổi kỹ thuật, một kết quả test và một báo cáo cá nhân.
4. Báo cáo `reports/<mssv>-<ten>.md` phải dẫn hash commit hoặc URL PR.
5. Sau khi merge đủ ba phần, người tích hợp chạy lại `python -m src.evaluate_pipeline` và toàn bộ `pytest -q`.
