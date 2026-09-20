"""Reciprocal Rank Fusion cho dense và BM25."""

from __future__ import annotations


def rerank_rrf(
    ranked_lists: list[list[dict]],
    top_k: int = 5,
    k: int = 60,
) -> list[dict]:
    if top_k <= 0:
        return []
    if k < 0:
        raise ValueError("RRF k phải không âm")

    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    first_seen: dict[str, int] = {}
    seen_counter = 0
    for ranked_list in ranked_lists:
        seen_in_list: set[str] = set()
        for rank, item in enumerate(ranked_list, 1):
            item_id = item["id"]
            if item_id in seen_in_list:
                continue
            seen_in_list.add(item_id)
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            if item_id not in items:
                items[item_id] = item
                first_seen[item_id] = seen_counter
                seen_counter += 1

    ranked_ids = sorted(scores, key=lambda item_id: (-scores[item_id], first_seen[item_id]))
    results: list[dict] = []
    for item_id in ranked_ids[:top_k]:
        result = {**items[item_id], "score": scores[item_id], "retrieval_method": "hybrid"}
        result["metadata"] = dict(items[item_id]["metadata"])
        results.append(result)
    return results


if __name__ == "__main__":
    print("RRF module ready")
