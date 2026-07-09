from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np

from api import providers
from api.generator import INSUFFICIENT_ANSWER, GeneratorError
from api.kg import CONCEPT_LEXICON, detect_concepts, get_knowledge_graph
from api.models import Citation, KGConceptRef, KGInsight, RAGResponse, RetrievedChunk
from api.settings import Settings
from api.text_normalize import (
    ARABIC_VARIANTS,
    DIACRITICS_RE,
    STOPWORDS,
    TOKEN_RE,
    WHITESPACE_RE,
    normalize_arabic_text,
    tokenize_for_overlap,
)

__all__ = [
    "DISCLAIMER",
    "SYSTEM_PROMPT",
    "ARABIC_VARIANTS",
    "DIACRITICS_RE",
    "WHITESPACE_RE",
    "TOKEN_RE",
    "STOPWORDS",
    "normalize_arabic_text",
    "tokenize_for_overlap",
    "answer_question",
    "encode_texts",
    "format_passage_for_embedding",
    "format_query_for_embedding",
    "rerank_chunks",
]

DISCLAIMER = "هذا شرح أولي مبني على المصادر المسترجعة ولا يُعد استشارة قانونية ولا يغني عن مراجعة محامٍ مختص أو النص القانوني الرسمي."

SYSTEM_PROMPT = """أنت مساعد معلوماتي لمشروع Lawz AI JO.
مهمتك شرح النصوص القانونية الأردنية المسترجعة بلغة عربية بسيطة.
لا تقدم استشارة قانونية نهائية.
لا تخترع مواد أو مراجع غير موجودة.
اعتمد فقط على النصوص القانونية المسترجعة.
إذا لم تكف النصوص، قل بوضوح: لا تكفي قاعدة المعرفة الحالية للإجابة بثقة.
لا تعرض خطوات التفكير.
لا تكتب <think>.
أجب مباشرة وباختصار."""


def uses_e5_prefix(model_name: str) -> bool:
    return "e5" in (model_name or "").lower()


def format_query_for_embedding(question: str, model_name: str) -> str:
    question = question.strip()
    if uses_e5_prefix(model_name) and not question.lower().startswith("query:"):
        return f"query: {question}"
    return question


def format_passage_for_embedding(text: str, model_name: str) -> str:
    text = text.strip()
    if uses_e5_prefix(model_name) and not text.lower().startswith("passage:"):
        return f"passage: {text}"
    return text


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def encode_texts(texts: list[str], model_name: str) -> list[list[float]]:
    model = get_embedding_model(model_name)
    try:
        vectors = model.encode(texts, normalize_embeddings=True)
    except TypeError:
        vectors = model.encode(texts)
        vectors = np.asarray(vectors, dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        vectors = vectors / np.maximum(norms, 1e-12)

    return np.asarray(vectors, dtype=np.float32).tolist()


def embed_question(question: str, settings: Settings) -> list[float]:
    text = format_query_for_embedding(question, settings.embedding_model)
    return encode_texts([text], settings.embedding_model)[0]


def retrieve_chunks(question_vector: list[float], k: int, settings: Settings) -> list[dict[str, Any]]:
    import weaviate

    client = weaviate.Client(url=settings.weaviate_url)
    properties = [
        "chunk_id",
        "source_name",
        "reference",
        "topic",
        "text",
        "source_page",
        "source_type",
        "jurisdiction",
    ]

    result = (
        client.query.get(settings.weaviate_class, properties)
        .with_near_vector({"vector": question_vector})
        .with_limit(k)
        .with_additional(["distance"])
        .do()
    )

    rows = result.get("data", {}).get("Get", {}).get(settings.weaviate_class, []) or []
    chunks: list[dict[str, Any]] = []
    for row in rows:
        additional = row.get("_additional") or {}
        distance = additional.get("distance")
        try:
            vector_score = max(0.0, 1.0 - float(distance)) if distance is not None else 0.0
        except (TypeError, ValueError):
            vector_score = 0.0

        chunk = {key: row.get(key) for key in properties}
        chunk["vector_score"] = vector_score
        chunks.append(chunk)
    return chunks


def rerank_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    question_concepts: list[str] | None = None,
    kg_boost_per_concept: float = 0.04,
) -> list[dict[str, Any]]:
    """Lexical-overlap rerank with an optional knowledge-graph concept boost.

    A chunk that shares legal concepts with the question (e.g. both mention
    "الفصل التعسفي") gets a small additive boost per shared concept, so
    graph-relevant chunks win ties against merely vector-similar ones.
    """
    question_tokens = tokenize_for_overlap(question)
    concepts = set(question_concepts or [])
    kg = get_knowledge_graph() if concepts else None

    reranked: list[dict[str, Any]] = []
    for chunk in chunks:
        searchable = " ".join(
            [
                str(chunk.get("topic") or ""),
                str(chunk.get("reference") or ""),
                str(chunk.get("text") or ""),
            ]
        )
        overlap_count = len(question_tokens & tokenize_for_overlap(searchable))
        score = float(chunk.get("vector_score") or 0.0) + 0.05 * overlap_count

        shared_concepts: list[str] = []
        if kg is not None:
            chunk_id = str(chunk.get("chunk_id") or "")
            chunk_concepts = kg.chunk_concepts.get(chunk_id)
            if chunk_concepts is None:
                chunk_concepts = detect_concepts(str(chunk.get("text") or ""))
            shared_concepts = [cid for cid in chunk_concepts if cid in concepts]
            score += kg_boost_per_concept * len(shared_concepts)

        updated = dict(chunk)
        updated["score"] = round(min(1.0, score), 4)
        updated["overlap_count"] = overlap_count
        updated["kg_concepts"] = shared_concepts
        reranked.append(updated)

    return sorted(reranked, key=lambda item: item["score"], reverse=True)


