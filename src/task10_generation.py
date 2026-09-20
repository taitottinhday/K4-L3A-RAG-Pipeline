"""Generation grounded, có citation và safe refusal."""

from __future__ import annotations

import os
from pathlib import Path
import time
import warnings

from dotenv import load_dotenv

from .contracts import validate_generation_result
from .task9_retrieval_pipeline import retrieve


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

TOP_K = 5
TOP_P = 0.9
TEMPERATURE = 0.2
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()
_LLM_MODEL_OVERRIDE = os.getenv("LLM_MODEL", "").strip()
_PROVIDER_MODELS = {
    "gemini": os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest").strip(),
    "openai": os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip(),
    "anthropic": os.getenv("ANTHROPIC_MODEL", "").strip(),
}
LLM_MODEL = _LLM_MODEL_OVERRIDE or _PROVIDER_MODELS.get(LLM_PROVIDER, "")
SAFE_REFUSAL = "Tôi không thể xác minh thông tin này từ các nguồn hiện có."

SYSTEM_PROMPT = """Bạn là trợ lý tra cứu chính sách giáo dục Việt Nam.
Chỉ trả lời bằng thông tin trong context. Mỗi ý quan trọng phải dẫn nguồn dạng [1], [2].
Không dùng kiến thức bên ngoài, không suy đoán. Nếu context không đủ, hãy nói rõ không thể
xác minh. Trả lời ngắn gọn bằng tiếng Việt."""


def reorder_for_llm(chunks: list[dict]) -> list[dict]:
    """Đặt chunk quan trọng xen kẽ đầu/cuối mà không sửa input hay ID."""
    if len(chunks) <= 2:
        return list(chunks)
    return list(chunks[::2]) + list(reversed(chunks[1::2]))


def format_context(chunks: list[dict]) -> str:
    parts: list[str] = []
    for index, chunk in enumerate(chunks, 1):
        citation_index = int(chunk.get("citation_index", index))
        metadata = chunk["metadata"]
        source = metadata["source"]
        url = metadata.get("url")
        parts.append(
            f"[{citation_index}] Title: {metadata['title']}\n"
            f"Source: {source}\n"
            f"URL: {url or 'N/A'}\n"
            f"Retrieval: {chunk['retrieval_method']} | Score: {chunk['score']:.6f}\n"
            f"{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


def call_llm(system_prompt: str, user_message: str) -> str:
    """Dispatch OpenAI, Gemini hoặc Anthropic và luôn trả text thuần."""
    if LLM_PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY chưa được cấu hình trong .env")
        client = genai.Client(api_key=api_key)
        try:
            for attempt in range(3):
                try:
                    chat = client.chats.create(
                        model=LLM_MODEL,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            temperature=TEMPERATURE,
                            top_p=TOP_P,
                        ),
                    )
                    response = chat.send_message(user_message)
                    text = response.text
                    break
                except Exception as error:
                    transient = "503" in str(error) or "429" in str(error)
                    if not transient or attempt == 2:
                        raise
                    time.sleep(2 ** (attempt + 1))
        finally:
            client.close()
    elif LLM_PROVIDER == "openai":
        try:
            from openai import OpenAI
        except ImportError as error:
            raise RuntimeError('Cài OpenAI bằng: pip install -e ".[openai]"') from error
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("OPENAI_API_KEY chưa được cấu hình")
        response = OpenAI(api_key=api_key).responses.create(
            model=LLM_MODEL,
            instructions=system_prompt,
            input=user_message,
        )
        text = response.output_text
    elif LLM_PROVIDER == "anthropic":
        try:
            from anthropic import Anthropic
        except ImportError as error:
            raise RuntimeError('Cài Anthropic bằng: pip install -e ".[anthropic]"') from error
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY chưa được cấu hình")
        response = Anthropic(api_key=api_key).messages.create(
            model=LLM_MODEL,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            temperature=TEMPERATURE,
            max_tokens=1200,
        )
        text = "".join(block.text for block in response.content if hasattr(block, "text"))
    else:
        raise ValueError(f"LLM_PROVIDER không hợp lệ: {LLM_PROVIDER}")

    if not text or not text.strip():
        raise RuntimeError("LLM không trả về nội dung")
    return text.strip()


def generate_with_citation(query: str, top_k: int = TOP_K) -> dict:
    """Retrieve, reorder, generate và giữ sources khớp số citation."""
    if not isinstance(query, str) or not query.strip() or top_k <= 0:
        result = {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
        validate_generation_result(result)
        return result
    try:
        chunks = retrieve(query.strip(), top_k=top_k)
    except Exception as error:
        warnings.warn(f"Retrieval failed: {error}", RuntimeWarning, stacklevel=2)
        chunks = []
    if not chunks:
        result = {"answer": SAFE_REFUSAL, "sources": [], "retrieval_source": "none"}
        validate_generation_result(result)
        return result

    labeled = [dict(chunk, citation_index=index) for index, chunk in enumerate(chunks, 1)]
    reordered = reorder_for_llm(labeled)
    context = format_context(reordered)
    user_message = f"Context:\n{context}\n\nCâu hỏi: {query.strip()}"
    try:
        answer = call_llm(SYSTEM_PROMPT, user_message)
    except Exception as error:
        warnings.warn(f"Generation failed: {error}", RuntimeWarning, stacklevel=2)
        answer = SAFE_REFUSAL

    method = chunks[0]["retrieval_method"]
    retrieval_source = "pageindex" if method == "pageindex" else "hybrid"
    result = {
        "answer": answer,
        "sources": chunks,
        "retrieval_source": retrieval_source,
    }
    validate_generation_result(result)
    return result


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(generate_with_citation("Những đối tượng nào được miễn học phí?"))
