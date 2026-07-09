from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class RAGRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000)
    k: int = Field(default=5, ge=1, le=10)
    provider: Literal["ollama", "openai", "anthropic"] | None = Field(
        default=None, description="Override the configured LLM provider for this request."
    )
    model: str | None = Field(
        default=None, max_length=120, description="Override the provider's default model name."
    )


class Citation(BaseModel):
    chunk_id: str
    source_name: str
    reference: str
    topic: str
    source_page: int | None = None
    articles: list[int] = Field(default_factory=list)


class RetrievedChunk(BaseModel):
    chunk_id: str
    topic: str
    reference: str
    score: float
    text_preview: str
    kg_concepts: list[str] = Field(default_factory=list)


class KGConceptRef(BaseModel):
    id: str
    label: str


class KGInsight(BaseModel):
    question_concepts: list[KGConceptRef] = Field(default_factory=list)
    related_concepts: list[KGConceptRef] = Field(default_factory=list)
    related_articles: list[int] = Field(default_factory=list)
    boosted_chunks: int = 0


class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation]
    confidence: float = Field(..., ge=0.0, le=1.0)
    retrieved_chunks: list[RetrievedChunk]
    disclaimer: str
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None
    kg: KGInsight | None = None


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str
    service: str
    dependencies: dict[str, dict[str, Any]]


class CorpusChunk(BaseModel):
    chunk_id: str
    source_type: str
    source_name: str
    reference: str
    topic: str
    source_page: int | None = None
    text: str
    articles: list[int] = Field(default_factory=list)


class CorpusPage(BaseModel):
    items: list[CorpusChunk]
    total: int
    limit: int
    offset: int


class TopicCount(BaseModel):
    topic: str
    count: int


class ProviderStatus(BaseModel):
    id: str
    label: str
    kind: str
    model: str | None = None
    configured: bool
    available: bool
    active: bool


class ProvidersResponse(BaseModel):
    active: str
    providers: list[ProviderStatus]
