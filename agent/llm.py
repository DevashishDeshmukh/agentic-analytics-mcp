"""LLM wrapper over the OpenAI chat-completions API.

Works with OpenAI, Azure OpenAI, Google Gemini (OpenAI-compatible endpoint) and
Ollama. Pick with LLM_PROVIDER in .env. Handles JSON output, rate limits and
usage tracking.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache

from openai import AzureOpenAI, OpenAI

from common.settings import get_settings

# Paid list prices, USD per 1M tokens (input, output). Approximate: check the
# provider's pricing page and override with LLM_PRICE_IN / LLM_PRICE_OUT.
# Reported cost = what the run WOULD cost on a paid plan, even on a free tier.
LIST_PRICES = {
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-2.5-pro": (1.25, 10.00),
}
MAX_RETRIES = 8


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0
    by_step: dict[str, dict[str, int]] = field(default_factory=dict)

    def add(self, step: str, inp: int, out: int) -> None:
        self.input_tokens += inp
        self.output_tokens += out
        self.calls += 1
        s = self.by_step.setdefault(step, {"input": 0, "output": 0})
        s["input"] += inp
        s["output"] += out

    def cost_usd(self) -> float | None:
        s = get_settings()
        env_in, env_out = os.environ.get("LLM_PRICE_IN"), os.environ.get("LLM_PRICE_OUT")
        if env_in and env_out:
            p_in, p_out = float(env_in), float(env_out)
        elif s.llm_provider == "ollama":
            p_in, p_out = 0.0, 0.0
        elif s.llm_model in LIST_PRICES:
            p_in, p_out = LIST_PRICES[s.llm_model]
        else:
            return None
        return round((self.input_tokens * p_in + self.output_tokens * p_out) / 1e6, 6)


@lru_cache
def _client() -> OpenAI:
    s = get_settings()
    if s.llm_provider == "azure":
        return AzureOpenAI(
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_key=s.llm_api_key,
            api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            max_retries=MAX_RETRIES,
        )
    if not s.llm_api_key:
        raise SystemExit(f"No API key for LLM_PROVIDER={s.llm_provider}. See .env.example.")
    return OpenAI(api_key=s.llm_api_key, base_url=s.llm_base_url, max_retries=MAX_RETRIES)


class _Throttle:
    """Space calls to stay under LLM_RPM (free tiers enforce per-minute limits)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next = 0.0

    def wait(self) -> None:
        rpm = get_settings().llm_rpm
        if not rpm:
            return
        with self._lock:
            now = time.monotonic()
            if now < self._next:
                time.sleep(self._next - now)
            self._next = max(now, self._next) + 60.0 / rpm


_throttle = _Throttle()


def _parse_json(content: str) -> dict:
    text = content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
        text = text.rsplit("```", 1)[0]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"error": "model returned invalid JSON", "raw": content}


def chat_json(system: str, user: str, usage: Usage, step: str) -> dict:
    """Call the model and parse a JSON object response."""
    s = get_settings()
    kwargs = {}
    if s.llm_temperature is not None:
        kwargs["temperature"] = s.llm_temperature
    _throttle.wait()
    resp = _client().chat.completions.create(
        model=s.llm_model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        **kwargs,
    )
    if resp.usage:
        usage.add(step, resp.usage.prompt_tokens, resp.usage.completion_tokens)
    return _parse_json(resp.choices[0].message.content or "{}")
