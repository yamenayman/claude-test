from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    weaviate_url: str = "http://weaviate:8080"
    weaviate_class: str = "LegalChunk"
    embedding_model: str = "intfloat/multilingual-e5-small"
    top_k: int = 5
    rag_prompt_top_n: int = 3
    chunk_text_limit: int = 900

    # Retrieval backend: "auto" (Weaviate when reachable, else local),
    # "weaviate" (force dense vector search), or "local" (offline BM25 + KG).
    retrieval_backend: str = "auto"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "qwen3:4b"
    ollama_timeout_seconds: float = 120

    # LLM provider selection: "ollama" (local, default), "openai" (any
    # OpenAI-compatible API), or "anthropic" (Claude API).
    llm_provider: str = "ollama"
    llm_timeout_seconds: float = 120
    llm_max_tokens: int = 4096

    openai_base_url: str = "https://api.openai.com/v1"
    openai_api_key: str = ""
    openai_model: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-4-8"
    # Set to "adaptive" to enable adaptive thinking (only on thinking-capable
    # models such as Opus/Sonnet 4.6+). Leave empty for Haiku and others.
    anthropic_thinking: str = ""

    # Knowledge-graph score boost applied per shared concept during rerank.
    kg_boost_per_concept: float = 0.04

    api_url: str = "http://api:8000"
    next_public_api_url: str = "http://localhost:8001"
    web_origin: str = "http://localhost:3001"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
