"""Hybrid retrieval: dense + BM25 + một lần RRF + PageIndex fallback."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank_rrf
from .task8_pageindex_vectorless import pageindex_search


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


SCORE_THRESHOLD = _env_float("SCORE_THRESHOLD", 0.30)
DEFAULT_TOP_K = 5


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
) -> list[dict]:
    """Dùng cosine gốc để quyết định fallback, không dùng RRF score."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    candidate_k = max(top_k * 2, top_k)
    dense = semantic_search(query.strip(), top_k=candidate_k)
    sparse = lexical_search(query.strip(), top_k=candidate_k)

    if use_reranking:
        hybrid = rerank_rrf([dense, sparse], top_k=top_k)
    else:
        hybrid = dense[:top_k]

    best_dense_score = float(dense[0]["score"]) if dense else 0.0
    if best_dense_score < score_threshold:
        try:
            fallback = pageindex_search(query.strip(), top_k=top_k)
            if fallback:
                return fallback[:top_k]
        except Exception:
            # Provider ngoài không được làm crash UI; hybrid vẫn là kết quả hợp lệ.
            pass
    return hybrid[:top_k]


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for result in retrieve("Ai được miễn học phí?", top_k=3):
        print(result["retrieval_method"], result["score"], result["metadata"]["title"])
