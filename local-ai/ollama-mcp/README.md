# ollama-mcp

A small MCP server that exposes your local Ollama as native tools for Claude
Code and Claude Desktop. Companion to the
[`local-llm-delegation` skill](../../.claude/skills/engineering/ai/local-llm-delegation/).

## Tools

| Tool | Purpose |
|---|---|
| `ollama_chat(model, prompt, system?, images?, json_mode?)` | Single-turn chat with optional vision and JSON mode |
| `ollama_embed(text, model="nomic-embed-text-v2-moe")` | Produce an embedding vector |
| `ollama_health(model?)` | Verify Ollama is up and (optionally) a model is pulled |
| `ollama_list()` | List all locally-pulled models |

## Supported clients

| App | Sandbox? | Transport | Works? |
|---|---|---|---|
| **Claude Code** (CLI) | No | `stdio` | ✅ |
| **Claude Desktop** | No | `stdio` | ✅ |
| **Claude Cowork** | Yes (Linux VM) | `stdio` via Claude Code bridge | ✅ Tools appear in main session and in spawned subagents. See [About Claude Cowork](#about-claude-cowork) for one subagent wrinkle. |

> Throughout this README, `$REPO` means the directory you cloned this into. Replace it with your actual path (e.g. `~/projects/agent-skills/local-ai/ollama-mcp`). Run `pwd` while inside the directory to get the value.

## Install (one-time, per machine)

```bash
cd $REPO/local-ai/ollama-mcp
# Option A — uv (recommended, faster):
brew install uv && uv venv && uv pip install -r requirements.txt
# Option B — plain venv:
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Launcher path is `$REPO/local-ai/ollama-mcp/.venv/bin/python` either way.

Smoke-test:

```bash
ollama serve &              # if not already running (or open the Ollama.app)
.venv/bin/python server.py  # should print nothing and wait on stdin — Ctrl-C
```

## Wire it into each app

### Claude Code (CLI)

Add to `~/.claude/mcp_servers.json` (create the file if missing). Substitute `$REPO` with your actual cloned path:

```json
{
  "mcpServers": {
    "ollama": {
      "command": "$REPO/local-ai/ollama-mcp/.venv/bin/python",
      "args": ["$REPO/local-ai/ollama-mcp/server.py"]
    }
  }
}
```

Restart Claude Code. Tools appear as `mcp__ollama__ollama_chat`, `mcp__ollama__ollama_embed`, etc.

### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add the same block:

```json
{
  "mcpServers": {
    "ollama": {
      "command": "$REPO/local-ai/ollama-mcp/.venv/bin/python",
      "args": ["$REPO/local-ai/ollama-mcp/server.py"]
    }
  }
}
```

**Fully quit** Claude Desktop (⌘Q) and reopen. The tools appear under Customize → Connectors → "ollama" (labeled `LOCAL DEV`, in the "Desktop" group).

> **"Needs approval" can't be changed to "Always allow"?** That's a Team/Enterprise org policy — your Anthropic org owner disabled it. Tooltip in the UI: *"'Always allow' is disabled by your admin. Ask them to turn it on in Organization settings → Cowork."* Email your org owner if you want to flip it.

## About Claude Cowork

**Cowork can use this server too** — verified end-to-end. The mechanism is the Claude Code bridge, not a Cowork custom connector. There are two distinct paths and only one of them needs the cloud-tunnel song-and-dance:

### Path that works: stdio MCP via the Claude Code bridge ✅

When you register this server in `~/.claude/mcp_servers.json` (the [Claude Code CLI](#claude-code-cli) instructions above), Claude Code spawns it locally as a `stdio` process on your Mac. Cowork's Linux sandbox **shares the same MCP surface as your local Claude Code session** by tunneling tool calls back through the bridge. Wire path:

```
Cowork Linux sandbox
  → mcp__ollama__ollama_chat tool call
  → bridge_repl_v2 channel (Anthropic-managed, encrypted)
  → your local Claude Code on the Mac
  → spawned stdio server (this repo's server.py)
  → http://localhost:11434  (Ollama on your Mac)
  → reply back up the same chain
```

You don't need a public tunnel, auth shim, or org allowlist. If `mcp__ollama__*` works in your local Claude Code, it works in Cowork.

**One Cowork-specific wrinkle: Ollama tools are *deferred* in both the main session and in subagents.** They show up by name in a system reminder ("The following deferred tools are now available via ToolSearch") but their JSON schemas aren't loaded yet — calling them directly will fail with InputValidationError. Load the schemas once via ToolSearch before the first call:

```
ToolSearch(query="select:mcp__ollama__ollama_chat,mcp__ollama__ollama_health,mcp__ollama__ollama_list,mcp__ollama__ollama_embed", max_results=4)
```

After that the tools are callable as normal for the rest of the session. **If you delegate Ollama work to a subagent, repeat this in the subagent's prompt** — the subagent starts with its own fresh tool list and won't have inherited yours. Example: "Use ToolSearch to load the `mcp__ollama__*` tools, then call `ollama_chat` to ...". In Claude Code CLI and Claude Desktop the tools appear directly with no ToolSearch step needed.

### Path that doesn't work without extra plumbing: Cowork *custom connector* (remote MCP)

If you instead try to add this server via Cowork's UI as a custom remote MCP connector, Anthropic's docs apply:

> "When you add a custom connector, Claude connects to your remote MCP server from **Anthropic's cloud infrastructure**, rather than from your local device, and your MCP server must be reachable over the public internet from Anthropic's IP ranges."
> — [Get started with custom connectors using remote MCP](https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp)

For *that* path you'd need:

1. **Publicly reachable URL** from Anthropic's IP ranges. Tailscale `*.ts.net` doesn't qualify — tailnet-only. Use Tailscale Funnel, Cloudflare Tunnel, ngrok with a stable hostname, or port-forward a real domain.
2. **Authentication** in front. Ollama ships with none; exposing it raw lets anyone with the URL run inference on your hardware.
3. **Org-admin allowlist** under Organization settings → Connectors (Team/Enterprise plans).

There's almost never a reason to take this route when the bridge path above already works. The custom-connector path is documented here only to flag the distinction — if a future Anthropic doc says "Cowork can't call your local server," they're usually talking about the custom-connector path, not stdio bridging.

## Advanced: HTTP/SSE mode

The server can also run as a standalone HTTP service for any client that speaks remote MCP — useful for testing, sharing across machines on a private network, or as the starting point for a public tunneled deployment.

```bash
MCP_TRANSPORT=sse MCP_PORT=8765 .venv/bin/python server.py
# Then curl http://localhost:8765/sse — expect HTTP 200 (SSE stream)
```

### launchd plist (auto-start)

A template plist lives at [`launchd/com.local.ollama-mcp.plist.template`](launchd/com.local.ollama-mcp.plist.template) with `__INSTALL_DIR__` placeholders. Render and install:

```bash
cd $REPO/local-ai/ollama-mcp
sed "s|__INSTALL_DIR__|$(pwd)|g" launchd/com.local.ollama-mcp.plist.template \
  > ~/Library/LaunchAgents/com.local.ollama-mcp.plist
launchctl load ~/Library/LaunchAgents/com.local.ollama-mcp.plist
launchctl list | grep ollama-mcp   # PID + exit code 0 = healthy
```

Logs: `/tmp/ollama-mcp.log` and `/tmp/ollama-mcp.err`.

Stop / uninstall:

```bash
launchctl unload ~/Library/LaunchAgents/com.local.ollama-mcp.plist
rm ~/Library/LaunchAgents/com.local.ollama-mcp.plist
```

> By default the plist binds to `0.0.0.0:8765` (all interfaces on this Mac). Set `MCP_HOST` to `127.0.0.1` in the plist's `EnvironmentVariables` to lock to localhost only. Don't expose `0.0.0.0` on a network you don't trust — Ollama has no auth.

## Optional environment variables

```json
{
  "mcpServers": {
    "ollama": {
      "command": "...",
      "args": ["..."],
      "env": {
        "OLLAMA_HOST": "http://localhost:11434",
        "OLLAMA_TIMEOUT": "600"
      }
    }
  }
}
```

For the SSE/launchd path, also:

| Var | Default | Notes |
|---|---|---|
| `MCP_TRANSPORT` | `stdio` | Set to `sse` or `streamable-http` for HTTP mode. |
| `MCP_HOST` | `0.0.0.0` | Bind interface. Use `127.0.0.1` to lock to localhost only. |
| `MCP_PORT` | `8765` | Pick a different port if 8765 is taken. |

## Troubleshooting

- **"Cannot reach Ollama at http://localhost:11434"** — Ollama daemon isn't running. `ollama serve`, or open the Ollama app.
- **Tools don't appear in Claude** — restart the host app. MCP servers are spawned at app start.
- **`ModuleNotFoundError: No module named 'mcp'`** — your launcher python doesn't have the `mcp` package. Use the `.venv/bin/python` from the venv you created in [Install](#install-one-time-per-machine), not the system `python3`.
- **launchd exit code 1 instead of 0** — check `/tmp/ollama-mcp.err`. Most common cause is the plist's `__INSTALL_DIR__` not being substituted (verify by `cat ~/Library/LaunchAgents/com.local.ollama-mcp.plist`).
- **Tailscale auth dialog hangs** (only relevant for Advanced/HTTP setups) — corporate VPNs (Vanderbilt AnyConnect, etc.) can block the GUI's browser handoff. Workaround: quit the GUI dialog, run `tailscale up` from the terminal, paste the printed URL into a browser manually.
