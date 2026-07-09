# Lawz AI JO

Lawz AI JO is an Arabic Retrieval-Augmented Generation (RAG) assistant for Jordanian labor-law information, enhanced with a **legal knowledge graph** and **pluggable LLM providers**. It is an informational legal explainer, not a lawyer and not legal advice.

## What It Does

- Takes Arabic legal-information questions from the web UI or API.
- Detects Jordanian labor-law concepts in the question using a curated Arabic lexicon.
- Retrieves relevant Jordanian labor-law chunks from Weaviate and boosts chunks that share legal concepts with the question (graph-augmented rerank).
- Generates the answer with the provider of your choice:
  - **Ollama** (local, default — no data leaves your machine),
  - any **OpenAI-compatible API** (OpenAI, Groq, OpenRouter, DeepSeek, local vLLM, ...),
  - the **Anthropic Claude API**.
- Returns an Arabic answer, backend-generated citations (with article numbers), retrieved chunk previews, confidence, knowledge-graph insights, and a legal disclaimer.
- Serves a professional Arabic RTL web UI: assistant, interactive knowledge-graph explorer, legal-corpus library, live system status, and an about page.

## What It Does Not Do

- No PDF upload.
- No DOCX parsing.
- No contract review.
- No risk scoring.
- No modification of the legal source texts — the law chunks are read-only and the knowledge graph is derived from them automatically.
- Not a broad legal chatbot.

## Architecture

```text
User -> Web UI (Next.js)
     -> FastAPI
        -> concept detection (Arabic lexicon)      ─┐
        -> Weaviate vector retrieval                ├─ knowledge graph
        -> KG-boosted rerank                       ─┘
        -> LLM provider (Ollama | OpenAI-compatible | Anthropic)
     <- answer + citations + KG insights
```

The knowledge graph is built deterministically at startup from the seeded legal chunks (sources, articles, topics, concepts, and their relations) — it always stays in sync with the corpus and never requires a separate database.

Ollama does not run inside Docker. It must run on your host machine. The API container reaches it with:

```text
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

API providers (OpenAI-compatible / Anthropic) are optional: configure the corresponding key in `.env` and either set `LLM_PROVIDER` or pick the provider per request from the UI.

## Services And Ports

| Service | URL |
| --- | --- |
| Web UI | http://localhost:3001 |
| API | http://localhost:8001 |
| Weaviate | http://localhost:8081 |
| Ollama | http://localhost:11434 |

## Web UI Pages

| Page | Path | Description |
| --- | --- | --- |
| المساعد | `/` | Ask questions, pick the LLM provider, view answers with citations, confidence, and KG insights. |
| شبكة المعرفة | `/graph` | Interactive force-directed knowledge graph (concepts, articles, topics, sources) with search, filters, and node details. |
| المكتبة القانونية | `/library` | Browse and search the read-only legal corpus with topic and source filters. |
| حالة النظام | `/status` | Live health of the API, Weaviate, LLM providers, and the knowledge graph. |
| حول المشروع | `/about` | Project scope, architecture, and limits. |

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/healthz` | Liveness. |
| GET | `/readyz` | Readiness of Weaviate and the active LLM provider. |
| POST | `/rag/answer` | Answer a question. Body: `{"question", "k", "provider"?, "model"?}`. |
| GET | `/llm/providers` | Configured/available LLM providers and the active one. |
| GET | `/kg/overview` | Knowledge-graph node/edge counts by type. |
| GET | `/kg/graph?types=&limit=` | Subgraph for visualization (default: concept, article, topic, source). |
| GET | `/kg/node/{id}` | One node with its neighbors grouped by type. |
| GET | `/kg/search?q=` | Search graph nodes by label. |
| GET | `/kg/concepts` | The legal-concept lexicon with per-concept chunk counts. |
| GET | `/corpus/chunks?q=&topic=&source_type=&limit=&offset=` | Browse the read-only legal corpus. |
| GET | `/corpus/topics` | Topics with chunk counts. |
| GET | `/metrics/` | Prometheus metrics. |

Example — ask with a specific provider:

```bash
curl -X POST http://localhost:8001/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question":"هل يجوز إنهاء عقد العمل بدون إشعار؟","k":5,"provider":"anthropic"}'
```

## Windows Prerequisites

- Windows 10 or Windows 11.
- Docker Desktop installed and running.
- Docker Desktop using Linux containers / WSL2 backend.
- Ollama for Windows installed (only needed for the local provider).
- Git installed.
- `qwen3:4b` pulled in Ollama (only needed for the local provider).

## Windows Setup With PowerShell

Clone the repo:

```powershell
git clone <repo-url>
cd <repo-folder>
```

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Install the local Ollama model (skip if you will use an API provider):

```powershell
ollama pull qwen3:4b
ollama list
curl.exe http://localhost:11434/api/tags
```

Start the Docker stack:

```powershell
docker compose -p lawz-ai-jo up -d --build
docker compose -p lawz-ai-jo ps
```

Check the API:

```powershell
curl.exe http://localhost:8001/healthz
curl.exe http://localhost:8001/readyz
```

Seed Weaviate:

```powershell
docker compose -p lawz-ai-jo exec api python -m api.seed_weaviate
```

Ask a test question:

