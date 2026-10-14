"""Task 19 -- SHARED-WITH-M5 config shape integration.

M5 v0.4.0 (SHARED-WITH-M5 amendment, Known Blockers row 1) ships
PipelineConfig. xfail removed; test must pass with real imports.
The FakePipelineConfig in tests/fixtures/m8_fixtures.py remains as a
duck-typed stand-in for tests that exercise M8 internals in isolation.
"""

from __future__ import annotations


def test_m5_exposes_pipeline_config() -> None:
    from m5_config_loader import PipelineConfig  # noqa: F401

    cfg = PipelineConfig(
        checkpointer_dsn_vault_path="secret/data/m8/checkpointer_dsn",
        hitl_hmac_key_vault_path="secret/data/m8/hitl_hmac_key",
        gateway_base_url="https://m6-gateway.internal:8443",
        gateway_mtls_client_cert_path="/etc/m8/mtls/client.pem",
        audit_base_url="https://m10-audit.internal:8443",
        audit_mtls_client_cert_path="/etc/m8/mtls/audit.pem",
    )
    assert cfg.checkpointer_backend == "postgres"
    assert cfg.max_concurrent_instruments == 10
    assert cfg.max_pipeline_wall_clock_seconds == 1_200
    assert cfg.token_budgets["stage_12_cross_source_synthesis"] == 15_000


def test_fake_pipeline_config_shape_is_valid() -> None:
    """Verify the fake stand-in shape has all expected attributes."""
    from tests.fixtures.m8_fixtures import FakePipelineConfig

    cfg = FakePipelineConfig()
    expected_attrs = [
        "model_id",
        "model_provider",
        "region",
        "checkpointer_backend",
        "checkpointer_dsn_vault_path",
        "hitl_hmac_key_vault_path",
        "hitl_timeout_seconds",
        "max_concurrent_instruments",
        "max_pipeline_wall_clock_seconds",
        "alert_pipeline_wall_clock_seconds",
        "gateway_base_url",
        "gateway_mtls_client_cert_path",
        "audit_base_url",
        "audit_mtls_client_cert_path",
        "token_budgets",
    ]
    for attr in expected_attrs:
        assert hasattr(cfg, attr), f"FakePipelineConfig missing {attr}"


def test_fake_pipeline_config_field_set_matches_real() -> None:
    """FakePipelineConfig's public fields should be a subset of the real one.

    Ensures we don't regress the duck-typing contract when the real
    PipelineConfig adds new fields in future minor bumps.
    """
    from m5_config_loader import PipelineConfig
    from tests.fixtures.m8_fixtures import FakePipelineConfig

    real_fields = set(PipelineConfig.model_fields)
    fake_fields = set(FakePipelineConfig.model_fields)
    assert fake_fields <= real_fields, (
        f"FakePipelineConfig has unknown fields: {fake_fields - real_fields}"
    )
