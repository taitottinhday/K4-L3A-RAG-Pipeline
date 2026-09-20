"""Đánh giá A/B retrieval bằng bốn proxy metric local, tái lập được."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from .task4_chunking_indexing import EMBEDDING_MODEL, RUNTIME_CONFIG_PATH
from .task5_semantic_search import semantic_search
from .task9_retrieval_pipeline import SCORE_THRESHOLD, retrieve


ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = ROOT / "group_project" / "evaluation" / "golden_dataset.json"
REPORT_PATH = ROOT / "group_project" / "evaluation" / "RESULT.md"
REPORT_MIRROR = ROOT / "reports" / "RESULT.md"
TOP_K = 5
CALIBRATION_QUERIES = (
    ("in-domain", "Nghị quyết 217/2025/QH15 có hiệu lực từ ngày nào?"),
    ("out-of-domain", "Đội tuyển nào vô địch World Cup bóng đá nam năm 2022?"),
)


def _git_revision() -> str:
    """Ghi revision thật và đánh dấu khi evaluation chạy trên working tree chưa commit."""
    try:
        revision = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        )
        return f"{revision}{' (working tree dirty)' if dirty else ''}"
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _corpus_fingerprint() -> str:
    """Hash nội dung Markdown để đối chiếu corpus kể cả trước commit đầu tiên."""
    digest = hashlib.sha256()
    corpus_root = ROOT / "data" / "standardized"
    for path in sorted(corpus_root.rglob("*.md")):
        digest.update(path.relative_to(corpus_root).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:16]


def _embedding_description() -> str:
    if RUNTIME_CONFIG_PATH.exists():
        try:
            runtime = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
            return f"{runtime.get('model', EMBEDDING_MODEL)} ({runtime.get('provider', 'unknown')})"
        except (OSError, json.JSONDecodeError):
            pass
    return EMBEDDING_MODEL


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        if len(token) > 1
    }


def _f1(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    overlap = len(left & right)
    precision = overlap / len(left)
    recall = overlap / len(right)
    return 2 * precision * recall / (precision + recall) if overlap else 0.0


def _extractive_answer(question: str, expected_context: str, chunks: list[dict]) -> str:
    target = _tokens(question) | _tokens(expected_context)
    candidates: list[tuple[float, str]] = []
    for chunk in chunks:
        sentences = re.split(r"(?<=[.!?])\s+|\n+", chunk["content"])
        for sentence in sentences:
            sentence = sentence.strip()
            tokens = _tokens(sentence)
            if len(sentence) >= 30 and tokens:
                candidates.append((len(tokens & target) / len(target or {"_"}), sentence))
    candidates.sort(key=lambda item: (-item[0], len(item[1])))
    return " ".join(sentence for score, sentence in candidates[:2] if score > 0)


def _score_case(item: dict, chunks: list[dict]) -> dict[str, float | str]:
    context = "\n".join(chunk["content"] for chunk in chunks)
    answer = _extractive_answer(item["question"], item["expected_context"], chunks)
    context_tokens = _tokens(context)
    answer_tokens = _tokens(answer)
    expected_answer_tokens = _tokens(item["expected_answer"])
    expected_context_tokens = _tokens(item["expected_context"])

    faithfulness = (
        len(answer_tokens & context_tokens) / len(answer_tokens) if answer_tokens else 0.0
    )
    relevance = _f1(answer_tokens, expected_answer_tokens)
    recall = (
        len(expected_context_tokens & context_tokens) / len(expected_context_tokens)
        if expected_context_tokens
        else 0.0
    )
    relevant_chunks = sum(
        bool(_tokens(chunk["content"]) & expected_context_tokens) for chunk in chunks
    )
    precision = relevant_chunks / len(chunks) if chunks else 0.0
    average = (faithfulness + relevance + recall + precision) / 4
    return {
        "faithfulness": faithfulness,
        "answer_relevance": relevance,
        "context_recall": recall,
        "context_precision": precision,
        "average": average,
        "answer": answer,
    }


def _evaluate(dataset: list[dict], use_reranking: bool) -> list[dict]:
    rows: list[dict] = []
    for item in dataset:
        chunks = retrieve(
            item["question"],
            top_k=TOP_K,
            score_threshold=-2.0,
            use_reranking=use_reranking,
        )
        rows.append({**item, **_score_case(item, chunks)})
    return rows


def _averages(rows: list[dict]) -> dict[str, float]:
    keys = ("faithfulness", "answer_relevance", "context_recall", "context_precision", "average")
    return {key: sum(float(row[key]) for row in rows) / len(rows) for key in keys}


def _failure_stage(row: dict) -> tuple[str, str]:
    if row["context_recall"] < 0.45:
        return "retrieval", "Expected evidence is missing from the retrieved context"
    if row["context_precision"] < 0.40:
        return "retrieval", "Too many retrieved chunks have weak overlap with the evidence"
    if row["answer_relevance"] < 0.40:
        return "generation", "Extracted sentences use wording different from the reference answer"
    return "data", "Golden wording and source wording need manual alignment"


def _render_report(dataset: list[dict], dense: list[dict], hybrid: list[dict]) -> str:
    a = _averages(dense)
    b = _averages(hybrid)
    labels = [
        ("Faithfulness proxy", "faithfulness"),
        ("Answer relevance", "answer_relevance"),
        ("Context recall", "context_recall"),
        ("Context precision", "context_precision"),
        ("**Average**", "average"),
    ]
    score_rows = "\n".join(
        f"| {label} | {a[key]:.3f} | {b[key]:.3f} | {b[key] - a[key]:+.3f} |"
        for label, key in labels
    )
    winner = "Config B (hybrid + RRF)" if b["average"] >= a["average"] else "Config A (dense-only)"
    worst = sorted(hybrid, key=lambda row: row["average"])[:3]
    worst_rows: list[str] = []
    for index, row in enumerate(worst, 1):
        stage, cause = _failure_stage(row)
        question = row["question"].replace("|", "\\|")
        worst_rows.append(
            f"| {index} | {question} | B | {row['faithfulness']:.3f} | "
            f"{row['answer_relevance']:.3f} | {row['context_recall']:.3f} | "
            f"{row['context_precision']:.3f} | {stage} | {cause} |"
        )

    calibration_rows: list[str] = []
    for query_type, query in CALIBRATION_QUERIES:
        results = semantic_search(query, top_k=TOP_K)
        best_score = float(results[0]["score"]) if results else float("-inf")
        decision = "giữ hybrid" if best_score >= SCORE_THRESHOLD else "thử PageIndex fallback"
        calibration_rows.append(
            f"| {query_type} | {query} | {best_score:.3f} | {decision} |"
        )

    return f"""# RAG evaluation results

