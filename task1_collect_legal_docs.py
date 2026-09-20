"""Tải bộ văn bản pháp luật công khai dùng cho demo RAG."""

from __future__ import annotations

from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "landing" / "legal"

# Nguồn chính thức, công khai. Tên file ổn định để chạy lại không tạo bản sao.
LEGAL_SOURCES = [
    {
        "filename": "thong_tu_07_2022_tuyen_sinh.pdf",
        "url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2022/01/07bgd.pdf",
    },
    {
        "filename": "nghi_quyet_217_2025_mien_hoc_phi.pdf",
        "url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/7/217qh.signed.pdf",
    },
    {
        "filename": "van_ban_hop_nhat_07_2024_mo_nganh_dao_tao.pdf",
        "url": "https://datafiles.chinhphu.vn/cpp/files/vbpq/2024/12/07-vbhn-bgd.pdf",
    },
]


def setup_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _valid_pdf(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 1024:
        return False
    with path.open("rb") as stream:
        return stream.read(5) == b"%PDF-"


def download_documents() -> None:
    """Tải ba PDF; bỏ qua file hợp lệ đã có và báo lỗi rõ ràng."""
    setup_directory()
    failures: list[str] = []
    headers = {"User-Agent": "Mozilla/5.0 RAG-course-project/1.0"}

    for source in LEGAL_SOURCES:
        target = DATA_DIR / source["filename"]
        if _valid_pdf(target):
            print(f"Already exists: {target.name}")
            continue
        try:
            response = requests.get(
                source["url"], headers=headers, timeout=(10, 90), allow_redirects=True
            )
            response.raise_for_status()
            content = response.content
            if len(content) <= 1024 or not content.startswith(b"%PDF-"):
                raise ValueError("server did not return a valid PDF")
            target.write_bytes(content)
            print(f"Downloaded: {target.name} ({len(content):,} bytes)")
        except (requests.RequestException, OSError, ValueError) as error:
            failures.append(f"{source['filename']}: {error}")

    valid_count = sum(_valid_pdf(DATA_DIR / item["filename"]) for item in LEGAL_SOURCES)
    if valid_count < len(LEGAL_SOURCES):
        details = "\n- ".join(failures) or "unknown error"
        raise RuntimeError(f"Only {valid_count}/3 legal PDFs are ready:\n- {details}")


if __name__ == "__main__":
    download_documents()
