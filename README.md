# Memory-Facade

A thin, **stateless** MCP server that gives every coding agent (Claude Code,
Codex, OpenCode, Hermes) one *curated* entry point to shared memory — automatic
bank/tag routing, URL-ingest → linked article, session → documentation set, and
consistency tooling (dedupe / reroute).

It **orchestrates** [Hindsight](https://hindsight.vectorize.io) (facts) and
LightRAG (corpora). It does **not** reimplement storage and never creates banks.

See `~/Projects/common-memory/docs/memory-facade-architecture.md` for the design
and the 2026-08-18 content baseline.

## Run (stdio MCP server)

```sh
uv run python -m mf.server
```

## Where it runs

Production MCP surface: the centralized MCP gateway (`ghcr.io/tbxark/mcp-proxy`,
container `mcp-gateway`) on Orange Pi 5, published by HAProxy as
`https://mcp.msmsoft.net/memory_facade/mcp`.

Note the **underscore**: the gateway namespace is the config key `memory_facade`,
so the hyphenated `https://mcp.msmsoft.net/memory-facade/mcp` returns 404.

It is Ansible-managed from `infra-control`:
`roles/mcp-gateway/defaults/main.yml` (`mcp_gateway_servers.memory_facade`) with
the release pinned by `mcp_gateway_memory_facade_version`, deployed by
`playbooks/deploy/mcp-gateway.yml`. Never hand-edit `/opt/mcp-gateway/config.json`
— the next Ansible run silently reverts it.

A second, **dormant** registration exists in `msm-ai-gateway`
(`ai.msmsoft.net/memory_facade/mcp`, from `config/litellm.yaml`). No client is
configured for it; see `deploy/litellm-mcp-entry.md` before relying on it.

## Test

```sh
env -u PYTHONPATH uv run --extra dev pytest -q
```

> Note: on Sergey's host the shell exports a `PYTHONPATH` pointing at the Hermes
> venv. Unset it (`env -u PYTHONPATH …`) before running here, otherwise the
> wrong pydantic/pydantic_core gets imported and collection fails.
