# Lawz AI JO Project Guide

This guide explains the Lawz AI JO capstone project in enough detail for teammates, reviewers, and future PDF export.

## 1. Project Overview

Lawz AI JO is a focused Arabic Retrieval-Augmented Generation (RAG) assistant for Jordanian labor-law information. It accepts an Arabic question, detects the labor-law concepts it mentions, retrieves relevant legal chunks from Weaviate, boosts graph-related chunks with a legal knowledge graph, builds a grounded Arabic prompt, generates the answer through a pluggable LLM provider (local Ollama by default, or any OpenAI-compatible API, or the Anthropic Claude API), and returns an Arabic answer with backend-generated citations and knowledge-graph insights.

The project is intentionally focused. It is not a broad legal chatbot. It demonstrates a clean graph-augmented RAG workflow with local Docker services, pluggable generation, observability, and smoke evaluation.

## 2. Problem Statement

Jordanian labor-law information can be hard to search and summarize for non-specialists. The project provides a simple interface where a user can ask a labor-law information question in Arabic and receive a short grounded explanation with references to retrieved source chunks.

The answer is informational only. It is not a final legal opinion and does not replace official legal texts or a qualified lawyer.

## 3. Scope

The project does:

- Accept Arabic labor-law information questions.
- Detect labor-law concepts in the question using a curated Arabic lexicon.
- Embed the question with `intfloat/multilingual-e5-small`.
- Retrieve relevant legal chunks from Weaviate.
- Apply a lexical overlap rerank plus a knowledge-graph concept boost on top of vector retrieval.
- Build a grounded Arabic prompt from retrieved context.
- Generate with the configured provider: local Ollama (`qwen3:4b` by default), any OpenAI-compatible API, or the Anthropic Claude API — switchable per request.
- Return an Arabic answer, backend citations (with article numbers), retrieved chunk previews, confidence, knowledge-graph insights, and disclaimer.
- Build and serve a legal knowledge graph (sources, articles, topics, concepts) derived automatically from the seed chunks.
- Expose health, readiness, metrics, and structured logs.
- Provide a full Next.js web UI: assistant, knowledge-graph explorer, legal-corpus library, system status, and about pages.
- Provide a smoke evaluation script.

## 4. Non-scope

The project does not include:

- PDF upload.
- DOCX parsing.
- Contract review.
- Risk scoring.
- Neo4j or any external graph database (the knowledge graph is in-process and derived from the corpus).
- LangChain.
- Modification of the legal source texts.
- Broad legal chatbot behavior.
- Production legal-advice workflows.

## 5. Architecture

```text
User
  -> Web UI on http://localhost:3001
  -> FastAPI on http://localhost:8001
     -> concept detection (Arabic legal lexicon)
     -> Weaviate on http://localhost:8081 (vector retrieval)
     -> knowledge-graph boosted rerank
     -> LLM provider:
        - Ollama qwen3:4b on http://localhost:11434 (default, local)
        - or any OpenAI-compatible API
        - or the Anthropic Claude API
  -> Arabic answer with backend citations and KG insights
```

Docker Compose runs Weaviate, the FastAPI API, and the web UI. Ollama does not run in Docker. It runs on the teammate's host machine, and the API container connects to it through:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

## 6. File-by-file Explanation

### `api/main.py`

Creates the FastAPI application. It defines:

- `GET /healthz` for basic API health.
- `GET /readyz` for Weaviate and active LLM-provider readiness checks.
- `POST /rag/answer` for the main RAG answer endpoint (accepts optional `provider` and `model` overrides).
- `GET /llm/providers` for provider configuration/availability.
- `GET /kg/overview`, `GET /kg/graph`, `GET /kg/node/{id}`, `GET /kg/search`, `GET /kg/concepts` for the knowledge graph.
- `GET /corpus/chunks` and `GET /corpus/topics` for read-only corpus browsing.
- CORS settings for the web UI.
- Observability middleware and metrics setup.

The route catches generation errors from any provider and returns a clean service-unavailable response.

### `api/settings.py`

Defines environment-driven settings using Pydantic settings. Important values include Weaviate URL/class, embedding model, retrieval limits, the active LLM provider and per-provider configuration (Ollama URL/model, OpenAI-compatible base URL/key/model, Anthropic key/model), the knowledge-graph boost factor, API URL, web URL, and CORS origin.

### `api/models.py`

Defines Pydantic request and response models:

