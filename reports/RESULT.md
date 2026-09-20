# RAG evaluation results

## Run information

| Field | Value |
| --- | --- |
| Evaluation date (UTC) | 2026-09-20T07:44:27+00:00 |
| Git revision | 6a2a2d4 (working tree dirty) |
| Corpus fingerprint (SHA-256) | `8d90464bb1bbb69d` |
| Framework | local deterministic proxy evaluator v1 |
| Generator | extractive sentence selector (same for A/B) |
| Embedding model | local-hash (hash) |
| Golden dataset size | 15 |
| `top_k` | 5 |
| Fallback | disabled during A/B (`score_threshold=-2`) |

## Configurations

- **Config A — dense-only:** `use_reranking=False`.
- **Config B — hybrid + RRF:** dense + BM25, `use_reranking=True`.

Hai config giữ nguyên corpus, golden set, answer selector, metric và `top_k`; chỉ thay retrieval strategy.

## Threshold calibration

Fallback dùng cosine gốc của dense, không dùng điểm RRF. Với `SCORE_THRESHOLD=0.30`:

| Loại query | Query | Best dense cosine | Quyết định |
| --- | --- | ---: | --- |
| in-domain | Nghị quyết 217/2025/QH15 có hiệu lực từ ngày nào? | 0.221 | thử PageIndex fallback |
| out-of-domain | Đội tuyển nào vô địch World Cup bóng đá nam năm 2022? | 0.155 | thử PageIndex fallback |

Query ngoài domain nằm dưới threshold nên pipeline thử PageIndex; nếu provider không cấu hình hoặc lỗi, pipeline giữ kết quả hybrid và generation phải từ chối khi context không đủ bằng chứng.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
| --- | ---: | ---: | ---: |
| Faithfulness proxy | 1.000 | 1.000 | +0.000 |
| Answer relevance | 0.571 | 0.617 | +0.046 |
| Context recall | 0.910 | 0.954 | +0.044 |
| Context precision | 1.000 | 1.000 | +0.000 |
| **Average** | 0.870 | 0.893 | +0.023 |

## A/B comparison

- Cấu hình có điểm trung bình cao hơn: **Config B (hybrid + RRF)**.
- Hybrid đặc biệt hữu ích với số hiệu văn bản và cụm từ chính xác; dense hỗ trợ câu hỏi diễn đạt lại.
- Trade-off: Config B chạy thêm BM25 và một lần RRF trên local CPU, không phát sinh thêm API call.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| --: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| 1 | Điều kiện về cơ sở vật chất để cơ sở giáo dục đại học được hoạt động đào tạo là gì? | B | 1.000 | 0.190 | 0.450 | 1.000 | generation | Extracted sentences use wording different from the reference answer |
| 2 | Nghị định 81/2021/NĐ-CP có hiệu lực từ ngày nào? | B | 1.000 | 0.294 | 1.000 | 1.000 | generation | Extracted sentences use wording different from the reference answer |
| 3 | Nguồn tài chính của cơ sở giáo dục đại học gồm những nguồn nào? | B | 1.000 | 0.300 | 1.000 | 1.000 | generation | Extracted sentences use wording different from the reference answer |

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| ---: | --- | --- | --- | --- |
| 1 | Bổ sung hoặc làm sạch nguồn cho câu có recall thấp | Worst performers thiếu expected evidence | Tăng context recall | Chạy lại evaluator, so sánh recall từng câu |
| 2 | Điều chỉnh chunk theo heading pháp lý | Chunk ngoài chủ đề làm precision thấp | Tăng context precision | A/B chunk 400/700 ký tự |
| 3 | Hiệu chỉnh threshold bằng in/out-domain queries | Fallback phải dựa trên cosine dense gốc | Giảm trả lời ngoài miền | Ghi precision/recall tại nhiều threshold |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| --- | --- | ---: | --- | --- |
| Dense + BM25 + RRF | Dense-only | +0.023 average | Thêm BM25/RRF local | Giữ hybrid |

## Methodology note

Faithfulness là tỷ lệ token của câu trích xuất có trong retrieved context; answer relevance là token F1 với expected answer; context recall là độ phủ expected context; context precision là tỷ lệ chunk có bằng chứng liên quan. Đây là proxy local tái lập được, không phải điểm RAGAS/LLM-judge.
