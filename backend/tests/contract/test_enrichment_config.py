"""Phase 10.1b: enrichment config parsing contract tests.

Covers:
  - Defaults: enabled=false, auto_enqueue=false, worker_enabled=false
  - Boolean parsing: true/false, 1/0, yes/no, on/off, case-insensitive
  - Invalid boolean falls back safely
  - Numeric defaults and invalid fallback
  - worker_enabled parsed but no worker started in this PR
"""

import pytest

from backend.app.services.enrichment_config import EnrichmentConfig, load_enrichment_config


# ── Defaults ──────────────────────────────────────────────────────────────────

class TestDefaults:
    def test_all_defaults_preserve_manual_behavior(self, monkeypatch):
        """With no env vars set, config must be manual-only."""
        # Clear all relevant env vars
        for key in [
            "ENRICHMENT_ENABLED", "ENRICHMENT_AUTO_ENQUEUE",
            "ENRICHMENT_WORKER_ENABLED", "ENRICHMENT_PROVIDER",
            "ENRICHMENT_PROMPT_VERSION", "ENRICHMENT_MAX_PER_MINUTE",
            "ENRICHMENT_MAX_RETRIES", "ENRICHMENT_WORKER_IDLE_SLEEP_S",
            "ENRICHMENT_WORKER_POLL_INTERVAL_S", "ENRICHMENT_TIMEOUT_S",
        ]:
            monkeypatch.delenv(key, raising=False)

        cfg = load_enrichment_config()

        assert cfg.enabled is False
        assert cfg.auto_enqueue is False
        assert cfg.worker_enabled is False
        assert cfg.provider == "edge_vlm"
        assert cfg.prompt_version == "phase10_1_obs_v1"
        assert cfg.max_per_minute == 10
        assert cfg.max_retries == 2
        assert cfg.worker_idle_sleep_s == 5.0
        assert cfg.worker_poll_interval_s == 2.0
        assert cfg.timeout_s == 30

    def test_dataclass_is_frozen(self, monkeypatch):
        """EnrichmentConfig must be immutable."""
        for key in [
            "ENRICHMENT_ENABLED", "ENRICHMENT_AUTO_ENQUEUE",
            "ENRICHMENT_WORKER_ENABLED", "ENRICHMENT_PROVIDER",
            "ENRICHMENT_PROMPT_VERSION",
        ]:
            monkeypatch.delenv(key, raising=False)

        cfg = load_enrichment_config()
        with pytest.raises(AttributeError):
            cfg.enabled = True  # type: ignore[misc]


# ── Boolean parsing ───────────────────────────────────────────────────────────

class TestBooleanParsing:
    @pytest.mark.parametrize("value", ["true", "TRUE", "True", "1", "yes", "YES", "on", "ON"])
    def test_truthy_values(self, monkeypatch, value):
        monkeypatch.setenv("ENRICHMENT_ENABLED", value)
        for key in ["ENRICHMENT_AUTO_ENQUEUE", "ENRICHMENT_WORKER_ENABLED"]:
            monkeypatch.delenv(key, raising=False)
        cfg = load_enrichment_config()
        assert cfg.enabled is True

    @pytest.mark.parametrize("value", ["false", "FALSE", "False", "0", "no", "NO", "off", "OFF"])
    def test_falsy_values(self, monkeypatch, value):
        monkeypatch.setenv("ENRICHMENT_ENABLED", value)
        for key in ["ENRICHMENT_AUTO_ENQUEUE", "ENRICHMENT_WORKER_ENABLED"]:
            monkeypatch.delenv(key, raising=False)
        cfg = load_enrichment_config()
        assert cfg.enabled is False

    def test_invalid_boolean_falls_back_false(self, monkeypatch):
        """Invalid boolean string should fall back to False with warning."""
        monkeypatch.setenv("ENRICHMENT_ENABLED", "maybe")
        for key in ["ENRICHMENT_AUTO_ENQUEUE", "ENRICHMENT_WORKER_ENABLED"]:
            monkeypatch.delenv(key, raising=False)
        cfg = load_enrichment_config()
        assert cfg.enabled is False

    def test_whitespace_trimmed(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_ENABLED", "  true  ")
        for key in ["ENRICHMENT_AUTO_ENQUEUE", "ENRICHMENT_WORKER_ENABLED"]:
            monkeypatch.delenv(key, raising=False)
        cfg = load_enrichment_config()
        assert cfg.enabled is True

    def test_auto_enqueue_boolean(self, monkeypatch):
        for key in ["ENRICHMENT_ENABLED", "ENRICHMENT_WORKER_ENABLED"]:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("ENRICHMENT_AUTO_ENQUEUE", "yes")
        cfg = load_enrichment_config()
        assert cfg.auto_enqueue is True

    def test_worker_enabled_boolean(self, monkeypatch):
        for key in ["ENRICHMENT_ENABLED", "ENRICHMENT_AUTO_ENQUEUE"]:
            monkeypatch.delenv(key, raising=False)
        monkeypatch.setenv("ENRICHMENT_WORKER_ENABLED", "1")
        cfg = load_enrichment_config()
        assert cfg.worker_enabled is True


# ── Numeric parsing ───────────────────────────────────────────────────────────

class TestNumericParsing:
    def test_valid_int(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_MAX_PER_MINUTE", "20")
        cfg = load_enrichment_config()
        assert cfg.max_per_minute == 20

    def test_invalid_int_falls_back_default(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_MAX_PER_MINUTE", "abc")
        cfg = load_enrichment_config()
        assert cfg.max_per_minute == 10

    def test_valid_float(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_WORKER_IDLE_SLEEP_S", "3.5")
        cfg = load_enrichment_config()
        assert cfg.worker_idle_sleep_s == 3.5

    def test_invalid_float_falls_back_default(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_WORKER_IDLE_SLEEP_S", "xyz")
        cfg = load_enrichment_config()
        assert cfg.worker_idle_sleep_s == 5.0

    def test_timeout_s(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_TIMEOUT_S", "60")
        cfg = load_enrichment_config()
        assert cfg.timeout_s == 60


# ── Provider / prompt_version string parsing ──────────────────────────────────

class TestStringParsing:
    def test_provider_default(self, monkeypatch):
        monkeypatch.delenv("ENRICHMENT_PROVIDER", raising=False)
        cfg = load_enrichment_config()
        assert cfg.provider == "edge_vlm"

    def test_provider_normalized(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_PROVIDER", "  Template  ")
        cfg = load_enrichment_config()
        assert cfg.provider == "template"

    def test_prompt_version_default(self, monkeypatch):
        monkeypatch.delenv("ENRICHMENT_PROMPT_VERSION", raising=False)
        cfg = load_enrichment_config()
        assert cfg.prompt_version == "phase10_1_obs_v1"

    def test_prompt_version_custom(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_PROMPT_VERSION", "v2_experiment")
        cfg = load_enrichment_config()
        assert cfg.prompt_version == "v2_experiment"


# ── worker_enabled parsed but not acted on ────────────────────────────────────

class TestWorkerEnabledParsed:
    """worker_enabled exists in config and is parsed, but this PR does NOT start any worker."""

    def test_worker_enabled_parsed_when_true(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_WORKER_ENABLED", "true")
        cfg = load_enrichment_config()
        assert cfg.worker_enabled is True
        # No assertion about worker starting — that's a future PR concern.

    def test_worker_enabled_parsed_when_false(self, monkeypatch):
        monkeypatch.setenv("ENRICHMENT_WORKER_ENABLED", "false")
        cfg = load_enrichment_config()
        assert cfg.worker_enabled is False
