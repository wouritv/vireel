"""
retention_config.py -- Media lifecycle / retention policy configuration.

Storage is no longer a quota sold to the user (no "X Go / Y Go used", no
storage add-on, no plan-tied Go allowance) -- the user only ever spends
credits. Internally, Vireel still has to decide how long it physically
keeps a media file in S3, and what that costs, so those two concerns live
here as the single source of truth:

  - how long a media file is retained, by media type (source vs produced)
    and by whether the owning user had an active subscription at the
    moment the media was created (see resolve_retention_days) -- never
    recomputed later from a live subscription lookup, see app.py's
    _finalize_media_retention_billing;
  - what Vireel's own internal S3 storage cost is, per GB per day
    (S3_STORAGE_COST_PER_GB_DAY), used by billing.py to add a retention
    cost component to a job's existing credit cost.

Every duration/rate is environment-configured, validated once here at
import time so a misconfigured deploy fails loudly at startup instead of
silently applying a nonsensical retention window or cost.
"""
import os
from typing import Dict


class RetentionConfigError(ValueError):
    """Raised at import time when a RETENTION_*/S3_STORAGE_COST_PER_GB_DAY
    environment variable is missing, malformed, negative, or inconsistent
    with another one."""


def _non_negative_int(env_name: str, default: int) -> int:
    raw = os.environ.get(env_name, str(default))
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        raise RetentionConfigError(f"{env_name} must be an integer, got {raw!r}")
    if value < 0:
        raise RetentionConfigError(f"{env_name} must be >= 0, got {value}")
    return value


def _non_negative_float(env_name: str, default: float) -> float:
    raw = os.environ.get(env_name, str(default))
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        raise RetentionConfigError(f"{env_name} must be a number, got {raw!r}")
    if value < 0:
        raise RetentionConfigError(f"{env_name} must be >= 0, got {value}")
    return value


# ---------------------------------------------------------------------------
# Retention durations (days for media, hours for temp files / notice lead
# time -- see the module docstring).
# ---------------------------------------------------------------------------
RETENTION_FREE_SOURCE_DAYS = _non_negative_int("RETENTION_FREE_SOURCE_DAYS", 2)
RETENTION_FREE_PRODUCED_DAYS = _non_negative_int("RETENTION_FREE_PRODUCED_DAYS", 14)
RETENTION_SUBSCRIBER_SOURCE_DAYS = _non_negative_int("RETENTION_SUBSCRIBER_SOURCE_DAYS", 10)
RETENTION_SUBSCRIBER_PRODUCED_DAYS = _non_negative_int("RETENTION_SUBSCRIBER_PRODUCED_DAYS", 30)

# Not a user-facing media retention window -- how long an orphaned
# temporary/working file (extracted frames, ffmpeg intermediates, ...)
# from a crashed/interrupted job is allowed to survive before the cleanup
# sweep reclaims it (see app.py's process_temp_file_cleanup_jobs).
RETENTION_TEMP_FILES_HOURS = _non_negative_int("RETENTION_TEMP_FILES_HOURS", 24)

# How long before a PRODUCED media's retention_expires_at the one-shot
# "download it before it's gone" notification fires (see
# process_media_expiry_notification_jobs). Source media is never notified
# (see the module docstring on process_media_expiry_notification_jobs).
RETENTION_NOTIFICATION_HOURS_BEFORE = _non_negative_int("RETENTION_NOTIFICATION_HOURS_BEFORE", 48)

# Vireel's own internal cost assumption for S3 storage, per GB per day --
# distinct from (and additive to, never replacing) the existing per-
# operation S3 cost already modeled in billing.py's AMAZON_S3_GO_PRICE/
# AMAZON_S3_*_REQUEST_PRICE constants. Defaults to roughly AMAZON_S3_GO_PRICE
# (S3 Standard's per-GB-MONTH price) spread evenly over a 30-day month --
# a reasonable default, but this is Vireel's own billing-engine input, not
# a direct AWS passthrough, so it stays independently configurable.
S3_STORAGE_COST_PER_GB_DAY = _non_negative_float("S3_STORAGE_COST_PER_GB_DAY", 0.0008)


