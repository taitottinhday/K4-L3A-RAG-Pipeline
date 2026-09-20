"""Thu thập năm trang chính sách công khai thành JSON có metadata."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re

import requests


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "landing" / "news"

ARTICLE_URLS = [
    "https://vanban.chinhphu.vn/?docid=203950&pageid=27160",
    "https://vanban.chinhphu.vn/?docid=163054&pageid=27160",
    "https://vanban.chinhphu.vn/?docid=214401&pageid=27160",
    "https://vanban.chinhphu.vn/?docid=198740&pageid=27160",
    (
        "https://tuyensinh.moet.gov.vn/ts/van-ban/"
        "thong-tu-06-2026-tt-bgddt-cua-bo-giao-duc-va-dao-tao-ban-hanh-"
        "quy-che-tuyen-sinh-cac-nganh-dao-tao-t--9483cd05-0038-4279-8fe7-ea36aa5e67ac"
    ),
]


class _ReadableHTML(HTMLParser):
    """Trình tách nội dung nhỏ, không cần browser hay API crawler."""

    ignored_tags = {"script", "style", "svg", "noscript", "nav", "footer"}
    block_tags = {"p", "div", "article", "section", "li", "h1", "h2", "h3", "h4", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._ignored_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags:
            self._ignored_depth += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.block_tags and self._parts and self._parts[-1] != "\n":
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self.ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.block_tags:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if not text or self._ignored_depth:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
        self._parts.append(text)

    def markdown(self) -> str:
        raw = " ".join(self._parts)
        lines = [re.sub(r"\s+", " ", line).strip() for line in raw.split("\n")]
        unique: list[str] = []
        for line in lines:
            if len(line) >= 20 and (not unique or line != unique[-1]):
                unique.append(line)
        return "\n\n".join(unique)


def _crawl_sync(url: str) -> dict:
    response = requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0 RAG-course-project/1.0"},
        timeout=(10, 60),
    )
    response.raise_for_status()
    response.encoding = response.apparent_encoding or response.encoding
    parser = _ReadableHTML()
    parser.feed(response.text)
    content = parser.markdown()
    if len(content) < 200:
        raise ValueError("page contains too little readable content")
    title = re.sub(r"\s+", " ", parser.title).strip() or "Văn bản giáo dục"
    return {
        "url": url,
        "title": title,
        "date_crawled": datetime.now(timezone.utc).isoformat(),
        "content_markdown": f"# {title}\n\n{content}",
    }


async def crawl_article(url: str) -> dict:
    """Crawl trong worker thread để không chặn event loop."""
    return await asyncio.to_thread(_crawl_sync, url)


async def crawl_all() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    outcomes = await asyncio.gather(
        *(crawl_article(url) for url in ARTICLE_URLS), return_exceptions=True
    )
    failures: list[str] = []
    for index, (url, outcome) in enumerate(zip(ARTICLE_URLS, outcomes), 1):
        if isinstance(outcome, BaseException):
            failures.append(f"{url}: {outcome}")
            continue
        output = DATA_DIR / f"article_{index:02d}.json"
        output.write_text(
            json.dumps(outcome, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Saved: {output.name}")
    if failures:
        raise RuntimeError("Some pages could not be crawled:\n- " + "\n- ".join(failures))


if __name__ == "__main__":
    asyncio.run(crawl_all())
