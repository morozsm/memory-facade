# Memory-Facade deployment & security posture

This document captures how memory-facade is deployed and the non-negotiable
security posture. Deploy is **deliberately not wired up yet** — this is the
target design so all builds stay compatible. Group 4 performs the actual deploy.

## Transport

Memory-facade is an **MCP stdio server** (`python -m mf.server`, fastmcp). It is
launched as a child process by an MCP runtime that owns the stdio/HTTP bridge.
For this stack, that runtime is the `msm-ai-gateway` **LiteLLM MCP runtime**
(verified feasible): the runtime's Docker image adds `uv`/`uvx`, so the facade
runs via `uv run --project … python -m mf.server`.

## Add to LiteLLM runtime (`config/litellm.yaml`)

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
