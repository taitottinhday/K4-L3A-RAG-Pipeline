"""Chuẩn hóa PDF và JSON thành Markdown có metadata máy đọc được."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LANDING_DIR = ROOT / "data" / "landing"
OUTPUT_DIR = ROOT / "data" / "standardized"
METADATA_PREFIX = "<!-- rag-metadata:"
LEGAL_PROVENANCE = {
    "thong_tu_07_2022_tuyen_sinh.pdf": {
        "url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/01/07bgd.pdf",
        "fallback_json": None,
    },
    "nghi_quyet_217_2025_mien_hoc_phi.pdf": {
        "url": "https://vanban.chinhphu.vn/?docid=214401&pageid=27160",
        "fallback_json": "article_03.json",
    },
    "van_ban_hop_nhat_07_2024_mo_nganh_dao_tao.pdf": {
        "url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/12/07-vbhn-bgd.pdf",
        "fallback_json": None,
    },
}


def _with_metadata(metadata: dict, content: str) -> str:
    header = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
    return f"{METADATA_PREFIX} {header} -->\n\n{content.strip()}\n"


def convert_legal_docs() -> None:
    from markitdown import MarkItDown

    legal_dir = LANDING_DIR / "legal"
    output_dir = OUTPUT_DIR / "legal"
    output_dir.mkdir(parents=True, exist_ok=True)
    converter = MarkItDown()
    files = sorted(
        path for path in legal_dir.iterdir()
        if path.is_file()
        and path.suffix.lower() in {".pdf", ".doc", ".docx"}
        and path.name in LEGAL_PROVENANCE
    )
    if not files:
        raise FileNotFoundError("Chưa có PDF/DOCX trong data/landing/legal")

    for path in files:
        result = converter.convert(str(path))
        content = (result.text_content or "").strip()
        if len(content) < 200:
            fallback_name = LEGAL_PROVENANCE.get(path.name, {}).get("fallback_json")
            fallback_path = LANDING_DIR / "news" / str(fallback_name)
            if not fallback_name or not fallback_path.exists():
                raise ValueError(f"Không trích xuất đủ nội dung từ {path.name}")
            fallback = json.loads(fallback_path.read_text(encoding="utf-8"))
            content = str(fallback["content_markdown"]).strip()
        title = next(
            (line.lstrip("# ").strip() for line in content.splitlines() if line.strip()),
            path.stem.replace("_", " ").title(),
        )
        metadata = {
            "source": path.name,
            "title": title[:250],
            "doc_type": "legal",
            "url": LEGAL_PROVENANCE.get(path.name, {}).get("url"),
        }
        target = output_dir / f"{path.stem}.md"
        target.write_text(_with_metadata(metadata, content), encoding="utf-8")
        print(f"Converted: {target.relative_to(ROOT)}")


def convert_news_articles() -> None:
    news_dir = LANDING_DIR / "news"
    output_dir = OUTPUT_DIR / "news"
    output_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(news_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError("Chưa có JSON trong data/landing/news")

    required = {"url", "title", "date_crawled", "content_markdown"}
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = required - data.keys()
        if missing:
            raise ValueError(f"{path.name} thiếu field: {sorted(missing)}")
        content = str(data["content_markdown"]).strip()
        if len(content) < 200:
            raise ValueError(f"{path.name} có nội dung quá ngắn")
        metadata = {
            "source": str(data["url"]),
            "title": str(data["title"])[:250],
            "doc_type": "news",
            "url": str(data["url"]),
        }
        provenance = f"**Ngày thu thập:** {data['date_crawled']}\n\n{content}"
        target = output_dir / f"{path.stem}.md"
        target.write_text(_with_metadata(metadata, provenance), encoding="utf-8")
        print(f"Converted: {target.relative_to(ROOT)}")


def convert_all() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    convert_legal_docs()
    convert_news_articles()
    print(f"Markdown ready: {OUTPUT_DIR}")


if __name__ == "__main__":
    convert_all()
