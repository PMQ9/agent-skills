#!/usr/bin/env python3
"""Tiny stdlib-only wrapper around the local Ollama HTTP API.

Subcommands:
    chat    — text chat, optional images, optional JSON mode
    embed   — produce an embedding vector for a single string
    health  — verify Ollama is reachable and a given model is pulled

Exit codes:
    0  success
    1  Ollama unreachable
    2  model not pulled / not found
    3  invalid args / IO error
    4  model returned malformed output (e.g., --json was requested but
       the response wasn't valid JSON after one retry)

Design notes:
- stdlib only (urllib) — no extra installs.
- Defaults to http://localhost:11434; override with OLLAMA_HOST env var.
- For chat, the prompt can come from --prompt or stdin (read if stdin is
  not a tty). Images are passed as file paths and base64-encoded inline.
- For long generations, --stream prints chunks as they arrive; otherwise
  the full response is collected and printed once.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "600"))  # seconds


def _post(path: str, payload: dict, stream: bool = False):
    url = f"{HOST}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        return urllib.request.urlopen(req, timeout=TIMEOUT)
    except urllib.error.URLError as e:
        sys.stderr.write(
            f"ollama_call: cannot reach Ollama at {HOST} ({e}). "
            f"Is the daemon running? Try `ollama serve` or open the Ollama app.\n"
        )
        sys.exit(1)


def _get(path: str):
    url = f"{HOST}{path}"
    try:
        return urllib.request.urlopen(url, timeout=TIMEOUT)
    except urllib.error.URLError as e:
        sys.stderr.write(
            f"ollama_call: cannot reach Ollama at {HOST} ({e}).\n"
        )
        sys.exit(1)


def _pulled_models() -> list[str]:
    with _get("/api/tags") as resp:
        body = json.loads(resp.read())
    return [m.get("name", "").split(":")[0] for m in body.get("models", [])] + [
        m.get("name", "") for m in body.get("models", [])
    ]


def cmd_health(args):
    """Exit 0 if reachable and model is pulled; 1 if not reachable; 2 if missing."""
    pulled = _pulled_models()
    if not args.model:
        print(f"ok: ollama reachable at {HOST}; {len(set(pulled))} models pulled")
        return
    base = args.model.split(":")[0]
    if args.model in pulled or base in pulled:
        print(f"ok: {args.model} is available")
        return
    sys.stderr.write(
        f"ollama_call: model '{args.model}' is not pulled. "
        f"Run `ollama pull {args.model}` first.\n"
    )
    sys.exit(2)


def _read_prompt(args) -> str:
    if args.prompt:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    sys.stderr.write("ollama_call: no --prompt given and stdin is empty\n")
    sys.exit(3)


def _encode_images(paths: list[str]) -> list[str]:
    out = []
    for p in paths:
        path = Path(p)
        if not path.is_file():
            sys.stderr.write(f"ollama_call: image not found: {p}\n")
            sys.exit(3)
        out.append(base64.b64encode(path.read_bytes()).decode("ascii"))
    return out


def cmd_chat(args):
    message = {"role": "user", "content": _read_prompt(args)}
    if args.image:
        message["images"] = _encode_images(args.image)

    payload = {
        "model": args.model,
        "messages": [message],
        "stream": bool(args.stream),
    }
    if args.json:
        payload["format"] = "json"
    if args.system:
        payload["messages"].insert(0, {"role": "system", "content": args.system})

    resp = _post("/api/chat", payload, stream=bool(args.stream))

    if args.stream:
        # Server sends one JSON object per line until "done": true
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if not line:
                continue
            chunk = json.loads(line)
            sys.stdout.write(chunk.get("message", {}).get("content", ""))
            sys.stdout.flush()
            if chunk.get("done"):
                break
        sys.stdout.write("\n")
        return

    body = json.loads(resp.read())
    content = body.get("message", {}).get("content", "")
    if args.json:
        # Validate it actually parses; if not, surface the malformed output
        # so the caller can decide to retry.
        try:
            json.loads(content)
        except json.JSONDecodeError:
            sys.stderr.write(
                "ollama_call: --json was set but model output is not valid JSON.\n"
                f"Raw output:\n{content}\n"
            )
            sys.exit(4)
    sys.stdout.write(content)
    if not content.endswith("\n"):
        sys.stdout.write("\n")


def cmd_embed(args):
    text = args.text if args.text else (sys.stdin.read() if not sys.stdin.isatty() else "")
    if not text.strip():
        sys.stderr.write("ollama_call embed: --text or stdin required\n")
        sys.exit(3)
    payload = {"model": args.model, "input": text}
    resp = _post("/api/embed", payload)
    body = json.loads(resp.read())
    # /api/embed returns {"embeddings": [[...]]}; older /api/embeddings returns {"embedding": [...]}
    vec = (body.get("embeddings") or [body.get("embedding")])[0]
    if not vec:
        sys.stderr.write(f"ollama_call: empty embedding response: {body}\n")
        sys.exit(4)
    print(json.dumps(vec))


def build_parser():
    p = argparse.ArgumentParser(prog="ollama_call", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("chat", help="text chat (optional images, JSON mode)")
    c.add_argument("--model", required=True)
    c.add_argument("--prompt", help="prompt text (omit to read from stdin)")
    c.add_argument("--system", help="optional system prompt")
    c.add_argument("--image", action="append", default=[], help="path to image; repeatable")
    c.add_argument("--json", action="store_true", help="force JSON-mode output")
    c.add_argument("--stream", action="store_true", help="stream tokens to stdout")
    c.set_defaults(fn=cmd_chat)

    e = sub.add_parser("embed", help="produce an embedding vector")
    e.add_argument("--model", default="nomic-embed-text-v2-moe")
    e.add_argument("--text", help="text to embed (omit to read from stdin)")
    e.set_defaults(fn=cmd_embed)

    h = sub.add_parser("health", help="check Ollama daemon + model availability")
    h.add_argument("--model", help="optional model tag to verify is pulled")
    h.set_defaults(fn=cmd_health)

    return p


def main():
    args = build_parser().parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
