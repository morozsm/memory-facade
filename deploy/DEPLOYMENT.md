# Memory-Facade deployment & security posture

Three surfaces exist, only one of them is the production path:

- **Production MCP gateway (LIVE, Ansible-managed):** the facade runs as a stdio
  server inside the centralized `mcp-gateway` container
  (`ghcr.io/tbxark/mcp-proxy`, `uvx` + pinned release wheel) and is published as
  `https://mcp.msmsoft.net/memory_facade/mcp`. Managed from the `infra-control`
  repo (`roles/mcp-gateway`), not from `msm-ai-gateway`. See
  "Mode B — production MCP gateway" below.
- **Mode A — local standalone (LIVE, Mac only):** memory-facade runs as a launchd
  LaunchAgent on the Mac, exposing streamable-http on `127.0.0.1:8500/mcp`.
  Hermes connects via `hermes mcp add memory-facade --url http://127.0.0.1:8500/mcp/`
  and gets all 6 curated tools. No Orange Pi, no production change.
- **Legacy LiteLLM registration (dormant, not used by any client):** a separate
  `memory_facade` entry in `msm-ai-gateway/config/litellm.yaml`, reachable as
  `ai.msmsoft.net/memory_facade/mcp` behind gateway auth. It is not the
  production path and it drifted a release behind; see
  `litellm-mcp-entry.md`.

## Transport

Memory-facade is an **MCP server** (fastmcp) that supports both:
- **stdio** (`python -m mf.server`) — used by the production MCP gateway
  (`uvx` launches it) and by process-managed clients.
- **streamable-http / sse** (`python -m mf.server --transport streamable-http
  --host 127.0.0.1 --port 8500`) — used by the Mode A launchd deployment.

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

## Mode B — production MCP gateway (Ansible, live)

The facade is a server entry in the centralized MCP gateway
(`ghcr.io/tbxark/mcp-proxy`, container `mcp-gateway` on Orange Pi 5), rendered
from `infra-control` — not from `msm-ai-gateway`:

- `roles/mcp-gateway/defaults/main.yml`:
  - `mcp_gateway_servers.memory_facade` — `command: uvx`,
    `args: [--from, <wheel URL>, memory-facade]`, env `HINDSIGHT_API_URL` /
    `HINDSIGHT_API_KEY`, `enabled: true`
  - `mcp_gateway_memory_facade_version` — the pinned release. Bump it on every
    release: uv caches per-URL, so the URL must change for a new wheel to be used.
- `roles/mcp-gateway/templates/config.json.j2` renders `/opt/mcp-gateway/config.json`.
- `playbooks/deploy/mcp-gateway.yml` deploys it; the handler restarts `mcp-proxy`.
- `roles/mcp-gateway/tasks/preflight.yml` fails the deploy when the server is
  enabled but `HINDSIGHT_API_URL` / `HINDSIGHT_API_KEY` are missing.

Public URL: `https://mcp.msmsoft.net/memory_facade/mcp`. HAProxy frontend
`mcp_gateway_host` (source ACL: LAN/Tailnet only) → `be_mcp_gateway` →
`mcp-gateway:9090`. The path segment is the config key, so it is `memory_facade`
with an **underscore** — `/memory-facade/mcp` returns 404.

```sh
cd ~/Projects/infra-control
ansible-playbook playbooks/deploy/mcp-gateway.yml --limit rag
```

Do not hand-edit `/opt/mcp-gateway/config.json`: the next Ansible run reverts it.

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

## Wiring status

Wired today:

- **Cline** — `~/.cline/data/settings/cline_mcp_settings.json`, server
  `memory-facade` → `https://mcp.msmsoft.net/memory_facade/mcp`
  (`transport.type: streamableHttp`, `timeout: 60`).
- **Hermes** — local Mode A endpoint `http://127.0.0.1:8500/mcp/`.

Not wired: Claude Code, Codex, OpenCode. Their remote-endpoint recipe is below.

Smoke after wiring: `ping` → `{"status":"healthy","database":"connected"}`, then
`memory_recall(query=<real query>)` returns a cited synthesis (verified live:
aggregation + provenance work).
