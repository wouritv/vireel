import importlib
import sys

import pytest


# Each call below pops and reimports retention_config, which redefines
# RetentionConfigError as a brand-new class object every time -- a
# pytest.raises(RetentionConfigError) bound to an earlier import would
# never match an instance raised by a later one. ValueError (its stable
# base class) is specific enough to satisfy SonarQube's "don't catch bare
# Exception" rule without that reload-identity trap.
def _reload_retention_config(monkeypatch, **env):
    for key in [
        "RETENTION_FREE_SOURCE_DAYS", "RETENTION_FREE_PRODUCED_DAYS",
        "RETENTION_SUBSCRIBER_SOURCE_DAYS", "RETENTION_SUBSCRIBER_PRODUCED_DAYS",
        "RETENTION_TEMP_FILES_HOURS", "RETENTION_NOTIFICATION_HOURS_BEFORE",
        "S3_STORAGE_COST_PER_GB_DAY",
    ]:
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    sys.modules.pop("retention_config", None)
    return importlib.import_module("retention_config")


def test_defaults_match_spec(monkeypatch):
    rc = _reload_retention_config(monkeypatch)
    assert rc.RETENTION_FREE_SOURCE_DAYS == 2
    assert rc.RETENTION_FREE_PRODUCED_DAYS == 14
    assert rc.RETENTION_SUBSCRIBER_SOURCE_DAYS == 10
    assert rc.RETENTION_SUBSCRIBER_PRODUCED_DAYS == 30
    assert rc.RETENTION_TEMP_FILES_HOURS == 24
    assert rc.RETENTION_NOTIFICATION_HOURS_BEFORE == 48
    assert rc.S3_STORAGE_COST_PER_GB_DAY > 0


def test_rejects_negative_value(monkeypatch):
    with pytest.raises(ValueError):
        _reload_retention_config(monkeypatch, RETENTION_FREE_SOURCE_DAYS="-1")


def test_rejects_non_numeric_value(monkeypatch):
    with pytest.raises(ValueError):
        _reload_retention_config(monkeypatch, RETENTION_FREE_SOURCE_DAYS="not-a-number")


def test_rejects_subscriber_shorter_than_free_source(monkeypatch):
    with pytest.raises(ValueError):
        _reload_retention_config(monkeypatch, RETENTION_SUBSCRIBER_SOURCE_DAYS="1", RETENTION_FREE_SOURCE_DAYS="2")


def test_rejects_subscriber_shorter_than_free_produced(monkeypatch):
    with pytest.raises(ValueError):
        _reload_retention_config(monkeypatch, RETENTION_SUBSCRIBER_PRODUCED_DAYS="5", RETENTION_FREE_PRODUCED_DAYS="14")


def test_rejects_produced_shorter_than_source_within_free_tier(monkeypatch):
    with pytest.raises(ValueError):
        _reload_retention_config(monkeypatch, RETENTION_FREE_PRODUCED_DAYS="1", RETENTION_FREE_SOURCE_DAYS="2")


def test_rejects_produced_shorter_than_source_within_subscriber_tier(monkeypatch):
    with pytest.raises(ValueError):
        _reload_retention_config(
            monkeypatch, RETENTION_SUBSCRIBER_PRODUCED_DAYS="5", RETENTION_SUBSCRIBER_SOURCE_DAYS="10",
        )


def test_accepts_zero_as_a_valid_boundary(monkeypatch):
    # 0 is a legitimate (if extreme) configuration -- "no free-tier
    # retention at all" -- and must not be rejected as if it were negative.
    rc = _reload_retention_config(
        monkeypatch,
        RETENTION_FREE_SOURCE_DAYS="0", RETENTION_FREE_PRODUCED_DAYS="0",
        RETENTION_SUBSCRIBER_SOURCE_DAYS="0", RETENTION_SUBSCRIBER_PRODUCED_DAYS="0",
    )
    assert rc.RETENTION_FREE_SOURCE_DAYS == 0


def test_resolve_retention_days_selects_tier_and_media_type(monkeypatch):
    rc = _reload_retention_config(monkeypatch)
    assert rc.resolve_retention_days(rc.MEDIA_TYPE_SOURCE, has_active_subscription=False) == rc.RETENTION_FREE_SOURCE_DAYS
    assert rc.resolve_retention_days(rc.MEDIA_TYPE_SOURCE, has_active_subscription=True) == rc.RETENTION_SUBSCRIBER_SOURCE_DAYS
    assert rc.resolve_retention_days(rc.MEDIA_TYPE_PRODUCED, has_active_subscription=False) == rc.RETENTION_FREE_PRODUCED_DAYS
    assert rc.resolve_retention_days(rc.MEDIA_TYPE_PRODUCED, has_active_subscription=True) == rc.RETENTION_SUBSCRIBER_PRODUCED_DAYS


def test_resolve_retention_days_rejects_unknown_media_type(monkeypatch):
    rc = _reload_retention_config(monkeypatch)
    with pytest.raises(ValueError):
        rc.resolve_retention_days("not_a_real_type", has_active_subscription=True)


def test_retention_config_snapshot_has_every_field(monkeypatch):
    rc = _reload_retention_config(monkeypatch)
    snapshot = rc.retention_config_snapshot()
    assert snapshot["retention_free_source_days"] == rc.RETENTION_FREE_SOURCE_DAYS
    assert snapshot["s3_storage_cost_per_gb_day"] == rc.S3_STORAGE_COST_PER_GB_DAY
