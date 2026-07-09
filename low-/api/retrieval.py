"""Retrieval backends for the RAG pipeline.

Two interchangeable backends produce the candidate chunks that feed the
knowledge-graph rerank:

- ``weaviate``: dense vector search over embeddings stored in Weaviate
  (the production path; needs the vector store and the E5 embedding model).
- ``local``: a fully in-process lexical backend (BM25 over the seeded legal
  chunks, blended with a small knowledge-graph concept signal). It needs no
  external service and no model download, so it works offline and is the
  automatic fallback when Weaviate is unreachable.

Both backends return a list of chunk dicts carrying a ``vector_score`` in
``[0, 1]`` plus a ``retrieval_backend`` marker, so the downstream rerank in
``api.rag`` treats them identically.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

from api.corpus import get_corpus_chunks
from api.kg import detect_concepts, get_knowledge_graph
from api.settings import Settings
from api.text_normalize import tokenize_for_overlap

BACKENDS = ("weaviate", "local")

# BM25 hyper-parameters.
_BM25_K1 = 1.5
_BM25_B = 0.75


class RetrievalError(RuntimeError):
    """Raised when the requested retrieval backend cannot serve a query."""


def _chunk_searchable(chunk: dict[str, Any]) -> str:
    return " ".join(
        [
            str(chunk.get("topic") or ""),
            str(chunk.get("reference") or ""),
            str(chunk.get("text") or ""),
        ]
    )


@lru_cache(maxsize=1)
def _bm25_index() -> dict[str, Any]:
    """Build a small BM25 index over the seeded corpus (cached)."""
    chunks = get_corpus_chunks()
    doc_tokens: list[list[str]] = []
    doc_freq: dict[str, int] = {}
    for chunk in chunks:
        tokens = list(tokenize_for_overlap(_chunk_searchable(chunk)))
        doc_tokens.append(tokens)
        for term in set(tokens):
            doc_freq[term] = doc_freq.get(term, 0) + 1

    total_docs = len(chunks)
    avg_len = (sum(len(tokens) for tokens in doc_tokens) / total_docs) if total_docs else 0.0
    idf = {
        term: math.log(1 + (total_docs - freq + 0.5) / (freq + 0.5))
        for term, freq in doc_freq.items()
    }
    term_freqs = [
        {term: tokens.count(term) for term in set(tokens)} for tokens in doc_tokens
    ]
    return {
        "chunks": chunks,
        "term_freqs": term_freqs,
        "doc_lengths": [len(tokens) for tokens in doc_tokens],
        "avg_len": avg_len,
        "idf": idf,
    }


def _bm25_scores(query_terms: set[str]) -> list[float]:
    index = _bm25_index()
    idf = index["idf"]
    avg_len = index["avg_len"] or 1.0
    scores: list[float] = []
    for term_freq, doc_len in zip(index["term_freqs"], index["doc_lengths"]):
        score = 0.0
        for term in query_terms:
            freq = term_freq.get(term)
            if not freq:
                continue
            denom = freq + _BM25_K1 * (1 - _BM25_B + _BM25_B * doc_len / avg_len)
            score += idf.get(term, 0.0) * (freq * (_BM25_K1 + 1)) / denom
        scores.append(score)
    return scores


def retrieve_local(question: str, k: int, settings: Settings) -> list[dict[str, Any]]:
    """Offline lexical + knowledge-graph retrieval over the seeded chunks."""
    index = _bm25_index()
    chunks = index["chunks"]
    if not chunks:
        return []

    query_terms = tokenize_for_overlap(question)
    scores = _bm25_scores(query_terms)
    max_score = max(scores) if scores else 0.0

    kg = get_knowledge_graph()
    question_concepts = set(detect_concepts(question))

    ranked: list[dict[str, Any]] = []
    for chunk, raw_score in zip(chunks, scores):
        # Normalize BM25 into [0, 1] so it lines up with vector distances.
        base = (raw_score / max_score) if max_score > 0 else 0.0
        chunk_id = str(chunk.get("chunk_id") or "")
        shared = question_concepts & set(kg.chunk_concepts.get(chunk_id, []))
        # Small concept nudge keeps graph-relevant chunks competitive.
        score = min(1.0, base + 0.05 * len(shared))
        row = dict(chunk)
        row["vector_score"] = round(score, 6)
        row["retrieval_backend"] = "local"
        ranked.append(row)

    ranked.sort(key=lambda item: item["vector_score"], reverse=True)
    # Drop chunks with no lexical or concept signal at all.
    hits = [row for row in ranked if row["vector_score"] > 0.0]
    return (hits or ranked)[:k]


def retrieve_weaviate(question: str, k: int, settings: Settings) -> list[dict[str, Any]]:
    """Dense vector retrieval from Weaviate (embeds the question with E5)."""
    from api.rag import embed_question, retrieve_chunks

    vector = embed_question(question, settings)
    rows = retrieve_chunks(vector, k, settings)
    for row in rows:
        row["retrieval_backend"] = "weaviate"
    return rows


def _weaviate_reachable(settings: Settings) -> bool:
    import httpx

    url = f"{settings.weaviate_url.rstrip('/')}/v1/.well-known/ready"
    try:
        return httpx.get(url, timeout=3).status_code == 200
    except httpx.HTTPError:
        return False


def resolve_backend(settings: Settings) -> str:
    """Pick the retrieval backend.

    ``local`` and ``weaviate`` are explicit. ``auto`` (the default) uses
    Weaviate when it is reachable and falls back to the offline local backend
    otherwise, so the app keeps working without the vector store.
    """
    choice = (settings.retrieval_backend or "auto").strip().lower()
    if choice == "local":
        return "local"
    if choice == "weaviate":
        return "weaviate"
    return "weaviate" if _weaviate_reachable(settings) else "local"


def retrieve(question: str, k: int, settings: Settings) -> tuple[list[dict[str, Any]], str]:
    backend = resolve_backend(settings)
    if backend == "weaviate":
        try:
            return retrieve_weaviate(question, k, settings), "weaviate"
        except Exception:
            # If the vector path breaks at query time (store down, model
            # missing), degrade gracefully to the offline backend.
            return retrieve_local(question, k, settings), "local"
    return retrieve_local(question, k, settings), "local"
