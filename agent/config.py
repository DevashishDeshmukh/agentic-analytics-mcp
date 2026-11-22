"""Load the MCP server registry and feature-flag configs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml

from common.settings import get_settings

# Keep stdio servers quiet so agent output stays readable.
QUIET_ENV = {"FASTMCP_LOG_LEVEL": "CRITICAL",
             "TQDM_DISABLE": "1"}


@dataclass(frozen=True)
class Features:
    name: str
    rag: bool = True
    k: int = 6


def load_features(name: str | None = None) -> Features:
    path = get_settings().root / "config" / "features.yaml"
    doc = yaml.safe_load(path.read_text())
    name = name or doc["default"]
    if name not in doc["configs"]:
        raise SystemExit(f"Unknown config '{name}'. Options: {', '.join(doc['configs'])}")
    return Features(name=name, **(doc["configs"][name] or {}))


def load_mcp_config() -> dict[str, Any]:
    """Return a fastmcp multi-server config built from config/servers.yaml."""
    root = get_settings().root
    doc = yaml.safe_load((root / "config" / "servers.yaml").read_text())
    servers = {}
    for name, spec in doc["servers"].items():
        if "url" in spec:
            servers[name] = {"url": spec["url"]}
        else:
            servers[name] = {"command": spec["command"], "args": spec.get("args", []),
                             "cwd": str(root), "env": {**QUIET_ENV, **spec.get("env", {})}}
    return {"mcpServers": servers}
