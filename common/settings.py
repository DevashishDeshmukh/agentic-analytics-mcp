"""Central settings loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# Every provider below speaks the OpenAI chat-completions API.
PROVIDERS = {
    "openai": {"base_url": None, "key_env": "OPENAI_API_KEY", "model": "gpt-4.1-mini"},
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "key_env": "GEMINI_API_KEY",
        "model": "gemini-3.5-flash-lite",
    },
    "ollama": {"base_url": "http://localhost:11434/v1", "key_env": None,
               "model": "qwen2.5-coder:7b"},
    "azure": {"base_url": None, "key_env": "AZURE_OPENAI_API_KEY", "model": None},
}


@dataclass(frozen=True)
class Settings:
    admin_dsn: str
    warehouse_dsn: str
    knowledge_dsn: str
    embedding_model: str
    llm_provider: str
    llm_model: str
    llm_base_url: str | None
    llm_api_key: str | None
    llm_temperature: float | None
    llm_rpm: int | None
    root: Path = ROOT


def _env(name: str) -> str | None:
    v = os.environ.get(name, "").strip()
    return v or None


@lru_cache
def get_settings() -> Settings:
    provider = (_env("LLM_PROVIDER") or "openai").lower()
    if provider not in PROVIDERS:
        raise SystemExit(f"LLM_PROVIDER must be one of {', '.join(PROVIDERS)}")
    preset = PROVIDERS[provider]
    legacy = _env("OPENAI_MODEL") if provider in ("openai", "azure") else None
    model = _env("LLM_MODEL") or legacy or preset["model"]
    if not model:
        raise SystemExit(f"Set LLM_MODEL for provider '{provider}'.")
    key = _env(preset["key_env"]) if preset["key_env"] else "ollama"
    temp = _env("LLM_TEMPERATURE") or _env("OPENAI_TEMPERATURE")
    rpm = _env("LLM_RPM")
    return Settings(
        admin_dsn=_env("ADMIN_DSN") or "postgresql://postgres:postgres@localhost:5433/analytics",
        warehouse_dsn=_env("WAREHOUSE_DSN")
        or "postgresql://agent_readonly:agent_readonly_dev@localhost:5433/analytics",
        knowledge_dsn=_env("KNOWLEDGE_DSN")
        or "postgresql://knowledge_reader:knowledge_reader_dev@localhost:5433/analytics",
        embedding_model=_env("EMBEDDING_MODEL") or "BAAI/bge-small-en-v1.5",
        llm_provider=provider,
        llm_model=model,
        llm_base_url=_env("LLM_BASE_URL") or preset["base_url"],
        llm_api_key=key,
        llm_temperature=float(temp) if temp else None,
        llm_rpm=int(rpm) if rpm else None,
    )
