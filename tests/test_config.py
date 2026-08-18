"""Tests for mf.config resolution (no network, no side effects)."""

from mf import config


def test_defaults_without_env(monkeypatch):
    monkeypatch.delenv("HINDSIGHT_API_URL", raising=False)
    monkeypatch.delenv("HINDSIGHT_API_KEY", raising=False)
    assert config.hindsight_api_url() == "https://memory.msmsoft.net"
    # api key defaults to empty on trusted network
    assert config.hindsight_api_key() == ""


def test_env_override(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_API_URL", "http://localhost:8000")
    monkeypatch.setenv("HINDSIGHT_API_KEY", "abc")
    assert config.hindsight_api_url() == "http://localhost:8000"
    assert config.hindsight_api_key() == "abc"


def test_trailing_slash_stripped(monkeypatch):
    monkeypatch.setenv("HINDSIGHT_API_URL", "https://memory.msmsoft.net/")
    assert config.hindsight_api_url() == "https://memory.msmsoft.net"


def test_timeout_default(monkeypatch):
    monkeypatch.delenv("HINDSIGHT_TIMEOUT", raising=False)
    assert config.hindsight_timeout() == 30.0