- `RAGRequest` (with optional `provider`/`model` overrides)
- `Citation` (with extracted article numbers)
- `RetrievedChunk` (with matched KG concepts)
- `KGInsight` / `KGConceptRef`
- `RAGResponse` (with `provider`, `model`, `latency_ms`, `kg`)
- `CorpusChunk` / `CorpusPage` / `TopicCount`
- `ProviderStatus` / `ProvidersResponse`
- `HealthResponse`
- `ReadyResponse`

These models keep the API response shape explicit and testable.

### `api/text_normalize.py`

Shared Arabic text normalization (hamza/teh-marbuta folding, diacritics removal, Arabic-Indic digit mapping) and tokenization used by both retrieval and the knowledge graph.

### `api/corpus.py`

Read-only loader for `api/seed_chunks.json` with search/filter helpers and article-number extraction (`المادة N`). The legal texts are never modified.

### `api/kg.py`

Builds the legal knowledge graph deterministically from the seed chunks at startup:

- A curated Arabic lexicon of ~30 labor-law concepts with alias matching (whole-word, attached-particle aware).
- Nodes: sources, articles, topics, concepts, chunks.
- Edges: chunk relations plus projected relations (concept co-occurrence, article/topic coverage).
- Query helpers: stats, subgraph for visualization, node neighborhoods, search, related concepts.

### `api/providers.py`

The LLM provider layer with one interface and three backends: `ollama` (local `/api/chat`), `openai` (any OpenAI-compatible `/chat/completions`), and `anthropic` (official `anthropic` SDK). Handles provider resolution, per-request overrides, output cleaning, latency measurement, and configuration status reporting.

### `api/deps.py`

Small dependency module that exposes `get_settings` and `Settings` for FastAPI dependency injection.

### `api/rag.py`

Contains the core RAG flow:

1. Detect labor-law concepts in the question (knowledge graph lexicon).
2. Normalize and embed the user question.
3. Query Weaviate using a near-vector search.
4. Convert vector distance to an approximate score.
5. Rerank using a lexical overlap bonus plus a per-shared-concept knowledge-graph boost.
6. Build a grounded Arabic prompt from the top retrieved chunks.
7. Call the configured LLM provider (with optional per-request override).
8. Clean the answer.
9. Build backend citations, retrieved chunk previews, and knowledge-graph insights.

Citations are created by the backend from retrieved chunks. The LLM is not trusted to invent or format citations.

### `api/generator.py`

Legacy Ollama generator kept for backward compatibility. It exposes `GeneratorError`, the abstention message, and `<think>` output cleaning used by the provider layer. New code goes through `api/providers.py`.

### `api/observability.py`

Defines:

- Prometheus counters, histograms, and gauges.
- Request ID middleware.
- Structured JSON request logging.
- Metrics middleware.
- `/metrics` ASGI app mount.

Metric labels are bounded and do not include user questions or request IDs.

### `api/seed_weaviate.py`

Seeds Weaviate from `api/seed_chunks.json`. It:

1. Reads and validates seed chunks.
2. Connects to Weaviate.
3. Deletes the existing `LegalChunk` class if present.
4. Creates a schema with external vectors and cosine distance.
5. Embeds chunk text with `intfloat/multilingual-e5-small`.
6. Batch inserts chunks with vectors.
7. Prints a short summary.

Known successful seed summary:

```text
class: LegalChunk
chunks_loaded: 73
embedding_model: intfloat/multilingual-e5-small
first_chunk_id: official_labor_law_art_002_p01
last_chunk_id: betterwork_guide_page_067
```

### `api/seed_chunks.json`

JSON array containing the legal chunks used for Weaviate seeding. Each chunk includes:

- `chunk_id`
- `source_name`
- `reference`
- `topic`
- `text`
- `source_page`
- `source_type`
- `jurisdiction`
- `embedding_text`

The current seed file contains 73 legal chunks.

### `data/rag_smoke.json`

Small smoke evaluation fixture. It contains 5 Arabic test questions and expected topic/reference hints where available.

### `eval_rag_smoke.py`

Command-line smoke evaluation script. It calls the live API, measures latency, checks answer presence, citation presence, abstention count, retrieval hits when expected chunk IDs exist, and reference hits when expected reference text exists.

Default output:

```text
outputs/rag_smoke_results.json
```

### `docker-compose.yml`

Defines the local stack:

- `weaviate` on host port `8081`.
- `api` on host port `8001`.
- `web` on host port `3001`.

It also maps `host.docker.internal` so the API container can reach host Ollama.

### `api/Dockerfile`

