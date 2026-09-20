"""Đọc Markdown, chia chunk, embedding và upsert vào ChromaDB."""

from __future__ import annotations

from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import re
import warnings

from dotenv import load_dotenv

from .contracts import validate_document


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

STANDARDIZED_DIR = ROOT / "data" / "standardized"
CHROMA_DIR = ROOT / "chroma_db"
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))
CHUNKING_METHOD = "recursive"

EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "hash").strip().lower()
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "local-hash").strip()
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))
EMBEDDING_FALLBACK_PROVIDER = os.getenv(
    "EMBEDDING_FALLBACK_PROVIDER", "hash"
).strip().lower()
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "rag_documents")
RUNTIME_CONFIG_PATH = CHROMA_DIR / "embedding_runtime.json"
_METADATA_RE = re.compile(r"^<!--\s*rag-metadata:\s*(\{.*?\})\s*-->\s*", re.DOTALL)
_LAST_PROVIDER_USED = EMBEDDING_PROVIDER


def _normalized(vector: list[float]) -> list[float]:
    magnitude = math.sqrt(sum(value * value for value in vector))
    return [value / magnitude for value in vector] if magnitude else vector


def _hash_embeddings(texts: list[str]) -> list[list[float]]:
    """Embedding offline có tính xác định; chỉ dùng làm fallback/demo."""
    output: list[list[float]] = []
    for text in texts:
        vector = [0.0] * EMBEDDING_DIM
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
        for feature in features:
            digest = hashlib.sha256(feature.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
            sign = 1.0 if digest[4] & 1 else -1.0
            vector[index] += sign
        output.append(_normalized(vector))
    return output


def _gemini_embeddings(texts: list[str]) -> list[list[float]]:
    from google import genai
    from google.genai import types

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY chưa được cấu hình trong .env")
    client = genai.Client(api_key=api_key)
    vectors: list[list[float]] = []
    for offset in range(0, len(texts), 50):
        batch_texts = texts[offset : offset + 50]
        contents = [
            types.Content(parts=[types.Part.from_text(text=text)]) for text in batch_texts
        ]
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=EMBEDDING_DIM),
        )
        batch = [_normalized(list(item.values or [])) for item in response.embeddings or []]
        if len(batch) != len(batch_texts):
            raise RuntimeError("Gemini trả về sai số lượng embedding")
        vectors.extend(batch)
    return vectors


@lru_cache(maxsize=2)
def _sentence_transformer(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            'Cài provider local bằng: pip install -e ".[local-embeddings]"'
        ) from error
    return SentenceTransformer(model_name)


