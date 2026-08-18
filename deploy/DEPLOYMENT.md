# Memory-Facade deployment & security posture

Two deployment modes:

- **Mode A — local standalone (LIVE now):** memory-facade runs as a launchd
  LaunchAgent on the Mac, exposing streamable-http on `127.0.0.1:8500/mcp`.
  Hermes connects via `hermes mcp add memory-facade --url http://127.0.0.1:8500/mcp/`
  and gets all 6 curated tools. No Orange Pi, no production change.
- **Mode B — Orange Pi LiteLLM runtime (prepared, NOT deployed):** facade runs
  as a stdio server inside the `msm-ai-gateway` LiteLLM MCP runtime, exported as
  `/memory-facade/mcp`. Requires push of the repo + `production-up.sh` + user
  approval (see `litellm-mcp-entry.md`).

## Transport

Memory-facade is an **MCP server** (fastmcp) that supports both:
- **stdio** (`python -m mf.server`) — used by Mode B / process-managed clients.
- **streamable-http / sse** (`python -m mf.server --transport streamable-http
  --host 127.0.0.1 --port 8500`) — used by Mode A standalone deployment.

## Mode A — local launchd service (live)

LaunchAgent `~/Library/LaunchAgents/com.msmsoft.memory-facade.plist` runs the
facade with `KeepAlive` on `127.0.0.1:8500`, `PYTHONPATH` cleared (the Hermes env
otherwise shadows pydantic), `HINDSIGHT_API_URL=https://memory.msmsoft.net`, logs
to `~/.hermes/logs/memory-facade*.log`.

```sh
launchctl load ~/Library/LaunchAgents/com.msmsoft.memory-facade.plist   # start
launchctl unload ~/Library/LaunchAgents/com.msmsoft.memory-facade.plist # stop
```

Hermes wiring (done): `hermes mcp add memory-facade --url "http://127.0.0.1:8500/mcp/"`.
Verified via `hermes mcp list` (enabled) and an end-to-end
streamable-http `memory_recall` call. **New Hermes session required to expose the
`mcp_memory_facade_*` tools** (no hot-reload).

## Mode B — Orange Pi LiteLLM runtime (prepared, not deployed)

Mirrors the existing `lightrag` entry exactly (stdio + `allow_all_keys` + env
injection). Example:

```yaml
mcp_servers:
  memory-facade:
    transport: stdio
    command: uv
    args:
      - run
      - --project
      - /opt/memory-facade
      - python
      - -m
      - mf.server
    env:
      HINDSIGHT_API_URL: os.environ/HINDSIGHT_API_URL
      HINDSIGHT_API_KEY: os.environ/HINDSIGHT_API_KEY
    allow_all_keys: true
```

Routed by the gateway as `/memory-facade/mcp` on `mcp.msmsoft.net`, with the
`MCP_INTERNAL_KEY` trust bridge and HAProxy source ACL — same as `/context7/mcp`
and `/lightrag/mcp`. See `msm-ai-gateway` `AGENTS.md` (MCP changes) and
`gateway/app.py` (`_is_mcp_transport_path`).

## Security posture (non-negotiable)

1. **No public exposure.** Bind only to the trusted network / Tailscale / LAN.
   The gateway's HAProxy source ACL already limits `memory.msmsoft.net` to
   trusted sources; memory-facade inherits that. Never open an unauthenticated
   public endpoint.
2. **No app auth on the Hindsight side.** `HINDSIGHT_API_KEY` is empty on the
   trusted network. The facade passes it through only if set; it never invents a
   token (matches `common-memory` client-setup).
3. **No secrets in the repo.** Runtime secrets (API keys) come from env/BWS, not
   source. The facade itself holds no secrets.
4. **Never create a bank.** All facade tools route only to existing,
   taxonomy-approved banks; the approval gate in `common-memory`
   (`agent-memory-bootstrap.md` §1.2) is inherited. Ambiguous → ask, don't guess.
5. **Mutating tools default to `commit=false`.** Dedup/reroute/retain only apply
   on explicit `commit=true`; nothing writes to `global-user` automatically.

## Rollout

- Group 4 wires `deploy/` scripts (compose/env) + adds the facade to each
  client (Claude Code, Codex, OpenCode, Hermes) pointing at `/memory-facade/mcp`.
- Smoke after deploy: each client can `memory_recall` a real query and get a
  cited synthesis (verified live earlier: aggregation + provenance work).