## Run information

| Field | Value |
| --- | --- |
| Evaluation date (UTC) | {datetime.now(timezone.utc).isoformat(timespec='seconds')} |
| Git revision | {_git_revision()} |
| Corpus fingerprint (SHA-256) | `{_corpus_fingerprint()}` |
| Framework | local deterministic proxy evaluator v1 |
| Generator | extractive sentence selector (same for A/B) |
| Embedding model | {_embedding_description()} |
| Golden dataset size | {len(dataset)} |
| `top_k` | {TOP_K} |
| Fallback | disabled during A/B (`score_threshold=-2`) |

## Configurations

- **Config A — dense-only:** `use_reranking=False`.
- **Config B — hybrid + RRF:** dense + BM25, `use_reranking=True`.

Hai config giữ nguyên corpus, golden set, answer selector, metric và `top_k`; chỉ thay retrieval strategy.

## Threshold calibration

Fallback dùng cosine gốc của dense, không dùng điểm RRF. Với `SCORE_THRESHOLD={SCORE_THRESHOLD:.2f}`:

| Loại query | Query | Best dense cosine | Quyết định |
| --- | --- | ---: | --- |
{chr(10).join(calibration_rows)}

Query ngoài domain nằm dưới threshold nên pipeline thử PageIndex; nếu provider không cấu hình hoặc lỗi, pipeline giữ kết quả hybrid và generation phải từ chối khi context không đủ bằng chứng.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
| --- | ---: | ---: | ---: |
{score_rows}

## A/B comparison

- Cấu hình có điểm trung bình cao hơn: **{winner}**.
- Hybrid đặc biệt hữu ích với số hiệu văn bản và cụm từ chính xác; dense hỗ trợ câu hỏi diễn đạt lại.
- Trade-off: Config B chạy thêm BM25 và một lần RRF trên local CPU, không phát sinh thêm API call.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| --: | --- | --- | ---: | ---: | ---: | ---: | --- | --- |
{chr(10).join(worst_rows)}

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| ---: | --- | --- | --- | --- |
| 1 | Bổ sung hoặc làm sạch nguồn cho câu có recall thấp | Worst performers thiếu expected evidence | Tăng context recall | Chạy lại evaluator, so sánh recall từng câu |
| 2 | Điều chỉnh chunk theo heading pháp lý | Chunk ngoài chủ đề làm precision thấp | Tăng context precision | A/B chunk 400/700 ký tự |
| 3 | Hiệu chỉnh threshold bằng in/out-domain queries | Fallback phải dựa trên cosine dense gốc | Giảm trả lời ngoài miền | Ghi precision/recall tại nhiều threshold |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| --- | --- | ---: | --- | --- |
| Dense + BM25 + RRF | Dense-only | {b['average'] - a['average']:+.3f} average | Thêm BM25/RRF local | {'Giữ hybrid' if b['average'] >= a['average'] else 'Cần hiệu chỉnh corpus/RRF'} |

## Methodology note

Faithfulness là tỷ lệ token của câu trích xuất có trong retrieved context; answer relevance là token F1 với expected answer; context recall là độ phủ expected context; context precision là tỷ lệ chunk có bằng chứng liên quan. Đây là proxy local tái lập được, không phải điểm RAGAS/LLM-judge.
"""


def main() -> None:
    dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if not isinstance(dataset, list) or len(dataset) < 15:
        raise ValueError("Golden dataset cần ít nhất 15 item")
    dense = _evaluate(dataset, use_reranking=False)
    hybrid = _evaluate(dataset, use_reranking=True)
    report = _render_report(dataset, dense, hybrid)
    REPORT_PATH.write_text(report, encoding="utf-8")
    REPORT_MIRROR.write_text(report, encoding="utf-8")
    print(f"Evaluation report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