```powershell
curl.exe -X POST http://localhost:8001/rag/answer -H "Content-Type: application/json" -d "{\"question\":\"هل يجوز إنهاء عقد العمل بدون إشعار؟\",\"k\":5}"
```

Open the app:

```text
http://localhost:3001
```

`qwen3:4b` can be slow on local machines. Some answers may take 2-4 minutes. API providers (OpenAI-compatible or Anthropic) answer in seconds.

## Environment File

Start from:

```powershell
Copy-Item .env.example .env
```

Key values (see `.env.example` for the full list):

```env
WEAVIATE_URL=http://weaviate:8080
WEAVIATE_CLASS=LegalChunk
EMBEDDING_MODEL=intfloat/multilingual-e5-small
TOP_K=5
RAG_PROMPT_TOP_N=3
CHUNK_TEXT_LIMIT=900
KG_BOOST_PER_CONCEPT=0.04

# ollama | openai | anthropic
LLM_PROVIDER=ollama
LLM_MAX_TOKENS=4096

OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:4b

OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=
OPENAI_MODEL=

ANTHROPIC_API_KEY=
ANTHROPIC_MODEL=claude-opus-4-8

NEXT_PUBLIC_API_URL=http://localhost:8001
WEB_ORIGIN=http://localhost:3001
```

Do not commit `.env`.

## Using An API Provider Instead Of Ollama

1. Put your key in `.env`:
   - Anthropic: set `ANTHROPIC_API_KEY` (and optionally `ANTHROPIC_MODEL`).
   - OpenAI-compatible: set `OPENAI_API_KEY`, `OPENAI_MODEL`, and (for non-OpenAI gateways) `OPENAI_BASE_URL`.
2. Either set `LLM_PROVIDER=anthropic` (or `openai`) as the default, or leave `ollama` as default and switch per question from the UI's provider selector.
3. Restart the stack: `docker compose -p lawz-ai-jo up -d --build`.

`/readyz` requires a reachable Ollama only when the active provider is `ollama`; for API providers it checks that the credentials are configured.

## Knowledge Graph

The graph is derived automatically from `api/seed_chunks.json` (never modified):

- **Nodes**: sources (2), law articles (المادة N), topics, legal concepts from a curated Arabic lexicon (~30 concepts such as الفصل التعسفي، الأجر، الإجازة السنوية), and text chunks.
- **Edges**: chunk→source/topic/article/concept plus projected relations (concept↔concept co-occurrence, article↔concept coverage, topic↔concept).
- **Usage**: question concepts boost matching chunks during rerank (`KG_BOOST_PER_CONCEPT`), answers include KG insights (question concepts, related articles, related concepts), and the `/graph` page renders the network interactively.

## If `/readyz` Says Ollama Is Not Ready

1. Check Ollama is reachable from Windows:

   ```powershell
   curl.exe http://localhost:11434/api/tags
   ```

2. Open the Ollama app from the Start Menu.

3. Check and pull the model:

   ```powershell
   ollama list
   ollama pull qwen3:4b
   ```

4. Restart Docker Desktop.

5. Restart the stack:

   ```powershell
   docker compose -p lawz-ai-jo down
   docker compose -p lawz-ai-jo up -d --build
   ```

6. Optional advanced local-development step: if the API container still cannot reach Ollama on Windows, create a user environment variable:

   ```text
   OLLAMA_HOST=0.0.0.0:11434
   ```

   Then quit Ollama from the taskbar and start it again from the Start Menu. Use this only for trusted local development.

7. Or simply switch to an API provider (see above) — the stack works without Ollama in that case.

## Common Issues

- Port already in use: stop the other service using ports `3001`, `8001`, `8081`, or `11434`.
- Docker Desktop not running: start Docker Desktop and wait until it is ready.
- Ollama model missing: run `ollama pull qwen3:4b`.
- First API call is slow: the embedding model and generator may warm up.
- Smoke evaluation takes time: `qwen3:4b` may take 2-4 minutes per question.
- `/metrics` redirects to `/metrics/`: use `curl.exe -L http://localhost:8001/metrics` or open `http://localhost:8001/metrics/`.
- `jq` may not be installed on Windows. It is optional.

## Stop Or Reset

Stop containers:

```powershell
docker compose -p lawz-ai-jo down
```

Delete containers and the Weaviate volume:

```powershell
docker compose -p lawz-ai-jo down -v
```

## Tests

Backend tests cover middlewares, metrics, the smoke evaluator, the knowledge graph, providers, rerank boosting, and the new endpoints:

```powershell
python -m pytest tests/ -q
```

## Evaluation

Run the smoke evaluation after the stack is running and Weaviate is seeded:

```powershell
python eval_rag_smoke.py --api-url http://localhost:8001 --timeout 300 --output outputs/rag_smoke_results.json
```

If Python cannot import `httpx` on Windows, install it locally:

```powershell
python -m pip install httpx
```

The evaluation fixture is `data/rag_smoke.json`. The generated report is written under `outputs/`, which should not be committed.

## GitHub Safety

Do not commit local or generated files such as:

- `.env`
- `.venv/`
- `node_modules/`
- `.next/`
- `outputs/`
- `__pycache__/`
- `.pytest_cache/`

## More Documentation

- [Windows Quickstart](docs/WINDOWS_QUICKSTART.md)
- [Project Guide](docs/PROJECT_GUIDE.md)

## License

MIT