Builds the Python API image. It installs CPU-only Torch first, then installs `requirements.txt`, copies the API package and seed script, and starts Uvicorn.

### `web/`

Professional Arabic RTL Next.js UI with a shared design system (`styles/globals.css`, light/dark themes, Jordan-inspired palette) and a common layout (`components/Layout.js`):

- `pages/index.js` — the assistant: question box, provider selector, retrieval size, sample questions, local question history, answers with citations, confidence, retrieved chunks, and knowledge-graph insights.
- `pages/graph.js` + `components/ForceGraph.js` — interactive force-directed knowledge-graph explorer (canvas, dependency-free physics) with type filters, search, node selection, and neighbor navigation.
- `pages/library.js` — read-only legal-corpus browser with text search, topic and source filters, and pagination.
- `pages/status.js` — live health of the API, Weaviate, LLM providers, and the knowledge graph.
- `pages/about.js` — project scope, architecture, and limits.
- `lib/api.js` — small fetch helpers around `NEXT_PUBLIC_API_URL`.

### `web/package.json`

Defines the web dependencies and scripts:

- `next`
- `react`
- `react-dom`
- `npm run dev`
- `npm run build`
- `npm run start`

### `seed_weaviate.sh`

Small helper script that runs:

```bash
python -m api.seed_weaviate
```

On Windows, teammates can run the Python module directly inside the API container instead:

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

### `README.md`

Primary teammate-facing setup document. It is Windows-first and includes ports, prerequisites, setup commands, troubleshooting, evaluation, and GitHub safety notes.

## 7. Runtime Flow

### User Question

The user enters an Arabic labor-law information question in the web UI or sends it directly to:

```text
POST /rag/answer
```

Example:

```json
{
  "question": "هل يجوز إنهاء عقد العمل بدون إشعار؟",
  "k": 5
}
```

### Question Embedding

The API formats the question for the E5 embedding model:

```text
query: {question}
```

It embeds the question using `intfloat/multilingual-e5-small`.

### Weaviate Retrieval

The API queries the `LegalChunk` class in Weaviate using near-vector search. It asks for legal chunk fields plus vector distance metadata.

### Reranking

The API combines:

- Vector score from Weaviate distance.
- Small lexical overlap bonus from normalized Arabic question terms and chunk text/topic/reference.
- A knowledge-graph boost (`KG_BOOST_PER_CONCEPT`, default `0.04`) for every legal concept the chunk shares with the question.

This stays simple and avoids cross-encoders or additional ML models, while letting graph-relevant chunks win ties against merely vector-similar ones.

### Prompt Building

The API builds a grounded Arabic prompt from the top retrieved chunks. The prompt tells the model:

- Use only retrieved legal texts.
- Do not invent references.
- Do not provide final legal advice.
- Say clearly when context is insufficient.
- Do not output `<think>`.

### Generation

The API calls the active provider (or the per-request override):

- `ollama` — `http://host.docker.internal:11434/api/chat` with `qwen3:4b` by default.
- `openai` — `{OPENAI_BASE_URL}/chat/completions` with `OPENAI_MODEL`.
- `anthropic` — the Claude API through the official SDK with `ANTHROPIC_MODEL` (default `claude-opus-4-8`).

### Response With Backend Citations

The API returns:

- `answer`
- `citations` (with article numbers)
- `confidence`
- `retrieved_chunks` (with matched KG concepts)
- `provider`, `model`, `latency_ms`
- `kg` (question concepts, related concepts, related articles, boosted-chunk count)
- `disclaimer`

Citations are created from retrieved chunks, not from the LLM output.

## 8. Models

### Embedding Model

```text
intfloat/multilingual-e5-small
```

This model supports multilingual retrieval and works well with E5 prefixes:

- `query:` for user questions.
- `passage:` for legal chunks.

### Generators

| Provider | Default model | Notes |
| --- | --- | --- |
| `ollama` (default) | `qwen3:4b` | Fully local. Can be slow on typical laptops (2-4 minutes per answer). |
| `openai` | `OPENAI_MODEL` from `.env` | Works with any OpenAI-compatible endpoint (OpenAI, Groq, OpenRouter, DeepSeek, local vLLM). |
| `anthropic` | `claude-opus-4-8` | Uses the official `anthropic` SDK with adaptive thinking. |

The provider is chosen by `LLM_PROVIDER` and can be overridden per request (`provider`/`model` fields) or from the UI selector.

## 9. Data

### Legal Chunks

Current seed data:

```text
api/seed_chunks.json
```

Count:

```text
73 legal chunks
```

