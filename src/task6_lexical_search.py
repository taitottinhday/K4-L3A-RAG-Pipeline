"""BM25 search dùng đúng corpus chunks của Task 4."""

from __future__ import annotations

import re

from .task4_chunking_indexing import chunk_documents, load_documents


CORPUS: list[dict] = []


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.lower(), flags=re.UNICODE)


def _corpus() -> list[dict]:
    global CORPUS
    if not CORPUS:
        CORPUS = chunk_documents(load_documents())
    return CORPUS


def build_bm25_index(corpus: list[dict]):
    """Tạo BM25Plus để score ổn định cả với corpus rất nhỏ."""
    from rank_bm25 import BM25Plus

    if not corpus:
        return None
    return BM25Plus([_tokenize(item["content"]) for item in corpus])


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    corpus = _corpus()
    bm25 = build_bm25_index(corpus)
    if bm25 is None:
        return []
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    query_set = set(query_tokens)
    scores = bm25.get_scores(query_tokens)
    candidates = [
        (index, float(score))
        for index, score in enumerate(scores)
        if query_set.intersection(_tokenize(corpus[index]["content"]))
    ]
    candidates.sort(key=lambda pair: (-pair[1], corpus[pair[0]]["id"]))
    results: list[dict] = []
    for index, score in candidates[:top_k]:
        item = corpus[index]
        results.append(
            {
                "id": item["id"],
                "content": item["content"],
                "score": score,
                "metadata": dict(item["metadata"]),
                "retrieval_method": "bm25",
            }
        )
    return results


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for result in lexical_search("học phí sinh viên", top_k=3):
        print(result["score"], result["metadata"]["title"])