def _embed_with_provider(texts: list[str], provider: str) -> list[list[float]]:
    if provider == "gemini":
        return _gemini_embeddings(texts)
    if provider == "hash":
        return _hash_embeddings(texts)
    if provider == "sentence_transformers":
        model = _sentence_transformer(EMBEDDING_MODEL)
        return model.encode(texts, normalize_embeddings=True).tolist()
    if provider == "openai":
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError('Cài OpenAI bằng: pip install -e ".[openai]"') from error
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình")
        response = OpenAI(api_key=api_key).embeddings.create(
            model=EMBEDDING_MODEL, input=texts, dimensions=EMBEDDING_DIM
        )
        return [_normalized(list(item.embedding)) for item in response.data]
    raise ValueError(f"EMBEDDING_PROVIDER không hợp lệ: {provider}")


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed một batch bằng provider đã chọn, có fallback offline tùy chọn."""
    global _LAST_PROVIDER_USED
    if not texts:
        return []
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Mỗi text cần là chuỗi không rỗng")

    # Query phải dùng đúng không gian vector đã dùng lúc index. Nếu provider đó
    # lỗi, fail rõ ràng thay vì âm thầm đổi provider và trả kết quả sai.
    provider = EMBEDDING_PROVIDER
    locked_to_index = False
    if len(texts) == 1 and RUNTIME_CONFIG_PATH.exists():
        try:
            runtime = json.loads(RUNTIME_CONFIG_PATH.read_text(encoding="utf-8"))
            if int(runtime.get("dimension", 0)) == EMBEDDING_DIM:
                provider = str(runtime.get("provider") or provider)
                locked_to_index = True
        except (OSError, ValueError, json.JSONDecodeError):
            pass
    try:
        vectors = _embed_with_provider(texts, provider)
        _LAST_PROVIDER_USED = provider
        return vectors
    except Exception as error:
        fallback = EMBEDDING_FALLBACK_PROVIDER
        if locked_to_index or not fallback or fallback == provider:
            raise
        warnings.warn(
            f"Embedding provider '{provider}' lỗi ({error}); dùng '{fallback}'.",
            RuntimeWarning,
            stacklevel=2,
        )
        vectors = _embed_with_provider(texts, fallback)
        _LAST_PROVIDER_USED = fallback
        return vectors


def get_collection():
    """Mở collection Chroma persistent dùng cosine distance."""
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _read_markdown(path: Path) -> tuple[dict, str]:
    raw = path.read_text(encoding="utf-8-sig").strip()
    match = _METADATA_RE.match(raw)
    if match:
        metadata = json.loads(match.group(1))
        content = raw[match.end() :].strip()
    else:
        metadata = {
            "source": path.name,
            "title": path.stem.replace("_", " ").title(),
            "doc_type": "legal" if "legal" in path.parts else "news",
            "url": None,
        }
        content = raw
    metadata = {
        "source": str(metadata.get("source") or path.name),
        "title": str(metadata.get("title") or path.stem),
        "doc_type": str(metadata.get("doc_type") or "unknown"),
        "url": metadata.get("url") or None,
    }
    return metadata, content


def load_documents() -> list[dict]:
    """Đọc mọi Markdown theo thứ tự ổn định và kiểm tra contract."""
    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        metadata, content = _read_markdown(path)
        if not content:
            continue
        document = {
            "id": path.relative_to(STANDARDIZED_DIR).as_posix(),
            "content": content,
            "metadata": metadata,
        }
        validate_document(document)
        documents.append(document)
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    """Chia Document thành chunks có ID và chunk_index ổn định."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
        separators=["\n\n", "\n", ". ", "; ", " ", ""],
    )
    chunks: list[dict] = []
    for document in documents:
        validate_document(document)
        texts = [text.strip() for text in splitter.split_text(document["content"]) if text.strip()]
        for index, text in enumerate(texts):
            chunk = {
                "id": f"{document['id']}::chunk-{index}",
                "content": text,
                "metadata": {**document["metadata"], "chunk_index": index},
            }
            validate_document(chunk, require_chunk=True)
            chunks.append(chunk)
    return chunks


def embed_chunks(chunks: list[dict]) -> list[dict]:
    """Thêm vector vào bản sao của từng chunk."""
    if not chunks:
        return []
    vectors = embed_texts([chunk["content"] for chunk in chunks])
    if len(vectors) != len(chunks):
        raise RuntimeError("Số embedding không khớp số chunk")
    return [{**chunk, "embedding": vector} for chunk, vector in zip(chunks, vectors)]


def _chroma_metadata(metadata: dict) -> dict:
    return {
        "source": str(metadata["source"]),
        "title": str(metadata["title"]),
        "doc_type": str(metadata["doc_type"]),
        "url": str(metadata.get("url") or ""),
        "chunk_index": int(metadata["chunk_index"]),
    }


def index_to_vectorstore(chunks: list[dict]) -> None:
    """Upsert thay vì add để chạy lại không sinh ID trùng."""
    if not chunks:
        raise ValueError("Không có chunk để index; hãy chạy Task 1-3 trước")
    collection = get_collection()
    incoming_ids = {chunk["id"] for chunk in chunks}
    existing_ids = set(collection.get(include=[]).get("ids") or [])
    stale_ids = sorted(existing_ids - incoming_ids)
    if stale_ids:
        collection.delete(ids=stale_ids)
    for offset in range(0, len(chunks), 100):
        batch = chunks[offset : offset + 100]
        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[_chroma_metadata(chunk["metadata"]) for chunk in batch],
        )
    RUNTIME_CONFIG_PATH.write_text(
        json.dumps(
            {
                "provider": _LAST_PROVIDER_USED,
                "configured_provider": EMBEDDING_PROVIDER,
                "model": EMBEDDING_MODEL if _LAST_PROVIDER_USED != "hash" else "local-hash",
                "dimension": EMBEDDING_DIM,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_pipeline() -> None:
    documents = load_documents()
    if not documents:
        raise FileNotFoundError("Không có Markdown; chạy python -m src.task3_convert_markdown")
    chunks = chunk_documents(documents)
    embedded_chunks = embed_chunks(chunks)
    index_to_vectorstore(embedded_chunks)
    print(f"Indexed {len(embedded_chunks)} chunks from {len(documents)} documents")


if __name__ == "__main__":
    run_pipeline()