def truncate_text(text: str, limit: int) -> str:
    text = WHITESPACE_RE.sub(" ", (text or "").strip())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def build_user_prompt(question: str, chunks: list[dict[str, Any]], settings: Settings) -> str:
    context_parts = []
    for index, chunk in enumerate(chunks, start=1):
        topic = chunk.get("topic") or "بدون موضوع"
        reference = chunk.get("reference") or "بدون مرجع"
        text = truncate_text(str(chunk.get("text") or ""), settings.chunk_text_limit)
        context_parts.append(f"[{index}] {topic} - {reference}\n{text}")

    context = "\n\n".join(context_parts)
    return f"""السؤال:
{question}

النصوص القانونية المسترجعة:
{context}

المطلوب:
أجب بالعربية بصيغة منظمة:
1. الإجابة المختصرة
2. السبب بناءً على النصوص المسترجعة
3. المواد أو المراجع ذات الصلة
4. تنبيه قانوني مختصر: هذا شرح أولي وليس استشارة قانونية

Rules:
- Do not include <think>.
- Do not show reasoning steps.
- Do not invent article numbers.
- Do not mention citations that are not in retrieved context.
- If context is not enough, say:
  لا تكفي قاعدة المعرفة الحالية للإجابة بثقة."""


def build_citations(chunks: list[dict[str, Any]]) -> list[Citation]:
    kg = get_knowledge_graph()
    citations: list[Citation] = []
    seen: set[str] = set()
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        if not chunk_id or chunk_id in seen:
            continue
        seen.add(chunk_id)
        citations.append(
            Citation(
                chunk_id=chunk_id,
                source_name=str(chunk.get("source_name") or ""),
                reference=str(chunk.get("reference") or ""),
                topic=str(chunk.get("topic") or ""),
                source_page=chunk.get("source_page"),
                articles=kg.chunk_articles.get(chunk_id, []),
            )
        )
    return citations


def build_retrieved_preview(chunks: list[dict[str, Any]]) -> list[RetrievedChunk]:
    previews: list[RetrievedChunk] = []
    for chunk in chunks:
        concept_labels = [
            CONCEPT_LEXICON[cid]["label"]
            for cid in chunk.get("kg_concepts") or []
            if cid in CONCEPT_LEXICON
        ]
        previews.append(
            RetrievedChunk(
                chunk_id=str(chunk.get("chunk_id") or ""),
                topic=str(chunk.get("topic") or ""),
                reference=str(chunk.get("reference") or ""),
                score=float(chunk.get("score") or 0.0),
                text_preview=truncate_text(str(chunk.get("text") or ""), 260),
                kg_concepts=concept_labels,
            )
        )
    return previews


def build_kg_insight(
    question_concepts: list[str],
    prompt_chunks: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
) -> KGInsight:
    kg = get_knowledge_graph()
    related_articles: list[int] = []
    for chunk in prompt_chunks:
        chunk_id = str(chunk.get("chunk_id") or "")
        for number in kg.chunk_articles.get(chunk_id, []):
            if number not in related_articles:
                related_articles.append(number)

    related = [
        KGConceptRef(id=item["id"], label=item["label"])
        for item in kg.related_concepts(question_concepts, limit=6)
    ]
    return KGInsight(
        question_concepts=[
            KGConceptRef(id=f"concept:{cid}", label=CONCEPT_LEXICON[cid]["label"])
            for cid in question_concepts
            if cid in CONCEPT_LEXICON
        ],
        related_concepts=related,
        related_articles=sorted(related_articles),
        boosted_chunks=sum(1 for chunk in reranked if chunk.get("kg_concepts")),
    )


def answer_question(
    question: str,
    k: int,
    settings: Settings,
    provider: str | None = None,
    model: str | None = None,
) -> RAGResponse:
    question_concepts = detect_concepts(question)
    query_vector = embed_question(question, settings)
    retrieved = retrieve_chunks(query_vector, k, settings)
    reranked = rerank_chunks(
        question,
        retrieved,
        question_concepts=question_concepts,
        kg_boost_per_concept=settings.kg_boost_per_concept,
    )

    kg_insight = build_kg_insight(question_concepts, reranked[: settings.rag_prompt_top_n], reranked)

    if not reranked:
        return RAGResponse(
            answer=INSUFFICIENT_ANSWER,
            citations=[],
            confidence=0.0,
            retrieved_chunks=[],
            disclaimer=DISCLAIMER,
            kg=kg_insight,
        )

    prompt_chunks = reranked[: settings.rag_prompt_top_n]
    user_prompt = build_user_prompt(question, prompt_chunks, settings)
    try:
        generation = providers.generate(SYSTEM_PROMPT, user_prompt, settings, provider=provider, model=model)
    except GeneratorError:
        raise

    answer = generation.text
    confidence = 0.0 if INSUFFICIENT_ANSWER in answer else float(prompt_chunks[0].get("score") or 0.0)

    return RAGResponse(
        answer=answer,
        citations=build_citations(prompt_chunks),
        confidence=round(min(1.0, max(0.0, confidence)), 3),
        retrieved_chunks=build_retrieved_preview(reranked[:k]),
        disclaimer=DISCLAIMER,
        provider=generation.provider,
        model=generation.model,
        latency_ms=generation.latency_ms,
        kg=kg_insight,
    )
