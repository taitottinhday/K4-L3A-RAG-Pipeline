"""Dense search trên ChromaDB bằng cùng embedding function với Task 4."""

from __future__ import annotations

from .task4_chunking_indexing import embed_texts, get_collection


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        return []
    collection = get_collection()
    count = collection.count() if hasattr(collection, "count") else top_k
    if count == 0:
        return []
    response = collection.query(
        query_embeddings=[embed_texts([query.strip()])[0]],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )
    results: list[dict] = []
    for item_id, content, raw_metadata, distance in zip(
        response["ids"][0],
        response["documents"][0],
        response["metadatas"][0],
        response["distances"][0],
    ):
        metadata = dict(raw_metadata)
        metadata["url"] = metadata.get("url") or None
        metadata["chunk_index"] = int(metadata["chunk_index"])
        results.append(
            {
                "id": item_id,
                "content": content,
                "score": float(max(-1.0, min(1.0, 1.0 - float(distance)))),
                "metadata": metadata,
                "retrieval_method": "dense",
            }
        )
    return sorted(results, key=lambda item: (-item["score"], item["id"]))[:top_k]


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for result in semantic_search("chính sách miễn học phí", top_k=3):
        print(result["score"], result["metadata"]["title"])
