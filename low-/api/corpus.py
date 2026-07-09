"""Read-only access to the seeded legal corpus.

The legal chunks in ``seed_chunks.json`` are the source of truth for the law
texts. This module never mutates them; it only loads, filters, and serves them
to the API layer and the knowledge-graph builder.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.text_normalize import normalize_arabic_text

SEED_PATH = Path(__file__).with_name("seed_chunks.json")

ARTICLE_RE = re.compile(r"الماده\s*(?:رقم\s*)?\(?\s*(\d{1,3})\s*\)?")


@lru_cache(maxsize=1)
def get_corpus_chunks() -> tuple[dict[str, Any], ...]:
    rows = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError(f"{SEED_PATH} must contain a JSON array.")
    return tuple(rows)


def extract_article_numbers(reference: str | None, text: str | None = None) -> list[int]:
    """Extract Jordanian labor-law article numbers from a reference string."""
    numbers: list[int] = []
    seen: set[int] = set()
    for source in (reference, text):
        if not source:
            continue
        normalized = normalize_arabic_text(source)
        for match in ARTICLE_RE.finditer(normalized):
            value = int(match.group(1))
            # "رقم 8 لسنة 1996" is the law number, not an article; the regex
            # anchors on "الماده" so law numbers never reach this point.
            if value not in seen:
                seen.add(value)
                numbers.append(value)
    return numbers


def list_topics() -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for chunk in get_corpus_chunks():
        topic = str(chunk.get("topic") or "").strip()
        if topic:
            counts[topic] = counts.get(topic, 0) + 1
    return [
        {"topic": topic, "count": count}
        for topic, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def search_chunks(
    query: str | None = None,
    topic: str | None = None,
    source_type: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    normalized_query = normalize_arabic_text(query or "")
    results: list[dict[str, Any]] = []
    for chunk in get_corpus_chunks():
        if topic and str(chunk.get("topic") or "") != topic:
            continue
        if source_type and str(chunk.get("source_type") or "") != source_type:
            continue
        if normalized_query:
            haystack = normalize_arabic_text(
                " ".join(
                    [
                        str(chunk.get("topic") or ""),
                        str(chunk.get("reference") or ""),
                        str(chunk.get("text") or ""),
                    ]
                )
            )
            if normalized_query not in haystack:
                continue
        results.append(chunk)

    total = len(results)
    page = results[offset : offset + limit]
    items = [
        {
            "chunk_id": str(chunk.get("chunk_id") or ""),
            "source_type": str(chunk.get("source_type") or ""),
            "source_name": str(chunk.get("source_name") or ""),
            "reference": str(chunk.get("reference") or ""),
            "topic": str(chunk.get("topic") or ""),
            "source_page": chunk.get("source_page"),
            "text": str(chunk.get("text") or ""),
            "articles": extract_article_numbers(chunk.get("reference"), None),
        }
        for chunk in page
    ]
    return items, total
