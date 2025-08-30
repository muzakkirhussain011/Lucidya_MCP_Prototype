# app/config.py
from __future__ import annotations
import os
from dataclasses import dataclass

def _as_bool(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")

@dataclass
class Settings:
    # Ollama / models
    ollama_base: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
    ollama_embed: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    ollama_think: bool = _as_bool(os.getenv("OLLAMA_THINK"), False)

    # Web search toggle
    online_search: bool = _as_bool(os.getenv("ONLINE_SEARCH"), True)

    # Hard requirements at startup
    require_llm: bool = _as_bool(os.getenv("REQUIRE_LLM"), True)
    require_embeddings: bool = _as_bool(os.getenv("REQUIRE_EMBEDDINGS"), True)

    # Outreach compliance
    min_days_between_touches: int = int(os.getenv("MIN_DAYS_BETWEEN_TOUCHES", "7"))

    # ---- pgvector / Postgres (optional) ----
    # Example DSN: postgresql://user:pass@127.0.0.1:5432/mydb
    pg_dsn: str | None = os.getenv("PG_DSN") or None
    pg_schema: str = os.getenv("PG_SCHEMA", "public")
    pg_table: str = os.getenv("PG_TABLE", "embeddings")
    # cosine, l2, or ip (we use cosine by default)
    pg_distance: str = os.getenv("PG_DISTANCE", "cosine")

_settings: Settings | None = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
