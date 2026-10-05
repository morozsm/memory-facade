"""Self-describing usage policy for the memory-facade MCP server.

Exposed as the ``memory-usage-policy`` prompt and the ``memory://taxonomy``
resource, so every MCP client learns *when* to query deep memory and *which
bank* to use — without reading repo docs first.

Source of truth for bank boundaries: ``docs/hindsight-bank-taxonomy.md`` in
morozsm/common-memory. Keep this module in sync when the taxonomy changes.
"""

from __future__ import annotations

USAGE_POLICY = """\
# Deep-memory usage policy (memory-facade)

This server is a curated entry point to a deep-memory stack: Hindsight
(durable facts) plus LightRAG (document corpora). It is NOT a scratchpad.
Your own session/local memory is separate — always check it first.

## When to query (memory_recall)

- The task needs durable facts or history your local memory lacks: past
  decisions and their rationale, technical archaeology ("how did we build
  X"), protocol details, infra setup history, customer evidence.
- The expected value beats ~3s latency plus the context cost of results.

## When NOT to query

- Greetings, acknowledgements, verbatim/formatting tasks.
- The answer is already in hand (local memory, tools, web, conversation).
- You need live or operational state: what an agent is doing right now,
  job status, fresh logs. That lives in agents' local memory and working
  files — never in the deep stack.
- Scratch material: noisy drafts, large logs, raw transcripts, secrets,
  large code/doc corpora. Policy forbids storing these in Hindsight.

## Which bank

Banks are HARD isolation boundaries: graphs, observations and mental models
never cross banks, and there is no cross-bank visibility. Route per topic
(full table: memory://taxonomy):

- global-user: durable personal preferences, working style, language,
  cross-project user context. Never project/domain facts or transcripts.
- product-rigplane: Rigplane product memory — CI-V profiles, triage
  evidence, priorities, ticket references.
- infra: shared infrastructure — hosts, services, Ansible, benchmarks,
  and the memory stack itself.
- projects: miscellaneous projects — goals, decisions, constraints, status.
- business: MSMSoft strategy, plans, customers/partners (no PII, no secrets).
- work: ServerStack / DigitalOcean work context.
- medical: restricted health summaries. Avoid unless health-relevant.

Default to the topic's bank, not global-user. Multiple banks are allowed
when the question genuinely spans them.

## Tags

Use deterministic, lowercase tags for scoping inside a bank:
project:<id>, component:<id>, env:<id>, host:<id>, service:<id>,
agent:<id>, session:<id>, domain:<id>. Do not invent ad-hoc namespaces.
"""

BANK_TAXONOMY = """\
# Hindsight bank taxonomy (summary)

Source of truth: docs/hindsight-bank-taxonomy.md in morozsm/common-memory.
Banks are hard isolation boundaries. Do not create banks; route with tags.

| Bank | Purpose | Recall routing |
| --- | --- | --- |
| global-user | Durable personal preferences, working style, engineering values, language, cross-project user context. | Personalization. No project/domain facts, no transcripts, no secrets. |
| infra | Shared cross-agent infrastructure: Hindsight, LightRAG, home-lab, Ansible, benchmarks, hosts, services, network. | Tags: project:*, component:*, env:*, host:*, service:*, agent:*, session:*, domain:*. |
| product-rigplane | Rigplane product memory across components. | Tags: product:rigplane, project:rigplane, component:*. |
| projects | Misc projects not justifying a dedicated bank: goals, decisions, constraints, status, pointers. | Tags: project:*, component:*. |
| business | Durable MSMSoft business context: strategy, plans, customer/partner summaries. | Tags: org:msmsoft, domain:business, project:*, product:*, customer:*, partner:*. No PII/secrets. |
| work | Durable professional work context (ServerStack, DigitalOcean): decisions, constraints, procedures. | Tags: org:serverstack, provider:digitalocean, project:*, env:*, host:*, service:*. |
| medical | Restricted personal health context: user-approved summaries, constraints, follow-ups. | True isolation boundary. Summaries with pointers only. |

Retired/nonexistent bank names (never recreate): agent-codex,
project-rigplane-pro, project-rigplane-core, project-rigplane-tower.
"""
