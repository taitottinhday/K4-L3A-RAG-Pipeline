"""PageIndex Cloud fallback tùy chọn, luôn fail-safe khi chưa có key."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from dotenv import load_dotenv
import requests


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "").strip()
PAGEINDEX_BASE_URL = os.getenv("PAGEINDEX_BASE_URL", "https://api.pageindex.ai").rstrip("/")
LANDING_LEGAL_DIR = ROOT / "data" / "landing" / "legal"
STANDARDIZED_DIR = ROOT / "data" / "standardized"
CACHE_PATH = ROOT / "pageindex_doc_ids.json"


def _load_cache() -> dict[str, dict]:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def upload_documents() -> None:
    """Upload PDF chưa có trong cache. Chỉ gọi khi đã điền PAGEINDEX_API_KEY."""
    if not PAGEINDEX_API_KEY:
        print("PageIndex disabled: PAGEINDEX_API_KEY is empty")
        return
    cache = _load_cache()
    pdfs = sorted(LANDING_LEGAL_DIR.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError("Không có PDF trong data/landing/legal")

    headers = {"api_key": PAGEINDEX_API_KEY}
    for path in pdfs:
        fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
        cached = cache.get(path.name, {})
        if cached.get("sha256") == fingerprint and cached.get("doc_id"):
            print(f"Already uploaded: {path.name}")
            continue
        with path.open("rb") as stream:
            response = requests.post(
                f"{PAGEINDEX_BASE_URL}/doc/",
                headers=headers,
                files={"file": (path.name, stream, "application/pdf")},
                timeout=(15, 180),
            )
        response.raise_for_status()
        payload = response.json()
        doc_id = payload.get("doc_id")
        if not doc_id:
            raise RuntimeError(f"PageIndex không trả doc_id cho {path.name}")
        cache[path.name] = {
            "doc_id": doc_id,
            "sha256": fingerprint,
            "source": path.name,
            "title": path.stem.replace("_", " ").title(),
        }
        CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Uploaded: {path.name} -> {doc_id}")


def _citation_content(citation: dict, fallback: str) -> str:
    for key in ("text", "quote", "content", "snippet"):
        value = citation.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return fallback.strip()


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    """Query PageIndex Chat API và chuẩn hóa citation thành SearchResult."""
    if not PAGEINDEX_API_KEY or not query.strip() or top_k <= 0:
        return []
    cache = _load_cache()
    doc_ids = [item.get("doc_id") for item in cache.values() if item.get("doc_id")]
    if not doc_ids:
        return []

    response = requests.post(
        f"{PAGEINDEX_BASE_URL}/chat/completions",
        headers={"api_key": PAGEINDEX_API_KEY, "Content-Type": "application/json"},
        json={
            "messages": [{"role": "user", "content": query.strip()}],
            "stream": False,
            "doc_id": doc_ids,
            "temperature": 0.0,
            "enable_citations": True,
        },
        timeout=(15, 120),
    )
    response.raise_for_status()
    payload = response.json()
    message = (payload.get("choices") or [{}])[0].get("message") or {}
    answer = str(message.get("content") or "").strip()
    citations = payload.get("citations") or message.get("citations") or []
    by_doc_id = {item["doc_id"]: item for item in cache.values() if item.get("doc_id")}

    if not citations and answer:
        citations = [{"doc_id": doc_ids[0], "text": answer}]
    results: list[dict] = []
    seen: set[str] = set()
    for rank, citation in enumerate(citations, 1):
        if not isinstance(citation, dict):
            continue
        doc_id = citation.get("doc_id") or citation.get("document_id") or doc_ids[0]
        cached = by_doc_id.get(doc_id, {})
        page = citation.get("page") or citation.get("page_number") or 0
        content = _citation_content(citation, answer)
        if not content:
            continue
        item_id = f"pageindex::{doc_id}::page-{page}::rank-{rank}"
        if item_id in seen:
            continue
        seen.add(item_id)
        results.append(
            {
                "id": item_id,
                "content": content,
                "score": 1.0 / rank,
                "metadata": {
                    "source": str(cached.get("source") or doc_id),
                    "title": str(cached.get("title") or "PageIndex result"),
                    "doc_type": "legal",
                    "url": None,
                    "chunk_index": rank - 1,
                },
                "retrieval_method": "pageindex",
            }
        )
    return results[:top_k]


if __name__ == "__main__":
    upload_documents()
