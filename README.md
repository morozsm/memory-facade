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

Deployed as an MCP server in the `msm-ai-gateway` LiteLLM MCP runtime, routed as
`/memory-facade/mcp` (same pattern as `lightrag` in `config/litellm.yaml`).

## Test

```sh
env -u PYTHONPATH uv run --extra dev pytest -q
```

> Note: on Sergey's host the shell exports a `PYTHONPATH` pointing at the Hermes
> venv. Unset it (`env -u PYTHONPATH …`) before running here, otherwise the
> wrong pydantic/pydantic_core gets imported and collection fails.
