"""Copilot backend settings. Every knob is env-driven and validated at startup;
secrets carry no default so a missing one fails fast instead of silently running
with a demo value (01-architecture.md §9; 00-decisions.md A-06, D-06b).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # --- Copilot API -----------------------------------------------------------------
    copilot_api_host: str = "0.0.0.0"
    copilot_api_port: int = 8080
    copilot_api_key: str  # required (A-06) -- enforced on every route except /health
    llm_max_calls_per_conversation: int = Field(default=8, ge=1)

    # --- LLM provider (Anthropic is always the default -- D-06b) ---------------------
    llm_provider: Literal["anthropic", "openai", "stub"] = "anthropic"
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_anthropic_planner: str = "claude-haiku-4-5"
    llm_anthropic_synthesizer: str = "claude-sonnet-5"
    llm_openai_cheap: str = "gpt-5-mini"
    llm_openai_frontier: str = "gpt-5"
    langchain_tracing_v2: bool = False

    # --- MCP -----------------------------------------------------------------------
    mcp_transport: Literal["stdio", "http"] = "http"
    mcp_alarm_url: str = "http://alarm-mcp:9000/mcp"

    # --- RAG / retrieval -------------------------------------------------------------
    document_path: str = "./rag/documents"
    vector_store_url: str = "http://qdrant:6333"
    qdrant_collection_alias: str = "policy_chunks"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    rag_rerank_enabled: bool = True
    rag_min_score: float = Field(default=0.35, ge=0, le=1)
    rag_min_citations: int = Field(default=1, ge=0)

    # --- Postgres: copilot database (copilot_rw -- no grant on alarmdb, see D-05) ----
    copilot_db_host: str = "postgres"
    copilot_db_port: int = 5432
    copilot_db_name: str = "copilot"
    copilot_db_user: str = "copilot_rw"
    copilot_db_password: str  # required -- secret, no default

    # --- Observability -----------------------------------------------------------------
    log_level: str = "INFO"
