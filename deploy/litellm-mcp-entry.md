# Memory-Facade: exact mcp_servers entry for the LiteLLM runtime

This is the block to merge into `msm-ai-gateway/config/litellm.yaml` under
`mcp_servers:` (next to the existing `context7` and `lightrag` entries).

```yaml
  memory-facade:
    transport: stdio
    command: uvx
    args:
      - --from
      - git+https://github.com/<owner>/memory-facade.git
      - memory-facade
    env:
      HINDSIGHT_API_URL: os.environ/HINDSIGHT_API_URL
      HINDSIGHT_API_KEY: os.environ/HINDSIGHT_API_KEY
    allow_all_keys: true
    description: Curated shared-memory layer (recall/ingest/session/dedupe/reroute)
```

## Preconditions (must pass before this is applied)

1. **Push memory-facade** to a git host the runtime container can reach
   (GitHub or the private host). Replace `<owner>` above with the real org. The
   project ships an executable console script via its `pyproject.toml`
   (entry point `memory-facade = mf.server:main`) — verify `[project.scripts]`
   exists before relying on `uvx ... memory-facade`.
2. **Set HINDSIGHT_API_URL / HINDSIGHT_API_KEY** in the gateway's deploy env
   (via BWS, not Compose literal secrets), so the container env interpolation
   resolves.
3. **ARM64 compat** — the Orange Pi 5 runtime image is arm64; verify the facade
   and its deps (fastmcp, httpx) install cleanly on arm64. Pin the uvx source by
   commit/tag, not a moving branch.
4. **HAProxy** — the gateway already routes `/mcp/{server}/mcp`. No HAProxy
   change needed to expose `/memory-facade/mcp`; only the AGENTS.md "MCP
   changes" gate applies (digest-pinned runtime, `MCP_INTERNAL_KEY` bridge).

## Do NOT do autonomously

- Editing the **production** `config/litellm.yaml` must go through the repo's
  `check.sh` + `integration-test.sh` gates and `production-up.sh` deploy. This
  is a production change on Orange Pi — requires explicit user approval (repo
  AGENTS.md: "Do not change ... production host during a review/diagnosis-only
  task"; deploy only through `production-up.sh`).
