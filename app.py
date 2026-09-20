"""Giao diện Streamlit cho pipeline RAG."""

from __future__ import annotations

import streamlit as st

from src.task10_generation import generate_with_citation
from src.task4_chunking_indexing import get_collection


st.set_page_config(page_title="RAG chính sách giáo dục", page_icon="🎓", layout="wide")


def render_sources(sources: list[dict], retrieval_source: str) -> None:
    if not sources:
        return
    with st.expander(f"Nguồn tham khảo ({len(sources)}) · {retrieval_source}"):
        for index, source in enumerate(sources, 1):
            metadata = source["metadata"]
            st.markdown(
                f"**[{index}] {metadata['title']}**  \n"
                f"`{source['retrieval_method']}` · score `{source['score']:.4f}` · "
                f"chunk `{metadata['chunk_index']}`"
            )
            location = metadata.get("url") or metadata["source"]
            if str(location).startswith("http"):
                st.markdown(f"[Mở nguồn]({location})")
            else:
                st.caption(f"Nguồn: {location}")
            preview = source["content"].replace("\n", " ").strip()
            st.write(preview[:500] + ("…" if len(preview) > 500 else ""))
            if index < len(sources):
                st.divider()


if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("🎓 RAG giáo dục")
    st.caption("Tra cứu văn bản về học phí, tuyển sinh và đào tạo đại học.")
    top_k = st.slider("Số đoạn ngữ cảnh", 3, 10, 5)
    try:
        indexed_count = get_collection().count()
    except Exception:
        indexed_count = 0
    if indexed_count:
        st.success(f"Đã index {indexed_count} chunks")
    else:
        st.warning("Chưa có index. Chạy `python -m src.task4_chunking_indexing`.")
    if st.button("Xóa lịch sử chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

st.title("Chatbot chính sách giáo dục")
st.caption("Câu trả lời chỉ dựa trên corpus và luôn kèm nguồn để đối chiếu.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message["role"] == "assistant":
            render_sources(message.get("sources", []), message.get("retrieval_source", "none"))

query = st.chat_input("Ví dụ: Những đối tượng nào được miễn học phí?")
if query:
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang tìm nguồn và tổng hợp..."):
            result = generate_with_citation(query, top_k=top_k)
        st.markdown(result["answer"])
        render_sources(result["sources"], result["retrieval_source"])

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": result["answer"],
            "sources": result["sources"],
            "retrieval_source": result["retrieval_source"],
        }
    )
