"""Tests for mf.recall — multi-bank aggregation, dedup, synthesis (no network)."""

from mf.recall import RecallError, Synthesizer, recall


class FakeHindsight:
    """Scripted per-bank recall for tests."""

    def __init__(self, per_bank: dict[str, list[dict]]):
        self.per_bank = per_bank
        self.calls: list[tuple[str, str]] = []

    def recall(self, bank_id, query, types=None, budget="mid", **kw):
        self.calls.append((bank_id, query))
        items = self.per_bank.get(bank_id, [])
        return {"results": items}


def _item(bank, id_, text, chunk=None, tags=None):
    return {
        "id": id_,
        "text": text,
        "type": "world",
        "tags": tags or [],
        "chunk_id": chunk,
    }


def test_recall_aggregates_banks_with_provenance():
    fake = FakeHindsight(
        {
            "global-user": [_item("g", "1", "personal fact A")],
            "infra": [_item("i", "2", "infra fact B")],
        }
    )
    result = recall(fake, "meaning of life", banks=["global-user", "infra"])
    assert result.query == "meaning of life"
    # both banks queried
    assert [b for b, _ in fake.calls] == ["global-user", "infra"]
    # both items present with per-bank labels
    banks = {it.bank for it in result.items}
    assert banks == {"global-user", "infra"}
    assert result.items[0].citation == "[[global-user:1]]"


def test_recall_dedups_shared_chunk():
    fake = FakeHindsight(
        {
            # two rows share the same chunk_id -> dedup to one
            "infra": [
                _item("i", "2", "fact A", chunk="chunk-9"),
                _item("i", "3", "fact A duplicate", chunk="chunk-9"),
            ]
        }
    )
    result = recall(fake, "redis", banks=["infra"])
    deduped = result.deduped_items()
    assert len(deduped) == 1
    assert deduped[0].id == "2"


def test_synthesis_includes_citations():
    fake = FakeHindsight(
        {"infra": [_item("i", "1", "429 usage_limit_reached is quota")]}
    )
    result = recall(fake, "quota 429", banks=["infra"])
    text = Synthesizer().synthesize(result)
    assert "[[infra:1]]" in text
    assert "429 usage_limit_reached" in text


def test_synthesis_empty():
    fake = FakeHindsight({})
    result = recall(fake, "nothing", banks=["infra"])
    assert "No matching memories" in Synthesizer().synthesize(result)


def test_recall_rejects_malformed_payload():
    fake = FakeHindsight({"infra": "not-a-list"})
    try:
        recall(fake, "x", banks=["infra"])
        assert False, "expected RecallError"
    except RecallError:
        pass