def _validate_consistency() -> None:
    """Refuses a configuration where the numbers would contradict the
    policy's own stated intent, rather than just being individually
    non-negative:
      - a subscriber must never be retained for LESS time than a free
        account for the same media type (the whole point of subscribing
        is a longer window, not a shorter one);
      - within either tier, a produced (final) deliverable must never be
        retained for less time than the source footage it was made from
        (it would routinely outlive its own result otherwise)."""
    if RETENTION_SUBSCRIBER_SOURCE_DAYS < RETENTION_FREE_SOURCE_DAYS:
        raise RetentionConfigError(
            f"RETENTION_SUBSCRIBER_SOURCE_DAYS ({RETENTION_SUBSCRIBER_SOURCE_DAYS}) must be >= "
            f"RETENTION_FREE_SOURCE_DAYS ({RETENTION_FREE_SOURCE_DAYS})"
        )
    if RETENTION_SUBSCRIBER_PRODUCED_DAYS < RETENTION_FREE_PRODUCED_DAYS:
        raise RetentionConfigError(
            f"RETENTION_SUBSCRIBER_PRODUCED_DAYS ({RETENTION_SUBSCRIBER_PRODUCED_DAYS}) must be >= "
            f"RETENTION_FREE_PRODUCED_DAYS ({RETENTION_FREE_PRODUCED_DAYS})"
        )
    if RETENTION_FREE_PRODUCED_DAYS < RETENTION_FREE_SOURCE_DAYS:
        raise RetentionConfigError(
            f"RETENTION_FREE_PRODUCED_DAYS ({RETENTION_FREE_PRODUCED_DAYS}) must be >= "
            f"RETENTION_FREE_SOURCE_DAYS ({RETENTION_FREE_SOURCE_DAYS})"
        )
    if RETENTION_SUBSCRIBER_PRODUCED_DAYS < RETENTION_SUBSCRIBER_SOURCE_DAYS:
        raise RetentionConfigError(
            f"RETENTION_SUBSCRIBER_PRODUCED_DAYS ({RETENTION_SUBSCRIBER_PRODUCED_DAYS}) must be >= "
            f"RETENTION_SUBSCRIBER_SOURCE_DAYS ({RETENTION_SUBSCRIBER_SOURCE_DAYS})"
        )


_validate_consistency()


MEDIA_TYPE_SOURCE = "source"
MEDIA_TYPE_PRODUCED = "produced"
MEDIA_TYPES = (MEDIA_TYPE_SOURCE, MEDIA_TYPE_PRODUCED)


def resolve_retention_days(media_type: str, has_active_subscription: bool) -> int:
    """The single place that turns (media_type, subscription status at
    creation time) into a number of days -- called exactly once, at media
    creation (see app.py's _finalize_media_retention_billing), and the
    result is stored on the media_assets row forever after. Never called
    again later to "recompute" an already-created media's retention."""
    if media_type == MEDIA_TYPE_SOURCE:
        return RETENTION_SUBSCRIBER_SOURCE_DAYS if has_active_subscription else RETENTION_FREE_SOURCE_DAYS
    if media_type == MEDIA_TYPE_PRODUCED:
        return RETENTION_SUBSCRIBER_PRODUCED_DAYS if has_active_subscription else RETENTION_FREE_PRODUCED_DAYS
    raise ValueError(f"Unknown media_type: {media_type!r} (expected one of {MEDIA_TYPES})")


def retention_config_snapshot() -> Dict[str, float]:
    """A plain dict of every currently-configured value -- used to
    snapshot s3_storage_cost_per_gb_day (and, for completeness, the
    retention durations) onto a billing log entry at the moment a cost is
    computed, so a later env var change can never retroactively change
    how an already-billed job reads in the audit trail."""
    return {
        "retention_free_source_days": RETENTION_FREE_SOURCE_DAYS,
        "retention_free_produced_days": RETENTION_FREE_PRODUCED_DAYS,
        "retention_subscriber_source_days": RETENTION_SUBSCRIBER_SOURCE_DAYS,
        "retention_subscriber_produced_days": RETENTION_SUBSCRIBER_PRODUCED_DAYS,
        "retention_temp_files_hours": RETENTION_TEMP_FILES_HOURS,
        "retention_notification_hours_before": RETENTION_NOTIFICATION_HOURS_BEFORE,
        "s3_storage_cost_per_gb_day": S3_STORAGE_COST_PER_GB_DAY,
    }
