# Memory-Facade: the LiteLLM `mcp_servers` entry (legacy, dormant)

Status: this registration **exists today** in `msm-ai-gateway/config/litellm.yaml`
under `mcp_servers:` (next to `context7` and `lightrag`) and answers at
`ai.msmsoft.net/memory_facade/mcp` behind gateway auth, but **no client is
configured for it**. The production surface is the Ansible-managed MCP gateway at
`https://mcp.msmsoft.net/memory_facade/mcp` — see `DEPLOYMENT.md`.

It is also version-stale by design of the two mechanisms: this entry pins the
wheel by hand, while the production gateway is pinned by
`mcp_gateway_memory_facade_version` in `infra-control`. Keep them in step, or
retire this entry.

```yaml
  memory_facade:
    transport: stdio
    command: uvx
    args:
      - --from
      - https://github.com/morozsm/memory-facade/releases/download/v0.1.3/memory_facade-0.1.3-py3-none-any.whl
      - memory-facade
    env:
      HINDSIGHT_API_URL: os.environ/HINDSIGHT_API_URL
      HINDSIGHT_API_KEY: os.environ/HINDSIGHT_API_KEY
    allow_all_keys: true
    description: Curated shared-memory layer (recall/ingest/session/dedupe/reroute)
```

The key name is the URL namespace: LiteLLM serves `/<key>/mcp`, so the route is
`/memory_facade/mcp` (underscore) — `/memory-facade/mcp` is 404. The wheel URL is
a public release asset; no PAT is needed.

## Preconditions (must pass before this is applied)

1. **The wheel is published** as a public GitHub release asset — that is what is
   deployed (`uvx --from <wheel URL> memory-facade`). Confirm the asset exists
   before pinning it: the release URL must return the wheel, not 404.
2. **Set HINDSIGHT_API_URL / HINDSIGHT_API_KEY** in the gateway's deploy env
   (via BWS, not Compose literal secrets), so the container env interpolation
   resolves.
3. **ARM64 compat** — the Orange Pi 5 runtime image is arm64; verify the facade
   and its deps (fastmcp, httpx) install cleanly on arm64.
4. **Routing** — LiteLLM serves `/<key>/mcp`, so this entry appears at
   `ai.msmsoft.net/memory_facade/mcp` with the `MCP_INTERNAL_KEY` trust bridge
   and the HAProxy source ACL. `mcp.msmsoft.net` is served by the separate
   `mcp-gateway` proxy, **not** by LiteLLM — never document this entry under that
   hostname.

## Do NOT do autonomously

- Editing the **production** `config/litellm.yaml` must go through the repo's
  `check.sh` + `integration-test.sh` gates and `production-up.sh` deploy. This is
  a production change on Orange Pi — requires explicit user approval (repo
  AGENTS.md: "Do not change ... production host during a review/diagnosis-only
  task"; deploy only through `production-up.sh`).
- For the production MCP surface the change belongs in `infra-control`
  (`roles/mcp-gateway`), not here. A LiteLLM deploy recreates the whole
  `redis`/`litellm`/`gateway`/`a2a-registry-watchdog` stack, so do not trigger it
  for a dormant entry without cause.
