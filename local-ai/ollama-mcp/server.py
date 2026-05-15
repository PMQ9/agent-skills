#!/usr/bin/env python3
"""Ollama MCP server.

Exposes the local Ollama HTTP API as MCP tools so Claude Code (CLI), Claude
Desktop, and Claude Cowork can call them natively instead of shelling out.

Cowork support is via the Claude Code bridge: when this server is registered
in ~/.claude/mcp_servers.json, Cowork's Linux sandbox tunnels tool calls back
through the bridge to your local Claude Code, which spawns this server as a
stdio process. No public tunnel or custom-connector setup is needed. The
separate Cowork *custom remote MCP connector* flow would require a publicly
reachable URL + org-admin allowlist and is not how this server is intended
to be used — see README's "About Claude Cowork" section.

In Cowork, the `mcp__ollama__*` tools are *deferred* in both the main
session and in spawned subagents — they must call
`ToolSearch(query="select:mcp__ollama__ollama_chat,...")` once before
the first invocation. Claude Code CLI and Claude Desktop don't need this.

Transports:
    stdio (default)        — Claude Code CLI, Claude Desktop, and the Cowork
                             bridge all spawn this process over stdio.
    sse                    — HTTP server for advanced/non-Claude clients or test rigs.
    streamable-http        — Newer HTTP transport; functionally equivalent to sse.

Tools:
    ollama_chat   — text chat with optional images and optional JSON mode
    ollama_embed  — produce an embedding vector for a string
    ollama_health — verify Ollama is reachable and (optionally) a model is pulled
    ollama_list   — list pulled models on the user's machine

Env:
    OLLAMA_HOST      default http://localhost:11434
    OLLAMA_TIMEOUT   seconds, default 600
    MCP_TRANSPORT    stdio | sse | streamable-http  (default: stdio)
    MCP_HOST         bind address for HTTP mode     (default: 0.0.0.0)
    MCP_PORT         port for HTTP mode             (default: 8765)
"""

from __future__ import annotations

import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))

# Bind address / port matter only for sse and streamable-http transports.
# FastMCP takes them at construction time, not on .run().
mcp = FastMCP(
    "ollama",
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8765")),
)


# ---------- internal HTTP helpers ----------

def _post(path: str, payload: dict) -> dict:
    url = f"{HOST}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {HOST} ({e}). "
            f"Is the daemon running? Try `ollama serve` or open the Ollama app."
        ) from e


def _get(path: str) -> dict:
    url = f"{HOST}{path}"
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"Cannot reach Ollama at {HOST} ({e})."
        ) from e


def _encode_images(paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        path = Path(p).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {p}")
        out.append(base64.b64encode(path.read_bytes()).decode("ascii"))
    return out


# ---------- MCP tools ----------

@mcp.tool()
def ollama_chat(
    model: str,
    prompt: str,
    system: str | None = None,
    images: list[str] | None = None,
    json_mode: bool = False,
) -> str:
    """Send a single-turn chat request to a local Ollama model.

    Args:
        model: Ollama model tag (e.g. "qwen3", "qwen3vl", "llama3.2:3b").
        prompt: The user message.
        system: Optional system prompt.
        images: Optional list of local image paths to attach (for vision models).
        json_mode: If True, forces the model to return valid JSON. The caller is
            still responsible for json.loads()ing the result.

    Returns:
        The model's text output.

    Raises:
        RuntimeError if the daemon isn't reachable or the model isn't pulled.
    """
    message: dict = {"role": "user", "content": prompt}
    if images:
        message["images"] = _encode_images(images)

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append(message)

    payload: dict = {"model": model, "messages": messages, "stream": False}
    if json_mode:
        payload["format"] = "json"

    body = _post("/api/chat", payload)
    return body.get("message", {}).get("content", "")


@mcp.tool()
def ollama_embed(text: str, model: str = "nomic-embed-text-v2-moe") -> list[float]:
    """Produce an embedding vector for a single string.

    Args:
        text: The text to embed.
        model: Embedding model tag. Defaults to nomic-embed-text-v2-moe
            (multilingual, MoE, Matryoshka dims). Use "nomic-embed-text" for
            English-only / legacy indexes.

    Returns:
        A list of floats (the embedding vector).
    """
    body = _post("/api/embed", {"model": model, "input": text})
    vec = (body.get("embeddings") or [body.get("embedding")])[0]
    if not vec:
        raise RuntimeError(f"Empty embedding response: {body}")
    return vec


@mcp.tool()
def ollama_health(model: str | None = None) -> dict:
    """Check that Ollama is reachable and optionally that a model is pulled.

    Args:
        model: Optional model tag to verify is available locally.

    Returns:
        {"ok": True, "host": ..., "models_pulled": N, "model_available": bool?}
        Raises RuntimeError if Ollama itself is unreachable.
    """
    body = _get("/api/tags")
    pulled = body.get("models", [])
    names = {m.get("name", "") for m in pulled}
    names.update(n.split(":")[0] for n in list(names))

    out: dict = {"ok": True, "host": HOST, "models_pulled": len(pulled)}
    if model:
        out["model"] = model
        out["model_available"] = model in names or model.split(":")[0] in names
        if not out["model_available"]:
            out["hint"] = f"Run `ollama pull {model}` to install."
    return out


@mcp.tool()
def ollama_list() -> list[dict]:
    """List all models currently pulled on the user's local Ollama.

    Returns:
        A list of {"name", "size", "modified_at"} dicts.
    """
    body = _get("/api/tags")
    return [
        {
            "name": m.get("name"),
            "size": m.get("size"),
            "modified_at": m.get("modified_at"),
        }
        for m in body.get("models", [])
    ]


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