### Weaviate Class

Class name:

```text
LegalChunk
```

Schema fields:

- `chunk_id`
- `source_name`
- `reference`
- `topic`
- `text`
- `source_page`
- `source_type`
- `jurisdiction`

Vectors are provided externally by the API seeding script. Weaviate does not vectorize text by itself.

### Citation Fields

Each citation returned by the API includes:

- `chunk_id`
- `source_name`
- `reference`
- `topic`
- `source_page`

## 10. How To Run On Windows

Recommended path for teammates: Windows PowerShell + Docker Desktop + Ollama Windows app.

Do not run this from WSL unless you know your Docker/Ollama networking.

Before running commands, make sure Docker Desktop is installed and running, Ollama for Windows is installed, and `qwen3:4b` is pulled locally. `jq` is optional on Windows; the documented commands do not require it.

```powershell
git clone <repo-url>
cd <repo-folder>
Copy-Item .env.example .env

ollama pull qwen3:4b
ollama list
curl.exe http://localhost:11434/api/tags

docker compose -p lawz-ai-jo up -d --build
docker compose -p lawz-ai-jo ps

curl.exe http://localhost:8001/healthz
curl.exe http://localhost:8001/readyz

docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate

curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

Open:

```text
http://localhost:3001
```

## 11. How To Run On Linux

Ollama still runs on the host. Start Ollama and pull the model:

```bash
ollama pull qwen3:4b
curl http://localhost:11434/api/tags
```

Create `.env`:

```bash
cp .env.example .env
```

Start the stack:

```bash
docker compose -p lawz-ai-jo up -d --build
docker compose -p lawz-ai-jo ps
```

Check readiness:

```bash
curl http://localhost:8001/healthz
curl http://localhost:8001/readyz
```

Seed:

```bash
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

Ask:

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"هل يجوز إنهاء عقد العمل بدون إشعار؟","k":5}'
```

## 12. Troubleshooting History

### Docker Ports Already Taken

Issue: Docker ports `8001`, `8081`, and `3001` were already taken by old `docker-proxy` processes from another Docker context.

Fix: Checked Docker contexts and stopped old main-repo containers that were still holding the ports.

Useful commands:

```bash
docker context ls
docker ps
docker compose -p <old-project-name> down
```

### Compose File Had `api` At Root Level

Issue: `docker-compose.yml` once had `api` at the root level and failed with:

```text
additional properties 'api' not allowed
```

Fix: Ensured `api` is nested under the top-level `services:` key.

### `/metrics` Redirects

Issue: `GET /metrics` returned a `307` redirect to `/metrics/`.

Fix: Use:

```bash
curl -L http://localhost:8001/metrics
```

or:

```bash
curl http://localhost:8001/metrics/
```

On Windows PowerShell, use `curl.exe`.

### Local Eval Missing `httpx`

Issue: The local evaluation script failed in `.venv` because `httpx` was missing.

Fix:

```bash
python -m pip install httpx
```

### Slow Generation

Issue: `qwen3:4b` generation was slow, taking around 2-4 minutes per answer.

Fix: Use a longer timeout for evaluation:

```bash
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```

## 13. Known Limitations

- Not legal advice.
- Small legal corpus.
- Small smoke evaluation.
- Slow local generation.
- Confidence score is approximate.
- LLM wording may need legal review.

## 14. Future Work

- Add 50+ hand-labeled evaluation questions.
- Improve confidence scoring.
- Explore faster generation options.
- Add a smaller model option.
- Improve frontend loading and progress feedback.
- Add a dataset card.
- Add optional contract upload later.
- Add optional report export later.
- Explore possible hosted deployment.

## 15. Appendix: Key Commands

### Start

```powershell
docker compose -p lawz-ai-jo up -d --build
```

### Stop

```powershell
docker compose -p lawz-ai-jo down
```

### Stop And Delete Weaviate Volume

```powershell
docker compose -p lawz-ai-jo down -v
```

### Check Services

```powershell
docker compose -p lawz-ai-jo ps
```

### API Health

```powershell
curl.exe http://localhost:8001/healthz
curl.exe http://localhost:8001/readyz
```

### Ollama Health

```powershell
curl.exe http://localhost:11434/api/tags
```

### Seed Weaviate

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

### Ask A Question

```powershell
curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

### Metrics

```powershell
curl.exe -L http://localhost:8001/metrics
```

### API Logs

```powershell
docker compose -p lawz-ai-jo logs api --tail=120
```

### Smoke Evaluation

```powershell
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```
