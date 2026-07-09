# Lawz AI JO Web

Professional Arabic RTL Next.js UI for the Jordanian labor-law assistant.

## Pages

| Path | Page |
| --- | --- |
| `/` | Assistant: ask questions, pick the LLM provider, view cited answers with confidence and knowledge-graph insights, local question history. |
| `/graph` | Interactive knowledge-graph explorer (canvas force layout, no external chart libraries). |
| `/library` | Read-only legal-corpus browser with search, topic, and source filters. |
| `/status` | Live system status: API, Weaviate, LLM providers, knowledge graph. |
| `/about` | Project scope, architecture, and limits. |

Light/dark themes (auto + manual toggle) with a Jordan-inspired palette.

## Local run

```bash
npm install
npm run dev
```

The UI expects the API at `NEXT_PUBLIC_API_URL`, defaulting to `http://localhost:8001`.
