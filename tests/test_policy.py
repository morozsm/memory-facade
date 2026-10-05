"""Tests for the self-describing policy prompt/resource (no network)."""

import asyncio

from fastmcp import Client

from mf import policy
from mf import server

ALL_BANKS = [
    "global-user",
    "infra",
    "projects",
    "product-rigplane",
    "business",
    "work",
    "medical",
]


def test_taxonomy_mentions_all_banks():
    for bank in ALL_BANKS:
        assert bank in policy.BANK_TAXONOMY, f"missing bank: {bank}"


def test_usage_policy_has_gate_and_routing():
    text = policy.USAGE_POLICY.lower()
    assert "when to query" in text
    assert "when not to query" in text
    for bank in ALL_BANKS:
        assert bank in policy.USAGE_POLICY, f"missing bank: {bank}"


def test_prompt_registered_and_served():
    async def go():
        async with Client(server.mcp) as client:
            prompts = await client.list_prompts()
            assert "memory-usage-policy" in [p.name for p in prompts]
            result = await client.get_prompt("memory-usage-policy")
            body = result.messages[0].content.text
            assert policy.USAGE_POLICY in body

    asyncio.run(go())


def test_taxonomy_resource_registered_and_served():
    async def go():
        async with Client(server.mcp) as client:
            resources = await client.list_resources()
            assert "memory://taxonomy" in [str(r.uri) for r in resources]
            contents = await client.read_resource("memory://taxonomy")
            assert policy.BANK_TAXONOMY in contents[0].text

    asyncio.run(go())
