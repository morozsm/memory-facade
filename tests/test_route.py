"""Tests for mf._route — auto bank/tag routing (no network)."""

import pytest

from mf._route import AmbiguousRouteError, _contains_keyword, derive_tags, route


def test_routes_infra_text_to_infra():
    r = route("redployed redis through docker compose on orange pi")
    assert r.bank == "infra"
    assert r.method == "auto"


def test_routes_personal_preference_to_global_user():
    r = route("I prefer concise status updates and direct action")
    assert r.bank == "global-user"
    assert r.method == "auto"


def test_explicit_bank_override_wins():
    r = route("any text", explicit_bank="infra")
    assert r.bank == "infra"
    assert r.method == "explicit"


def test_explicit_bank_not_in_allowlist_raises():
    with pytest.raises(AmbiguousRouteError):
        route("text", explicit_bank="sensitive-new-bank")


def test_ambiguous_content_raises():
    # No keyword matches -> should ask, not guess
    with pytest.raises(AmbiguousRouteError):
        route("the weather today is quite pleasant in the park")


def test_derive_tags_memory_domain():
    tags = derive_tags("hindsight recall and retain memory policy")
    assert "domain:memory" in tags
    assert "project:common-memory" in tags


def test_derive_tags_infra_domain():
    tags = derive_tags("litellm gateway deploy via mcp")
    assert "service:ai-gateway" in tags
    assert "domain:infra" in tags


def test_health_check_is_not_medical():
    with pytest.raises(AmbiguousRouteError):
        route("Telegram polling health check passed and the service is healthy")
    assert route("health check on the deployment pipeline").bank == "infra"


def test_business_keyword_in_hostname_does_not_outscore_infra_evidence():
    text = "rerank.customer.example.test failed with GPU OOM on the deployment host"
    assert route(text).bank == "infra"


def test_provider_name_alone_is_not_professional_work():
    with pytest.raises(AmbiguousRouteError):
        route("DigitalOcean model catalog")


def test_memory_admin_fact_beats_embedded_product_name():
    text = "memory bank inventory includes a retired rigplane component and auto-retain policy"
    assert route(text).bank == "infra"


@pytest.mark.parametrize(
    ("text", "keyword"),
    [
        ("healthy service", "health"),
        ("xcustomer", "customer"),
        ("mcp2", "mcp"),
    ],
)
def test_keyword_does_not_match_inside_ascii_token(text, keyword):
    assert not _contains_keyword(text, keyword)


@pytest.mark.parametrize(
    "text",
    [
        "mcp_server on docker_compose crashed",
        "настройка MCPсервер и nginx",
        "医疗mcp部署",
        "memory\u00a0bank policy",
        "go‑to‑market pricing",
        "orange−pi docker",
        "orange⁃pi docker",
    ],
)
def test_common_separator_and_mixed_script_shapes_remain_routable(text):
    assert route(text).bank in {"infra", "business"}


def test_explicit_health_record_tie_prefers_sensitive_bank():
    result = route("personal health records stored in a docker container")
    assert result.bank == "medical"
    assert result.tags == ["sensitivity:restricted"]
    with pytest.raises(AmbiguousRouteError):
        route(
            "personal health records stored in a docker container",
            bank_allowlist=("infra", "global-user"),
        )


def test_operational_diagnostics_remains_infra():
    assert route("network diagnostics for the nginx deployment").bank == "infra"


@pytest.mark.parametrize(
    "text",
    [
        "doctors prescriptions archived in the postgres backup",
        "clinics and doctors notes exported to a docker volume",
        "my medications are stored in a note on the docker host",
        "her diagnoses were exported from the postgres database",
        "blood tests and lab work saved to the vault",
        "prescriptions scanned and uploaded via the gateway",
        "my medi\u200bcal diagnosis backed up to postgres and redis",
        "doc\u00adtor prescrip\u00adtion stored on the nginx docker host",
        "my health is deteriorating",
        "mental health notes synced to postgres",
        "clinical notes exported to the docker host",
        "I was diagnosed with hypertension; notes in the postgres backup",
        "health insurance claim uploaded to nginx",
        "patient chart and hospital discharge summary on the redis box",
        "therapy session notes in the gateway archive",
        "m\u0435dical record on the docker host",
    ],
)
def test_phi_terms_always_route_to_sensitive_bank(text):
    assert route(text).bank == "medical"


@pytest.mark.parametrize("bank", ["project-rigplane-core", "project-rigplane-tower"])
def test_retired_bank_is_rejected_as_explicit_target(bank):
    with pytest.raises(AmbiguousRouteError):
        route("any content", explicit_bank=bank)
