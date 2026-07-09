from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.corpus import list_topics, search_chunks
from api.deps import Settings, get_settings
from api.generator import GeneratorError, INSUFFICIENT_ANSWER
from api.kg import get_knowledge_graph
from api.models import (
    CorpusPage,
    HealthResponse,
    ProvidersResponse,
    RAGRequest,
    RAGResponse,
    TopicCount,
)
from api.observability import (
    RAG_ANSWERS_TOTAL,
    RAG_GENERATION_ERRORS_TOTAL,
    RAG_RETRIEVED_CHUNKS,
    setup_observability,
)
from api.providers import provider_statuses, resolve_provider
from api.rag import answer_question


SERVICE_NAME = "lawz-ai-jo-api"
VALID_KG_NODE_TYPES = {"concept", "article", "topic", "source", "chunk"}


def check_weaviate_ready(settings: Settings) -> dict[str, object]:
    url = f"{settings.weaviate_url.rstrip('/')}/v1/.well-known/ready"
    try:
        response = httpx.get(url, timeout=3)
        return {
            "ok": response.status_code == 200,
            "url": url,
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def check_ollama_ready(settings: Settings) -> dict[str, object]:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
    try:
        response = httpx.get(url, timeout=3)
        return {
            "ok": response.status_code == 200,
            "url": url,
            "status_code": response.status_code,
        }
    except httpx.HTTPError as exc:
        return {"ok": False, "url": url, "error": str(exc)}


def check_llm_ready(settings: Settings) -> dict[str, object]:
    """Readiness of the active LLM provider.

    Local Ollama gets a live reachability probe; API providers are considered
    ready when their credentials are configured (no billable probe on boot).
    """
    provider = resolve_provider(settings)
    if provider == "ollama":
        return {**check_ollama_ready(settings), "provider": "ollama"}
    if provider == "openai":
        ok = bool(settings.openai_api_key and settings.openai_model)
        return {"ok": ok, "provider": "openai", "model": settings.openai_model or None}
    ok = bool(settings.anthropic_api_key)
    return {"ok": ok, "provider": "anthropic", "model": settings.anthropic_model}


def create_app() -> FastAPI:
    app = FastAPI(
        title="Lawz AI JO",
        description="مساعد معلوماتي عربي لقانون العمل الأردني: استرجاع + رسم معرفي + توليد.",
        version="0.2.0",
    )
    settings = get_settings()

    allowed_origins = {
        settings.web_origin,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    }
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(allowed_origins),
        # Also allow localhost/preview hosts on any port so the dev UI can
        # reach the API when served from a proxied preview origin.
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )
    setup_observability(app)

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok", service=SERVICE_NAME)

    @app.get("/readyz")
    def readyz(settings: Settings = Depends(get_settings)):
        dependencies = {
            "weaviate": check_weaviate_ready(settings),
            "llm": check_llm_ready(settings),
        }
        ready = all(bool(item.get("ok")) for item in dependencies.values())
        payload = {
            "status": "ok" if ready else "not_ready",
            "service": SERVICE_NAME,
            "dependencies": dependencies,
        }
        if not ready:
            return JSONResponse(status_code=503, content=payload)
        return payload

    @app.post("/rag/answer", response_model=RAGResponse)
    def rag_answer(request: RAGRequest, settings: Settings = Depends(get_settings)) -> RAGResponse:
        try:
            response = answer_question(
                request.question,
                request.k,
                settings,
                provider=request.provider,
                model=request.model,
            )
        except GeneratorError as exc:
            RAG_ANSWERS_TOTAL.labels(outcome="error").inc()
            RAG_GENERATION_ERRORS_TOTAL.inc()
            raise HTTPException(status_code=503, detail=f"LLM provider unavailable: {exc}") from exc
        except Exception:
            RAG_ANSWERS_TOTAL.labels(outcome="error").inc()
            raise

        outcome = "abstained" if INSUFFICIENT_ANSWER in response.answer else "answered"
        RAG_ANSWERS_TOTAL.labels(outcome=outcome).inc()
        RAG_RETRIEVED_CHUNKS.observe(len(response.retrieved_chunks))
        return response

    # ------------------------------------------------------------------
    # LLM providers
    # ------------------------------------------------------------------

    @app.get("/llm/providers", response_model=ProvidersResponse)
    def llm_providers(settings: Settings = Depends(get_settings)) -> ProvidersResponse:
        return ProvidersResponse(
            active=resolve_provider(settings),
            providers=provider_statuses(settings),
        )

    # ------------------------------------------------------------------
    # Knowledge graph
    # ------------------------------------------------------------------

    @app.get("/kg/overview")
    def kg_overview():
        return get_knowledge_graph().stats()

    @app.get("/kg/graph")
    def kg_graph(
        types: str | None = Query(default=None, description="Comma-separated node types."),
        limit: int = Query(default=400, ge=1, le=1000),
    ):
        node_types: set[str] | None = None
        if types:
            node_types = {item.strip() for item in types.split(",") if item.strip()}
            invalid = node_types - VALID_KG_NODE_TYPES
            if invalid:
                raise HTTPException(status_code=422, detail=f"Unknown node types: {sorted(invalid)}")
        return get_knowledge_graph().subgraph(node_types=node_types, limit=limit)

    @app.get("/kg/concepts")
    def kg_concepts():
        return {"concepts": get_knowledge_graph().concept_list()}

    @app.get("/kg/search")
    def kg_search(q: str = Query(..., min_length=1, max_length=120), limit: int = Query(default=20, ge=1, le=50)):
        return {"results": get_knowledge_graph().search(q, limit=limit)}

    @app.get("/kg/node/{node_id:path}")
    def kg_node(node_id: str):
        found = get_knowledge_graph().get_node(node_id)
        if found is None:
            raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
        return found

    # ------------------------------------------------------------------
    # Legal corpus (read-only)
    # ------------------------------------------------------------------

    @app.get("/corpus/chunks", response_model=CorpusPage)
    def corpus_chunks(
        q: str | None = Query(default=None, max_length=200),
        topic: str | None = Query(default=None, max_length=200),
        source_type: str | None = Query(default=None, max_length=60),
        limit: int = Query(default=20, ge=1, le=100),
        offset: int = Query(default=0, ge=0),
    ) -> CorpusPage:
        items, total = search_chunks(query=q, topic=topic, source_type=source_type, limit=limit, offset=offset)
        return CorpusPage(items=items, total=total, limit=limit, offset=offset)

    @app.get("/corpus/topics", response_model=list[TopicCount])
    def corpus_topics() -> list[TopicCount]:
        return [TopicCount(**item) for item in list_topics()]

    return app


app = create_app()
