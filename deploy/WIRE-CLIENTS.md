# Wiring memory-facade into Claude Code, Codex, OpenCode, Hermes

Once the facade is deployed as `/memory-facade/mcp` (see `litellm-mcp-entry.md`),
each agent connects as a single remote MCP server. This keeps the *curated* tools
(`memory_recall`, `memory_ingest_url`, `memory_session_to_docs`,
`memory_dedupe`, `memory_reroute`) in one place while raw per-bank Hindsight MCP
endpoints remain available alongside.

> **Global-config gate:** these edits touch each client's *global* config.
> Per the Common Memory contract (`agent-memory-bootstrap.md` §1.6): read the
> current config, back it up, and get user approval before applying. None of
> these files are modified by this automation — they are prepared configs.

## Claude Code

Add to user config (`claude mcp add` or `~/.claude.json` mcpServers):

```sh
claude mcp add --transport http memory-facade --scope user https://mcp.msmsoft.net/memory-facade/mcp
claude mcp list
```

## Codex

Add under `[mcp_servers]` in `~/.codex/config.toml`:

```toml
[mcp_servers.memory-facade]
url = "https://mcp.msmsoft.net/memory-facade/mcp"
startup_timeout_sec = 20
tool_timeout_sec = 60
```

Verify: `codex mcp list` / `codex mcp get memory-facade`.

## OpenCode

Add to the `mcp` block of `~/.config/opencode/opencode.json`:

```jsonc
{
  "mcp": {
    "memory-facade": {
      "type": "remote",
      "url": "https://mcp.msmsoft.net/memory-facade/mcp",
      "enabled": true
    }
  }
}
```

Verify: `opencode mcp list` shows `memory-facade` enabled.

## Hermes

Hermes can expose the facade as a set of MCP tools via its MCP client config (the
same mechanism used for `hindsight-global` / `hindsight-infra`). Point the server
at the facade endpoint; the curated tools then appear as `memory_*`.

## Smoke (after wiring, from each client)

1. `memory_recall(query="user working style")` → cited synthesis.
2. `memory_ingest_url(url=<real url>)` → article card with `related` links.
3. `memory_dedupe(bank="infra", commit=false)` → duplicate groups reported.
4. `memory_reroute(source_bank="global-user", commit=false)` → misroute proposals.

All default read-only; commits require explicit `commit=true` per the safety gate.
