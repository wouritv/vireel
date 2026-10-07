import os
import uuid
import math
import subprocess
import threading
import json
import hashlib
import base64
import shutil
import glob
import time
import asyncio
import aiofiles
import itertools
import secrets
import re
import ipaddress
import socket
import sys
import types
from datetime import datetime, timezone, timedelta, date
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from typing import Dict, Optional, List, Any, Annotated, Tuple, Literal
from contextlib import asynccontextmanager
from urllib.parse import urlparse, unquote, urlencode, quote
from urllib.request import Request as UrlRequest, urlopen, HTTPRedirectHandler, build_opener
from starlette.background import BackgroundTask
from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, Request, Header, BackgroundTasks, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, StreamingResponse
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from pydantic import BaseModel, Field
import jwt as pyjwt
from jwt import PyJWTError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
def _import_stripe():
    try:
        import stripe as stripe_module
        return stripe_module
    except ImportError:  # pragma: no cover - optional at import time
        return None


stripe = _import_stripe()
from s3_uploader import (
    upload_file_to_s3,
    generate_presigned_url,
    delete_s3_object,
    get_s3_object_size,
    download_s3_object,
)
from supabase_request import (
	insert_reels as supabase_insert_reels,
	list_reels as supabase_list_reels,
	get_reel as supabase_get_reel,
	get_reel_by_job_clip as supabase_get_reel_by_job_clip,
	update_reel_media_by_job_clip as supabase_update_reel_media_by_job_clip,
  update_reel_base_media_by_job_clip as supabase_update_reel_base_media_by_job_clip,
	soft_delete_reel as supabase_soft_delete_reel,
	insert_reel_visual as supabase_insert_reel_visual,
	list_reel_visuals as supabase_list_reel_visuals,
	get_reel_visual as supabase_get_reel_visual,
	update_reel_visual as supabase_update_reel_visual,
	delete_reel_visual as supabase_delete_reel_visual,
	insert_captions as supabase_insert_captions,
	list_captions as supabase_list_captions,
	get_caption as supabase_get_caption,
	get_caption_by_job_clip as supabase_get_caption_by_job_clip,
	get_caption_by_job_clip_any as supabase_get_caption_by_job_clip_any,
	update_caption as supabase_update_caption,
	soft_delete_caption as supabase_soft_delete_caption,
	is_supabase_configured,
	create_project as supabase_create_project,
	list_projects as supabase_list_projects,
	get_project as supabase_get_project,
	update_project as supabase_update_project,
	update_project_status as supabase_update_project_status,
	soft_delete_project as supabase_soft_delete_project,
	get_reels_by_project as supabase_get_reels_by_project,
	get_captions_by_project as supabase_get_captions_by_project,
	increment_project_output_count as supabase_increment_project_output_count,
	list_abonnements as supabase_list_abonnements,
	get_user_abonnement,
	get_abonnement as supabase_get_abonnement,
	insert_souscription as supabase_insert_souscription,
	get_souscription_by_reference as supabase_get_souscription_by_reference,
	get_client as supabase_get_client,
	get_user_data as supabase_get_user_data,
	upsert_user_data_credits as supabase_upsert_user_data_credits,
	set_user_data_balance as supabase_set_user_data_balance,
	zero_subscription_credit as supabase_zero_subscription_credit,
	set_user_max_daily_publications as supabase_set_user_max_daily_publications,
	consume_publish_quota as supabase_consume_publish_quota,
	deduct_user_credits as supabase_deduct_user_credits,
	insert_user_data_history as supabase_insert_user_data_history,
	upsert_user_data_history_entry as supabase_upsert_user_data_history_entry,
	get_user_data_history as supabase_get_user_data_history,
	get_latest_user_paid_subscription as supabase_get_latest_user_paid_subscription,
	update_souscription_row as supabase_update_souscription_row,
	list_user_souscriptions as supabase_list_user_souscriptions,
	list_souscriptions_due_for_monthly_credit_allocation as supabase_list_souscriptions_due_for_monthly_credit_allocation,
	add_one_month as supabase_add_one_month,
	update_job_record as supabase_update_job_record,
	get_job_record as supabase_get_job_record,
	count_active_jobs_for_user as supabase_count_active_jobs_for_user,
	list_active_jobs as supabase_list_active_jobs,
  get_latest_job_record_by_project as supabase_get_latest_job_record_by_project,
	get_transcription_by_job_clip as supabase_get_transcription_by_job_clip,
	upsert_transcription as supabase_upsert_transcription,
	update_transcription_translations_cache as supabase_update_transcription_translations_cache,
	insert_style_edit_version as supabase_insert_style_edit_version,
	list_style_edit_versions as supabase_list_style_edit_versions,
	delete_style_edit_versions as supabase_delete_style_edit_versions,
	insert_anonymous_story as supabase_insert_anonymous_story,
	list_anonymous_stories as supabase_list_anonymous_stories,
	get_anonymous_story as supabase_get_anonymous_story,
	get_anonymous_story_by_job as supabase_get_anonymous_story_by_job,
	update_anonymous_story as supabase_update_anonymous_story,
	soft_delete_anonymous_story as supabase_soft_delete_anonymous_story,
	get_anonymous_stories_by_project as supabase_get_anonymous_stories_by_project,
	insert_film_summary as supabase_insert_film_summary,
	list_film_summaries as supabase_list_film_summaries,
	get_film_summary as supabase_get_film_summary,
	update_film_summary as supabase_update_film_summary,
	soft_delete_film_summary as supabase_soft_delete_film_summary,
	get_film_summaries_by_project as supabase_get_film_summaries_by_project,
	list_caption_style_themes as supabase_list_caption_style_themes,
	upsert_caption_style_theme as supabase_upsert_caption_style_theme,
	delete_caption_style_theme as supabase_delete_caption_style_theme,
	list_reel_dates_since as supabase_list_reel_dates_since,
	list_caption_dates_since as supabase_list_caption_dates_since,
	list_anonymous_story_dates_since as supabase_list_anonymous_story_dates_since,
	list_film_summary_dates_since as supabase_list_film_summary_dates_since,
	SUPABASE_USER_DATA_HISTORY_TABLE,
	get_or_create_referral_code as supabase_get_or_create_referral_code,
	get_referral_code_owner as supabase_get_referral_code_owner,
	get_referral_by_referred_user as supabase_get_referral_by_referred_user,
	insert_referral as supabase_insert_referral,
	update_referral_row as supabase_update_referral_row,
	claim_referral_subscription_reward as supabase_claim_referral_subscription_reward,
	list_referrals_by_referrer as supabase_list_referrals_by_referrer,
	invalidate_referral as supabase_invalidate_referral,
	get_auth_user_created_at as supabase_get_auth_user_created_at,
	insert_promotional_credit_batch as supabase_insert_promotional_credit_batch,
	list_active_promotional_credit_batches as supabase_list_active_promotional_credit_batches,
	CREDIT_BATCH_TIER_PROMOTIONAL,
	CREDIT_BATCH_TIER_PURCHASED,
	revoke_promotional_credit_batches_by_source_reference as supabase_revoke_promotional_credit_batches_by_source_reference,
	insert_notification as supabase_insert_notification,
	list_notifications as supabase_list_notifications,
	mark_notification_read as supabase_mark_notification_read,
	mark_all_notifications_read as supabase_mark_all_notifications_read,
	insert_media_asset as supabase_insert_media_asset,
	get_media_asset_by_content as supabase_get_media_asset_by_content,
	list_media_assets_due_for_expiration as supabase_list_media_assets_due_for_expiration,
	mark_media_asset_expired as supabase_mark_media_asset_expired,
	mark_media_asset_deleted as supabase_mark_media_asset_deleted,
	list_produced_media_due_for_notification as supabase_list_produced_media_due_for_notification,
	list_media_assets_by_content_ids as supabase_list_media_assets_by_content_ids,
	mark_media_asset_notified as supabase_mark_media_asset_notified,
	CONTENT_KIND_PROJECT_SOURCE,
	CONTENT_KIND_REEL,
	CONTENT_KIND_CAPTION,
	CONTENT_KIND_FILM_SUMMARY,
	CONTENT_KIND_ANONYMOUS_STORY,
)
import anonymous_stories
import email_templates
import film_summary
import film_summary_render
from billing import (
    usd_to_credits,
    usd_to_final_credits,
    calculate_credits_for_operation,
    estimate_reel_cost_usd,
    estimate_caption_cost_usd,
    estimate_film_summary_analysis_cost_usd,
    estimate_film_summary_render_cost_usd,
    DEFAULT_REEL_CREDITS,
    DEFAULT_CAPTION_CREDITS,
    CREDIT_UNIT_PRICE_BY_DOLLAR,
    estimate_llm_usage_cost_usd,
    add_retention_cost_to_breakdown,
)
from retention_config import (
    resolve_retention_days,
    MEDIA_TYPE_SOURCE,
    MEDIA_TYPE_PRODUCED,
    S3_STORAGE_COST_PER_GB_DAY,
    RETENTION_TEMP_FILES_HOURS,
    RETENTION_NOTIFICATION_HOURS_BEFORE,
)
from job_manager import JobManager, JobType, calc_elapsed_seconds
from pipelines import ReelProcessingPipeline, CaptionProcessingPipeline
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Shared literals (audit: SonarQube python:S1192 -- avoid duplicating the
# same string in many places, since a future edit to one copy easily misses
# the others).
_METADATA_JSON_SUFFIX = "_metadata.json"
_METADATA_JSON_GLOB = "*_metadata.json"
_INVALID_OR_EXPIRED_SESSION_TOKEN = "Invalid or expired session token"
_CAPTIONS_PREFIX = "captions/"
_GEMINI_API_KEY_NOT_CONFIGURED = "Gemini API Key not configured on server (.env)"
_CONTENT_TYPE_JSON = "application/json"
_DEFAULT_UPLOAD_FILENAME = "upload.mp4"
_CLIP_INDEX_SUFFIX_PATTERN = r"_clip_(\d+)\.mp4$"
_JOB_NOT_FOUND = "Job not found"
_INVALID_INPUT_FILENAME = "Invalid input filename"
_CLIP_NOT_FOUND = "Clip not found"
_FACEBOOK_TOKEN_EXPIRED_OR_MISSING = "Facebook page access token expired or missing"
_FACEBOOK_TARGET_ID_MISSING = "Connected Facebook target id is missing"
_METADATA_NOT_FOUND = "Metadata not found"
_HTTPS_SCHEME_PREFIX = "https://"
_INVALID_SCHEDULED_DATE = "Invalid scheduled_date (expected ISO-8601)"
_SESSION_NOT_FOUND = "Session not found"
_SUPABASE_NOT_CONFIGURED = "Supabase is not configured"
_CAPTION_NOT_FOUND = "Caption not found"
_STORY_NOT_FOUND = "Anonymous story not found"
_STORIES_PREFIX = "anonymous_stories/"
_ANONYMOUS_STORIES_DISABLED = "Anonymous stories are not enabled on this deployment."
_FILM_SUMMARIES_PREFIX = "film_summaries/"
_PROJECTS_PREFIX = "projects/"
_FILM_SUMMARY_DISABLED = "Film summaries are not enabled on this deployment."
_FILM_SUMMARY_NOT_FOUND = "Film summary not found"
_SUPABASE_PROJECTS_NOT_CONFIGURED = "Supabase projects is not configured"
_PROJECT_NOT_FOUND = "Project not found"
_REEL_NOT_FOUND = "Reel not found"
_UNSUPPORTED_PLATFORM = "Unsupported platform"
_INVALID_PLAN_PRICE = "Invalid plan price"
_NO_MEDIA_URL_AVAILABLE = "No media URL available"


def _generic_error(
    log_message: str,
    exc: Exception,
    status_code: int = 500,
    detail: str = "Une erreur interne est survenue. Veuillez reessayer.",
) -> HTTPException:
    """Log the full exception server-side (with traceback) and return an
    HTTPException carrying only a generic, non-identifying message for the
    client. Raw exception text can leak internal file paths, library stack
    fragments, or upstream API error bodies to any caller (audit finding:
    information disclosure via error messages) -- callers should always
    `raise _generic_error(...) from exc` instead of `detail=str(exc)`.
    """
    logger.exception("%s: %s", log_message, exc)
    return HTTPException(status_code=status_code, detail=detail)


def _coded_error(status_code: int, code: str, message: str, **extra: Any) -> HTTPException:
    """Business-logic error with a stable machine-readable `code` alongside
    the English `message`, so the dashboard can show a translated message
    (see dashboard/src/pages/Settings.jsx's translateApiError) instead of
    this raw English text. `extra` carries values the translated message
    needs to interpolate (e.g. plan_change_over_limit's max/details)."""
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra})


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL", "noreply@vireel.co")

load_dotenv()

# Constants
UPLOAD_DIR = "uploads"
OUTPUT_DIR = "output"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Configuration
# Default to 1 if not set, but user can set higher for powerful servers
MAX_CONCURRENT_JOBS = int(os.environ.get("MAX_CONCURRENT_JOBS", "5"))
# Security: caps how many non-terminal (created/queued/processing/retry_wait)
# jobs a single user can have at once, independent of MAX_CONCURRENT_JOBS
# (which only throttles *execution*, not submission). Without this, one
# account could flood the queue, local disk, and S3 storage with an
# unbounded number of simultaneous submissions (see audit finding H7).
MAX_ACTIVE_JOBS_PER_USER = int(os.environ.get("MAX_ACTIVE_JOBS_PER_USER", "3"))
QUEUE_WORKER_COUNT = int(os.environ.get("QUEUE_WORKER_COUNT", "1"))
REEL_JOB_MAX_ATTEMPTS = int(os.environ.get("REEL_JOB_MAX_ATTEMPTS", "2"))
REEL_JOB_RETRY_DELAY_SECONDS = int(os.environ.get("REEL_JOB_RETRY_DELAY_SECONDS", "15"))
CAPTION_JOB_MAX_ATTEMPTS = int(os.environ.get("CAPTION_JOB_MAX_ATTEMPTS", "2"))
CAPTION_JOB_RETRY_DELAY_SECONDS = int(os.environ.get("CAPTION_JOB_RETRY_DELAY_SECONDS", "10"))
CAPTION_TRANSCRIBE_TIMEOUT_SECONDS = int(os.environ.get("CAPTION_TRANSCRIBE_TIMEOUT_SECONDS", "1800"))
MAX_FILE_SIZE_MB = 2048  # 2GB limit
REEL_MAX_DURATION_MINUTES = float(os.environ.get("REEL_MAX_DURATION", "180"))
# Security: hard ceiling on how long the main reel-generation subprocess may
# run before being killed. Without this, a pathological/adversarial input
# (a file or filter chain that makes ffmpeg/whisper/detection spin) could
# hang a worker slot indefinitely, and since MAX_CONCURRENT_JOBS is small,
# a handful of such jobs can starve the whole queue for every user (see
# security audit finding H13).
REEL_JOB_MAX_PROCESSING_SECONDS = int(os.environ.get("REEL_JOB_MAX_PROCESSING_SECONDS", str(4 * 3600)))
# Hard ceiling for individual ffmpeg/ffprobe subprocess calls elsewhere
# (thumbnail generation, format probing, single-clip edits) that are
# expected to be quick relative to the whole job.
FFPROBE_TIMEOUT_SECONDS = int(os.environ.get("FFPROBE_TIMEOUT_SECONDS", "60"))
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))
REEL_MAX_STORAGE_GB = float(os.environ.get("REEL_MAX_STORAGE", "15"))
CAPTION_MAX_DURATION_MINUTES = float(os.environ.get("CAPTION_MAX_DURATION", str(REEL_MAX_DURATION_MINUTES)))
CAPTION_MAX_STORAGE_GB = float(os.environ.get("CAPTION_MAX_STORAGE", str(REEL_MAX_STORAGE_GB)))
# Feature flag (spec section 17): lets ops disable the whole feature without
# a deploy while the pipeline is validated, or roll it out progressively.
ANONYMOUS_STORIES_ENABLED = os.environ.get("ANONYMOUS_STORIES_ENABLED", "true").lower() in ("1", "true", "yes")
# Independent of CAPTION_MAX_DURATION_MINUTES: anonymous stories reuse
# _validate_caption_source_constraints for its duration/size checks, but a
# testimonial video is a different kind of source than a caption job's --
# tightening CAPTION_MAX_DURATION for captions (e.g. down to 30min) must
# not also cap how long a story's source video can be.
ANONYMOUS_STORY_MAX_DURATION_MINUTES = float(os.environ.get("ANONYMOUS_STORY_MAX_DURATION", "180"))
STORY_JOB_MAX_ATTEMPTS = 1  # no dedicated retry worker for this queue -- see _run_anonymous_story_job

# Film Summary ("Resume de film") configuration -- spec section 4 "Variables
# de configuration proposees". Every numeric limit is environment-driven
# (never hardcoded) and re-exposed to the frontend via GET /api/config.
FILM_SUMMARY_ENABLED = os.environ.get("FILM_SUMMARY_ENABLED", "true").lower() in ("1", "true", "yes")
FILM_SUMMARY_MAX_SOURCE_DURATION_SECONDS = float(os.environ.get("FILM_SUMMARY_MAX_SOURCE_DURATION_SECONDS", str(4 * 3600)))
FILM_SUMMARY_MIN_SOURCE_DURATION_SECONDS = float(os.environ.get("FILM_SUMMARY_MIN_SOURCE_DURATION_SECONDS", "600"))
FILM_SUMMARY_MAX_UPLOAD_SIZE_BYTES = float(os.environ.get("FILM_SUMMARY_MAX_UPLOAD_SIZE_BYTES", str(20 * 1024 ** 3)))
FILM_SUMMARY_MIN_TARGET_DURATION_SECONDS = float(os.environ.get("FILM_SUMMARY_MIN_TARGET_DURATION_SECONDS", "180"))
FILM_SUMMARY_MAX_TARGET_DURATION_SECONDS = float(os.environ.get("FILM_SUMMARY_MAX_TARGET_DURATION_SECONDS", "1200"))
FILM_SUMMARY_ALLOWED_MIME_TYPES = [
    v.strip() for v in os.environ.get(
        "FILM_SUMMARY_ALLOWED_MIME_TYPES", "video/mp4,video/quicktime,video/x-matroska,video/webm",
    ).split(",") if v.strip()
]
FILM_SUMMARY_VALIDATION_THRESHOLD = float(os.environ.get("FILM_SUMMARY_VALIDATION_THRESHOLD", "0.75"))
FILM_SUMMARY_SCENE_THRESHOLD = float(os.environ.get("FILM_SUMMARY_SCENE_THRESHOLD", "27.0"))
# PySceneDetect decodes the source frame-by-frame with no progress
# callback and no timeout of its own -- on a slow/oddly-encoded source this
# can run far longer than the job is realistically ever going to finish,
# stalling the job at "detecting_scenes" forever with no error surfaced to
# the user. Bounded here so a stuck decode fails the job (SCENE_DETECTION_
# FAILED, retryable) instead of hanging silently.
FILM_SUMMARY_SCENE_DETECTION_TIMEOUT_SECONDS = int(os.environ.get("FILM_SUMMARY_SCENE_DETECTION_TIMEOUT_SECONDS", "1800"))
FILM_SUMMARY_DURATION_TOLERANCE_RATIO = float(os.environ.get("FILM_SUMMARY_DURATION_TOLERANCE_RATIO", "0.15"))
FILM_SUMMARY_TTS_MODEL = os.environ.get("FILM_SUMMARY_TTS_MODEL", "gpt-4o-mini-tts")
FILM_SUMMARY_TTS_DEFAULT_VOICE = os.environ.get("FILM_SUMMARY_TTS_DEFAULT_VOICE", "cedar")
FILM_SUMMARY_JOB_MAX_ATTEMPTS = int(os.environ.get("FILM_SUMMARY_JOB_MAX_ATTEMPTS", "2"))
# Fixed demo line synthesized once per voice for the create-form's "listen
# before choosing" preview (see get_film_summary_voice_preview_endpoint) --
# a single canned sentence, independent of the film's own narration
# language, since the point is to hear the voice's timbre, not the language.
FILM_SUMMARY_VOICE_PREVIEW_TEXT = os.environ.get(
    "FILM_SUMMARY_VOICE_PREVIEW_TEXT",
    "Bonjour, je suis la voix qui pourra raconter le resume de votre film.",
)

VIREEL_VIDEO_FORMAT = os.environ.get("VIREEL_VIDEO_FORMAT", "mp4,mov,avi")
# How long a job's local temp artifacts (FFmpeg intermediates, extracted
# frames/chunks, local uploads, finished-job output dirs) stick around
# before cleanup -- see RETENTION_TEMP_FILES_HOURS / process_temp_file_
# cleanup_jobs. This is the ONLY category RETENTION_TEMP_FILES_HOURS
# governs: it's unrelated to the per-media S3 retention durations
# (RETENTION_FREE_*/RETENTION_SUBSCRIBER_*), which apply only to the
# user-facing, S3-persisted media the retention/expiration sweep manages.
JOB_RETENTION_SECONDS = RETENTION_TEMP_FILES_HOURS * 3600
OUTPUT_SWEEP_INTERVAL_SECONDS = int(os.environ.get("OUTPUT_SWEEP_INTERVAL_SECONDS", str(6 * 3600)))
OUTPUT_SWEEP_MIN_AGE_SECONDS = int(os.environ.get("OUTPUT_SWEEP_MIN_AGE_SECONDS", "1800"))
SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS = int(os.environ.get("SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS", "10"))
# Granularity is a monthly anniversary, so polling once a day is plenty --
# this only decides how late a refill can run past its due date, not
# whether it runs at all (see process_annual_credit_refill_jobs).
ANNUAL_CREDIT_REFILL_INTERVAL_SECONDS = int(os.environ.get("ANNUAL_CREDIT_REFILL_INTERVAL_SECONDS", str(24 * 3600)))
# How often the two media-retention sweeps run -- NOT how long anything is
# kept (that's RETENTION_FREE_*/RETENTION_SUBSCRIBER_*/RETENTION_NOTIFICATION_
# HOURS_BEFORE in retention_config.py); this only decides how promptly an
# already-due expiration/notification is acted on.
MEDIA_EXPIRATION_SWEEP_INTERVAL_SECONDS = int(os.environ.get("MEDIA_EXPIRATION_SWEEP_INTERVAL_SECONDS", "300"))
MEDIA_EXPIRY_NOTIFICATION_SWEEP_INTERVAL_SECONDS = int(os.environ.get("MEDIA_EXPIRY_NOTIFICATION_SWEEP_INTERVAL_SECONDS", str(3600)))
# Referral program -- the backend is the sole source of truth for these
# amounts (see /api/referrals/config); the frontend never hardcodes them.
REFERRAL_SIGNUP_BONUS_CREDITS = float(os.environ.get("REFERRAL_SIGNUP_BONUS_CREDITS", "50") or "50")
REFERRAL_MONTHLY_BONUS_CREDITS = float(os.environ.get("REFERRAL_MONTHLY_BONUS_CREDITS", "100") or "100")
REFERRAL_ANNUAL_BONUS_CREDITS = float(os.environ.get("REFERRAL_ANNUAL_BONUS_CREDITS", "300") or "300")
PROMOTIONAL_CREDITS_EXPIRATION_DAYS = int(os.environ.get("PROMOTIONAL_CREDITS_EXPIRATION_DAYS", "60") or "60")
# A directly-purchased credit top-up (_handle_credit_purchase) -- unlike
# subscription credit, which resets every billing cycle, a paid top-up
# keeps its own validity window, independent of and typically much longer
# than the promotional one above.
PURCHASED_CREDITS_EXPIRATION_DAYS = int(os.environ.get("PURCHASED_CREDITS_EXPIRATION_DAYS", "365") or "365")
# This codebase has no signup webhook/trigger on auth.users (accounts are
# created directly by the frontend's Supabase Auth SDK call, never via a
# backend endpoint) -- the referral-association endpoint instead verifies
# "is this account genuinely brand new" by checking the Auth account's own
# created_at against this grace window (see get_auth_user_created_at),
# generous enough to cover an OAuth provider round-trip plus any page
# reload, while still rejecting an existing account trying to retroactively
# attach a referrer long after signing up.
REFERRAL_ASSOCIATION_WINDOW_MINUTES = int(os.environ.get("REFERRAL_ASSOCIATION_WINDOW_MINUTES", "60") or "60")
ADMIN_API_SECRET = os.environ.get("ADMIN_API_SECRET", "")
DISABLE_YOUTUBE_URL = os.environ.get("DISABLE_YOUTUBE_URL", "false").lower() in ("1", "true", "yes")
HIDE_SOCIAL_PLATFORMS = os.environ.get("HIDE_SOCIAL_PLATFORMS", "false").lower() in ("1", "true", "yes")
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "eur").lower()
STRIPE_SUCCESS_URL = os.environ.get("STRIPE_SUCCESS_URL", "")
STRIPE_CANCEL_URL = os.environ.get("STRIPE_CANCEL_URL", "")
STORAGE_RETENTION_PERIODE_DAYS = max(0, int(os.environ.get("STORAGE_RETENTION_PERIODE", "7") or "7"))
MIN_OPERATION_START_CREDITS = float(os.environ.get("MIN_OPERATION_START_CREDITS", "1"))

# Social publishing constants
ALLOWED_YT_PRIVACY = {"public", "private", "unlisted"}
YT_CHUNK_SIZE = 8 * 1024 * 1024
YT_MAX_RETRIES_PER_CHUNK = 3
LINKEDIN_API_VERSION = os.environ.get("LINKEDIN_API_VERSION", "202607")  # YYYYMM, à mettre à jour périodiquement
LINKEDIN_MAX_RETRIES_PER_PART = 3
EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
EXPORT_AUDIO_BITRATE = os.environ.get("VIREEL_EXPORT_AUDIO_BITRATE", "192k")
PLATFORM_CONFIG = {
    "linkedin": {
        "auth_url": "https://www.linkedin.com/oauth/v2/authorization",
        "token_url": "https://www.linkedin.com/oauth/v2/accessToken",
        "client_id": os.getenv("LINKEDIN_CLIENT_ID"),
        "client_secret": os.getenv("LINKEDIN_CLIENT_SECRET"),
        # No analytics scope is requested here: real LinkedIn analytics
        # (page/post insights) require the LinkedIn Marketing Developer
        # Platform, a separate partner/developer approval process that
        # cannot be obtained by writing code -- see
        # _get_social_insights_for_account, which reports this platform as
        # unsupported for the analytics feature rather than silently
        # returning nothing.
        "scopes": ["w_member_social", "openid", "profile","email"],
    },
    "facebook": {
        "auth_url": "https://www.facebook.com/v19.0/dialog/oauth",
        "token_url": "https://graph.facebook.com/v19.0/oauth/access_token",
        "client_id": os.getenv("FACEBOOK_CLIENT_ID"),
        "client_secret": os.getenv("FACEBOOK_CLIENT_SECRET"),
        # pages_manage_engagement is required for the Page itself to comment
        # on its own posts (POST /{post_id}/comments with the Page token --
        # see _post_facebook_comment) -- pages_manage_posts alone only
        # covers creating the post. Meta requires pages_read_user_content to
        # be requested alongside pages_manage_engagement (its App Review
        # docs state the submission must include pages_show_list and
        # pages_read_user_content to use pages_manage_engagement).
        # read_insights is required for the Page Insights /insights edge
        # used by the social analytics dashboard block (see
        # _fetch_facebook_page_insights) -- pages_read_engagement alone does
        # not cover it.
        "scopes": [
            "pages_show_list", "pages_manage_posts", "pages_read_engagement",
            "pages_manage_engagement", "pages_read_user_content", "read_insights",
        ],
    },
    "instagram": {
        "auth_url": "https://www.instagram.com/oauth/authorize",
        "token_url": "https://api.instagram.com/oauth/access_token",
        "long_lived_token_url": "https://graph.instagram.com/access_token",
        "client_id": os.getenv("INSTAGRAM_APP_ID"),
        "client_secret": os.getenv("INSTAGRAM_APP_SECRET"),
        # publish_to_instagram/publish_to_instagram_image (content_publish)
        # and identity lookup at connect time (basic) are the only ones the
        # app's own endpoints call today. manage_messages/manage_comments
        # were requested but never used by any endpoint -- dropped so App
        # Review isn't asked to approve permissions with no real use case
        # to demonstrate. manage_insights is kept deliberately (planned
        # analytics use) despite the same gap.
        # instagram_business_manage_insights is required by the social
        # analytics dashboard block added alongside
        # _fetch_instagram_insights (the /insights edge on an Instagram
        # Business/Creator account) -- keep it even if it looks unused by
        # publishing itself, a future cleanup pass should not remove it
        # again.
        "scopes": [
            "instagram_business_basic",
            "instagram_business_content_publish",
            "instagram_business_manage_insights",
        ],
    },
    "youtube": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": os.getenv("YOUTUBE_CLIENT_ID"),
        "client_secret": os.getenv("YOUTUBE_CLIENT_SECRET"),
        # yt-analytics.readonly is required for the separate YouTube
        # Analytics API (_fetch_youtube_analytics) -- youtube.readonly only
        # covers the Data API and does not grant access to Analytics reports.
        # yt-analytics-monetary.readonly is a further separate scope needed
        # only for revenue/ad metrics (_fetch_youtube_monetization) -- Google
        # treats it as sensitive, so accounts connected before this scope was
        # added must reconnect to grant it, and it also requires the channel
        # to be a YouTube Partner Program member; missing either just means
        # no monetization data, not an error (see _fetch_youtube_monetization).
        "scopes": [
            "https://www.googleapis.com/auth/youtube.upload",
            "https://www.googleapis.com/auth/youtube.readonly",
            "https://www.googleapis.com/auth/yt-analytics.readonly",
            "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
        ],
    },
    "tiktok": {
        "auth_url": "https://www.tiktok.com/v2/auth/authorize",
        "token_url": "https://open.tiktokapis.com/v2/oauth/token/",
        "client_id": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        # No analytics scope is requested here: real TikTok analytics
        # require the TikTok Business API, a separate partner/developer
        # approval process that cannot be obtained by writing code -- see
        # _get_social_insights_for_account, which reports this platform as
        # unsupported for the analytics feature rather than silently
        # returning nothing.
        "scopes": ["video.upload", "user.info.basic"],
    },
}

def _configure_stripe() -> None:
    if stripe and STRIPE_SECRET_KEY:
        stripe.api_key = STRIPE_SECRET_KEY


_configure_stripe()

# Application State
job_queue: asyncio.PriorityQueue[tuple[int, int, str]] = asyncio.PriorityQueue()
job_queue_seq = itertools.count()
JOB_PRIORITY_MIN = 1
JOB_PRIORITY_MAX = 3
DEFAULT_JOB_PRIORITY = 1
jobs: Dict[str, Dict] = {}
thumbnail_sessions: Dict[str, Dict] = {}
publish_jobs: Dict[str, Dict] = {}  # {publish_id: {status, result, error}}
# Semester to limit concurrency to MAX_CONCURRENT_JOBS
concurrency_semaphore = asyncio.Semaphore(MAX_CONCURRENT_JOBS)
reel_job_manager = JobManager(queue_name="reels")
running_reel_jobs: Dict[str, Dict[str, Any]] = {}
running_reel_jobs_lock = asyncio.Lock()

# Strong references to fire-and-forget background tasks. asyncio only holds
# a weak reference to a Task once nothing else references it, so a bare
# `asyncio.create_task(...)` whose return value is discarded can have its
# task garbage-collected mid-run, silently dropping the work (see the
# asyncio.create_task docs' own warning about this). Every fire-and-forget
# task in this module is created via _spawn_background_task so it can't be
# collected before it finishes.
_background_tasks: set = set()


def _spawn_background_task(coro) -> Optional["asyncio.Task"]:
    task = asyncio.create_task(coro)
    if task is not None:  # NOSONAR(S5727) real asyncio.create_task never returns None, but some tests monkeypatch it to return None to skip background dispatch -- this guard is what keeps that test double from crashing on .add_done_callback
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    return task

def _load_secret_key() -> str:
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY manquant dans l'environnement")
    return secret_key


SECRET_KEY = _load_secret_key()

_oauth_serializer = URLSafeTimedSerializer(SECRET_KEY)

# Supabase issues JWTs for authenticated sessions signed either with a legacy
# shared secret (HS256) or, for newer projects, with an asymmetric signing
# key (ES256) verified via the project's public JWKS endpoint. Which one
# applies is a per-project setting (Project Settings -> API -> JWT Settings),
# so both are supported here based on the `alg` in the token's own header --
# see _verify_supabase_jwt. SUPABASE_JWT_SECRET is distinct from
# SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY and only used for HS256.
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")
SUPABASE_URL_FOR_JWKS = (os.getenv("SUPABASE_URL") or "").rstrip("/")

# Lets a single deployment (the demo instance) restrict itself to a fixed
# list of emails without touching Supabase Auth's own sign-up settings or
# forking the codebase -- unset/empty (the expected production
# configuration) makes _enforce_demo_allowlist a complete no-op, so the
# exact same image can run as both the open production deployment and a
# gated demo one, differing only by this env var.
DEMO_ALLOWED_EMAILS = {
    e.strip().lower() for e in os.environ.get("DEMO_ALLOWED_EMAILS", "").split(",") if e.strip()
}
_DEMO_ACCOUNT_NOT_AUTHORIZED = "This account is not authorized on this deployment."


def _validate_supabase_jwt_config() -> None:
    if not SUPABASE_JWT_SECRET and not SUPABASE_URL_FOR_JWKS:
        raise RuntimeError(
            "Ni SUPABASE_JWT_SECRET ni SUPABASE_URL ne sont definis -- l'un des deux "
            "est requis pour verifier les tokens de session Supabase (sans cela, "
            "aucune requete ne peut etre authentifiee de maniere fiable)."
        )


_validate_supabase_jwt_config()

_supabase_jwks_client: Optional["pyjwt.PyJWKClient"] = None


def _get_supabase_jwks_client() -> "pyjwt.PyJWKClient":
    global _supabase_jwks_client
    if _supabase_jwks_client is None:
        if not SUPABASE_URL_FOR_JWKS:
            raise RuntimeError(
                "SUPABASE_URL manquant dans l'environnement -- requis pour verifier "
                "les tokens de session signes en ES256 via le JWKS du projet Supabase."
            )
        _supabase_jwks_client = pyjwt.PyJWKClient(
            f"{SUPABASE_URL_FOR_JWKS}/auth/v1/.well-known/jwks.json"
        )
    return _supabase_jwks_client

router = APIRouter()


def _is_pytest_runtime() -> bool:
    return "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in os.environ

def _load_frontend_origin() -> str:
    origin = os.environ.get("FRONTEND_ORIGIN")
    if origin:
        return origin
    if _is_pytest_runtime():
        # Test fallback: explicit non-wildcard origin keeps postMessage target strict.
        origin = "http://localhost"
        logger.warning("FRONTEND_ORIGIN not set; using test fallback '%s'", origin)
        return origin
    raise RuntimeError(
        "FRONTEND_ORIGIN must be set (exact frontend origin, e.g. 'https://app.vireel.com') "
        "-- postMessage must never target '*' when carrying selection data."
    )


FRONTEND_ORIGIN = _load_frontend_origin()

_PAGE_SELECTION_TTL_SECONDS = 600  # 10 minutes pour que l'utilisateur choisisse une page

def _load_encryption_key_raw() -> str:
    raw = os.environ.get("ENCRYPTION_KEY", "")
    if raw and len(raw) >= 16:
        return raw
    if _is_pytest_runtime():
        raw = raw or "unit-test-encryption-key-not-for-prod"
        logger.warning("ENCRYPTION_KEY missing/too short; using test fallback")
        return raw
    raise RuntimeError(
        "ENCRYPTION_KEY manquant ou trop court (16 caracteres minimum) -- "
        "requis pour chiffrer les tokens OAuth (YouTube/TikTok/...) stockes "
        "en base. L'application refuse de demarrer plutot que de stocker "
        "des tokens en clair ou faiblement proteges."
    )


_ENCRYPTION_KEY_RAW = _load_encryption_key_raw()

def _load_oauth_state_secret() -> str:
    secret = os.environ.get("OAUTH_STATE_SECRET")
    if secret:
        return secret
    # Keep startup resilient: reuse SECRET_KEY when a dedicated OAuth state secret is absent.
    if _is_pytest_runtime():
        logger.warning("OAUTH_STATE_SECRET not set; using SECRET_KEY as test fallback")
    else:
        logger.warning("OAUTH_STATE_SECRET not set; using SECRET_KEY fallback")
    return SECRET_KEY


_oauth_state_secret = _load_oauth_state_secret()

_page_selection_serializer = URLSafeTimedSerializer(
    _oauth_state_secret,  # réutilise ta clé secrète OAuth existante
    salt="fb-page-selection",
)

def _relocate_root_job_artifacts(job_id: str, job_output_dir: str) -> bool:
    """
    Backward-compat rescue:
    If main.py accidentally wrote metadata/clips into OUTPUT_DIR root (e.g. output/<jobid>_...),
    move them into output/<job_id>/ so the API can find and serve them.
    """
    try:
        os.makedirs(job_output_dir, exist_ok=True)
        root = OUTPUT_DIR
        pattern = os.path.join(root, f"{job_id}_*_metadata.json")
        meta_candidates = sorted(glob.glob(pattern), key=lambda p: os.path.getmtime(p), reverse=True)
        if not meta_candidates:
            return False

        # Move the newest metadata and its associated clips.
        metadata_path = meta_candidates[0]
        base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")

        # Move metadata
        dest_metadata = os.path.join(job_output_dir, os.path.basename(metadata_path))
        if os.path.abspath(metadata_path) != os.path.abspath(dest_metadata):
            shutil.move(metadata_path, dest_metadata)

        # Move any clips that match the same base_name into the job folder
        clip_pattern = os.path.join(root, f"{base_name}_clip_*.mp4")
        for clip_path in glob.glob(clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        # Also move any temp_ clips that might remain
        temp_clip_pattern = os.path.join(root, f"temp_{base_name}_clip_*.mp4")
        for clip_path in glob.glob(temp_clip_pattern):
            dest_clip = os.path.join(job_output_dir, os.path.basename(clip_path))
            if os.path.abspath(clip_path) != os.path.abspath(dest_clip):
                shutil.move(clip_path, dest_clip)

        return True
    except Exception:
        return False


def _cleanup_directory(path: str) -> None:
    """Best-effort recursive cleanup for ephemeral processing artifacts."""
    try:
        if path and os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def _resolve_job_metadata_path(job_id: str) -> Optional[str]:
    """Find metadata JSON for a job, including legacy root-output layouts."""
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
    if json_files:
        return json_files[0]

    # Backward-compat rescue for artifacts emitted into OUTPUT_DIR root.
    if _relocate_root_job_artifacts(job_id, output_dir):
        json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
        if json_files:
            return json_files[0]

    # Last-chance fallback: read directly from root if relocation could not run.
    root_candidates = sorted(
        glob.glob(os.path.join(OUTPUT_DIR, f"{job_id}_*_metadata.json")),
        key=lambda path: os.path.getmtime(path),
        reverse=True,
    )
    if root_candidates:
        return root_candidates[0]

    return None


def _estimate_transcript_duration_seconds(transcript: Dict[str, Any]) -> float:
    segments = (transcript or {}).get("segments") or []
    max_end = 0.0
    for seg in segments:
        try:
            max_end = max(max_end, float(seg.get("end", 0) or 0))
        except Exception:
            continue

    try:
        meta_seconds = float(((transcript or {}).get("meta") or {}).get("audio_seconds", 0) or 0)
    except Exception:
        meta_seconds = 0.0

    return max(max_end, meta_seconds)


def _verify_supabase_jwt(token: str) -> str:
    """Verify a Supabase-issued access token and return the authenticated user's id.

    Security note: this is the ONLY source of truth for user identity in this
    application. Client-supplied identity headers (e.g. X-User-Id) must never
    be trusted on their own -- they are not proof of anything, since any
    client can set an arbitrary value. The `sub` claim of a JWT that verifies
    either against SUPABASE_JWT_SECRET (legacy HS256 projects) or against the
    project's own public key fetched from its JWKS endpoint (newer ES256/
    RS256 projects) is proof, because only Supabase Auth (which authenticated
    the user's login) could have produced a valid signature. Which path
    applies is read from the token's own header, never trusted from outside
    it: HS256 is only ever checked against our dedicated shared secret, and
    ES256/RS256 only ever against the real public key looked up by `kid` from
    Supabase's JWKS, so the two verification paths can't be crossed to forge
    a signature (no alg-confusion between a public key and a shared secret).
    """
    try:
        # Sonar false positive (S5659): this only peeks at the `alg` header to pick
        # which key to verify against below -- pyjwt.decode() a few lines
        # down always performs full signature verification (never called
        # with verify_signature=False), against a key matched exactly to
        # the algorithm read here (see the docstring above for why that
        # pairing can't be crossed to forge a signature).
        alg = pyjwt.get_unverified_header(token).get("alg")  # NOSONAR
        if alg == "HS256":
            if not SUPABASE_JWT_SECRET:
                raise HTTPException(status_code=401, detail=_INVALID_OR_EXPIRED_SESSION_TOKEN)
            payload = pyjwt.decode(
                token,
                SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        elif alg in ("ES256", "RS256"):
            signing_key = _get_supabase_jwks_client().get_signing_key_from_jwt(token)
            payload = pyjwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                options={"require": ["exp", "sub"]},
            )
        else:
            raise HTTPException(status_code=401, detail=_INVALID_OR_EXPIRED_SESSION_TOKEN)
    except HTTPException:
        raise
    except PyJWTError as exc:
        logger.warning("Supabase JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail=_INVALID_OR_EXPIRED_SESSION_TOKEN) from exc

    user_id = str(payload.get("sub") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid session token: missing subject")

    if DEMO_ALLOWED_EMAILS:
        email = str(payload.get("email") or "").strip().lower()
        if email not in DEMO_ALLOWED_EMAILS:
            raise HTTPException(status_code=403, detail=_DEMO_ACCOUNT_NOT_AUTHORIZED)

    return user_id


def get_user_id_header(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
) -> str:
    """FastAPI dependency resolving the authenticated caller's user id.

    Requires a verified Supabase JWT (`Authorization: Bearer <access_token>`).
    The legacy `X-User-Id` header is intentionally never consulted here: it is
    a plain client-supplied string with no cryptographic proof behind it, so
    trusting it would let any caller impersonate any other user.
    """
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")
    return _verify_supabase_jwt(token)


def get_user_id_header_or_query_token(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
    token: Annotated[Optional[str], Query()] = None,
) -> str:
    """Same verified-JWT identity check as get_user_id_header, but also
    accepts the token via a `token` query parameter.

    Reserved for endpoints the browser loads directly from markup (<video
    src>, <img src>) rather than via fetch() -- those requests never carry
    custom headers, including Authorization, so the header-only check would
    always reject real playback. Every caller is still required to present
    a genuinely valid Supabase JWT either way; only the transport differs.
    """
    scheme, _, header_token = (authorization or "").partition(" ")
    if scheme.lower() == "bearer" and header_token:
        return _verify_supabase_jwt(header_token)
    if token:
        return _verify_supabase_jwt(token)
    raise HTTPException(status_code=401, detail="Missing Authorization Bearer token")


def _get_authenticated_user_id_optional(request: Request) -> Optional[str]:
    """Best-effort verified caller identity for endpoints that use it only as a
    lookup hint (never for access control). Returns None rather than raising
    when no valid Bearer token is present -- callers must not treat this as an
    authorization decision, only as an optional cache/lookup key. Never falls
    back to the unverified X-User-Id header.
    """
    authorization = request.headers.get("Authorization") or request.headers.get("authorization")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    try:
        return _verify_supabase_jwt(token)
    except HTTPException:
        return None

_ISO_UTC_OFFSET_SUFFIX = "+00:00"


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Accept both native ISO and trailing Z formats.
    if text.endswith("Z"):
        text = text[:-1] + _ISO_UTC_OFFSET_SUFFIX
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolve_scheduled_datetime(value: Any, timezone_name: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Already timezone-aware (offset or trailing Z)
    if text.endswith("Z") or "+" in text[10:] or "-" in text[10:]:
        return _parse_iso_datetime(text)

    # Naive local datetime -> interpret with provided timezone
    try:
        naive = datetime.fromisoformat(text)
    except Exception:
        return None

    if naive.tzinfo is not None:
        return naive.astimezone(timezone.utc)

    tz_name = (timezone_name or "UTC").strip() or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return naive.replace(tzinfo=tz).astimezone(timezone.utc)


def _clamp_job_priority(value: Any) -> int:
    try:
        raw = int(value)
    except Exception:
        raw = DEFAULT_JOB_PRIORITY
    return max(JOB_PRIORITY_MIN, min(JOB_PRIORITY_MAX, raw))


async def _resolve_user_job_priority(user_id: str) -> int:
    if not user_id or not is_supabase_configured():
        return DEFAULT_JOB_PRIORITY
    try:
        active = await get_user_abonnement(user_id)
        if not active:
            return DEFAULT_JOB_PRIORITY
        return _clamp_job_priority(active.get("priorite"))
    except Exception:
        return DEFAULT_JOB_PRIORITY


def _preemption_sort_key(ctx: Dict[str, Any]) -> tuple[int, float]:
    priority = _clamp_job_priority(ctx.get("priority", DEFAULT_JOB_PRIORITY))
    started_at = float(ctx.get("started_at", 0.0) or 0.0)
    return (priority, started_at)


def _get_preemption_candidate() -> Optional[Dict[str, Any]]:
    if not running_reel_jobs:
        return None

    candidate_job_id, candidate_ctx = min(
        running_reel_jobs.items(),
        key=lambda item: _preemption_sort_key(item[1]),
    )
    return {
        "job_id": candidate_job_id,
        "ctx": candidate_ctx,
        "priority": _clamp_job_priority(candidate_ctx.get("priority", DEFAULT_JOB_PRIORITY)),
    }


async def _maybe_preempt_lower_priority_running_job(incoming_priority: int, incoming_job_id: str) -> None:
    incoming_priority = _clamp_job_priority(incoming_priority)
    async with running_reel_jobs_lock:
        if len(running_reel_jobs) < MAX_CONCURRENT_JOBS:
            return

        candidate = _get_preemption_candidate()
        if not candidate:
            return

        candidate_job_id = candidate["job_id"]
        candidate_priority = candidate["priority"]
        if incoming_priority <= candidate_priority:
            return

        ctx = candidate["ctx"]
        ctx["preempt_requested"] = True
        process = ctx.get("process")

        if candidate_job_id in jobs:
            jobs[candidate_job_id]["logs"].append(
                f"Preemption requested by higher-priority job {incoming_job_id} (priority {incoming_priority})."
            )

        if process and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass


async def enqueue_reel_job(job_id: str, priority: Optional[int] = None) -> None:
    runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id) or {}
    final_priority = _clamp_job_priority(
        priority if priority is not None else runtime_job.get("priority", DEFAULT_JOB_PRIORITY)
    )
    runtime_job["priority"] = final_priority
    if job_id in reel_job_manager.runtime_jobs:
        reel_job_manager.runtime_jobs[job_id]["priority"] = final_priority
    if job_id in jobs:
        jobs[job_id]["priority"] = final_priority

    await _maybe_preempt_lower_priority_running_job(final_priority, job_id)
    await job_queue.put((-final_priority, next(job_queue_seq), job_id))


async def _schedule_reel_retry(job_id: str, delay_seconds: int) -> None:
    await asyncio.sleep(max(0, int(delay_seconds)))
    await reel_job_manager.retry_job(job_id)
    runtime = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id) or {}
    await enqueue_reel_job(job_id, priority=runtime.get("priority", DEFAULT_JOB_PRIORITY))


async def _ensure_retention_deadline_on_subscription(
    latest_subscription: Dict[str, Any],
    retention_deadline: datetime,
) -> None:
    subscription_id = latest_subscription.get("id")
    if subscription_id and not latest_subscription.get("retention_deadline_at"):
        await supabase_update_souscription_row(
            str(subscription_id),
            {"retention_deadline_at": retention_deadline.isoformat()},
            user_id=latest_subscription.get("userid"),
        )


async def _zero_balances_on_subscription_expiration(
    user_id: str,
    latest_subscription: Dict[str, Any],
) -> None:
    user_data = await supabase_get_user_data(user_id) or {}
    current_credit = float(user_data.get("credit") or 0.0)
    current_storage = float(user_data.get("stockage") or 0.0)

    if current_credit > 0.0 or current_storage > 0.0:
        await supabase_set_user_data_balance(user_id=user_id, credit=0.0, storage=0.0)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=current_credit,
            storage=current_storage,
            operation="output",
            operation_type="subscription_expiration",
            operation_id=str(latest_subscription.get("id") or ""),
        )


async def _disable_subscription_account_if_needed(
    latest_subscription: Dict[str, Any],
    now_utc: datetime,
    retention_deadline: datetime,
) -> None:
    subscription_id = latest_subscription.get("id")
    if subscription_id and not latest_subscription.get("account_disabled_at"):
        await supabase_update_souscription_row(
            str(subscription_id),
            {
                "account_disabled_at": now_utc.isoformat(),
                "retention_deadline_at": retention_deadline.isoformat(),
            },
            user_id=latest_subscription.get("userid"),
        )


async def _enforce_subscription_retention_policy(user_id: str) -> Dict[str, Any]:
    """Apply subscription retention policy and zero balances after retention deadline."""
    if not user_id or not is_supabase_configured():
        return {"state": "skipped"}

    active = await get_user_abonnement(user_id)
    if active:
        return {"state": "active", "subscription": active}

    latest = await supabase_get_latest_user_paid_subscription(user_id)
    if not latest:
        return {"state": "no_subscription"}

    end_date = _parse_iso_datetime(latest.get("payment_end_date"))
    if not end_date:
        return {"state": "no_subscription_end", "subscription": latest}

    now_utc = datetime.now(timezone.utc)
    retention_deadline = end_date + timedelta(days=STORAGE_RETENTION_PERIODE_DAYS)
    await _ensure_retention_deadline_on_subscription(latest, retention_deadline)

    if now_utc <= retention_deadline:
        return {
            "state": "retention_window",
            "subscription": latest,
            "retention_deadline_at": retention_deadline.isoformat(),
        }

    await _zero_balances_on_subscription_expiration(user_id, latest)
    await _disable_subscription_account_if_needed(latest, now_utc, retention_deadline)

    return {
        "state": "disabled",
        "subscription": latest,
        "retention_deadline_at": retention_deadline.isoformat(),
    }


async def _resolve_reel_input_url(job_id: str, clip_index: int) -> Optional[str]:
    if not is_supabase_configured():
        return None

    try:
        row = await supabase_get_reel_by_job_clip(job_id, clip_index)
    except Exception as e:
        print(f"⚠️ Supabase reel lookup failed for metadata hydration: {e}")
        return None

    if not row:
        return None

    # Prefer a fresh presigned URL from S3 key; fallback to stored URL.
    return _reel_media_url_from_s3_key(row.get("reel_s3_key") or "") or row.get("reel_url") or None


async def _resolve_caption_input_url(job_id: str, clip_index: int, user_id: Optional[str] = None) -> Optional[str]:
    if not is_supabase_configured():
        return None

    try:
        row = None
        if user_id:
            row = await supabase_get_caption_by_job_clip(job_id, int(clip_index), user_id)
        if not row:
            row = await supabase_get_caption_by_job_clip_any(job_id, int(clip_index))
    except Exception as e:
        print(f"⚠️ Supabase caption lookup failed for metadata hydration: {e}")
        return None

    if not row:
        return None

    # Prefer a fresh presigned URL from S3 key; fallback to stored URL.
    return _caption_media_url_from_s3_key(row.get("caption_s3_key") or "") or row.get("caption_url") or None


def _resolve_local_video_from_input_ref(input_ref: Optional[str]) -> Optional[tuple[str, str]]:
    """Resolve /videos/<job_id>/<filename> refs to local output file when possible."""
    ref = (input_ref or "").strip()
    if not ref:
        return None

    parsed = urlparse(ref)
    path_part = parsed.path or ref
    if not path_part.startswith("/videos/"):
        return None

    parts = path_part.split("/")
    if len(parts) < 4:
        return None

    ref_job_id = parts[2]
    ref_filename = _sanitize_input_filename("/".join(parts[3:]))
    if not ref_job_id or not ref_filename:
        return None

    candidate_path = os.path.join(OUTPUT_DIR, ref_job_id, ref_filename)
    if not os.path.exists(candidate_path):
        return None

    return candidate_path, ref_filename


def _resolve_hydration_video_source(
    source_ref: str,
    job_id: str,
    output_dir: str,
) -> Optional[tuple[str, str]]:
    local_ref = _resolve_local_video_from_input_ref(source_ref)
    if local_ref:
        local_video_path, local_video_name = local_ref
        hydrated_video_path = os.path.join(output_dir, local_video_name)
        if os.path.abspath(local_video_path) == os.path.abspath(hydrated_video_path):
            return local_video_path, local_video_name
        try:
            shutil.copy(local_video_path, hydrated_video_path)
            return hydrated_video_path, local_video_name
        except Exception as e:
            print(f"⚠️ Could not copy local reel for metadata hydration: {e}")
            return None

    parsed_source = urlparse(source_ref)
    if parsed_source.scheme not in ("http", "https"):
        return None

    try:
        return _download_input_url_to_job_dir(source_ref, job_id)
    except Exception as e:
        print(f"⚠️ Could not download reel for metadata hydration: {e}")
        return None


async def _hydrate_missing_job_metadata(
    job_id: str,
    clip_index: int,
    input_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Optional[str]:
    """Create minimal metadata for old reels by downloading and transcribing the clip on demand."""
    owner_user_id = (user_id or "").strip() or await _resolve_job_owner_user_id(job_id, clip_index)
    source_ref = (
        (input_url or "").strip()
        or await _resolve_reel_input_url(job_id, clip_index)
        or await _resolve_caption_input_url(job_id, clip_index, user_id=owner_user_id or None)
    )
    if not source_ref:
        return None

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    resolved_source = _resolve_hydration_video_source(source_ref, job_id, output_dir)
    if not resolved_source:
        return None
    local_video_path, local_video_name = resolved_source

    cached_transcription = await _load_cached_transcription(owner_user_id or None, job_id, clip_index)
    transcript = dict(cached_transcription.get("transcript_payload") or {}) if cached_transcription else {}
    if not transcript:
        try:
            from main import transcribe_video

            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, transcribe_video, local_video_path)
        except Exception as e:
            print(f"⚠️ Could not transcribe reel for metadata hydration: {e}")
            return None

    duration_sec = max(0.5, _estimate_transcript_duration_seconds(transcript))

    shorts = [
        {
            "title": f"Clip {i + 1}",
            "start": 0.0,
            "end": duration_sec,
            "duration": duration_sec,
            "video_url": "",
        }
        for i in range(clip_index + 1)
    ]
    shorts[clip_index]["video_url"] = f"/videos/{job_id}/{local_video_name}"

    metadata = {
        "shorts": shorts,
        "transcript": transcript,
        "generated_from_reel_fallback": {
            "created_at": int(time.time()),
            "source": "supabase_reel_or_input_url",
            "clip_index": clip_index,
        },
    }

    metadata_path = os.path.join(output_dir, f"{job_id}_fallback_metadata.json")
    try:
        _persist_metadata_json(metadata_path, metadata)
    except Exception as e:
        print(f"⚠️ Failed to write hydrated metadata: {e}")
        return None

    if owner_user_id:
        await _persist_transcription_cache(
            user_id=owner_user_id,
            job_id=job_id,
            clip_index=clip_index,
            source_type="hydration",
            source_value=source_ref,
            transcript=transcript,
        )

    return metadata_path


async def _get_or_build_job_metadata(
    job_id: str,
    clip_index: int,
    input_url: Optional[str] = None,
    user_id: Optional[str] = None,
) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    metadata_path = _resolve_job_metadata_path(job_id)
    if not metadata_path:
        metadata_path = await _hydrate_missing_job_metadata(
            job_id,
            clip_index,
            input_url=input_url,
            user_id=user_id,
        )
    if not metadata_path:
        return None, None

    try:
        async with aiofiles.open(metadata_path, "r", encoding="utf-8") as f:
            return metadata_path, json.loads(await f.read())
    except Exception as e:
        print(f"⚠️ Failed to read metadata: {e}")
        return None, None


def _transcript_full_text(transcript: Dict[str, Any]) -> str:
    if not isinstance(transcript, dict):
        return ""
    text = (transcript.get("text") or "").strip()
    if text:
        return text
    parts: List[str] = []
    for segment in (transcript.get("segments") or []):
        segment_text = (segment.get("text") or "").strip()
        if segment_text:
            parts.append(segment_text)
    return " ".join(parts).strip()


async def _load_cached_transcription(user_id: Optional[str], job_id: str, clip_index: int = 0) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured() or not user_id:
        return None
    try:
        row = await supabase_get_transcription_by_job_clip(job_id, clip_index, user_id)
    except Exception as e:
        print(f"⚠️ Failed to load cached transcription: {e}")
        return None
    if not row:
        return None
    payload = row.get("transcript_payload")
    if isinstance(payload, dict) and payload.get("segments"):
        return row
    return None


async def _persist_transcription_cache(
    *,
    user_id: Optional[str],
    job_id: str,
    clip_index: int,
    source_type: str,
    source_value: str,
    transcript: Dict[str, Any],
    billing_details: Optional[Dict[str, Any]] = None,
) -> None:
    if not is_supabase_configured() or not user_id:
        return
    meta = transcript.get("meta") or {}
    payload = {
        "user_id": user_id,
        "job_id": job_id,
        "clip_index": int(clip_index),
        "source_type": source_type,
        "source_value": source_value,
        "transcript_provider": meta.get("provider") or "unknown",
        "transcript_language": transcript.get("language") or "unknown",
        "transcript_text": _transcript_full_text(transcript),
        "transcript_payload": transcript,
        "billing_details": billing_details or {},
    }
    try:
        await supabase_upsert_transcription(payload)
    except Exception as e:
        print(f"⚠️ Failed to persist transcription cache: {e}")


async def _resolve_job_owner_user_id(job_id: str, clip_index: int) -> Optional[str]:
    in_memory = jobs.get(job_id) or {}
    user_id = (in_memory.get("user_id") or "").strip()
    if user_id:
        return user_id

    if not is_supabase_configured():
        return None

    try:
        reel_row = await supabase_get_reel_by_job_clip(job_id, int(clip_index))
        reel_user = str((reel_row or {}).get("reel_user_id") or "").strip()
        if reel_user:
            return reel_user
    except Exception:
        pass

    try:
        caption_row = await supabase_get_caption_by_job_clip_any(job_id, int(clip_index))
        caption_user = str((caption_row or {}).get("caption_user_id") or "").strip()
        if caption_user:
            return caption_user
    except Exception:
        pass

    return None


def _append_style_version_to_metadata(
    data: Dict[str, Any],
    clip_index: int,
    source_video_url: str,
    output_video_url: str,
    style_config: Dict[str, Any],
) -> int:
    history = data.get("style_history")
    if not isinstance(history, dict):
        history = {}
    key = str(int(clip_index))
    entries = history.get(key)
    if not isinstance(entries, list):
        entries = []

    version_number = len(entries) + 1
    entries.append(
        {
            "version": version_number,
            "operation_type": "subtitle_style",
            "created_at": int(time.time()),
            "source_video_url": source_video_url,
            "output_video_url": output_video_url,
            "style_config": style_config,
        }
    )
    history[key] = entries
    data["style_history"] = history
    return version_number


def _active_output_paths() -> set[str]:
    active_paths: set[str] = set()
    for job_data in jobs.values():
        if job_data.get("status") not in ("queued", "processing"):
            continue
        out_dir = job_data.get("output_dir")
        if out_dir:
            active_paths.add(os.path.abspath(out_dir))
    return active_paths


def _sweep_output_directory(now_ts: float) -> int:
    """Delete stale output artifacts in batches instead of per-job cleanup."""
    if not os.path.isdir(OUTPUT_DIR):
        return 0

    removed = 0
    active_paths = _active_output_paths()
    thumbnails_dir = os.path.abspath(os.path.join(OUTPUT_DIR, "thumbnails"))
    # Persistent cache (see synthesize_tts_segment / FILM_SUMMARY_VOICE_PREVIEWS_DIR),
    # not per-job output -- it must survive the sweep exactly like
    # thumbnails_dir, or it goes stale (mtime untouched) and gets wiped
    # entirely as soon as 30+ minutes pass without a new voice being
    # previewed, breaking every already-cached voice preview until the
    # next request regenerates it (reported bug: "No such file or
    # directory: 'output/voice_previews/<voice>.mp3.tmp-...'").
    voice_previews_dir = os.path.abspath(FILM_SUMMARY_VOICE_PREVIEWS_DIR)

    for child in os.listdir(OUTPUT_DIR):
        child_path = os.path.join(OUTPUT_DIR, child)
        abs_child = os.path.abspath(child_path)

        if abs_child in (thumbnails_dir, voice_previews_dir):
            continue
        if abs_child in active_paths:
            continue

        try:
            if now_ts - os.path.getmtime(child_path) < OUTPUT_SWEEP_MIN_AGE_SECONDS:
                continue

            if os.path.isdir(child_path):
                shutil.rmtree(child_path, ignore_errors=True)
            else:
                os.remove(child_path)
            removed += 1
        except Exception:
            continue

    return removed


def _reel_media_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _reel_thumbnail_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _project_thumbnail_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _project_thumbnail_url_from_ref(thumbnail_ref: str) -> str:
    ref = str(thumbnail_ref or "").strip()
    if not ref:
        return ""
    if ref.startswith(_HTTPS_SCHEME_PREFIX):
        return ref
    s3_key = _extract_s3_key_from_thumbnail_ref(ref)
    if not s3_key and ref.startswith(_PROJECTS_PREFIX):
        s3_key = ref
    if not s3_key:
        return ref
    return _project_thumbnail_url_from_s3_key(s3_key) or ref


def _generate_and_upload_project_thumbnail_from_source(source_video_path: str, bucket: str, user_id: str, project_ref_id: str) -> str:
    if not source_video_path or not os.path.exists(source_video_path) or not bucket:
        return ""

    thumb_local = _generate_reel_thumbnail_from_video(
        source_video_path,
        OUTPUT_DIR,
        f"project_{project_ref_id}",
        0,
    )
    if not thumb_local or not os.path.exists(thumb_local):
        return ""

    thumbnail_s3_key = f"{_PROJECTS_PREFIX}{user_id}/{project_ref_id}/thumbnail_source.jpg"
    uploaded = upload_file_to_s3(thumb_local, bucket, thumbnail_s3_key)
    try:
        os.remove(thumb_local)
    except Exception:
        pass
    return thumbnail_s3_key if uploaded else ""


def _cleanup_generated_clips_after_job(output_dir: str, base_name: str) -> None:
    """Remove generated clip files only after the reel job has fully completed."""
    if not output_dir or not base_name or not os.path.isdir(output_dir):
        return
    pattern = os.path.join(output_dir, f"{base_name}_clip_*.mp4")
    for clip_path in glob.glob(pattern):
        try:
            os.remove(clip_path)
        except FileNotFoundError:
            continue
        except Exception:
            continue


def _caption_media_url_from_s3_key(s3_key: str) -> str:
    if not s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, s3_key, expiration=7200) or ""


def _normalize_caption_row(row: Dict[str, Any]) -> Dict[str, Any]:
    media_url = _caption_media_url_from_s3_key(row.get("caption_s3_key") or "") or row.get("caption_url") or ""
    thumbnail_ref = row.get("caption_thumbnail_url") or ""
    thumbnail_url = _caption_media_url_from_s3_key(thumbnail_ref) if thumbnail_ref.startswith(_CAPTIONS_PREFIX) else thumbnail_ref
    preview_url = thumbnail_url or media_url

    # caption_original_url used to expose the clean, pre-caption clip
    # (generation_inputs.original_s3_key) so the app could point restyles at
    # it directly. The app now always works off a single URL -- the
    # currently displayed one -- so this just mirrors media_url; the clean
    # clip is still resolved server-side when actually re-burning (see
    # _resolve_authoritative_clean_video_source), which is what actually
    # keeps a restyle from stacking onto the default captions.
    return {
        **row,
        "caption_url": media_url or row.get("caption_url") or "",
        "caption_thumbnail_url": thumbnail_url,
        "caption_thumbnail_s3_key": thumbnail_ref if thumbnail_ref.startswith(_CAPTIONS_PREFIX) else "",
        "caption_playback_url": media_url,
        "caption_download_url": media_url,
        "caption_preview_url": preview_url,
        "caption_original_url": media_url,
        "media_url": media_url,
    }


_COMMON_VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv")


def _is_probably_video_url(value: str) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return False
    path = urlparse(text).path or text
    return path.endswith(_COMMON_VIDEO_EXTENSIONS + (".m4v", ".avi"))


async def _fetch_reel_and_caption_rows_for_preview(job_id: str, clip_index: int, user_id: str):
    reel_row: Optional[Dict[str, Any]] = None
    caption_row: Optional[Dict[str, Any]] = None

    try:
        maybe_reel = await supabase_get_reel_by_job_clip(job_id, int(clip_index), user_id=user_id)
        if str((maybe_reel or {}).get("reel_user_id") or "").strip() == user_id:
            reel_row = maybe_reel
    except Exception:
        reel_row = None

    try:
        caption_row = await supabase_get_caption_by_job_clip(job_id, int(clip_index), user_id)
    except Exception:
        caption_row = None

    return reel_row, caption_row


def _existing_preview_thumbnail_from_rows(reel_row: Optional[Dict[str, Any]], caption_row: Optional[Dict[str, Any]]) -> str:
    if reel_row:
        reel_thumb = _normalize_reel_row(reel_row).get("reel_thumbnail_url") or ""
        if reel_thumb and not _is_probably_video_url(reel_thumb):
            return reel_thumb

    if caption_row:
        caption_thumb = _normalize_caption_row(caption_row).get("caption_thumbnail_url") or ""
        if caption_thumb and not _is_probably_video_url(caption_thumb):
            return caption_thumb

    return ""


async def _clip_data_from_job_metadata(job_id: str, clip_index: int) -> Dict[str, Any]:
    _, metadata = await _get_or_build_job_metadata(job_id, clip_index)
    if isinstance(metadata, dict):
        shorts = metadata.get("shorts") or []
        if 0 <= int(clip_index) < len(shorts) and isinstance(shorts[int(clip_index)], dict):
            return shorts[int(clip_index)]
    return {}


def _build_preview_source_candidates(
    reel_row: Optional[Dict[str, Any]],
    caption_row: Optional[Dict[str, Any]],
    clip_data: Dict[str, Any],
) -> List[str]:
    source_candidates: List[str] = []
    if reel_row:
        source_candidates.extend([
            _reel_media_url_from_s3_key(str(reel_row.get("reel_s3_key") or "")),
            str(reel_row.get("reel_url") or ""),
        ])
    if caption_row:
        source_candidates.extend([
            _caption_media_url_from_s3_key(str(caption_row.get("caption_s3_key") or "")),
            str(caption_row.get("caption_url") or ""),
        ])
    source_candidates.extend([
        str(clip_data.get("video_url") or ""),
        str(clip_data.get("original_video_url") or ""),
    ])

    deduped_candidates: List[str] = []
    for candidate in source_candidates:
        c = str(candidate or "").strip()
        if c and c not in deduped_candidates:
            deduped_candidates.append(c)
    return deduped_candidates


def _resolve_local_video_path_for_preview(deduped_candidates: List[str], job_id: str):
    local_video_path = ""
    downloaded_video_path = ""
    for candidate in deduped_candidates:
        parsed = urlparse(candidate)
        if candidate.startswith("/videos/"):
            guessed = os.path.join(OUTPUT_DIR, job_id, os.path.basename(parsed.path or ""))
            if os.path.exists(guessed):
                local_video_path = guessed
                break
        elif os.path.exists(candidate):
            local_video_path = candidate
            break
        elif parsed.scheme in ("http", "https"):
            try:
                downloaded_video_path, _ = _download_input_url_to_job_dir(candidate, job_id)
                local_video_path = downloaded_video_path
                break
            except Exception:
                continue
    return local_video_path, downloaded_video_path


async def _update_caption_thumbnail_after_upload(caption_row: Optional[Dict[str, Any]], caption_thumb_uploaded: bool, user_id: str, caption_thumb_key: str) -> str:
    if not (caption_row and caption_thumb_uploaded):
        return ""
    await supabase_update_caption(
        str(caption_row.get("id")),
        user_id,
        {"caption_thumbnail_url": caption_thumb_key},
    )
    return _caption_media_url_from_s3_key(caption_thumb_key) or ""


async def _update_reel_thumbnail_after_upload(reel_row: Optional[Dict[str, Any]], reel_thumb_uploaded: bool, job_id: str, clip_index: int, user_id: str, reel_thumb_key: str, preview_url: str) -> str:
    if not (reel_row and reel_thumb_uploaded):
        return preview_url
    normalized_reel = _normalize_reel_row(reel_row)
    reel_media_url = normalized_reel.get("reel_url") or str(reel_row.get("reel_url") or "")
    if reel_media_url:
        await supabase_update_reel_media_by_job_clip(
            job_id=job_id,
            clip_index=int(clip_index),
            reel_url=reel_media_url,
            reel_s3_key=str(reel_row.get("reel_s3_key") or "") or None,
            reel_thumbnail_url=reel_thumb_key,
            user_id=user_id,
        )
    if not preview_url:
        preview_url = _reel_thumbnail_url_from_s3_key(reel_thumb_key) or ""
    return preview_url


def _cleanup_preview_thumbnail_temp_files(thumb_local: str, downloaded_video_path: str) -> None:
    try:
        if os.path.exists(thumb_local):
            os.remove(thumb_local)
    except Exception:
        pass
    try:
        if downloaded_video_path and os.path.exists(downloaded_video_path):
            os.remove(downloaded_video_path)
    except Exception:
        pass


async def _generate_and_upload_preview_thumbnail(
    thumb_local: str,
    downloaded_video_path: str,
    bucket: str,
    job_id: str,
    clip_index: int,
    user_id: str,
    reel_row: Optional[Dict[str, Any]],
    caption_row: Optional[Dict[str, Any]],
) -> str:
    preview_url = ""
    try:
        reel_thumb_key = f"reels/{user_id}/{job_id}/thumbnail_{int(clip_index)}.jpg"
        caption_thumb_key = f"captions/{user_id}/{job_id}/thumbnail_{int(clip_index)}_fallback.jpg"

        reel_thumb_uploaded = upload_file_to_s3(thumb_local, bucket, reel_thumb_key)
        caption_thumb_uploaded = upload_file_to_s3(thumb_local, bucket, caption_thumb_key)

        preview_url = await _update_caption_thumbnail_after_upload(caption_row, caption_thumb_uploaded, user_id, caption_thumb_key)
        preview_url = await _update_reel_thumbnail_after_upload(reel_row, reel_thumb_uploaded, job_id, clip_index, user_id, reel_thumb_key, preview_url)
    finally:
        _cleanup_preview_thumbnail_temp_files(thumb_local, downloaded_video_path)
    return preview_url


async def _fallback_preview_from_refetch(
    job_id: str,
    clip_index: int,
    user_id: str,
    reel_row: Optional[Dict[str, Any]],
    caption_row: Optional[Dict[str, Any]],
) -> str:
    if reel_row:
        refreshed = _normalize_reel_row(await supabase_get_reel_by_job_clip(job_id, int(clip_index), user_id=user_id) or {})
        fallback_reel_thumb = str(refreshed.get("reel_thumbnail_url") or "")
        if fallback_reel_thumb and not _is_probably_video_url(fallback_reel_thumb):
            return fallback_reel_thumb
    if caption_row:
        refreshed_caption = _normalize_caption_row(await supabase_get_caption_by_job_clip(job_id, int(clip_index), user_id) or {})
        fallback_caption_thumb = str(refreshed_caption.get("caption_thumbnail_url") or "")
        if fallback_caption_thumb and not _is_probably_video_url(fallback_caption_thumb):
            return fallback_caption_thumb
    return ""


async def _ensure_preview_image_for_clip(job_id: str, clip_index: int, user_id: str) -> str:
    if not is_supabase_configured() or not user_id:
        return ""

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""

    reel_row, caption_row = await _fetch_reel_and_caption_rows_for_preview(job_id, clip_index, user_id)

    existing = _existing_preview_thumbnail_from_rows(reel_row, caption_row)
    if existing:
        return existing

    clip_data = await _clip_data_from_job_metadata(job_id, clip_index)
    deduped_candidates = _build_preview_source_candidates(reel_row, caption_row, clip_data)
    local_video_path, downloaded_video_path = _resolve_local_video_path_for_preview(deduped_candidates, job_id)

    if not local_video_path or not os.path.exists(local_video_path):
        return ""

    thumb_local = _generate_reel_thumbnail_from_video(local_video_path, OUTPUT_DIR, job_id, int(clip_index))
    if not thumb_local or not os.path.exists(thumb_local):
        return ""

    preview_url = await _generate_and_upload_preview_thumbnail(
        thumb_local, downloaded_video_path, bucket, job_id, clip_index, user_id, reel_row, caption_row,
    )
    if preview_url:
        return preview_url

    return await _fallback_preview_from_refetch(job_id, clip_index, user_id, reel_row, caption_row)


def _job_uses_remote_source(job_data: Optional[Dict[str, Any]]) -> bool:
    payload = job_data or {}
    source_type = str(
        payload.get("source_type")
        or ((payload.get("attestation") or {}).get("source"))
        or ""
    ).strip().lower()
    return source_type == "url"


def _load_reel_job_metadata_snapshot(job_id: str):
    metadata_path = _resolve_job_metadata_path(job_id)
    metadata: Dict[str, Any] = {}
    shorts: List[Dict[str, Any]] = []
    cost_analysis = None
    base_name = ""

    if metadata_path and os.path.exists(metadata_path) and os.path.getsize(metadata_path) > 0:
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f) or {}
        except Exception:
            metadata = {}
        shorts = metadata.get("shorts") or []
        cost_analysis = metadata.get("cost_analysis")
        base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")

    return metadata_path, shorts, cost_analysis, base_name


def _ready_clip_entries_from_shorts(base_name: str, shorts: List[Dict[str, Any]], output_dir: str) -> List[Dict[str, Any]]:
    ready_entries: List[Dict[str, Any]] = []
    if not (base_name and shorts):
        return ready_entries
    for index, clip in enumerate(shorts, start=1):
        clip_filename = f"{base_name}_clip_{index}.mp4"
        clip_path = os.path.join(output_dir, clip_filename)
        if not os.path.exists(clip_path) or os.path.getsize(clip_path) <= 0:
            continue
        ready_entries.append(
            {
                "filename": clip_filename,
                "path": clip_path,
                "size_bytes": int(os.path.getsize(clip_path) or 0),
                "clip": dict(clip or {}),
            }
        )
    return ready_entries


def _ready_clip_entries_fallback_scan(output_dir: str) -> List[Dict[str, Any]]:
    ready_entries: List[Dict[str, Any]] = []
    if not os.path.isdir(output_dir):
        return ready_entries
    fallback_files = sorted(
        file_name
        for file_name in os.listdir(output_dir)
        if file_name.endswith(".mp4") and not file_name.startswith("temp_")
    )
    for file_name in fallback_files:
        clip_path = os.path.join(output_dir, file_name)
        ready_entries.append(
            {
                "filename": file_name,
                "path": clip_path,
                "size_bytes": int(os.path.getsize(clip_path) or 0),
                "clip": {},
            }
        )
    return ready_entries


def _partial_clips_from_ready_entries(job_id: str, ready_entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    partial_clips: List[Dict[str, Any]] = []
    for idx, entry in enumerate(ready_entries, start=1):
        clip_payload = dict(entry.get("clip") or {})
        clip_payload["video_url"] = f"/videos/{job_id}/{entry['filename']}"
        clip_payload.setdefault("title", f"Clip {idx}")
        partial_clips.append(clip_payload)
    return partial_clips


def _collect_reel_job_output_snapshot(job_id: str, output_dir: str) -> Dict[str, Any]:
    metadata_path, shorts, cost_analysis, base_name = _load_reel_job_metadata_snapshot(job_id)

    ready_entries = _ready_clip_entries_from_shorts(base_name, shorts, output_dir)
    if not ready_entries:
        ready_entries = _ready_clip_entries_fallback_scan(output_dir)

    partial_clips = _partial_clips_from_ready_entries(job_id, ready_entries)

    expected_clips = len(shorts) if shorts else len(ready_entries)
    total_size_bytes = sum(int(entry.get("size_bytes") or 0) for entry in ready_entries)
    result_data: Dict[str, Any] = {}
    if partial_clips:
        result_data["clips"] = partial_clips
    if cost_analysis is not None:
        result_data["cost_analysis"] = cost_analysis

    return {
        "metadata_path": metadata_path,
        "expected_clips": expected_clips,
        "processed_clips": len(ready_entries),
        "total_size_bytes": total_size_bytes,
        "result_data": result_data,
    }


def _estimate_reel_job_consumption(
    *,
    elapsed_seconds: float,
    uses_youtube: bool,
    processed_clips: int,
    expected_clips: int,
    storage_bytes: int,
) -> Dict[str, Any]:
    processed_count = max(0, int(processed_clips or 0))
    expected_count = max(0, int(expected_clips or 0))
    if processed_count <= 0:
        return {
            "processing_ratio": 0.0,
            "actual_cost_usd": 0.0,
            "actual_credit": 0.0,
            "actual_storage_gb": 0.0,
            "cost_breakdown": {},
        }

    processing_ratio = 1.0 if expected_count <= 0 else min(1.0, processed_count / expected_count)
    actual_storage_gb = _bytes_to_gb(storage_bytes)
    billed_video_size_gb = max(actual_storage_gb, 0.5)
    breakdown = estimate_reel_cost_usd(
        duration_minutes=max(float(elapsed_seconds or 0.0) / 60.0, 1.0),
        video_size_gb=billed_video_size_gb,
        uses_youtube_download=uses_youtube,
        youtube_download_gb=0.3 if uses_youtube else 0.0,
        uses_openai=True,
        uses_assembly=True,
    )
    credit_info = calculate_credits_for_operation(breakdown)
    return {
        "processing_ratio": round(processing_ratio, 4),
        "actual_cost_usd": round(float(breakdown.get("total_usd") or 0.0) * processing_ratio, 6),
        "actual_credit": round(float(credit_info.get("final_credits") or 0.0) * processing_ratio, 2),
        "actual_storage_gb": round(actual_storage_gb, 6),
        "cost_breakdown": credit_info,
    }


async def _settle_partial_reel_job_billing(
    job_id: str,
    user_id: Optional[str],
    job_data: Optional[Dict[str, Any]],
    fail_result: Dict[str, Any],
    consumption: Dict[str, Any],
) -> bool:
    debit_applied = False
    reserved_credits = float((job_data or {}).get("reel_required_credits") or 0.0)
    # Settle on any terminal (non-retryable) failure whenever there's a
    # partial charge to bill OR a reservation to refund -- otherwise a job
    # that fails before any billable progress (actual_credit == 0) would
    # never release its reservation back to the user.
    if not fail_result.get("retry") and user_id and (consumption["actual_credit"] > 0 or reserved_credits > 0):
        try:
            debit_applied = await reel_job_manager.debit_credits_for_job(
                job_id=job_id,
                user_id=user_id,
                credits=consumption["actual_credit"],
                storage_delta=0.0,
                operation_type="generation_reel",
                reserved_credits=reserved_credits,
            )
        except Exception as billing_error:
            jobs[job_id]["logs"].append(f"Partial billing failed: {billing_error}")
    return debit_applied


async def _mark_reel_job_project_failed(job_data: Optional[Dict[str, Any]], user_id: Optional[str]) -> None:
    if not (is_supabase_configured() and job_data):
        return
    project_id = job_data.get("project_id")
    if not project_id:
        return
    try:
        await supabase_update_project_status(project_id, "failed", user_id=user_id)
        logger.info(f"Project {project_id} marked as failed")
    except Exception as e:
        logger.warning(f"Failed to update project status to failed: {str(e)}")


async def _finalize_failed_reel_job(
    *,
    job_id: str,
    user_id: Optional[str],
    output_dir: str,
    job_data: Optional[Dict[str, Any]],
    start_ts: float,
    error_message: str,
    error_code: str,
    retry_delay_seconds: int,
) -> Dict[str, Any]:
    elapsed = round(calc_elapsed_seconds(start_ts), 3)
    snapshot = _collect_reel_job_output_snapshot(job_id, output_dir)
    consumption = _estimate_reel_job_consumption(
        elapsed_seconds=elapsed,
        uses_youtube=_job_uses_remote_source(job_data),
        processed_clips=snapshot.get("processed_clips", 0),
        expected_clips=snapshot.get("expected_clips", 0),
        storage_bytes=0,
    )
    result_data = dict(snapshot.get("result_data") or {})
    result_data["duration_seconds"] = elapsed
    result_data["billing"] = {
        "actual_cost_usd": consumption["actual_cost_usd"],
        "actual_credit": consumption["actual_credit"],
        "actual_storage_gb": 0.0,
        "processing_ratio": consumption["processing_ratio"],
        "debit_applied": False,
        "partial_failure": True,
    }

    fail_result = await reel_job_manager.fail_job(
        job_id,
        error_message,
        error_code=error_code,
        retry_delay_seconds=retry_delay_seconds,
        actual_cost_usd=consumption["actual_cost_usd"],
        actual_credit=consumption["actual_credit"],
        actual_storage_gb=0.0,
        consumed_quota=consumption["processing_ratio"],
        result_data=result_data,
        cost_breakdown=consumption["cost_breakdown"],
    )

    debit_applied = await _settle_partial_reel_job_billing(job_id, user_id, job_data, fail_result, consumption)

    result_data["billing"]["debit_applied"] = bool(debit_applied)
    await supabase_update_job_record(
        job_id,
        {
            "result_data": result_data,
            "cost_breakdown": consumption["cost_breakdown"],
        },
    )

    if result_data.get("clips"):
        jobs[job_id]["result"] = result_data
    jobs[job_id]["status"] = fail_result.get("status") or "failed"

    await _mark_reel_job_project_failed(job_data, user_id)

    return fail_result


def _extract_s3_key_from_thumbnail_ref(thumbnail_ref: str) -> str:
    """Accept raw S3 keys or s3://bucket/key refs and return object key only."""
    ref = (thumbnail_ref or "").strip()
    if not ref:
        return ""
    if ref.startswith("s3://"):
        without_scheme = ref[5:]
        parts = without_scheme.split("/", 1)
        if len(parts) == 2:
            return parts[1]
        return ""
    if ref.startswith(("reels/", _CAPTIONS_PREFIX, _PROJECTS_PREFIX, _STORIES_PREFIX, _FILM_SUMMARIES_PREFIX)):
        return ref
    return ""

def _generate_reel_thumbnail_from_video(
    video_path: str,
    output_dir: str,
    job_id: str,
    clip_index: int,
) -> str:
    """Extract a representative frame from a clip and save it as a JPEG thumbnail."""
    if not video_path or not os.path.exists(video_path):
        return ""

    thumb_dir = os.path.join(output_dir, "thumbnails", job_id)
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f"thumb_{clip_index + 1}.jpg")

    cap = None
    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return ""

        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if frame_count > 0:
            target_frame = max(0, min(frame_count - 1, frame_count // 5))
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

        ok, frame = cap.read()
        if not ok or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = cap.read()

        if not ok or frame is None:
            return ""

        if cv2.imwrite(thumb_path, frame):
            return thumb_path
        return ""
    except Exception:
        return ""
    finally:
        if cap is not None:
            try:
                cap.release()
            except Exception:
                pass


def _normalize_reel_row(row: Dict[str, Any]) -> Dict[str, Any]:
    media_url = _reel_media_url_from_s3_key(row.get("reel_s3_key") or "") or row.get("reel_url") or ""
    thumbnail_ref = row.get("reel_thumbnail_url") or row.get("reel_thumbnail_s3_key") or ""
    thumbnail_s3_key = _extract_s3_key_from_thumbnail_ref(thumbnail_ref)
    thumbnail_url = _reel_thumbnail_url_from_s3_key(thumbnail_s3_key) or thumbnail_ref or ""
    preview_url = thumbnail_url or media_url

    # reel_original_url used to expose the clean, pre-caption clip
    # (billing_details.original_s3_key) so the app could point restyles at
    # it directly. The app now always works off a single URL -- the
    # currently displayed one -- so this just mirrors media_url; the clean
    # clip is still resolved server-side when actually re-burning (see
    # _resolve_authoritative_clean_video_source), which is what actually
    # keeps a restyle from stacking onto the default captions.
    return {
        **row,
        "reel_url": media_url or row.get("reel_url") or "",
        "reel_thumbnail_url": thumbnail_url,
        "reel_preview_url": preview_url,
        "reel_playback_url": media_url,
        "reel_download_url": media_url,
        "reel_original_url": media_url,
        "media_url": media_url,
    }


def _upload_reel_clip_thumbnail(clip: Dict[str, Any], clip_path: str, output_dir: str, job_id: str, clip_index: int, user_id: str, bucket: str) -> str:
    source_thumbnail = _generate_reel_thumbnail_from_video(clip_path, output_dir, job_id, clip_index)
    generated_thumbnail_locally = bool(source_thumbnail)
    if not source_thumbnail:
        source_thumbnail = clip.get("thumbnail_url") or ""

    print("🖼️ Uploading thumbnail for clip", clip_index + 1, "from source:", source_thumbnail)

    thumbnail_s3_key = ""
    if source_thumbnail and os.path.exists(source_thumbnail):
        thumbnail_s3_key = f"reels/{user_id}/{job_id}/thumbnail_{clip_index}.jpg"
        uploaded_thumb = upload_file_to_s3(source_thumbnail, bucket, thumbnail_s3_key)
        if not uploaded_thumb:
            raise RuntimeError(f"Failed to upload thumbnail to S3: {thumbnail_s3_key}")

    if generated_thumbnail_locally and source_thumbnail:
        try:
            if os.path.exists(source_thumbnail):
                os.remove(source_thumbnail)
        except Exception:
            pass

    return thumbnail_s3_key


def _compute_clip_duration_seconds(clip: Dict[str, Any]) -> int:
    duration = clip.get("duration")
    if duration is not None:
        return duration
    try:
        start = float(clip.get("start", 0) or 0)
        end = float(clip.get("end", 0) or 0)
        return max(0, int(round(end - start)))
    except Exception:
        return 0


# Matches CaptionsModal.jsx's own DEFAULT_STYLE (dashboard/src/components/
# CaptionsModal.jsx) so a clip's default captions -- burned in automatically,
# server-side, before the user ever opens the editor -- look identical to
# what they'd get by opening "Sous-titres" and accepting the defaults. This
# is only ever the *factory* fallback now -- see _get_user_default_caption_
# style, which prefers a user's own saved default when one exists.
_DEFAULT_AUTO_CAPTION_STYLE_KWARGS: Dict[str, Any] = {
    "position": "bottom", "position_x": 50.0, "position_y": 82.0,
    "font_size": 14, "font_name": "Montserrat", "font_color": "#FFFFFF",
    "highlight_color": "#FFDD00", "border_color": "#000000", "border_width": 3,
    "text_shadow_color": "#000000", "shadow_blur": 8, "shadow_offset_x": 0, "shadow_offset_y": 2,
    "bg_color": "#000000", "bg_opacity": 0.0, "text_case": "none", "bold": True, "italic": False,
    "words_per_line": 4, "animation": "word-highlight",
}

# Sentinel (job_id, clip_index) under which a user's own default caption
# style is stored in style_edit_versions -- not a real job/clip, just a
# fixed key so "the user's global default" fits the same per-(user_id,
# job_id, clip_index) row shape everything else in that table uses,
# instead of needing a separate table. Each save (see
# set_default_caption_style_endpoint) appends a new version; the latest
# one wins, so "replacing" the default is just saving another version.
_DEFAULT_STYLE_SENTINEL_JOB_ID = "__user_default__"
_DEFAULT_STYLE_SENTINEL_CLIP_INDEX = 0


class DefaultCaptionStyleRequest(BaseModel):
    position: str = "bottom"
    position_x: float = 50.0
    position_y: float = 82.0
    font_size: int = Field(default=14, ge=10, le=200)
    font_name: str = "Montserrat"
    font_color: str = "#FFFFFF"
    highlight_color: str = "#FFDD00"
    border_color: str = "#000000"
    border_width: int = 3
    text_shadow_color: str = "#000000"
    shadow_blur: int = 8
    shadow_offset_x: int = 0
    shadow_offset_y: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    text_case: str = "none"
    bold: bool = True
    italic: bool = False
    words_per_line: int = Field(default=4, ge=1, le=10)
    animation: str = "word-highlight"


async def _get_user_default_caption_style(user_id: Optional[str]) -> Dict[str, Any]:
    """Resolves the style new clips get auto-captioned with: a user's own
    saved default when they have one (a readable, replaceable
    style_edit_versions row -- see set_default_caption_style_endpoint --
    rather than a value only ever baked into application code), falling
    back to the factory default (_DEFAULT_AUTO_CAPTION_STYLE_KWARGS)
    otherwise."""
    if is_supabase_configured() and user_id:
        try:
            versions = await supabase_list_style_edit_versions(
                _DEFAULT_STYLE_SENTINEL_JOB_ID, _DEFAULT_STYLE_SENTINEL_CLIP_INDEX, user_id,
            )
            if versions:
                style_config = versions[-1].get("style_config")
                if isinstance(style_config, dict) and style_config:
                    return style_config
        except Exception as exc:
            logger.warning("Failed to load user default caption style for %s: %s", user_id, exc)
    return dict(_DEFAULT_AUTO_CAPTION_STYLE_KWARGS)


async def _burn_default_captions_for_clip(
    input_path: str, output_path: str, transcript: Optional[Dict[str, Any]],
    clip_start: float, clip_end: float, job_id: str, clip_index: int,
    style_kwargs: Dict[str, Any],
) -> bool:
    """Burn default subtitles into a freshly produced clip so reels/captions
    come out captioned without the user opening the manual editor first.

    Reuses the same FFmpeg burn-in as the manual /api/subtitle endpoint
    (_burn_subtitles_for_request). `style_kwargs` is the resolved style to
    burn with (the user's own saved default when they have one, else the
    factory default -- see _get_user_default_caption_style), resolved once
    by the caller so it can also be recorded alongside the result (see
    _record_default_style_version) without a second lookup.

    Returns False (leaving the source clip untouched) when there's no
    transcript or no words fall inside this clip's time range -- a silent
    clip has nothing to caption.
    """
    if not transcript:
        return False
    srt_path = f"{output_path}.srt"
    try:
        # Any animation other than "none" highlights the currently-spoken
        # word (see Subtitles.tsx's isActive -> color = highlightColor,
        # applied for every animation value) -- generate_highlighted_srt
        # marks up the SRT so burn_subtitles can reproduce that in the
        # burned-in video instead of leaving it static.
        srt_generator = generate_srt if style_kwargs.get("animation", "none") == "none" else generate_highlighted_srt
        has_words = srt_generator(
            transcript, clip_start, clip_end, srt_path,
            max_words_per_line=style_kwargs["words_per_line"],
        )
        if not has_words:
            return False
        req = SubtitleRequest(job_id=job_id, clip_index=clip_index, **style_kwargs)
        await asyncio.to_thread(_burn_subtitles_for_request, req, input_path, srt_path, output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception as exc:
        logger.warning("Default caption burn failed for job %s clip %s: %s", job_id, clip_index, exc)
        return False
    finally:
        try:
            if os.path.exists(srt_path):
                os.remove(srt_path)
        except Exception:
            pass


# The version_number a clip's auto-applied default caption style is always
# recorded under (see _record_default_style_version) -- reset_caption_style_
# history looks this up specifically so "reset" restores the *styled*
# default instead of stripping captions back to a bare, uncaptioned clip.
_DEFAULT_STYLE_VERSION_NUMBER = 1


async def _record_default_style_version(
    user_id: str, job_id: str, clip_index: int, source_video_url: str, output_video_url: str,
    style_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Records the style a clip was actually auto-captioned with (the
    user's own saved default when they have one, else the factory default
    -- see _get_user_default_caption_style) as a real style_edit_versions
    row, the same table manual restyles are recorded in -- so the captions
    editor can treat "the default" as an actual version instead of a value
    only ever baked into application code, and so resetting a clip's
    captions falls back to this properly-styled version instead of a bare,
    uncaptioned video.

    Best-effort: any failure here must never fail the reel job itself -- it
    just means reset falls back to the plain original video for this clip."""
    if not (is_supabase_configured() and user_id):
        return
    try:
        await supabase_insert_style_edit_version({
            "user_id": user_id,
            "job_id": job_id,
            "clip_index": int(clip_index),
            "version_number": _DEFAULT_STYLE_VERSION_NUMBER,
            "operation_type": "subtitle_style",
            "source_video_url": source_video_url,
            "output_video_url": output_video_url,
            "style_config": style_config if isinstance(style_config, dict) and style_config else dict(_DEFAULT_AUTO_CAPTION_STYLE_KWARGS),
        })
    except Exception as exc:
        logger.warning("Failed to record default style version for job %s clip %s: %s", job_id, clip_index, exc)


async def _upload_and_finalize_auto_caption(
    clip_path: str,
    primary_path: str,
    auto_captioned: bool,
    clip: Dict[str, Any],
    default_style_kwargs: Dict[str, Any],
    user_id: str,
    job_id: str,
    clip_index: int,
    clip_filename: str,
    bucket: str,
) -> tuple:
    """Uploads the (possibly captioned) clip to S3 and, when auto-captioning
    was applied, also uploads the pre-caption original, estimates its
    caption cost, and records the default style version so a later reset
    can fall back to this properly-styled version. Returns (media_url,
    s3_key, clip_size_bytes, original_s3_key, caption_credit_cost,
    auto_caption_cost_breakdown)."""
    s3_key = f"reels/{user_id}/{job_id}/{clip_filename}"
    if not upload_file_to_s3(primary_path, bucket, s3_key):
        raise RuntimeError(f"Failed to upload clip to S3: {clip_filename}")
    clip_size_bytes = int(os.path.getsize(primary_path) or 0)
    media_url = _reel_media_url_from_s3_key(s3_key)

    if not auto_captioned:
        return media_url, s3_key, clip_size_bytes, "", 0.0, {}

    original_s3_key = f"reels/{user_id}/{job_id}/original_{clip_filename}"
    if not upload_file_to_s3(clip_path, bucket, original_s3_key):
        # Best-effort: the reel itself is already captioned and uploaded
        # above -- losing the pre-caption original only means a later
        # manual restyle rebuilds from the captioned version instead.
        original_s3_key = ""

    clip_duration_for_caption_cost = _compute_clip_duration_seconds(clip)
    auto_caption_cost_breakdown = _estimate_caption_cost_breakdown(
        duration_seconds=float(clip_duration_for_caption_cost or 0),
        size_bytes=float(clip_size_bytes),
        uses_assembly=False, uses_openai=False, uses_gemini=False,
    )
    caption_credit_cost = _estimate_caption_required_credits(
        duration_seconds=float(clip_duration_for_caption_cost or 0),
        size_bytes=float(clip_size_bytes),
        uses_assembly=False, uses_openai=False, uses_gemini=False,
    )
    await _record_default_style_version(
        user_id, job_id, clip_index,
        source_video_url=_reel_media_url_from_s3_key(original_s3_key) if original_s3_key else "",
        output_video_url=media_url,
        style_config=default_style_kwargs,
    )
    return media_url, s3_key, clip_size_bytes, original_s3_key, caption_credit_cost, auto_caption_cost_breakdown


async def _build_reel_row_for_clip(
    job_id: str,
    user_id: str,
    output_dir: str,
    bucket: str,
    base_name: str,
    clip: Dict[str, Any],
    i: int,
    now_iso: str,
    uses_youtube_source: bool,
    project_id: Optional[str],
    transcript: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    clip_filename = f"{base_name}_clip_{i}.mp4"
    clip_path = os.path.join(output_dir, clip_filename)
    if not os.path.exists(clip_path):
        return None

    clip_index = i - 1
    captioned_path = os.path.join(output_dir, f"{base_name}_clip_{i}_captioned.mp4")
    default_style_kwargs = await _get_user_default_caption_style(user_id)
    auto_captioned = await _burn_default_captions_for_clip(
        clip_path, captioned_path, transcript,
        float(clip.get("start", 0) or 0), float(clip.get("end", 0) or 0),
        job_id, clip_index, default_style_kwargs,
    )
    primary_path = captioned_path if auto_captioned else clip_path

    (
        media_url, s3_key, clip_size_bytes, original_s3_key,
        caption_credit_cost, auto_caption_cost_breakdown,
    ) = await _upload_and_finalize_auto_caption(
        clip_path, primary_path, auto_captioned, clip, default_style_kwargs,
        user_id, job_id, clip_index, clip_filename, bucket,
    )
    thumbnail_s3_key = _upload_reel_clip_thumbnail(clip, primary_path, output_dir, job_id, clip_index, user_id, bucket)

    duration = _compute_clip_duration_seconds(clip)
    reel_cost_breakdown = _estimate_reel_cost_breakdown(
        duration_seconds=float(duration or 0),
        size_bytes=float(clip_size_bytes),
        uses_youtube_source=uses_youtube_source,
    )

    reel_row = {
        "reel_url": media_url,
        "reel_thumbnail_url": thumbnail_s3_key if thumbnail_s3_key else "",
        "reel_title": clip.get("title") or clip.get("video_title_for_youtube_short") or f"Clip {i}",
        "reel_description": clip.get("video_description_for_instagram") or clip.get("video_description_for_tiktok") or "",
        "reel_duration": max(30, int(duration or 0)),
        "reel_created_at": now_iso,
        "reel_updated_at": now_iso,
        "reel_user_id": user_id,
        "reel_status": "termine",
        "reel_size_bytes": clip_size_bytes,
        "reel_s3_key": s3_key,
        "reel_job_id": job_id,
        "reel_clip_index": clip_index,
        "billing_details": _build_billing_details(
            "generation_reel",
            reel_cost_breakdown,
            actual_storage_gb=_bytes_to_gb(clip_size_bytes),
            extra={
                "clip_index": clip_index,
                "original_s3_key": original_s3_key,
                "auto_caption": {
                    "applied": auto_captioned,
                    "credit_cost": caption_credit_cost,
                    "cost_breakdown": auto_caption_cost_breakdown,
                },
            },
        ),
        "total_cost_usd": 0,
    }

    if project_id:
        reel_row["project_id"] = project_id

    return reel_row


async def _persist_reels_for_job(
    job_id: str,
    user_id: str,
    output_dir: str,
    metadata_path: str,
    clips: List[Dict[str, Any]],
    uses_youtube_source: bool = False,
    project_id: Optional[str] = None,
    transcript: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    if not user_id:
        raise RuntimeError("Missing app user id for reel persistence")
    if not is_supabase_configured():
        raise RuntimeError("Supabase reels is not configured")

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET is required for reel persistence")

    base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    rows: List[Dict[str, Any]] = []

    for i, clip in enumerate(clips, start=1):
        reel_row = await _build_reel_row_for_clip(
            job_id, user_id, output_dir, bucket, base_name, clip, i, now_iso, uses_youtube_source, project_id, transcript,
        )
        if reel_row:
            rows.append(reel_row)

    if not rows:
        raise RuntimeError("No generated clips were available for Supabase persistence")

    saved_rows = await supabase_insert_reels(rows)

    # Update project output count if project exists
    if project_id:
        try:
            await supabase_increment_project_output_count(project_id, user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to increment project output count: {str(e)}")

    return [_normalize_reel_row(row) for row in saved_rows]

def _is_job_expired(jdata: Dict[str, Any], now: float) -> bool:
    return bool(
        jdata.get("status") in ("completed", "failed")
        and jdata.get("output_dir")
        and os.path.isdir(jdata["output_dir"])
        and now - os.path.getmtime(jdata["output_dir"]) > JOB_RETENTION_SECONDS
    )


def _cleanup_expired_in_memory_jobs(now: float) -> None:
    # Cleanup in-memory API jobs (artifacts are cleaned by batched output sweeps).
    expired_api_jobs = [jid for jid, jdata in jobs.items() if _is_job_expired(jdata, now)]
    for jid in expired_api_jobs:
        del jobs[jid]

    # Cleanup SaaSShorts jobs from memory
    try:
        saas_expired = [jid for jid, jdata in saas_jobs.items() if _is_job_expired(jdata, now)]
        for jid in saas_expired:
            del saas_jobs[jid]
    except NameError:
        pass


def _cleanup_expired_uploads(now: float) -> None:
    for filename in os.listdir(UPLOAD_DIR):
        file_path = os.path.join(UPLOAD_DIR, filename)
        try:
            if now - os.path.getmtime(file_path) > JOB_RETENTION_SECONDS:
                os.remove(file_path)
        except Exception:
            pass


async def _reconcile_orphaned_jobs_on_startup() -> None:
    """Terminate and refund jobs left non-terminal by a previous process's
    restart/crash.

    Job execution state (JobManager.runtime_jobs, the in-memory queue) is
    never persisted -- only the Supabase job row survives a restart. A row
    still marked created/queued/processing/retry_wait from a prior process
    lifetime can never actually be resumed or retried (nothing will ever
    re-enqueue it), yet it keeps counting against MAX_ACTIVE_JOBS_PER_USER
    forever, eventually locking the affected users out of starting any new
    job. Runs once at startup, before the queue workers begin accepting
    new submissions.
    """
    if not is_supabase_configured():
        return
    try:
        orphaned = await supabase_list_active_jobs()
    except Exception as e:
        print(f"⚠️ Startup job reconciliation: failed to list active jobs: {e}")
        return

    for row in orphaned:
        job_id = row.get("id")
        user_id = row.get("user_id")
        if not job_id or not user_id:
            continue
        operation_type = "sous_titre" if row.get("queue_name") == "captions" else "generation_reel"
        try:
            await reel_job_manager.force_fail_orphaned_job(
                job_id,
                user_id,
                float(row.get("reserved_quota") or 0.0),
                operation_type=operation_type,
            )
        except Exception as e:
            print(f"⚠️ Startup job reconciliation: failed to close orphaned job {job_id}: {e}")

    if orphaned:
        print(f"🧹 Startup job reconciliation: closed {len(orphaned)} orphaned job(s) from a previous process.")


async def process_temp_file_cleanup_jobs():
    """One of the 3 required retention background processes (see the
    media lifecycle rework's module notes): cleans up local job temp
    artifacts (FFmpeg intermediates, extracted frames/chunks, uploads,
    finished job output dirs) -- a DIFFERENT category from the S3-persisted
    media the other two retention sweeps manage, governed by its own
    RETENTION_TEMP_FILES_HOURS (see JOB_RETENTION_SECONDS) rather than the
    per-media-type RETENTION_FREE_*/RETENTION_SUBSCRIBER_* durations.
    Idempotent: a file already gone by the time this runs is simply not
    there to remove again (os.remove's OSError is caught per-file, see
    _cleanup_expired_uploads), never a reason to fail the whole sweep."""
    import time
    print("🧹 Cleanup task started.")
    last_output_sweep = 0.0
    while True:
        try:
            await asyncio.sleep(300) # Check every 5 minutes
            now = time.time()

            if OUTPUT_SWEEP_INTERVAL_SECONDS > 0 and (now - last_output_sweep) >= OUTPUT_SWEEP_INTERVAL_SECONDS:
                removed_count = _sweep_output_directory(now)
                print(f"🧹 Output sweep completed (removed {removed_count} entries).")
                last_output_sweep = now

            _cleanup_expired_in_memory_jobs(now)
            _cleanup_expired_uploads(now)

        except Exception as e:
            print(f"⚠️ Cleanup error: {e}")

async def process_queue(worker_name: str):
    """Background worker to process jobs from the queue with concurrency limit."""
    print(f"🚀 Job Queue Worker {worker_name} started with {MAX_CONCURRENT_JOBS} concurrent slots.")
    while True:
        try:
            # Wait for a job
            queue_item = await job_queue.get()
            _, _, job_id = queue_item
            runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id) or {}
            job_priority = _clamp_job_priority(runtime_job.get("priority", DEFAULT_JOB_PRIORITY))

            # Acquire semaphore slot (waits if max jobs are running)
            await concurrency_semaphore.acquire()
            print(f"🔄 [{worker_name}] Acquired slot for job: {job_id} (priority={job_priority})")

            # Process in background task to not block the loop (allowing other slots to fill)
            _spawn_background_task(run_job_wrapper(job_id, job_priority))

        except Exception as e:
            print(f"❌ Queue dispatch error: {e}")
            await asyncio.sleep(1)

async def run_job_wrapper(job_id: str, job_priority: int):
    """Wrapper to run job and release semaphore"""
    execution_ctx: Dict[str, Any] = {
        "process": None,
        "preempt_requested": False,
        "priority": _clamp_job_priority(job_priority),
        "started_at": time.time(),
    }
    async with running_reel_jobs_lock:
        running_reel_jobs[job_id] = execution_ctx
    try:
        job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id)
        if job:
            job["priority"] = execution_ctx["priority"]
            if str(job.get("job_kind") or "reel") == "caption":
                await run_caption_job(job_id, job, execution_ctx=execution_ctx)
            else:
                await run_job(job_id, job, execution_ctx=execution_ctx)
    except Exception as e:
         print(f"❌ Job wrapper error {job_id}: {e}")
    finally:
        async with running_reel_jobs_lock:
            running_reel_jobs.pop(job_id, None)
        # Always release semaphore and mark queue task done
        concurrency_semaphore.release()
        job_queue.task_done()
        print(f"✅ Released slot for job: {job_id}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Close out jobs orphaned by a previous process's restart/crash before
    # accepting new submissions, so they stop counting against
    # MAX_ACTIVE_JOBS_PER_USER (see _reconcile_orphaned_jobs_on_startup).
    await _reconcile_orphaned_jobs_on_startup()

    # Start worker and cleanup
    worker_tasks = [
        asyncio.create_task(process_queue(f"worker-{idx + 1}"))
        for idx in range(max(1, QUEUE_WORKER_COUNT))
    ]
    cleanup_task = asyncio.create_task(process_temp_file_cleanup_jobs())
    scheduler_task = asyncio.create_task(process_scheduled_social_publish_jobs())
    annual_credit_refill_task = asyncio.create_task(process_annual_credit_refill_jobs())
    media_expiration_task = asyncio.create_task(process_media_expiration_jobs())
    media_expiry_notification_task = asyncio.create_task(process_media_expiry_notification_jobs())
    yield
    # Cleanup (optional: cancel worker)
    for task in worker_tasks:
        task.cancel()
    cleanup_task.cancel()
    scheduler_task.cancel()
    annual_credit_refill_task.cancel()
    media_expiration_task.cancel()
    media_expiry_notification_task.cancel()

app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend.
# Security: a wildcard origin combined with allow_credentials=True lets any
# website make authenticated-as-any-caller cross-origin requests and read
# the JSON response -- an explicit allow-list is required instead. Defaults
# to FRONTEND_ORIGIN (already a required, exact-origin env var used for the
# OAuth postMessage target); additional origins (e.g. a staging domain) can
# be added via CORS_ALLOWED_ORIGINS (comma-separated).
_cors_extra_origins = [
    o.strip() for o in os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]
_cors_allowed_origins = sorted({FRONTEND_ORIGIN, *_cors_extra_origins})
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for serving videos
app.mount("/videos", StaticFiles(directory=OUTPUT_DIR), name="videos")

# Mount static files for serving thumbnails
THUMBNAILS_DIR = os.path.join(OUTPUT_DIR, "thumbnails")
os.makedirs(THUMBNAILS_DIR, exist_ok=True)
app.mount("/thumbnails", StaticFiles(directory=THUMBNAILS_DIR), name="thumbnails")

# Mount static files for serving cached film-summary narrator voice previews
# (see get_film_summary_voice_preview_endpoint) -- generated once per voice
# on first request, then served from disk forever after.
FILM_SUMMARY_VOICE_PREVIEWS_DIR = os.path.join(OUTPUT_DIR, "voice_previews")
os.makedirs(FILM_SUMMARY_VOICE_PREVIEWS_DIR, exist_ok=True)
app.mount("/voice-previews", StaticFiles(directory=FILM_SUMMARY_VOICE_PREVIEWS_DIR), name="voice_previews")

class ProcessRequest(BaseModel):
    url: str

def enqueue_output(out, job_id):
    """Reads output from a subprocess and appends it to jobs logs."""
    try:
        for line in iter(out.readline, b''):
            decoded_line = line.decode('utf-8').strip()
            if decoded_line:
                print(f"📝 [Job Output] {decoded_line}")
                if job_id in jobs:
                    jobs[job_id]['logs'].append(decoded_line)
    except Exception as e:
        print(f"Error reading output for job {job_id}: {e}")
    finally:
        out.close()


async def _close_proxy_stream(upstream, client):
    try:
        await upstream.aclose()
    finally:
        await client.aclose()


@app.get("/api/media/proxy", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def proxy_media(request: Request, url: str, user_id: Annotated[str, Depends(get_user_id_header_or_query_token)]):
    """Proxy remote media through the backend so browser-side Remotion can fetch it same-origin.

    Security: this endpoint performs a server-side HTTP request to a URL the
    caller fully controls -- a classic SSRF primitive. It must never be
    reachable without authentication, and every request (including redirect
    hops) must go through _validate_download_url so it cannot be used to
    reach cloud metadata endpoints or internal/loopback services.

    Auth is verified via get_user_id_header_or_query_token rather than the
    usual header-only dependency: this URL is loaded directly by <video>/
    <img> markup (preview players, Remotion), which never attaches an
    Authorization header, so the frontend instead appends the caller's JWT
    as a `token` query parameter (see toBrowserSafeMediaUrl).
    """
    import httpx

    _validate_download_url(url)

    forward_headers = {}
    if request.headers.get("range"):
        forward_headers["Range"] = request.headers["range"]
    if request.headers.get("user-agent"):
        forward_headers["User-Agent"] = request.headers["user-agent"]

    client = httpx.AsyncClient(follow_redirects=False, timeout=120.0)
    try:
        upstream = await _validated_stream_request(client, "GET", url, headers=forward_headers)
    except Exception:
        await client.aclose()
        raise

    passthrough_headers = {}
    for header in ("content-type", "content-length", "accept-ranges", "content-range", "etag", "last-modified", "cache-control"):
        value = upstream.headers.get(header)
        if value:
            passthrough_headers[header] = value

    passthrough_headers["Access-Control-Allow-Origin"] = "*"
    passthrough_headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range, Accept-Ranges, ETag, Last-Modified"

    return StreamingResponse(
        upstream.aiter_bytes(),
        status_code=upstream.status_code,
        headers=passthrough_headers,
        background=BackgroundTask(_close_proxy_stream, upstream, client),
    )

def _spawn_job_subprocess(cmd, env, job_id: str, execution_ctx: Optional[Dict[str, Any]]):
    # Sonar false positive (S7487): this supervises the child process with
    # Popen + a non-blocking .poll()/.terminate() loop yielding via
    # `await asyncio.sleep(2)` between checks -- Popen's own spawn and
    # .poll()/.terminate() calls don't block the loop for any
    # meaningful duration (they're near-instant syscalls), and stdout
    # is drained on a dedicated thread below rather than on this task.
    # Converting to asyncio.create_subprocess_exec would need a
    # parallel rewrite of the preemption/timeout/partial-result-polling
    # state machine below and the threaded log capture -- deliberately
    # deferred as its own separately-tested change given how central
    # this function is to job execution, rather than rewritten
    # untested in the same pass as unrelated Sonar findings.
    process = subprocess.Popen(  # NOSONAR
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, # Merge stderr to stdout
        env=env,
        cwd=os.getcwd()
    )
    if execution_ctx is not None:
        execution_ctx["process"] = process

    # We need to capture logs in a thread because Popen isn't async
    t_log = threading.Thread(target=enqueue_output, args=(process.stdout, job_id))
    t_log.daemon = True
    t_log.start()
    return process


def _terminate_job_process_if_needed(process, job_id: str, execution_ctx: Optional[Dict[str, Any]], start_wait: float) -> None:
    if execution_ctx and execution_ctx.get("preempt_requested"):
        try:
            process.terminate()  # NOSONAR(S7487) same rationale as the Popen() call above
        except Exception:
            pass
    elif time.time() - start_wait > REEL_JOB_MAX_PROCESSING_SECONDS:
        # Security/reliability: kill a job that has been running far
        # longer than any legitimate input should require, instead
        # of letting it occupy a worker slot indefinitely (see
        # security audit finding H13).
        jobs[job_id]['logs'].append(
            f"Job exceeded max processing time ({REEL_JOB_MAX_PROCESSING_SECONDS}s); terminating."
        )
        try:
            process.terminate()  # NOSONAR(S7487) same rationale as the Popen() call above
        except Exception:
            pass


async def _publish_partial_reel_results_if_ready(output_dir: str, job_id: str, pipeline) -> None:
    # Check for partial results every 2 seconds. Look for metadata file.
    try:
        json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
        if not json_files:
            return
        target_json = json_files[0]
        # Read metadata (it might be being written to, so simple try/except or just read)
        # Use a lock or just robust read? json.load might fail if file is partial.
        # Usually main.py writes it once at start (based on my review).
        if os.path.getsize(target_json) <= 0:
            return
        # Sonar false positive (S7493): a small, infrequent read
        # (this loop only reaches here once every 2s, see
        # the `await asyncio.sleep(2)` a few lines up) --
        # not worth the risk of converting to aiofiles here,
        # which would break this function's existing
        # `builtins.open` test-mocking (aiofiles captures
        # its own reference to open() at import time, before
        # a test's monkeypatch of builtins.open can apply).
        with open(target_json, 'r') as f:  # NOSONAR
            data = json.load(f)

        base_name = os.path.basename(target_json).replace(_METADATA_JSON_SUFFIX, '')
        clips = data.get('shorts', [])
        cost_analysis = data.get('cost_analysis')

        # Check which clips actually exist on disk
        ready_clips = []
        for i, clip in enumerate(clips):
            clip_filename = f"{base_name}_clip_{i+1}.mp4"
            clip_path = os.path.join(output_dir, clip_filename)
            if os.path.exists(clip_path) and os.path.getsize(clip_path) > 0:
                # Checking if file is growing? For now assume if it exists and main.py moves it there, it's done.
                # main.py writes to temp_... then moves to final name. So presence means ready!
                clip_copy = dict(clip)
                clip_copy['video_url'] = f"/videos/{job_id}/{clip_filename}"
                clip_copy['reel_clip_index'] = i
                clip_copy['reel_job_id'] = job_id
                ready_clips.append(clip_copy)

        if ready_clips:
            jobs[job_id]['result'] = {'clips': ready_clips, 'cost_analysis': cost_analysis}
            await pipeline.cutting_clips()
    except Exception:
        # Ignore read errors during processing
        pass


async def _supervise_job_subprocess(process, job_id: str, output_dir: str, pipeline, execution_ctx: Optional[Dict[str, Any]]) -> int:
    start_wait = time.time()
    while process.poll() is None:  # NOSONAR(S7487) same rationale as the Popen() call above
        _terminate_job_process_if_needed(process, job_id, execution_ctx, start_wait)
        await asyncio.sleep(2)
        await _publish_partial_reel_results_if_ready(output_dir, job_id, pipeline)
    return process.returncode


async def _requeue_preempted_job(job_id: str, job_priority: int) -> None:
    jobs[job_id]['status'] = 'queued'
    jobs[job_id]['logs'].append("Job preempted by a higher-priority task and re-queued.")
    await reel_job_manager.enqueue_job(job_id)
    await enqueue_reel_job(job_id, priority=job_priority)


def _find_completed_job_metadata_path(job_id: str, output_dir: str) -> Optional[str]:
    json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
    if not json_files:
        # Backward-compat rescue if outputs were written to OUTPUT_DIR root
        if _relocate_root_job_artifacts(job_id, output_dir):
            json_files = glob.glob(os.path.join(output_dir, _METADATA_JSON_GLOB))
    return json_files[0] if json_files else None


async def _persist_completed_reel_job_or_fail(
    job_id: str, job_data: Dict[str, Any], output_dir: str, user_id: Optional[str],
    source_is_url: bool, target_json: str, clips: List[Dict[str, Any]], start_ts: float,
    transcript: Optional[Dict[str, Any]] = None,
):
    try:
        project_id = job_data.get("project_id") if job_data else None
        return await _persist_reels_for_job(
            job_id=job_id,
            user_id=user_id,
            output_dir=output_dir,
            metadata_path=target_json,
            clips=clips,
            uses_youtube_source=source_is_url,
            project_id=project_id,
            transcript=transcript,
        )
    except Exception as persist_error:
        jobs[job_id]['status'] = 'failed'
        jobs[job_id]['logs'].append(f"Supabase persistence failed: {persist_error}")
        fail_result = await _finalize_failed_reel_job(
            job_id=job_id,
            user_id=user_id,
            output_dir=output_dir,
            job_data=job_data,
            start_ts=start_ts,
            error_message=f"Supabase persistence failed: {persist_error}",
            error_code="REEL_PERSISTENCE_FAILED",
            retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
        )
        if fail_result.get("retry"):
            _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))
        return None


def _enrich_clips_with_saved_rows(clips: List[Dict[str, Any]], saved_rows: List[Dict[str, Any]], job_id: str) -> List[Dict[str, Any]]:
    enriched_clips: List[Dict[str, Any]] = []
    for i, clip in enumerate(clips):
        clip_copy = dict(clip)
        clip_copy['reel_clip_index'] = i
        clip_copy['reel_job_id'] = job_id
        if i < len(saved_rows):
            clip_copy['video_url'] = saved_rows[i].get('reel_playback_url') or saved_rows[i].get('reel_url')
            clip_copy['reel_id'] = saved_rows[i].get('id')
            clip_copy['thumbnail_url'] = saved_rows[i].get('reel_thumbnail_url') or saved_rows[i].get('reel_preview_url') or ''
            clip_copy['preview_image_url'] = saved_rows[i].get('reel_preview_url') or saved_rows[i].get('reel_thumbnail_url') or ''
        enriched_clips.append(clip_copy)
    return enriched_clips


async def _debit_auto_caption_credits_for_completed_job(job_id: str, user_id: Optional[str], saved_rows: List[Dict[str, Any]]) -> None:
    """Bills the per-clip auto-caption credit cost recorded on each saved
    reel row (see _burn_default_captions_for_clip) -- additive to the reel
    generation charge in _finalize_completed_reel_billing, but merged into
    that same job_id's user_data_history row (same operation_id, via
    upsert_user_data_history_entry) rather than its own separate line: to
    the user this is one reel generation, so it should show up as one
    history entry whose amount includes this cost and whose nature stays
    "generation_reel" (the primary charge for this job_id is always billed
    first -- see job_manager.debit_credits_for_job, called from
    _finalize_completed_reel_billing before this function is). The storage
    side is already counted in that charge's total_reel_size_bytes
    (reel_size_bytes is the post-burn, captioned file size), so only credit
    is added here."""
    auto_caption_credit_total = sum(
        float(((row.get("billing_details") or {}).get("auto_caption") or {}).get("credit_cost") or 0.0)
        for row in saved_rows
    )
    if not (is_supabase_configured() and user_id and auto_caption_credit_total > 0):
        return
    try:
        caption_debited = await supabase_deduct_user_credits(user_id, auto_caption_credit_total, 0.0)
        if caption_debited:
            await supabase_upsert_user_data_history_entry(
                user_id=user_id,
                credit=auto_caption_credit_total,
                storage=0.0,
                operation="output",
                operation_type="sous_titre",
                operation_id=job_id,
            )
    except Exception as caption_billing_error:
        logger.exception("Auto-caption billing update failed for job %s", job_id)
        jobs[job_id]['logs'].append(f"Auto-caption billing update failed: {caption_billing_error}")


async def _finalize_completed_reel_billing(
    job_id: str, job_data: Dict[str, Any], user_id: Optional[str], source_is_url: bool,
    start_ts: float, enriched_clips: List[Dict[str, Any]], cost_analysis, saved_rows: List[Dict[str, Any]],
) -> None:
    elapsed = round(calc_elapsed_seconds(start_ts), 3)
    total_reel_size_bytes = sum(int(row.get("reel_size_bytes") or 0) for row in saved_rows)
    billing = _estimate_reel_job_consumption(
        elapsed_seconds=elapsed,
        uses_youtube=source_is_url,
        processed_clips=len(saved_rows),
        expected_clips=len(enriched_clips),
        storage_bytes=total_reel_size_bytes,
    )
    retention = await _finalize_retention_billing_batch(job_id, user_id, [
        {
            "content_kind": CONTENT_KIND_REEL,
            "content_id": row.get("id"),
            "media_type": MEDIA_TYPE_PRODUCED,
            "size_bytes": row.get("reel_size_bytes"),
            "s3_bucket": os.environ.get("AWS_S3_BUCKET", "my-clips-bucket"),
            "s3_key": row.get("reel_s3_key"),
        }
        for row in saved_rows
    ])
    if retention["retention_storage_cost_usd"] or retention["retention_storage_credit_cost"]:
        billing["actual_cost_usd"] = round(billing["actual_cost_usd"] + retention["retention_storage_cost_usd"], 6)
        billing["actual_credit"] = round(billing["actual_credit"] + retention["retention_storage_credit_cost"], 2)
        billing["cost_breakdown"] = {
            **billing["cost_breakdown"],
            "retention_storage_cost_usd": retention["retention_storage_cost_usd"],
            "retention_storage_credit_cost": retention["retention_storage_credit_cost"],
            "media_assets": retention["media_assets"],
        }

    debit_applied = False
    logger.info(f"Billing info for job {job_id}: {billing}")
    job_reserved_credits = float(job_data.get("reel_required_credits") or 0.0)
    # Settle whenever there's an actual charge/storage change OR an
    # outstanding reservation to release -- otherwise a job whose
    # actual cost rounds to 0 would never refund its reservation.
    if is_supabase_configured() and user_id and (
        billing["actual_credit"] > 0 or billing["actual_storage_gb"] > 0 or job_reserved_credits > 0
    ):
        try:
            logger.info(f"Debiting credits for job {job_id}")
            debit_applied = await reel_job_manager.debit_credits_for_job(
                job_id=job_id,
                user_id=user_id,
                credits=billing["actual_credit"],
                storage_delta=-billing["actual_storage_gb"],
                operation_type="generation_reel",
                reserved_credits=job_reserved_credits,
            )
        except Exception as billing_error:
            logger.exception("Billing update failed")
            jobs[job_id]['logs'].append(f"Billing update failed: {billing_error}")

    # Additive to the reel generation charge above -- see
    # _debit_auto_caption_credits_for_completed_job for why.
    await _debit_auto_caption_credits_for_completed_job(job_id, user_id, saved_rows)

    result_payload = {
        'clips': enriched_clips,
        'cost_analysis': cost_analysis,
        'reels': saved_rows,
        'duration_seconds': elapsed,
        'billing': {
            'actual_cost_usd': billing['actual_cost_usd'],
            'actual_credit': billing['actual_credit'],
            'actual_storage_gb': billing['actual_storage_gb'],
            'processing_ratio': billing['processing_ratio'],
            'debit_applied': bool(debit_applied),
        },
    }
    await reel_job_manager.complete_job(
        job_id,
        result_payload,
        actual_cost_usd=billing['actual_cost_usd'],
        actual_credit=billing['actual_credit'],
        actual_storage_gb=billing['actual_storage_gb'],
        consumed_quota=billing['processing_ratio'],
        cost_breakdown=billing['cost_breakdown'],
    )


def _derive_reel_completion_summary_text(enriched_clips: List[Dict[str, Any]], saved_rows: List[Dict[str, Any]]) -> str:
    summary_text = ""
    if enriched_clips:
        top_clip = enriched_clips[0] if isinstance(enriched_clips[0], dict) else {}
        summary_text = (
            str(top_clip.get("video_description_for_instagram") or "")
            or str(top_clip.get("video_description_for_tiktok") or "")
            or str(top_clip.get("video_title_for_youtube_short") or "")
        )
    if not summary_text and saved_rows:
        first_row = saved_rows[0] if isinstance(saved_rows[0], dict) else {}
        summary_text = str(first_row.get("reel_description") or "")
    return summary_text


def _build_reel_completion_project_updates(job_data: Dict[str, Any], summary_text: str, saved_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    project_updates = {
        "description": _build_short_project_summary(summary_text),
        "output_count": len(saved_rows),
    }
    source_duration_value = int(float((job_data or {}).get("source_duration_seconds") or 0.0))
    if source_duration_value > 0:
        project_updates["source_duration"] = source_duration_value
    return project_updates


async def _update_project_on_reel_completion(
    job_data: Dict[str, Any], user_id: Optional[str], enriched_clips: List[Dict[str, Any]], saved_rows: List[Dict[str, Any]],
) -> None:
    project_id = job_data.get("project_id") if job_data else None
    if not (project_id and is_supabase_configured()):
        return
    try:
        await supabase_update_project_status(project_id, "completed", user_id=user_id)
        summary_text = _derive_reel_completion_summary_text(enriched_clips, saved_rows)
        project_updates = _build_reel_completion_project_updates(job_data, summary_text, saved_rows)
        await supabase_update_project(project_id, user_id or "", project_updates)
        logger.info(f"Project {project_id} marked as completed")
    except Exception as e:
        logger.warning(f"Failed to update project status to completed: {str(e)}")


_SOURCE_VIDEO_BASENAME = "source"
_SOURCE_VIDEO_EXTENSIONS = _COMMON_VIDEO_EXTENSIONS + (".m4v",)


def _find_leftover_source_video(output_dir: str) -> Optional[str]:
    """Locates the original video main.py downloaded for a plain YouTube URL
    job (kept around thanks to --keep-original), when app.py itself never
    learned its path (see _prepare_process_job_from_url's `-u` branch).
    Picks the first video file in the job's output dir that isn't a
    generated reel clip (`..._clip_N.mp4`) or an already-preserved source."""
    if not os.path.isdir(output_dir):
        return None
    for name in sorted(os.listdir(output_dir)):
        lower = name.lower()
        if not lower.endswith(_SOURCE_VIDEO_EXTENSIONS):
            continue
        if "_clip_" in lower or lower.startswith(f"{_SOURCE_VIDEO_BASENAME}."):
            continue
        return os.path.join(output_dir, name)
    return None


async def _upload_and_bill_preserved_source_video(job_id: str, user_id: Optional[str], local_path: str) -> None:
    """Backs up the locally preserved source video to S3 and debits the
    storage it consumes from the user's quota, the same way every other
    reel artifact's storage is billed (see _build_reel_row_for_clip's
    original_s3_key). Merged into this job_id's own user_data_history row
    (same operation_id, via upsert_user_data_history_entry) instead of its
    own separate line, same reasoning as
    _debit_auto_caption_credits_for_completed_job -- this call can run
    before or after that job's primary charge is billed (this function
    runs earlier in the reel pipeline), but both already share
    operation_type "generation_reel" so which one creates the row first
    doesn't matter here. Best-effort: the local copy is what actually
    powers manual clipping (_resolve_preserved_source_video), so a failure
    here never affects that -- it only means the backup/billing didn't
    happen."""
    if not user_id or not is_supabase_configured():
        return
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return
    try:
        ext = os.path.splitext(local_path)[1].lower() or ".mp4"
        s3_key = f"reels/{user_id}/{job_id}/source{ext}"
        if not upload_file_to_s3(local_path, bucket, s3_key):
            return
        storage_gb = _bytes_to_gb(int(os.path.getsize(local_path) or 0))
        if storage_gb <= 0:
            return
        debited = await supabase_deduct_user_credits(user_id, 0.0, -storage_gb)
        if debited:
            await supabase_upsert_user_data_history_entry(
                user_id=user_id,
                credit=0.0,
                storage=round(storage_gb, 6),
                operation="output",
                operation_type="generation_reel",
                operation_id=job_id,
            )
    except Exception as exc:
        logger.warning("Failed to upload/bill preserved source video for job %s: %s", job_id, exc)


async def _preserve_source_video_for_manual_clipping(
    job_id: str, job_data: Dict[str, Any], output_dir: str, user_id: Optional[str] = None,
) -> None:
    """Keeps a copy of the full source video after a reel job completes, so
    the user can later pick their own start/end range by hand (see
    POST /api/reels/{job_id}/custom-clip) instead of only the AI-selected
    clips -- even though the AI pipeline itself only ever needed the source
    transiently and normally has it deleted (uploads: run_job's
    _cleanup_job_input_file; plain YouTube URLs: main.py's own end-of-run
    cleanup, unless --keep-original was passed). The copy is also backed up
    to S3 and billed as storage against the user's quota, like any other
    reel artifact (see _upload_and_bill_preserved_source_video).

    Best-effort: any failure here must never fail the job itself -- it just
    means manual clipping won't be available for this particular job."""
    try:
        candidate = str(job_data.get("input_path") or "")
        if not candidate or not os.path.exists(candidate):
            candidate = _find_leftover_source_video(output_dir) or ""
        if not candidate or not os.path.exists(candidate):
            return
        ext = os.path.splitext(candidate)[1].lower() or ".mp4"
        if ext not in _SOURCE_VIDEO_EXTENSIONS:
            ext = ".mp4"
        dest = os.path.join(output_dir, f"{_SOURCE_VIDEO_BASENAME}{ext}")
        if os.path.abspath(candidate) != os.path.abspath(dest):
            shutil.copyfile(candidate, dest)
        await _upload_and_bill_preserved_source_video(job_id, user_id, dest)
    except Exception as exc:
        logger.warning("Failed to preserve source video for manual clipping (job %s): %s", job_id, exc)


def _resolve_preserved_source_video(output_dir: str) -> Optional[str]:
    """Finds the source video _preserve_source_video_for_manual_clipping
    saved for this job, if any (and if the job's output dir hasn't been
    swept yet by the retention cleanup -- see JOB_RETENTION_SECONDS)."""
    if not os.path.isdir(output_dir):
        return None
    for ext in _SOURCE_VIDEO_EXTENSIONS:
        candidate = os.path.join(output_dir, f"{_SOURCE_VIDEO_BASENAME}{ext}")
        if os.path.exists(candidate):
            return candidate
    return None


def _ensure_preserved_source_video_available(job_id: str, user_id: str, output_dir: str) -> Optional[str]:
    """Like _resolve_preserved_source_video, but falls back to re-downloading
    the S3 backup (see _upload_and_bill_preserved_source_video) when the
    local copy has been swept by the retention cleanup -- so manual clipping
    (and the project-level "Creation manuelle" scene view) keeps working
    long after a job's output dir is gone, not just within the first hour."""
    local_path = _resolve_preserved_source_video(output_dir)
    if local_path:
        return local_path

    if not (is_supabase_configured() and user_id):
        return None
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return None

    try:
        os.makedirs(output_dir, exist_ok=True)
        for ext in _SOURCE_VIDEO_EXTENSIONS:
            s3_key = f"reels/{user_id}/{job_id}/source{ext}"
            if get_s3_object_size(bucket, s3_key) <= 0:
                continue
            dest = os.path.join(output_dir, f"{_SOURCE_VIDEO_BASENAME}{ext}")
            if download_s3_object(bucket, s3_key, dest):
                return dest
    except Exception as exc:
        logger.warning("Failed to re-download preserved source video for job %s: %s", job_id, exc)
    return None


async def _handle_completed_reel_job_with_metadata(
    job_id: str, job_data: Dict[str, Any], output_dir: str, user_id: Optional[str],
    source_is_url: bool, start_ts: float, target_json: str, pipeline,
) -> None:
    # Sonar false positive (S7493): same reasoning as the read above in
    # this function -- small one-off read, and this function's
    # tests patch builtins.open directly (which aiofiles, having
    # captured its own reference to the real open() at import
    # time, wouldn't observe).
    with open(target_json, 'r') as f:  # NOSONAR
        data = json.load(f)

    # Enhance result with video URLs
    clips = data.get('shorts', [])
    cost_analysis = data.get('cost_analysis')

    await pipeline.uploading_reels(len(clips))
    saved_rows = await _persist_completed_reel_job_or_fail(
        job_id, job_data, output_dir, user_id, source_is_url, target_json, clips, start_ts,
        transcript=data.get("transcript"),
    )
    if saved_rows is None:
        return

    await _preserve_source_video_for_manual_clipping(job_id, job_data, output_dir, user_id)

    enriched_clips = _enrich_clips_with_saved_rows(clips, saved_rows, job_id)

    jobs[job_id]['result'] = {
        'clips': enriched_clips,
        'cost_analysis': cost_analysis,
        'reels': saved_rows,
    }
    await pipeline.finalizing()
    await _finalize_completed_reel_billing(job_id, job_data, user_id, source_is_url, start_ts, enriched_clips, cost_analysis, saved_rows)
    await _update_project_on_reel_completion(job_data, user_id, enriched_clips, saved_rows)

    _cleanup_generated_clips_after_job(output_dir, os.path.basename(target_json).replace(_METADATA_JSON_SUFFIX, ''))


async def _handle_completed_reel_job_without_metadata(job_id: str, job_data: Dict[str, Any], output_dir: str, start_ts: float) -> None:
    jobs[job_id]['status'] = 'failed'
    jobs[job_id]['logs'].append("No metadata file generated.")
    result = await _finalize_failed_reel_job(
        job_id=job_id,
        user_id=job_data.get("user_id"),
        output_dir=output_dir,
        job_data=job_data,
        start_ts=start_ts,
        error_message="No metadata file generated",
        error_code="METADATA_NOT_FOUND",
        retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
    )
    if result.get("retry"):
        _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))


async def _handle_completed_reel_job(job_id: str, job_data: Dict[str, Any], output_dir: str, user_id: Optional[str], source_is_url: bool, start_ts: float, pipeline) -> None:
    jobs[job_id]['status'] = 'completed'
    jobs[job_id]['logs'].append("Process finished successfully.")

    target_json = _find_completed_job_metadata_path(job_id, output_dir)
    if target_json:
        await _handle_completed_reel_job_with_metadata(job_id, job_data, output_dir, user_id, source_is_url, start_ts, target_json, pipeline)
    else:
        await _handle_completed_reel_job_without_metadata(job_id, job_data, output_dir, start_ts)


async def _handle_failed_reel_job_process(job_id: str, job_data: Dict[str, Any], output_dir: str, start_ts: float, returncode: int) -> None:
    jobs[job_id]['status'] = 'failed'
    jobs[job_id]['logs'].append(f"Process failed with exit code {returncode}")
    result = await _finalize_failed_reel_job(
        job_id=job_id,
        user_id=job_data.get("user_id"),
        output_dir=output_dir,
        job_data=job_data,
        start_ts=start_ts,
        error_message=f"Process failed with exit code {returncode}",
        error_code="PROCESS_EXIT",
        retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
    )
    if result.get("retry"):
        _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))


async def _handle_reel_job_execution_error(job_id: str, job_data: Dict[str, Any], output_dir: str, start_ts: float, error: Exception) -> None:
    jobs[job_id]['status'] = 'failed'
    jobs[job_id]['logs'].append(f"Execution error: {str(error)}")
    result = await _finalize_failed_reel_job(
        job_id=job_id,
        user_id=job_data.get("user_id"),
        output_dir=output_dir,
        job_data=job_data,
        start_ts=start_ts,
        error_message=f"Execution error: {str(error)}",
        error_code="EXECUTION_ERROR",
        retry_delay_seconds=REEL_JOB_RETRY_DELAY_SECONDS,
    )
    if result.get("retry"):
        _spawn_background_task(_schedule_reel_retry(job_id, REEL_JOB_RETRY_DELAY_SECONDS))


def _cleanup_job_input_file(input_path: Optional[str], job_id: str) -> None:
    # Only remove uploaded source files (stored under UPLOAD_DIR).
    # Downloaded files inside output/<job_id>/ must be preserved for retries;
    # they will be cleaned up by the periodic output sweep.
    if input_path and os.path.exists(input_path):
        output_job_dir = os.path.abspath(os.path.join(OUTPUT_DIR, job_id))
        is_in_output_dir = os.path.abspath(input_path).startswith(output_job_dir)
        if not is_in_output_dir:
            try:
                os.remove(input_path)
            except Exception:
                pass


async def run_job(job_id, job_data, execution_ctx: Optional[Dict[str, Any]] = None):
    """Executes the subprocess for a specific job."""

    cmd = job_data['cmd']
    env = job_data['env']
    output_dir = job_data['output_dir']
    user_id = job_data.get("user_id")
    input_path = job_data.get("input_path")
    source_is_url = _job_uses_remote_source(job_data)
    pipeline = ReelProcessingPipeline(reel_job_manager, job_id)
    job_priority = _clamp_job_priority(job_data.get("priority", DEFAULT_JOB_PRIORITY))
    start_ts = time.time()

    jobs[job_id]['status'] = 'processing'
    jobs[job_id]['priority'] = job_priority
    jobs[job_id]['logs'].append("Job started by worker.")
    await reel_job_manager.start_job(job_id)
    await pipeline.starting()
    print(f"🎬 [run_job] Executing command for {job_id}: {' '.join(cmd)}")

    try:
        process = _spawn_job_subprocess(cmd, env, job_id, execution_ctx)
        returncode = await _supervise_job_subprocess(process, job_id, output_dir, pipeline, execution_ctx)
        preempted = bool(execution_ctx and execution_ctx.get("preempt_requested"))

        if preempted:
            await _requeue_preempted_job(job_id, job_priority)
            return

        if returncode == 0:
            await _handle_completed_reel_job(job_id, job_data, output_dir, user_id, source_is_url, start_ts, pipeline)
        else:
            await _handle_failed_reel_job_process(job_id, job_data, output_dir, start_ts, returncode)

    except Exception as e:
        await _handle_reel_job_execution_error(job_id, job_data, output_dir, start_ts, e)
    finally:
        _cleanup_job_input_file(input_path, job_id)


async def _transcribe_caption_source(user_id: Optional[str], job_id: str, input_path: str, source_name: str):
    cached_transcription = await _load_cached_transcription(user_id, job_id, 0)
    if cached_transcription:
        jobs[job_id]["logs"].append("Using cached transcription from database.")
        return dict(cached_transcription.get("transcript_payload") or {})

    from main import transcribe_video

    loop = asyncio.get_event_loop()
    async with asyncio.timeout(max(1, CAPTION_TRANSCRIBE_TIMEOUT_SECONDS)):
        transcript = await loop.run_in_executor(None, transcribe_video, input_path)
    await _persist_transcription_cache(
        user_id=user_id,
        job_id=job_id,
        clip_index=0,
        source_type="caption_upload",
        source_value=source_name,
        transcript=transcript,
    )
    return transcript


def _build_and_persist_caption_metadata(job_id: str, output_dir: str, source_name: str, title: str, duration_sec: float, local_video_ref: str, transcript: Dict[str, Any]) -> None:
    metadata = {
        "shorts": [
            {
                "title": title,
                "start": 0.0,
                "end": duration_sec,
                "duration": duration_sec,
                "video_url": local_video_ref,
                "video_title_for_youtube_short": title,
                "video_description_for_instagram": "",
                "video_description_for_tiktok": "",
            }
        ],
        "transcript": transcript,
        "standalone_caption": {
            "created_at": int(time.time()),
            "source": "upload",
            "input_filename": source_name,
        },
    }
    metadata_path = os.path.join(output_dir, f"{job_id}_metadata.json")
    _persist_metadata_json(metadata_path, metadata)


def _upload_caption_source_and_thumbnail(
    input_path: str, user_id: Optional[str], job_id: str, bucket: str, local_video_ref: str,
    original_path: Optional[str] = None,
):
    caption_s3_key = f"captions/{user_id}/{job_id}/{os.path.basename(input_path)}"
    if not upload_file_to_s3(input_path, bucket, caption_s3_key):
        raise RuntimeError("Failed to upload caption source video to S3")
    media_url = _caption_media_url_from_s3_key(caption_s3_key) or local_video_ref

    original_s3_key = ""
    if original_path and os.path.exists(original_path):
        original_s3_key = f"captions/{user_id}/{job_id}/original_{os.path.basename(original_path)}"
        if not upload_file_to_s3(original_path, bucket, original_s3_key):
            # Best-effort: the job's own (already captioned) output is
            # already uploaded above -- losing the pre-caption original
            # only means a later manual restyle rebuilds from it instead.
            original_s3_key = ""

    thumbnail_ref = ""
    thumb_local = _generate_reel_thumbnail_from_video(input_path, OUTPUT_DIR, job_id, 0)
    if thumb_local:
        thumb_key = f"captions/{user_id}/{job_id}/thumbnail.jpg"
        if upload_file_to_s3(thumb_local, bucket, thumb_key):
            thumbnail_ref = thumb_key
        try:
            if os.path.exists(thumb_local):
                os.remove(thumb_local)
        except Exception:
            pass

    return caption_s3_key, media_url, thumbnail_ref, original_s3_key


def _build_caption_row_payload(
    job_id: str, job_data: Dict[str, Any], user_id: Optional[str], source_name: str, title: str,
    duration_sec: float, media_url: str, thumbnail_ref: str, caption_s3_key: str,
    caption_required_credits: float, caption_storage_gb: float, caption_cost_breakdown: Dict[str, Any],
    original_s3_key: str = "",
) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    row_payload: Dict[str, Any] = {
        "caption_url": media_url,
        "caption_thumbnail_url": thumbnail_ref,
        "caption_title": title,
        "caption_description": "",
        "caption_duration": max(1, int(round(duration_sec))),
        "caption_created_at": now_iso,
        "caption_updated_at": now_iso,
        "caption_user_id": user_id,
        "caption_status": "termine",
        "caption_job_id": job_id,
        "caption_clip_index": 0,
        "caption_s3_key": caption_s3_key,
        "generation_inputs": {
            "source_type": "file",
            "source_value": source_name,
            "caption_max_duration_minutes": CAPTION_MAX_DURATION_MINUTES,
            "caption_max_storage_gb": CAPTION_MAX_STORAGE_GB,
            "duration_seconds": duration_sec,
            "original_s3_key": original_s3_key,
        },
        "input_source_type": "file",
        "input_source_value": source_name,
        "billing_details": _build_billing_details(
            "sous_titre",
            caption_cost_breakdown,
            actual_credit=caption_required_credits,
            actual_storage_gb=caption_storage_gb,
            extra={
                "source_type": "file",
                "source_value": source_name,
            },
        ),
        "total_cost_usd": 0,
    }
    project_id = str(job_data.get("project_id") or "").strip()
    if project_id:
        row_payload["project_id"] = project_id
    return row_payload


async def _save_caption_row_and_debit(
    row_payload: Dict[str, Any], job_id: str, user_id: Optional[str],
    caption_required_credits: float, caption_storage_gb: float, caption_size_bytes: float = 0.0,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    normalized_item = {"id": f"local-{job_id}", **row_payload}
    retention: Dict[str, Any] = {"retention_storage_cost_usd": 0.0, "retention_storage_credit_cost": 0.0, "media_assets": []}
    if not is_supabase_configured():
        return normalized_item, retention

    saved = await supabase_insert_captions([row_payload])
    if saved:
        normalized_item = _normalize_caption_row(saved[0])

    # Retention is only computable once the caption's own id exists (its
    # media_assets row links back via content_id) -- hence after insert,
    # before the single combined debit below (additive, see
    # _finalize_media_retention_billing).
    retention = await _finalize_retention_billing_batch(job_id, user_id, [
        {
            "content_kind": CONTENT_KIND_CAPTION,
            "content_id": normalized_item.get("id"),
            "media_type": MEDIA_TYPE_PRODUCED,
            "size_bytes": caption_size_bytes,
            "s3_bucket": os.environ.get("AWS_S3_BUCKET", "my-clips-bucket"),
            "s3_key": row_payload.get("caption_s3_key"),
        }
    ])
    total_credits = round(caption_required_credits + retention["retention_storage_credit_cost"], 2)

    if user_id and (total_credits > 0 or caption_storage_gb > 0):
        debit_ok = await reel_job_manager.debit_credits_for_job(
            job_id=job_id,
            user_id=user_id,
            credits=total_credits,
            storage_delta=-caption_storage_gb,
            operation_type="sous_titre",
            reserved_credits=caption_required_credits,
        )
        if not debit_ok:
            raise RuntimeError("Insufficient credit/storage balance to finalize caption job")

    return normalized_item, retention


async def _update_project_on_caption_completion(job_data: Dict[str, Any], user_id: Optional[str], normalized_item: Dict[str, Any], local_duration: float) -> None:
    project_id = job_data.get("project_id")
    if not (project_id and is_supabase_configured()):
        return
    try:
        await supabase_update_project_status(project_id, "completed", user_id=user_id)
        project_summary = _build_short_project_summary(
            str(normalized_item.get("caption_description") or "")
            or str(normalized_item.get("caption_title") or "")
        )
        await supabase_update_project(
            project_id,
            user_id or "",
            {
                "description": project_summary,
                "thumbnail_url": str(normalized_item.get("caption_thumbnail_url") or "") or None,
                "output_count": 1,
                "source_duration": int(float(job_data.get("source_duration_seconds") or local_duration or 0.0)) or None,
            },
        )
        logger.info(f"Project {project_id} marked as completed")
    except Exception as e:
        logger.warning(f"Failed to update project status to completed: {str(e)}")


async def _mark_caption_job_project_failed(job_data: Dict[str, Any], user_id: Optional[str]) -> None:
    if not is_supabase_configured():
        return
    project_id = job_data.get("project_id")
    if not project_id:
        return
    try:
        await supabase_update_project_status(project_id, "failed", user_id=user_id)
        logger.info(f"Project {project_id} marked as failed")
    except Exception as e:
        logger.warning(f"Failed to update project status to failed: {str(e)}")


async def _refund_caption_job_reservation(job_id: str, job_data: Dict[str, Any], user_id: Optional[str], result: Dict[str, Any]) -> None:
    # Release the reservation made at job creation: nothing was billed
    # in this failure path, so the full reserved amount is refundable.
    if result.get("retry") or not user_id:
        return
    reserved = float(job_data.get("caption_required_credits") or 0.0)
    if reserved > 0 and is_supabase_configured():
        try:
            await reel_job_manager.refund_reservation(job_id, user_id, reserved, operation_type="sous_titre")
        except Exception as refund_error:
            logger.warning(f"Failed to refund caption reservation: {refund_error}")


async def _handle_caption_job_failure(job_id: str, job_data: Dict[str, Any], user_id: Optional[str], exc: Exception) -> None:
    jobs[job_id]["status"] = "failed"
    jobs[job_id]["logs"].append(f"Caption job failed: {exc}")
    result = await reel_job_manager.fail_job(
        job_id,
        str(exc),
        error_code="CAPTION_JOB_FAILED",
        retry_delay_seconds=CAPTION_JOB_RETRY_DELAY_SECONDS,
    )

    await _mark_caption_job_project_failed(job_data, user_id)
    await _refund_caption_job_reservation(job_id, job_data, user_id, result)

    if result.get("retry"):
        _spawn_background_task(_schedule_reel_retry(job_id, CAPTION_JOB_RETRY_DELAY_SECONDS))


async def _process_and_complete_caption_job(
    job_id: str, job_data: Dict[str, Any], user_id: Optional[str], pipeline: CaptionProcessingPipeline,
    input_path: str, source_name: str, local_duration: float, transcript: Dict[str, Any],
    caption_required_credits: float, output_dir: str,
) -> None:
    await pipeline.persisting()
    duration_sec = max(0.5, float(local_duration) or _estimate_transcript_duration_seconds(transcript))

    captioned_path = os.path.join(output_dir, f"captioned_{os.path.basename(input_path)}")
    default_style_kwargs = await _get_user_default_caption_style(user_id)
    auto_captioned = await _burn_default_captions_for_clip(
        input_path, captioned_path, transcript, 0.0, duration_sec, job_id, 0, default_style_kwargs,
    )
    primary_path = captioned_path if auto_captioned else input_path

    caption_storage_gb = _bytes_to_gb(float(os.path.getsize(primary_path) if os.path.exists(primary_path) else 0))
    caption_cost_breakdown = _estimate_caption_cost_breakdown(
        duration_seconds=duration_sec,
        size_bytes=float(os.path.getsize(primary_path) if os.path.exists(primary_path) else 0),
        uses_assembly=True,
        uses_openai=True,
        uses_gemini=False,
    )
    title = os.path.splitext(source_name)[0] or "Sous-titres"
    local_video_ref = f"/videos/{job_id}/{os.path.basename(primary_path)}"

    _build_and_persist_caption_metadata(job_id, output_dir, source_name, title, duration_sec, local_video_ref, transcript)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise RuntimeError("AWS_S3_BUCKET is required for caption persistence")
    caption_s3_key, media_url, thumbnail_ref, original_s3_key = _upload_caption_source_and_thumbnail(
        primary_path, user_id, job_id, bucket, local_video_ref,
        original_path=input_path if auto_captioned else None,
    )

    row_payload = _build_caption_row_payload(
        job_id, job_data, user_id, source_name, title, duration_sec, media_url, thumbnail_ref,
        caption_s3_key, caption_required_credits, caption_storage_gb, caption_cost_breakdown,
        original_s3_key=original_s3_key,
    )
    caption_size_bytes = float(os.path.getsize(primary_path) if os.path.exists(primary_path) else 0)
    normalized_item, retention = await _save_caption_row_and_debit(
        row_payload, job_id, user_id, caption_required_credits, caption_storage_gb, caption_size_bytes,
    )
    total_caption_credits = round(caption_required_credits + retention["retention_storage_credit_cost"], 2)
    if retention["retention_storage_cost_usd"] or retention["retention_storage_credit_cost"]:
        caption_cost_breakdown = {
            **caption_cost_breakdown,
            "retention_storage_cost_usd": retention["retention_storage_cost_usd"],
            "retention_storage_credit_cost": retention["retention_storage_credit_cost"],
            "media_assets": retention["media_assets"],
        }

    await pipeline.rendering()
    result_payload = {
        "item": _normalize_caption_row(normalized_item),
        "job_id": job_id,
        "clip_index": 0,
    }
    jobs[job_id]["result"] = result_payload
    jobs[job_id]["status"] = "completed"
    await reel_job_manager.complete_job(
        job_id,
        result_payload,
        actual_credit=total_caption_credits,
        actual_storage_gb=caption_storage_gb,
        consumed_quota=1.0,
        cost_breakdown=caption_cost_breakdown,
    )

    await _update_project_on_caption_completion(job_data, user_id, normalized_item, local_duration)

    await _persist_transcription_cache(
        user_id=user_id,
        job_id=job_id,
        clip_index=0,
        source_type="caption_upload",
        source_value=source_name,
        transcript=transcript,
        billing_details=_build_billing_details(
            "sous_titre",
            caption_cost_breakdown,
            actual_credit=caption_required_credits,
            actual_storage_gb=caption_storage_gb,
            extra={
                "source_type": "file",
                "source_value": source_name,
            },
        ),
    )


async def run_caption_job(job_id: str, job_data: Dict[str, Any], execution_ctx: Optional[Dict[str, Any]] = None):  # NOSONAR(S1172) kept for call-site symmetry with run_job, which does use it for preemption/timeout control -- both are dispatched identically from run_job_wrapper
    user_id = job_data.get("user_id")
    output_dir = str(job_data.get("output_dir") or "")
    input_path = str(job_data.get("input_path") or "")
    source_name = str(job_data.get("source_name") or os.path.basename(input_path) or "caption_source.mp4")
    caption_required_credits = float(job_data.get("caption_required_credits") or 0.0)
    pipeline = CaptionProcessingPipeline(reel_job_manager, job_id)

    jobs[job_id]["status"] = "processing"
    jobs[job_id]["logs"].append("Caption job started by worker.")
    await reel_job_manager.start_job(job_id)

    try:
        await pipeline.analyzing()
        if not input_path or not os.path.exists(input_path):
            raise RuntimeError("Uploaded source video not found for caption job")

        local_duration = _probe_local_video_duration_seconds(input_path)
        _validate_caption_source_constraints(
            duration_seconds=local_duration,
            size_bytes=float(os.path.getsize(input_path) if os.path.exists(input_path) else 0),
            source_label="fichier",
        )

        await pipeline.transcribing()
        transcript = await _transcribe_caption_source(user_id, job_id, input_path, source_name)

        await _process_and_complete_caption_job(
            job_id, job_data, user_id, pipeline, input_path, source_name,
            local_duration, transcript, caption_required_credits, output_dir,
        )
    except Exception as exc:
        await _handle_caption_job_failure(job_id, job_data, user_id, exc)
    finally:
        # Keep caption sources local only during processing.
        if input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
            except Exception:
                pass

@app.get("/api/config")
def get_config():
    return {
        "youtubeUrlEnabled": not DISABLE_YOUTUBE_URL,
        "hideSocialPlatforms": HIDE_SOCIAL_PLATFORMS,
        "captionMaxDurationMinutes": CAPTION_MAX_DURATION_MINUTES,
        "captionMaxStorageGb": CAPTION_MAX_STORAGE_GB,
        "filmSummaryEnabled": FILM_SUMMARY_ENABLED,
        "filmSummaryMinSourceDurationSeconds": FILM_SUMMARY_MIN_SOURCE_DURATION_SECONDS,
        "filmSummaryMaxSourceDurationSeconds": FILM_SUMMARY_MAX_SOURCE_DURATION_SECONDS,
        "filmSummaryMaxUploadSizeBytes": FILM_SUMMARY_MAX_UPLOAD_SIZE_BYTES,
        "filmSummaryMinTargetDurationSeconds": FILM_SUMMARY_MIN_TARGET_DURATION_SECONDS,
        "filmSummaryMaxTargetDurationSeconds": FILM_SUMMARY_MAX_TARGET_DURATION_SECONDS,
        "filmSummaryAllowedVoices": list(film_summary.ALLOWED_TTS_VOICES),
        "filmSummaryDefaultVoice": FILM_SUMMARY_TTS_DEFAULT_VOICE,
    }

@app.get("/api/services/status")
def get_services_status():
    """Check which API services are configured and available."""
    return {
        "gemini": {
            "available": bool(os.getenv("GEMINI_API_KEY")),
            "name": "Google Gemini",
            "description": "AI video analysis and clip generation"
        },
        "openai": {
            "available": bool(os.getenv("OPENAI_API_KEY")),
            "name": "OpenAI",
            "description": "Fallback AI provider"
        },
        "elevenlabs": {
            "available": bool(os.getenv("ELEVENLABS_API_KEY")),
            "name": "ElevenLabs",
            "description": "AI voice dubbing and translation"
        },
        "social_oauth": {
            "available": bool(
                os.getenv("FACEBOOK_CLIENT_ID")
                or os.getenv("LINKEDIN_CLIENT_ID")
                or os.getenv("YOUTUBE_CLIENT_ID")
                or os.getenv("TIKTOK_CLIENT_KEY")
                or os.getenv("INSTAGRAM_CLIENT_ID")
            ),
            "name": "Social OAuth",
            "description": "Native social account publishing"
        },
        "aws_s3": {
            "available": bool(os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY")),
            "name": "AWS S3",
            "description": "Video backup and storage"
        },
        "supabase": {
            "available": bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
            "name": "Supabase",
            "description": "Database and authentication"
        }
    }


def _bytes_to_gb(size_bytes: float) -> float:
    return max(0.0, float(size_bytes) / (1024 ** 3))


def _probe_local_video_duration_seconds(video_path: str) -> float:
    """Best-effort local video duration probe using ffprobe, fallback to OpenCV."""
    if not video_path or not os.path.exists(video_path):
        return 0.0

    try:
        probe_cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        out = subprocess.check_output(probe_cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
        duration = float(out or 0)
        if duration > 0:
            return duration
    except Exception:
        pass

    try:
        import cv2

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        duration = frame_count / fps if fps else 0.0
        return max(0.0, float(duration))
    except Exception:
        return 0.0


def _probe_remote_video_metadata(url_value: str) -> Dict[str, Any]:
    """Best-effort remote metadata probe via yt-dlp without downloading the file."""
    if not url_value:
        return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}

    # Security: url_value is client-supplied. Require it to actually look
    # like an http(s) URL before ever handing it to yt-dlp -- otherwise a
    # value starting with "-" could be parsed as a yt-dlp CLI flag (e.g.
    # --exec) instead of a target URL (argument injection). The "--" below
    # is a second, independent layer: it tells yt-dlp's own argument parser
    # that everything after it is a positional argument, never an option,
    # regardless of what url_value contains.
    if urlparse(url_value).scheme not in ("http", "https"):
        return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}

    try:
        cmd = ["yt-dlp", "--dump-json", "--skip-download", "--no-warnings", "--", url_value]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
        if not out:
            return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}
        payload = json.loads(out.splitlines()[-1])
        duration = float(payload.get("duration") or 0)
        size_bytes = float(payload.get("filesize") or payload.get("filesize_approx") or 0)
        title = str(payload.get("title") or "").strip()
        description = str(payload.get("description") or "").strip()
        return {
            "duration_seconds": max(0.0, duration),
            "size_bytes": max(0.0, size_bytes),
            "title": title,
            "description": description,
        }
    except Exception:
        return {"duration_seconds": 0.0, "size_bytes": 0.0, "title": "", "description": ""}


def _build_short_project_summary(raw_text: str, fallback_title: str = "") -> str:
    """Create a short project summary from available source metadata."""
    base = re.sub(r"\s+", " ", str(raw_text or "")).strip()
    if not base:
        base = re.sub(r"\s+", " ", str(fallback_title or "")).strip()
    if not base:
        return ""

    sentence = re.split(r"[\n\r]+|(?<=[.!?])\s+", base, maxsplit=1)[0].strip()
    compact = sentence or base
    words = compact.split()
    if len(words) > 18:
        compact = " ".join(words[:18]).rstrip(" ,;:-") + "..."
    return compact[:180]


def _project_name_from_uploaded_file(filename: str) -> str:
    source_name = os.path.basename(str(filename or "")).strip()
    if not source_name:
        return "Projet video"
    return os.path.splitext(source_name)[0] or source_name


def _validate_reel_source_constraints(duration_seconds: float, size_bytes: float, source_label: str) -> None:
    max_duration_seconds = max(0.0, REEL_MAX_DURATION_MINUTES) * 60.0
    max_size_bytes = max(0.0, REEL_MAX_STORAGE_GB) * (1024 ** 3)

    if max_size_bytes > 0 and size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Source {source_label} trop volumineuse: {_bytes_to_gb(size_bytes):.2f} Go. "
                f"Maximum autorise: {REEL_MAX_STORAGE_GB:.2f} Go."
            ),
        )

    if max_duration_seconds > 0 and duration_seconds > max_duration_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source {source_label} trop longue: {duration_seconds / 60.0:.2f} min. "
                f"Maximum autorise: {REEL_MAX_DURATION_MINUTES:.2f} min."
            ),
        )


def _validate_caption_source_constraints(
    duration_seconds: float, size_bytes: float, source_label: str,
    max_duration_minutes: float = CAPTION_MAX_DURATION_MINUTES,
    max_storage_gb: float = CAPTION_MAX_STORAGE_GB,
) -> None:
    max_duration_seconds = max(0.0, max_duration_minutes) * 60.0
    max_size_bytes = max(0.0, max_storage_gb) * (1024 ** 3)

    if max_size_bytes > 0 and size_bytes > max_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Source {source_label} trop volumineuse: {_bytes_to_gb(size_bytes):.2f} Go. "
                f"Maximum autorise: {max_storage_gb:.2f} Go."
            ),
        )

    if max_duration_seconds > 0 and duration_seconds > max_duration_seconds:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Source {source_label} trop longue: {duration_seconds / 60.0:.2f} min. "
                f"Maximum autorise: {max_duration_minutes:.2f} min."
            ),
        )


def _estimate_reel_required_credits(
    duration_seconds: float,
    size_bytes: float,
    uses_youtube_source: bool,
    *,
    uses_openai: bool = True,
    uses_assembly: bool = True,
    uses_gemini: bool = False,
) -> float:
    return float(
        _estimate_reel_cost_breakdown(
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            uses_youtube_source=uses_youtube_source,
            uses_openai=uses_openai,
            uses_assembly=uses_assembly,
            uses_gemini=uses_gemini,
        )["final_credits"]
    )


def _estimate_reel_cost_breakdown(
    duration_seconds: float,
    size_bytes: float,
    uses_youtube_source: bool,
    *,
    uses_openai: bool = True,
    uses_assembly: bool = True,
    uses_gemini: bool = False,
) -> Dict[str, Any]:
    duration_minutes = max(1.0, float(duration_seconds or 0.0) / 60.0)
    video_size_gb = max(0.0, _bytes_to_gb(float(size_bytes or 0.0)))
    youtube_download_gb = video_size_gb if uses_youtube_source else 0.0
    breakdown = estimate_reel_cost_usd(
        duration_minutes=duration_minutes,
        video_size_gb=video_size_gb,
        uses_youtube_download=uses_youtube_source,
        youtube_download_gb=youtube_download_gb,
        uses_openai=uses_openai,
        uses_assembly=uses_assembly,
        uses_gemini=uses_gemini,
    )
    return calculate_credits_for_operation(breakdown)


def _estimate_caption_required_credits(
    duration_seconds: float,
    size_bytes: float,
    *,
    uses_assembly: bool = True,
    uses_openai: bool = True,
    uses_gemini: bool = False,
) -> float:
    return float(
        _estimate_caption_cost_breakdown(
            duration_seconds=duration_seconds,
            size_bytes=size_bytes,
            uses_assembly=uses_assembly,
            uses_openai=uses_openai,
            uses_gemini=uses_gemini,
        )["final_credits"]
    )


def _estimate_caption_cost_breakdown(
    duration_seconds: float,
    size_bytes: float,
    *,
    uses_assembly: bool = True,
    uses_openai: bool = True,
    uses_gemini: bool = False,
) -> Dict[str, Any]:
    duration_minutes = max(1.0, float(duration_seconds or 0.0) / 60.0)
    video_size_gb = max(0.0, _bytes_to_gb(float(size_bytes or 0.0)))
    breakdown = estimate_caption_cost_usd(
        duration_minutes=duration_minutes,
        video_size_gb=video_size_gb,
        uses_assembly=uses_assembly,
        uses_openai=uses_openai,
        uses_gemini=uses_gemini,
    )
    return calculate_credits_for_operation(breakdown)


def _build_billing_details(
    operation: str,
    cost_breakdown: Optional[Dict[str, Any]] = None,
    *,
    actual_credit: Optional[float] = None,
    actual_storage_gb: float = 0.0,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    raw = dict(cost_breakdown or {})
    details: Dict[str, Any] = {
        "s3_usd": 0.0,
        "vps_usd": 0.0,
        "dataimpulse_usd": 0.0,
        "assembly_usd": 0.0,
        "openai_usd": 0.0,
        "gemini_usd": 0.0,
        "total_usd": 0.0,
        "base_credits": 0.0,
        "majoration_factor": 1.0,
        "final_credits": 0.0,
    }
    for key in list(details.keys()):
        try:
            details[key] = float(raw.get(key, details[key]) or 0.0)
        except Exception:
            details[key] = 0.0
    for key, value in raw.items():
        if key not in details:
            details[key] = value

    resolved_credit = details.get("final_credits", 0.0) if actual_credit is None else float(actual_credit or 0.0)
    details.update(
        {
            "operation": operation,
            "actual_credit": round(float(resolved_credit), 2),
            "actual_storage_gb": round(max(0.0, float(actual_storage_gb or 0.0)), 6),
        }
    )
    if extra:
        details.update(extra)
    return details


async def _enforce_job_concurrency_limit(user_id: str) -> None:
    """Reject new job submissions once a user already has
    MAX_ACTIVE_JOBS_PER_USER non-terminal jobs. MAX_CONCURRENT_JOBS only
    throttles execution (a semaphore around actually running jobs) -- it
    does nothing to stop one account from enqueueing an unbounded number of
    jobs, each of which uploads a source file to S3 and occupies a queue
    slot/local disk/database row before ever being throttled by that
    semaphore (see security audit finding H7)."""
    if not is_supabase_configured():
        return
    active_count = await supabase_count_active_jobs_for_user(user_id)
    if active_count >= MAX_ACTIVE_JOBS_PER_USER:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Trop de traitements en cours ({active_count}/{MAX_ACTIVE_JOBS_PER_USER}). "
                "Attendez qu'un traitement se termine avant d'en lancer un nouveau."
            ),
        )


async def _assert_user_has_required_credits(user_id: str, required_credits: float) -> float:
    required = float(required_credits or 0.0)
    if not is_supabase_configured():
        return required

    user_data = await supabase_get_user_data(user_id)
    available = float(user_data.get("credit", 0)) if user_data else 0.0
    # Security: the balance must cover both the actual estimated cost of this
    # operation AND the baseline minimum -- previously `required_credits` was
    # computed but never compared against `available`, letting any account
    # with a token balance above MIN_OPERATION_START_CREDITS (default 1)
    # launch operations of arbitrary cost for free while accruing unlimited
    # debt (see security audit finding C7).
    effective_minimum = max(MIN_OPERATION_START_CREDITS, required)
    if available < effective_minimum:
        raise HTTPException(
            status_code=402,
            detail=(
                "Crédits insuffisants pour lancer l'operation. "
                f"Requis : {effective_minimum} cr, disponible : {available} cr."
            ),
        )
    return required


async def _assert_user_has_active_subscription_for_publish(user_id: str) -> None:
    """Publishing to social networks never spends a credit, but still
    requires EITHER an active paid subscription OR at least some valid
    credit -- whatever its nature (subscription, promotional, or
    purchased, all counted together): an active subscription alone is
    always enough (even at 0 credit), and otherwise any positive total
    across the three pools is enough on its own, with no subscription at
    all. Only an account with neither is blocked."""
    if not is_supabase_configured():
        return
    subscription = await get_user_abonnement(user_id)
    if subscription:
        return
    user_data = await supabase_get_user_data(user_id)
    standard_credit = float((user_data or {}).get("credit") or 0.0)
    bonus_batches = await supabase_list_active_promotional_credit_batches(user_id)
    bonus_credit = sum(float(batch.get("amount_remaining") or 0.0) for batch in bonus_batches)
    if standard_credit + bonus_credit > 0:
        return
    raise HTTPException(
        status_code=402,
        detail="Un abonnement actif ou des credits valides sont requis pour publier sur les reseaux sociaux.",
    )


async def _assert_user_can_publish(user_id: str, count: int = 1) -> None:
    """Enforces the per-user daily publication quota: how many
    publications (one per account/platform target, counted at request
    time whether the publish is immediate or scheduled for later) this
    account may make today. The cap itself (abonnement.max_daily_
    publications, 0 = unlimited) is snapshotted onto user_data.
    max_daily_publications at allocation time (see _allocate_plan_
    resources/_finalize_immediate_upgrade) -- this reads only that
    snapshot, never a live plan lookup. Raises a coded 429 carrying
    max_daily/used_today/resets_at so the frontend can tell the user
    exactly when they'll be able to publish again."""
    if not is_supabase_configured():
        return
    result = await supabase_consume_publish_quota(user_id, count)
    if not result.get("allowed", True):
        raise _coded_error(
            429, "publish_quota_exceeded",
            f"Quota de publications quotidien atteint ({result.get('max_daily')} par jour).",
            max_daily=result.get("max_daily"), used_today=result.get("used_today"),
            resets_at=result.get("resets_at"),
        )


async def _assert_user_can_access_analytics(user_id: str) -> None:
    """Social insights and the analytics dashboard block are restricted to
    the gold and ultimate subscription tiers (priorite 2 and 3) -- silver
    (priorite 1) and no active subscription are both blocked."""
    if not is_supabase_configured():
        return
    plan = await _get_active_plan_for_user(user_id)
    priorite = int((plan or {}).get("priorite") or 1)
    if priorite < 2:
        raise HTTPException(
            status_code=403,
            detail="Les analyses sont reservees aux abonnements Gold et Ultimate.",
        )


async def _reserve_job_credits(user_id: str, required_credits: float) -> float:
    """Atomically reserve ``required_credits`` for a queued job (reel/caption
    generation) instead of merely checking the balance covers it. Two
    concurrent job submissions can no longer both pass a stale balance
    check before either is billed: the second submission sees the
    already-reduced balance from the first reservation (see security audit
    finding H8). The reservation is settled (extra debit or refund of the
    difference) against the job's actual cost at completion/failure via
    JobManager.debit_credits_for_job(reserved_credits=...), or refunded in
    full via JobManager.refund_reservation if the job never runs.
    """
    required = float(required_credits or 0.0)
    if not is_supabase_configured():
        return required
    if not await reel_job_manager.reserve_credits(user_id, required):
        available = float((await supabase_get_user_data(user_id) or {}).get("credit", 0))
        raise HTTPException(
            status_code=402,
            detail=(
                "Crédits insuffisants pour lancer l'operation. "
                f"Requis : {math.ceil(required)} cr, disponible : {available} cr."
            ),
        )
    return required


async def _finalize_media_retention_billing(
    *,
    job_id: Optional[str],
    user_id: Optional[str],
    content_kind: str,
    content_id: str,
    media_type: str,
    size_bytes: float,
    s3_bucket: Optional[str] = None,
    s3_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Fixes this media's retention policy FOREVER at the moment its
    definitive size is known (see retention_config.resolve_retention_days
    and the media_assets migration's module comment -- never recomputed
    later, even if the user's subscription or the env vars change
    afterward), persists its media_assets row, and returns a standalone
    retention cost line item (own USD/credit conversion, via the exact
    same billing.calculate_credits_for_operation engine already used for
    AI/processing/S3-operation costs -- never a parallel one) for the
    caller to ADD to its own actual_cost_usd/actual_credit, per the
    additive billing model (credits = existing costs + this one, never a
    replacement). Never raises: a persistence failure here must not block
    the job's own billing/credit settlement, only skip its own retention
    line item (logged) -- see also add_retention_cost_to_breakdown, which
    this re-uses for its own USD->credits conversion.
    """
    has_active_subscription = False
    if is_supabase_configured() and user_id:
        try:
            has_active_subscription = bool(await get_user_abonnement(user_id))
        except Exception:
            logger.exception("Failed to resolve subscription status for retention policy (job %s)", job_id)

    retention_days = resolve_retention_days(media_type, has_active_subscription)
    media_size_gb = _bytes_to_gb(size_bytes)
    # A standalone retention-only breakdown ({"total_usd": 0.0} + retention)
    # -- reuses add_retention_cost_to_breakdown/calculate_credits_for_operation
    # exactly as tested in tests/test_billing.py, just scoped to this one
    # additive component rather than merged into a ratio-adjusted breakdown.
    retention_breakdown = add_retention_cost_to_breakdown({"total_usd": 0.0}, media_size_gb, retention_days)
    retention_storage_cost_usd = float(retention_breakdown.get("retention_usd") or 0.0)
    retention_storage_credit_cost = float(retention_breakdown.get("final_credits") or 0.0)

    now = datetime.now(timezone.utc)
    retention_expires_at = now + timedelta(days=retention_days)
    subscription_status_at_creation = "active" if has_active_subscription else "free"

    if is_supabase_configured() and user_id:
        try:
            await supabase_insert_media_asset(
                user_id=user_id,
                content_kind=content_kind,
                content_id=content_id,
                media_type=media_type,
                subscription_status_at_creation=subscription_status_at_creation,
                retention_days=retention_days,
                retention_started_at=now,
                retention_expires_at=retention_expires_at,
                job_id=job_id,
                s3_bucket=s3_bucket,
                s3_key=s3_key,
                size_bytes=int(size_bytes or 0),
                s3_storage_cost_per_gb_day=S3_STORAGE_COST_PER_GB_DAY,
                retention_storage_cost_usd=retention_storage_cost_usd,
                retention_storage_credit_cost=retention_storage_credit_cost,
                billing_created_at=now,
            )
        except Exception:
            logger.exception("Failed to persist media_assets row for job %s / %s:%s", job_id, content_kind, content_id)

    return {
        "content_kind": content_kind,
        "content_id": content_id,
        "media_type": media_type,
        "media_size_bytes": int(size_bytes or 0),
        "media_size_gb": media_size_gb,
        "subscription_status_at_creation": subscription_status_at_creation,
        "retention_days": retention_days,
        # ISO strings, not datetime objects -- this dict is folded into the
        # job's cost_breakdown log (see _finalize_retention_billing_batch),
        # which gets JSON-serialized for persistence.
        "retention_started_at": now.isoformat(),
        "retention_expires_at": retention_expires_at.isoformat(),
        "s3_storage_cost_per_gb_day": S3_STORAGE_COST_PER_GB_DAY,
        "retention_storage_cost_usd": retention_storage_cost_usd,
        "retention_storage_credit_cost": retention_storage_credit_cost,
    }


async def _finalize_retention_billing_batch(
    job_id: Optional[str], user_id: Optional[str], media_entries: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Runs _finalize_media_retention_billing once per produced/source
    media file this job created (one call per entry -- e.g. one per saved
    reel row for a multi-clip job), then sums the standalone retention
    cost across all of them for the caller to ADD to its own
    actual_cost_usd/actual_credit, plus the full per-media snapshot list
    for the billing log's auditable decomposition."""
    total_cost_usd = 0.0
    total_credit_cost = 0.0
    snapshots: List[Dict[str, Any]] = []
    for entry in media_entries:
        if not entry.get("content_id"):
            continue
        snapshot = await _finalize_media_retention_billing(
            job_id=job_id,
            user_id=user_id,
            content_kind=entry["content_kind"],
            content_id=entry["content_id"],
            media_type=entry["media_type"],
            size_bytes=entry.get("size_bytes") or 0,
            s3_bucket=entry.get("s3_bucket"),
            s3_key=entry.get("s3_key"),
        )
        total_cost_usd += snapshot["retention_storage_cost_usd"]
        total_credit_cost += snapshot["retention_storage_credit_cost"]
        snapshots.append(snapshot)
    return {
        "retention_storage_cost_usd": round(total_cost_usd, 6),
        "retention_storage_credit_cost": round(total_credit_cost, 2),
        "media_assets": snapshots,
    }


async def _finalize_source_media_retention(
    job_id: Optional[str], user_id: Optional[str], project: Optional[Dict[str, Any]],
    size_bytes: float, s3_bucket: Optional[str], s3_key: Optional[str],
) -> None:
    """The shared SOURCE-media retention entry point for every pipeline's
    project/upload creation (reel, caption, anonymous story, film summary
    all create a `projects` row for their source upload -- see
    _create_process_endpoint_project/_create_caption_endpoint_project/
    _create_anonymous_story_endpoint_project/_create_film_summary_endpoint_project).
    Unlike produced media, no credits are reserved/debited for a source
    upload elsewhere in the existing flow, so this is its own small,
    standalone debit (reserved_credits=0.0) for just the retention line
    item -- never blocks the upload/job itself on failure, only logs,
    exactly like the other best-effort debit_ok checks in this file."""
    if not project or not project.get("id"):
        return
    retention = await _finalize_retention_billing_batch(job_id, user_id, [
        {
            "content_kind": CONTENT_KIND_PROJECT_SOURCE,
            "content_id": project.get("id"),
            "media_type": MEDIA_TYPE_SOURCE,
            "size_bytes": size_bytes,
            "s3_bucket": s3_bucket,
            "s3_key": s3_key,
        }
    ])
    retention_credits = retention["retention_storage_credit_cost"]
    if user_id and is_supabase_configured() and retention_credits > 0:
        try:
            debit_ok = await reel_job_manager.debit_credits_for_job(
                job_id=job_id,
                user_id=user_id,
                credits=retention_credits,
                storage_delta=0.0,
                operation_type="retention_storage_source",
                reserved_credits=0.0,
            )
            if not debit_ok:
                logger.warning("Insufficient balance to settle source-media retention (job %s)", job_id)
        except Exception:
            logger.exception("Failed to debit source-media retention cost (job %s)", job_id)


async def _attach_media_asset_fields(
    rows: List[Dict[str, Any]], content_kind: str, id_field: str = "id",
) -> List[Dict[str, Any]]:
    """Enriches each row (in place) with media_status/media_expires_at from
    its media_assets row -- one batched query for the whole page, never
    one per row. Purely informational for the UI (see the spec's
    "Disponible jusqu'au...", "Expire dans N jours", "Media expire" states
    on ReelsPage/CaptionsPage/etc.) -- never raises, and a row with no
    media_assets row at all (historical content predating this feature)
    just gets media_status=None, which the frontend treats as "no
    expiration info" rather than "unavailable"."""
    if not is_supabase_configured() or not rows:
        return rows
    ids = [row.get(id_field) for row in rows if row.get(id_field)]
    try:
        assets_by_id = await supabase_list_media_assets_by_content_ids(content_kind, ids)
    except Exception:
        logger.exception("Failed to batch-fetch media_assets for content_kind=%s", content_kind)
        return rows
    for row in rows:
        asset = assets_by_id.get(row.get(id_field))
        row["media_status"] = asset.get("media_status") if asset else None
        row["media_expires_at"] = asset.get("retention_expires_at") if asset else None
    return rows


def _allowed_video_formats() -> List[str]:
    return [
        fmt.strip().lower().lstrip(".")
        for fmt in str(VIREEL_VIDEO_FORMAT or "").split(",")
        if fmt and fmt.strip()
    ]


def _validate_video_extension(filename: str, context_label: str = "fichier") -> None:
    allowed = _allowed_video_formats()
    if not allowed:
        return

    ext = os.path.splitext(str(filename or ""))[1].lower().lstrip(".")
    if not ext or ext not in allowed:
        accepted = ", ".join(allowed)
        raise HTTPException(
            status_code=400,
            detail=f"Format video invalide pour {context_label}. Formats acceptes: {accepted}.",
        )


_AUTO_EDIT_KEYS = (
    "zoom",
    "brightness",
    "saturation",
    "contrast",
    "speed",
    "removeSilence",
    "cleanAudio",
    "removeBadTakes",
)


def _normalize_auto_edit_options(raw_options: Optional[Dict[str, Any]]) -> Dict[str, bool]:
    raw = raw_options or {}
    return {key: bool(raw.get(key)) for key in _AUTO_EDIT_KEYS}


def _apply_segment_option_defaults(segment: Dict[str, Any], options: Dict[str, Any]) -> Dict[str, Any]:
    seg = dict(segment or {})
    if not options["zoom"]:
        seg["zoom"] = 1.0
        seg["zoomCenterX"] = 0.5
        seg["zoomCenterY"] = 0.5
    if not options["brightness"]:
        seg["brightness"] = 1.0
    if not options["contrast"]:
        seg["contrast"] = 1.0
    if not options["saturation"]:
        seg["saturate"] = 1.0
    return seg


_AUTO_EDIT_APPLIED_STEP_LABELS = [
    ("removeBadTakes", "remove_bad_takes:queued"),
    ("removeSilence", "remove_silence:queued"),
    ("cleanAudio", "clean_audio:queued"),
    ("zoom", "zoom:enabled"),
    ("brightness", "brightness:enabled"),
    ("saturation", "saturation:enabled"),
    ("contrast", "contrast:enabled"),
    ("speed", "speed:queued"),
]


def _collect_applied_auto_edit_steps(options: Dict[str, Any]) -> List[str]:
    return [label for option_key, label in _AUTO_EDIT_APPLIED_STEP_LABELS if options[option_key]]


def _apply_auto_edit_options_to_effects_config(
    effects_config: Optional[Dict[str, Any]],
    raw_options: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], List[str]]:
    config = dict(effects_config or {})
    options = _normalize_auto_edit_options(raw_options)
    segments = config.get("segments") or []

    config["segments"] = [_apply_segment_option_defaults(segment, options) for segment in segments]
    applied_steps = _collect_applied_auto_edit_steps(options)

    return config, applied_steps


def _apply_auto_edit_options_to_filter_data(
    filter_data: Optional[Dict[str, Any]],
    raw_options: Optional[Dict[str, Any]],
) -> tuple[Dict[str, Any], List[str]]:
    data = dict(filter_data or {})
    filter_string = str(data.get("filter_string") or "").strip()
    options = _normalize_auto_edit_options(raw_options)
    if not filter_string:
        return data, []

    chain = VideoEditor._split_filter_chain(filter_string)
    normalized_chain: List[str] = []
    for part in chain:
        low = part.lower()

        if "zoompan=" in low and not options["zoom"]:
            continue
        if "hue=" in low and not options["saturation"]:
            continue
        if "eq=" in low and not (options["brightness"] or options["contrast"] or options["saturation"]):
            continue

        normalized_chain.append(part)

    data["filter_string"] = ",".join(normalized_chain)
    _, applied_steps = _apply_auto_edit_options_to_effects_config({"segments": []}, raw_options)
    return data, applied_steps


def _run_ffmpeg_command(cmd: List[str]) -> None:
    try:
        result = subprocess.run(
            cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg command timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s") from exc
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", errors="ignore") or "FFmpeg command failed")


def _video_has_audio_stream(video_path: str) -> bool:
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        out = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, timeout=FFPROBE_TIMEOUT_SECONDS
        ).decode("utf-8", errors="ignore").strip()
        return bool(out)
    except Exception:
        return False


def _merge_intervals(ranges: List[tuple[float, float]]) -> List[tuple[float, float]]:
    if not ranges:
        return []
    ordered = sorted((max(0.0, float(a)), max(0.0, float(b))) for a, b in ranges)
    merged: List[tuple[float, float]] = []
    for start, end in ordered:
        if end <= start:
            continue
        if not merged:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _invert_cut_ranges(total_duration: float, cut_ranges: List[tuple[float, float]]) -> List[tuple[float, float]]:
    duration = max(0.0, float(total_duration or 0.0))
    if duration <= 0:
        return []
    merged = _merge_intervals(cut_ranges)
    keep: List[tuple[float, float]] = []
    cursor = 0.0
    for start, end in merged:
        if start > cursor:
            keep.append((cursor, min(start, duration)))
        cursor = max(cursor, end)
    if cursor < duration:
        keep.append((cursor, duration))
    return [(a, b) for a, b in keep if (b - a) >= 0.08]


def _build_keep_time_expr(keep_ranges: List[tuple[float, float]]) -> str:
    chunks = [f"between(t,{round(start, 3)},{round(end, 3)})" for start, end in keep_ranges]
    return "+".join(chunks) if chunks else "0"


def _render_keep_ranges(input_path: str, output_path: str, keep_ranges: List[tuple[float, float]]) -> None:
    expr = _build_keep_time_expr(keep_ranges)
    has_audio = _video_has_audio_stream(input_path)
    if has_audio:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
            "-af", f"aselect='{expr}',asetpts=N/SR/TB",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", EXPORT_AUDIO_BITRATE,
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"select='{expr}',setpts=N/FRAME_RATE/TB",
            "-an",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            output_path,
        ]
    _run_ffmpeg_command(cmd)


def _detect_silence_cut_ranges(video_path: str, total_duration: float) -> List[tuple[float, float]]:
    cmd = [
        "ffmpeg", "-hide_banner", "-i", video_path,
        "-af", "silencedetect=noise=-35dB:d=0.35",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS)
    log_text = result.stderr.decode("utf-8", errors="ignore")

    starts = [float(val) for val in re.findall(r"silence_start:\s*(\d+(?:\.\d+)?)", log_text)]
    ends = [
        (float(a), float(b))
        for a, b in re.findall(r"silence_end:\s*(\d+(?:\.\d+)?)\s*\|\s*silence_duration:\s*(\d+(?:\.\d+)?)", log_text)
    ]

    cut_ranges: List[tuple[float, float]] = []
    pending_start_index = 0
    for end_value, silence_duration in ends:
        if pending_start_index >= len(starts):
            continue
        start_value = starts[pending_start_index]
        pending_start_index += 1
        if silence_duration >= 0.35 and end_value > start_value:
            cut_ranges.append((start_value, end_value))

    if pending_start_index < len(starts):
        for start_value in starts[pending_start_index:]:
            if total_duration > start_value:
                cut_ranges.append((start_value, total_duration))

    return _merge_intervals(cut_ranges)


def _atempo_chain(speed_factor: float) -> str:
    factor = max(0.5, min(2.0, float(speed_factor or 1.0)))
    return f"atempo={round(factor, 4)}"


def _apply_speed_transform(input_path: str, output_path: str, speed_factor: float = 1.08) -> None:
    factor = max(0.5, min(2.0, float(speed_factor or 1.0)))
    has_audio = _video_has_audio_stream(input_path)
    if has_audio:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", f"setpts=PTS/{round(factor, 4)}",
            "-filter:a", _atempo_chain(factor),
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", EXPORT_AUDIO_BITRATE,
            output_path,
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-filter:v", f"setpts=PTS/{round(factor, 4)}",
            "-an",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p",
            output_path,
        ]
    _run_ffmpeg_command(cmd)


def _apply_clean_audio_transform(input_path: str, output_path: str) -> None:
    if not _video_has_audio_stream(input_path):
        shutil.copy(input_path, output_path)
        return
    audio_filter = "highpass=f=80,lowpass=f=12000,afftdn=nf=-25,loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-c:v", "copy",
        "-af", audio_filter,
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    _run_ffmpeg_command(cmd)


_BAD_TAKE_FILLER_WORDS = {"um", "uh", "euh", "hmm", "erm", "hum", "ah"}


def _bad_take_candidate_from_segment(segment: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    start = float(segment.get("start", 0.0) or 0.0)
    end = float(segment.get("end", 0.0) or 0.0)
    if end <= start:
        return None
    text = str(segment.get("text") or "").strip().lower()
    words = [w for w in re.findall(r"[a-zA-Z']+", text) if w]
    if not words:
        return None

    filler_count = sum(1 for w in words if w in _BAD_TAKE_FILLER_WORDS)
    repeated = any(words[i] == words[i + 1] for i in range(len(words) - 1))
    reason = ""
    confidence = 0.0
    if filler_count >= 2:
        reason = "filler hesitation"
        confidence = min(0.98, 0.7 + 0.08 * filler_count)
    elif repeated and len(words) >= 4:
        reason = "repeated phrase"
        confidence = 0.82

    if not reason:
        return None
    return {
        "start": max(0.0, start - 0.06),
        "end": max(start, end + 0.06),
        "reason": reason,
        "confidence": round(confidence, 2),
    }


def _detect_bad_take_candidates_heuristic(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    segments = (transcript or {}).get("segments") or []
    candidates = [_bad_take_candidate_from_segment(segment) for segment in segments]
    return [c for c in candidates if c]


def _parse_bad_take_candidates_response(raw_text: str) -> List[Dict[str, Any]]:
    text = (raw_text or "").strip()
    if not text:
        return []

    # Sonar false positive (S8786): the lazy `.*?` here isn't nested inside another
    # quantifier (the classic (a+)+ backtracking blowup shape) -- worst
    # case is linear in len(text), and text is a bounded LLM response, not
    # attacker-controlled input.
    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)  # NOSONAR
    if fenced_match:
        text = fenced_match.group(1).strip()

    try:
        payload = json.loads(text)
    except Exception:
        return []

    if isinstance(payload, dict):
        items = payload.get("candidates")
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _sanitize_single_bad_take_candidate(candidate: Dict[str, Any], max_end: float) -> Optional[Dict[str, Any]]:
    try:
        start = float(candidate.get("start", 0.0) or 0.0)
        end = float(candidate.get("end", 0.0) or 0.0)
    except Exception:
        return None

    start = max(0.0, min(start, max_end))
    end = max(0.0, min(end, max_end))
    if end <= start:
        return None

    reason = str(candidate.get("reason") or "bad take").strip() or "bad take"
    reason = reason[:120]

    try:
        confidence = float(candidate.get("confidence", 0.5) or 0.5)
    except Exception:
        confidence = 0.5
    confidence = max(0.0, min(confidence, 1.0))

    return {
        "start": round(start, 3),
        "end": round(end, 3),
        "reason": reason,
        "confidence": round(confidence, 2),
    }


def _merge_overlapping_bad_take_candidates(normalized: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    for item in normalized:
        if not merged:
            merged.append(item)
            continue
        prev = merged[-1]
        if item["start"] <= prev["end"] and item["reason"] == prev["reason"]:
            prev["end"] = max(prev["end"], item["end"])
            prev["confidence"] = max(prev["confidence"], item["confidence"])
            continue
        merged.append(item)
    return merged


def _sanitize_bad_take_candidates(
    raw_candidates: List[Dict[str, Any]],
    max_end: float,
) -> List[Dict[str, Any]]:
    sanitized = [_sanitize_single_bad_take_candidate(c, max_end) for c in raw_candidates]
    normalized = [c for c in sanitized if c]
    normalized.sort(key=lambda x: (x["start"], x["end"]))
    return _merge_overlapping_bad_take_candidates(normalized)


def _build_compact_segments_for_bad_take_ai(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    compact_segments: List[Dict[str, Any]] = []
    for idx, segment in enumerate(segments[:140]):
        start = float(segment.get("start", 0.0) or 0.0)
        end = float(segment.get("end", 0.0) or 0.0)
        text = str(segment.get("text") or "").strip()
        if not text or end <= start:
            continue
        compact_segments.append(
            {
                "index": idx,
                "start": round(start, 3),
                "end": round(end, 3),
                "text": text,
            }
        )
    return compact_segments


def _call_openai_for_bad_takes(compact_segments: List[Dict[str, Any]], api_key: str, max_end: float) -> List[Dict[str, Any]]:
    prompt_payload = {
        "instructions": (
            "Detect low-quality speaking takes using multi-segment context. "
            "Consider hesitations, false starts, repeated fragments across neighboring segments, "
            "and self-corrections that hurt fluency. Return only meaningful cut candidates."
        ),
        "output_contract": {
            "format": "JSON",
            "top_level": "candidates",
            "fields": ["start", "end", "reason", "confidence"],
            "confidence_range": "0..1",
        },
        "segments": compact_segments,
    }

    try:
        from openai import OpenAI

        model = os.environ.get("OPENAI_BAD_TAKE_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a video editing analyst. "
                        "Use context between adjacent transcript segments before suggesting cuts. "
                        "Respond with strict JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(prompt_payload, ensure_ascii=True),
                },
            ],
            temperature=0.1,
            max_tokens=900,
        )
        raw_output = (response.choices[0].message.content or "").strip()
        parsed = _parse_bad_take_candidates_response(raw_output)
        return _sanitize_bad_take_candidates(parsed, max_end=max_end)
    except Exception as exc:
        print(f"⚠️ AI bad-take analysis failed, fallback heuristic. Reason: {exc}")
        return []


def _detect_bad_take_candidates_ai(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if os.environ.get("AUTO_EDIT_BAD_TAKE_AI", "true").strip().lower() in {"0", "false", "no"}:
        return []

    segments = (transcript or {}).get("segments") or []
    if not segments:
        return []

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_key":
        return []

    compact_segments = _build_compact_segments_for_bad_take_ai(segments)
    if not compact_segments:
        return []

    max_end = max(float(seg.get("end", 0.0) or 0.0) for seg in compact_segments)
    return _call_openai_for_bad_takes(compact_segments, api_key, max_end)


def _detect_bad_take_candidates(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ai_candidates = _detect_bad_take_candidates_ai(transcript)
    if ai_candidates:
        return ai_candidates
    return _detect_bad_take_candidates_heuristic(transcript)


def _auto_edit_temp_path(job_id: str, name: str) -> str:
    return os.path.join(OUTPUT_DIR, job_id, f"auto_{name}_{uuid.uuid4().hex[:8]}.mp4")


def _apply_remove_bad_takes_step(current_path: str, job_id: str, transcript: Optional[Dict[str, Any]], total_duration: float, cleanup_paths: List[str]):
    bad_take_candidates = _detect_bad_take_candidates(transcript)
    cut_ranges = [(float(c["start"]), float(c["end"])) for c in bad_take_candidates]
    keep_ranges = _invert_cut_ranges(total_duration, cut_ranges)
    if keep_ranges and len(keep_ranges) > 1:
        next_path = _auto_edit_temp_path(job_id, "bad_takes")
        _render_keep_ranges(current_path, next_path, keep_ranges)
        cleanup_paths.append(next_path)
        current_path = next_path
        total_duration = _probe_local_video_duration_seconds(current_path)
        step = f"remove_bad_takes:done:{len(bad_take_candidates)}"
    else:
        step = "remove_bad_takes:skipped"
    return current_path, total_duration, bad_take_candidates, step


def _apply_remove_silence_step(current_path: str, job_id: str, total_duration: float, cleanup_paths: List[str]):
    if not _video_has_audio_stream(current_path):
        return current_path, "remove_silence:no_audio"
    silence_ranges = _detect_silence_cut_ranges(current_path, total_duration)
    keep_ranges = _invert_cut_ranges(total_duration, silence_ranges)
    if keep_ranges and len(keep_ranges) > 1:
        next_path = _auto_edit_temp_path(job_id, "silence")
        _render_keep_ranges(current_path, next_path, keep_ranges)
        cleanup_paths.append(next_path)
        return next_path, f"remove_silence:done:{len(silence_ranges)}"
    return current_path, "remove_silence:skipped"


def _apply_clean_audio_step(current_path: str, job_id: str, cleanup_paths: List[str]):
    next_path = _auto_edit_temp_path(job_id, "clean_audio")
    _apply_clean_audio_transform(current_path, next_path)
    cleanup_paths.append(next_path)
    return next_path, "clean_audio:done"


def _apply_speed_step(current_path: str, job_id: str, cleanup_paths: List[str]):
    next_path = _auto_edit_temp_path(job_id, "speed")
    _apply_speed_transform(current_path, next_path, speed_factor=1.08)
    cleanup_paths.append(next_path)
    return next_path, "speed:done:1.08"


def _apply_auto_edit_media_steps(
    input_path: str,
    job_id: str,
    transcript: Optional[Dict[str, Any]],
    raw_options: Optional[Dict[str, Any]],
) -> tuple[str, List[str], List[Dict[str, Any]], List[str]]:
    options = _normalize_auto_edit_options(raw_options)
    steps: List[str] = []
    bad_take_candidates: List[Dict[str, Any]] = []
    cleanup_paths: List[str] = []
    current_path = input_path
    total_duration = _probe_local_video_duration_seconds(current_path)

    if options["removeBadTakes"]:
        current_path, total_duration, bad_take_candidates, step = _apply_remove_bad_takes_step(
            current_path, job_id, transcript, total_duration, cleanup_paths,
        )
        steps.append(step)
    else:
        steps.append("remove_bad_takes:disabled")

    if options["removeSilence"]:
        current_path, step = _apply_remove_silence_step(current_path, job_id, total_duration, cleanup_paths)
        steps.append(step)
    else:
        steps.append("remove_silence:disabled")

    if options["cleanAudio"]:
        current_path, step = _apply_clean_audio_step(current_path, job_id, cleanup_paths)
        steps.append(step)
    else:
        steps.append("clean_audio:disabled")

    if options["speed"]:
        current_path, step = _apply_speed_step(current_path, job_id, cleanup_paths)
        steps.append(step)
    else:
        steps.append("speed:disabled")

    return current_path, steps, bad_take_candidates, cleanup_paths

async def _resolve_process_endpoint_url_and_ack(request: Request, url: Optional[str], acknowledged: Optional[str]):
    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")

    # Handle JSON body manually for URL payload
    content_type = request.headers.get("content-type", "")
    if _CONTENT_TYPE_JSON in content_type:
        body = await request.json()
        url = body.get("url")
        ack_flag = bool(body.get("acknowledged"))

    return url, ack_flag


def _validate_process_endpoint_inputs(url: Optional[str], file: Optional[UploadFile], ack_flag: bool) -> None:
    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")
    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")
    if url and DISABLE_YOUTUBE_URL:
        raise HTTPException(status_code=403, detail="YouTube URL ingest is disabled on this deployment. Please upload a file you own.")


def _build_process_endpoint_attestation(request: Request, url: Optional[str]) -> Dict[str, Any]:
    client_ip = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        client_ip = fwd.split(",")[0].strip()
    user_agent = request.headers.get("user-agent", "")
    return {
        "acknowledged": True,
        "ip": client_ip,
        "user_agent": user_agent,
        "timestamp": time.time(),
        "source": "url" if url else "file",
    }


def _resolve_process_url_source(url: str, job_id: str) -> Dict[str, Any]:
    remote_meta = _probe_remote_video_metadata(url)
    duration_seconds = float(remote_meta.get("duration_seconds") or 0.0)
    source_duration_seconds = duration_seconds
    size_bytes = float(remote_meta.get("size_bytes") or 0.0)
    is_youtube_source = _is_youtube_url(url)
    project_source_type = "youtube" if is_youtube_source else "url"
    youtube_title = str(remote_meta.get("title") or "").strip()
    fallback_name = _sanitize_input_filename(url) or "Video distante"
    project_name = youtube_title or fallback_name
    project_description = _build_short_project_summary(str(remote_meta.get("description") or ""), fallback_title=project_name)

    input_path = None
    # If remote metadata is incomplete, download once and validate from local probe.
    # Keep YouTube URLs in -u mode; direct HTTP fetch of watch pages returns HTML.
    if (duration_seconds <= 0.0 or size_bytes <= 0.0) and not is_youtube_source:
        input_path, _ = _download_input_url_to_job_dir(url, job_id)
        duration_seconds = _probe_local_video_duration_seconds(input_path)
        source_duration_seconds = duration_seconds
        try:
            size_bytes = float(os.path.getsize(input_path))
        except Exception:
            size_bytes = 0.0

    return {
        "input_path": input_path,
        "duration_seconds": duration_seconds,
        "size_bytes": size_bytes,
        "source_duration_seconds": source_duration_seconds,
        "is_youtube_source": is_youtube_source,
        "project_source_type": project_source_type,
        "project_name": project_name,
        "project_description": project_description,
        "remote_meta": remote_meta,
    }


async def _reserve_reel_credits_or_cleanup(user_id: str, reel_required_credits: float, input_path: Optional[str], job_output_dir: str) -> None:
    try:
        await _reserve_job_credits(user_id, reel_required_credits)
    except HTTPException:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(job_output_dir, ignore_errors=True)
        raise


async def _prepare_process_job_from_url(url: str, user_id: str, job_id: str, job_output_dir: str, cmd: List[str]) -> Dict[str, Any]:
    source = _resolve_process_url_source(url, job_id)
    input_path = source["input_path"]
    duration_seconds = source["duration_seconds"]
    size_bytes = source["size_bytes"]

    _validate_reel_source_constraints(
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
        source_label="url",
    )
    reel_required_credits = _estimate_reel_required_credits(
        duration_seconds=duration_seconds,
        size_bytes=size_bytes,
        uses_youtube_source=True,
    )
    await _reserve_reel_credits_or_cleanup(user_id, reel_required_credits, input_path, job_output_dir)

    if input_path:
        cmd.extend(["-i", input_path])
    else:
        # --keep-original: without it main.py deletes the video it downloads
        # for a plain URL right after processing (see its __main__ cleanup),
        # which would make manual custom-clip selection (see
        # _preserve_source_video_for_manual_clipping) impossible for
        # anything that went through this branch (i.e. genuine YouTube
        # links, resolved via yt-dlp inside main.py rather than pre-
        # downloaded here).
        cmd.extend(["-u", url, "--keep-original"])

    return {
        "input_path": input_path,
        "reel_required_credits": reel_required_credits,
        "source_duration_seconds": source["source_duration_seconds"],
        "project_source_type": source["project_source_type"],
        "project_name": source["project_name"],
        "project_description": source["project_description"],
        "remote_meta": source["remote_meta"],
    }


async def _prepare_process_job_from_file(file: UploadFile, user_id: str, job_id: str, job_output_dir: str, cmd: List[str]) -> Dict[str, Any]:
    _validate_video_extension(file.filename if file else "", context_label="reel")
    project_source_type = "upload"
    project_name = _project_name_from_uploaded_file(file.filename if file else "")
    project_description = _build_short_project_summary(project_name, fallback_title=project_name)

    # Save uploaded file with size limit check
    # Security: sanitize the client-supplied filename to a safe basename
    # before joining it into a filesystem path (path traversal guard).
    safe_upload_name = _sanitize_input_filename(file.filename) or _DEFAULT_UPLOAD_FILENAME
    input_path = os.path.join(UPLOAD_DIR, f"{job_id}_{safe_upload_name}")

    # Read file in chunks to check size
    size = 0
    limit_bytes = max(0.0, REEL_MAX_STORAGE_GB) * (1024 ** 3)

    async with aiofiles.open(input_path, "wb") as buffer:
        while content := await file.read(1024 * 1024): # Read 1MB chunks
            size += len(content)
            if limit_bytes > 0 and size > limit_bytes:
                os.remove(input_path)
                shutil.rmtree(job_output_dir)
                raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Maximum autorise: {REEL_MAX_STORAGE_GB:.2f} Go")
            await buffer.write(content)

    local_duration = _probe_local_video_duration_seconds(input_path)
    source_duration_seconds = float(local_duration or 0.0)
    _validate_reel_source_constraints(
        duration_seconds=local_duration,
        size_bytes=float(size),
        source_label="fichier",
    )
    reel_required_credits = _estimate_reel_required_credits(
        duration_seconds=local_duration,
        size_bytes=float(size),
        uses_youtube_source=False,
    )
    await _reserve_reel_credits_or_cleanup(user_id, reel_required_credits, input_path, job_output_dir)

    cmd.extend(["-i", input_path])

    return {
        "input_path": input_path,
        "reel_required_credits": reel_required_credits,
        "source_duration_seconds": source_duration_seconds,
        "project_source_type": project_source_type,
        "project_name": project_name,
        "project_description": project_description,
        "remote_meta": {},
    }


async def _create_process_endpoint_project(
    user_id: str, job_id: str, job_prep: Dict[str, Any], source_value: str, url: Optional[str], source_duration_seconds: float,
):
    if not is_supabase_configured():
        return None, source_duration_seconds
    input_path = job_prep["input_path"]
    remote_meta = job_prep["remote_meta"]
    try:
        # Determine source duration and size
        if input_path and os.path.exists(input_path):
            source_size_bytes = os.path.getsize(input_path)
            source_duration_seconds = _probe_local_video_duration_seconds(input_path)
        else:
            source_size_bytes = int(float(remote_meta.get("size_bytes") or 0.0))
            source_duration_seconds = float(remote_meta.get("duration_seconds") or 0.0) or None

        # Upload source to S3 with project-based key structure
        bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
        source_basename = os.path.basename(input_path) if input_path else (_sanitize_input_filename(source_value) or "video.mp4")
        s3_source_key = f"projects/{job_id}/source/{source_basename}"

        if input_path and os.path.exists(input_path):
            upload_file_to_s3(input_path, bucket_name, s3_source_key)
        project_thumbnail_ref = _generate_and_upload_project_thumbnail_from_source(
            input_path,
            bucket_name,
            user_id,
            job_id,
        )

        # Create project record
        project = await supabase_create_project(
            user_id=user_id,
            name=job_prep["project_name"],
            description=job_prep["project_description"],
            project_type="reel",
            source_type=job_prep["project_source_type"],
            source_s3_key=s3_source_key,
            source_size=source_size_bytes,
            source_url=url if url else None,
            source_duration=int(source_duration_seconds) if source_duration_seconds else None,
            thumbnail_url=project_thumbnail_ref,
            status="processing",
        )
        await _finalize_source_media_retention(job_id, user_id, project, source_size_bytes, bucket_name, s3_source_key)
        return project, source_duration_seconds
    except Exception as e:
        logger.warning(f"Failed to create project for job {job_id}: {str(e)}")
        return None, source_duration_seconds


async def _enqueue_process_endpoint_job(
    job_id: str, user_id: str, cmd: List[str], env: Dict[str, str], job_output_dir: str,
    source_type: str, source_value: str, attestation: Dict[str, Any], job_priority: int,
    input_path: Optional[str], reel_required_credits: float, project, source_duration_seconds: float,
) -> None:
    runtime_payload = {
        'status': 'queued',
        'logs': [f"Job {job_id} queued."],
        'cmd': cmd,
        'env': env,
        'output_dir': job_output_dir,
        'input_path': input_path,
        'source_type': source_type,
        'source_value': source_value,
        'attestation': attestation,
        'user_id': user_id,
        'priority': job_priority,
        'reel_required_credits': reel_required_credits,
        'project_id': project.get("id") if project else None,
        'source_duration_seconds': source_duration_seconds,
    }

    jobs[job_id] = dict(runtime_payload)
    reel_job_manager.runtime_jobs[job_id] = dict(runtime_payload)

    # Persist job state in Supabase.
    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_REELS,
        pipeline_name="ReelProcessingPipeline",
        job_id=job_id,
        job_data={
            "source_type": source_type,
            "source_value": source_value,
            "output_dir": job_output_dir,
            "input_path": input_path,
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "reel_max_duration_minutes": REEL_MAX_DURATION_MINUTES,
            "reel_max_storage_gb": REEL_MAX_STORAGE_GB,
            "attestation": attestation,
            "reel_required_credits": reel_required_credits,
            "project_id": project.get("id") if project else None,
            "source_duration_seconds": source_duration_seconds,
        },
        runtime_data=dict(runtime_payload),
        max_attempts=REEL_JOB_MAX_ATTEMPTS,
        reserved_quota=reel_required_credits,
        priority=job_priority,
        queue_name="reels",
    )
    await reel_job_manager.enqueue_job(job_id)
    await ReelProcessingPipeline(reel_job_manager, job_id).queued()

    await enqueue_reel_job(job_id, priority=job_priority)


@app.post("/api/process", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 413: {"description": "Payload Too Large"}, 429: {"description": "Too Many Requests"}})
async def process_endpoint(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[Optional[UploadFile], File()] = None,
    url: Annotated[Optional[str], Form()] = None,
    acknowledged: Annotated[Optional[str], Form()] = None,
):
    # Determine API Key: Use .env configuration (GEMINI_API_KEY or OPENAI_API_KEY as fallback)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    url, ack_flag = await _resolve_process_endpoint_url_and_ack(request, url, acknowledged)
    _validate_process_endpoint_inputs(url, file, ack_flag)

    await _enforce_job_concurrency_limit(user_id)

    attestation = _build_process_endpoint_attestation(request, url)
    job_priority = await _resolve_user_job_priority(user_id)

    job_id = str(uuid.uuid4())
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(job_output_dir, exist_ok=True)
    source_type = "url" if url else "file"
    if url:
        source_value = url
    elif file:
        source_value = file.filename
    else:
        source_value = ""

    # Prepare Command
    cmd = ["python", "-u", "main.py"] # -u for unbuffered
    env = os.environ.copy()
    env["GEMINI_API_KEY"] = api_key # Override with key from request

    if url:
        job_prep = await _prepare_process_job_from_url(url, user_id, job_id, job_output_dir, cmd)
    else:
        job_prep = await _prepare_process_job_from_file(file, user_id, job_id, job_output_dir, cmd)

    cmd.extend(["-o", job_output_dir])

    print(f"[attestation] job={job_id} ip={attestation['ip']} source={attestation['source']} ack=true")

    project, source_duration_seconds = await _create_process_endpoint_project(
        user_id, job_id, job_prep, source_value, url, job_prep["source_duration_seconds"],
    )

    await _enqueue_process_endpoint_job(
        job_id, user_id, cmd, env, job_output_dir, source_type, source_value, attestation, job_priority,
        job_prep["input_path"], job_prep["reel_required_credits"], project, source_duration_seconds,
    )

    return {
        "job_id": job_id,
        "project_id": project.get("id") if project else None,
        "status": "queued"
    }

def _scan_partial_clips(output_dir: str, job_id: str) -> List[Dict[str, Any]]:
    if not os.path.exists(output_dir):
        return []
    clip_files = sorted([
        f for f in os.listdir(output_dir)
        if f.endswith('.mp4') and not f.startswith('temp_')
    ])
    partial_clips = []
    for i, clip_file in enumerate(clip_files):
        match = re.search(_CLIP_INDEX_SUFFIX_PATTERN, clip_file)
        resolved_clip_index = (int(match.group(1)) - 1) if match else i
        partial_clips.append({
            'video_url': f'/videos/{job_id}/{clip_file}',
            'file': clip_file,
            'index': resolved_clip_index,
            'reel_clip_index': resolved_clip_index,
            'status': 'generated'
        })
    return partial_clips


def _attach_partial_clips_if_processing(target: Dict[str, Any], status: Optional[str], output_dir: Optional[str], job_id: str) -> None:
    if status not in ('queued', 'processing') or not output_dir:
        return
    try:
        partial_clips = _scan_partial_clips(output_dir, job_id)
        if partial_clips:
            target['partialClips'] = partial_clips
    except Exception:
        # Silently fail - don't break the status endpoint
        pass


@app.get("/api/status/{job_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def get_status(job_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    # Best effort read of in-memory runtime state, but the *authorization*
    # scope always comes from the verified caller identity above -- never
    # fall back to an unscoped (user_id=None) lookup, which would let any
    # caller read any other user's job status/results (see security audit).
    runtime_job = reel_job_manager.runtime_jobs.get(job_id) or jobs.get(job_id)

    supabase_view = await reel_job_manager.get_job_view(job_id, user_id=user_id)
    if supabase_view:
        if runtime_job:
            _attach_partial_clips_if_processing(supabase_view, runtime_job.get('status'), runtime_job.get('output_dir'), job_id)
        return supabase_view

    if job_id not in jobs:
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)

    job = jobs[job_id]
    if (job.get("user_id") or "") != user_id:
        # Security: never serve another user's in-memory job state.
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
    response = {
        "status": job['status'],
        "logs": job['logs'],
        "result": job.get('result')
    }

    _attach_partial_clips_if_processing(response, job['status'], job.get('output_dir'), job_id)

    return response

from editor import VideoEditor
from subtitles import generate_srt, generate_highlighted_srt, burn_subtitles, generate_srt_from_video, SubtitleStyleOptions
from hooks import add_hook_to_video
from visuals import apply_visuals_to_video
from thumbnail import analyze_video_for_titles, refine_titles, generate_thumbnail, generate_youtube_description

class EditRequest(BaseModel):
    job_id: str
    clip_index: int
    api_key: Optional[str] = None
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    auto_edit_options: Optional[Dict[str, bool]] = None


def _sanitize_input_filename(value: Optional[str]) -> Optional[str]:
    """Normalize a filename or URL into a safe local basename."""
    if not value:
        return None

    candidate = str(value).strip()
    if not candidate:
        return None

    parsed = urlparse(candidate)
    if parsed.scheme or parsed.netloc:
        candidate = os.path.basename(parsed.path)
    else:
        candidate = os.path.basename(candidate.split('?')[0])

    candidate = unquote(candidate)
    return candidate or None


_JOB_ID_PATTERN = re.compile(r"^[0-9a-fA-F-]{8,64}$")


async def _require_job_ownership(job_id: str, user_id: str) -> None:
    """Validate job_id format and verify it belongs to the authenticated caller.

    Security: job_id is interpolated into filesystem paths (os.path.join)
    and, for subtitle burning, into an ffmpeg -vf filter expression. Without
    this check a client could supply another user's job_id (cross-tenant
    IDOR) or a path-traversal payload like "../../etc" (see security audit
    finding on /api/edit and /api/subtitle). Ownership is verified against
    persisted job state, not just in-memory state, so it still works after a
    worker restart.
    """
    if not _JOB_ID_PATTERN.match(job_id or ""):
        raise HTTPException(status_code=400, detail="Invalid job_id")

    in_memory = jobs.get(job_id) or reel_job_manager.runtime_jobs.get(job_id)
    if in_memory:
        if (in_memory.get("user_id") or "") != user_id:
            raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
        return

    if is_supabase_configured():
        row = await reel_job_manager.get_job_view(job_id, user_id=user_id)
        if row:
            return

    raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)


def _is_youtube_url(value: str) -> bool:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host == "youtu.be" or host == "youtube.com" or host.endswith(".youtube.com")


class _SSRFSafeRedirectHandler(HTTPRedirectHandler):
    """Re-validates every redirect hop against _validate_download_url, so a
    malicious/compromised server cannot bypass SSRF protection by 302-ing to
    an internal/loopback/cloud-metadata address after the initial URL passed
    validation."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_download_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _download_input_url_to_job_dir(input_url: str, job_id: str) -> tuple[str, str]:
    """Download a remote clip URL into output/<job_id> and return (path, filename)."""
    # Security: this fetches a URL fully controlled by the client (SSRF
    # primitive) -- always validate against private/loopback/link-local/cloud
    # metadata addresses before making any outbound request.
    _validate_download_url(input_url)
    if _is_youtube_url(input_url):
        raise HTTPException(
            status_code=400,
            detail=(
                "Les URLs YouTube standard ne peuvent pas etre telechargees directement. "
                "Utilisez la generation Reel avec URL (mode yt-dlp) ou une URL directe de fichier video."
            ),
        )

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)

    source_name = _sanitize_input_filename(input_url) or f"remote_{job_id}.mp4"
    filename = f"remote_{uuid.uuid4().hex[:8]}_{source_name}"
    local_path = os.path.join(output_dir, filename)

    try:
        request = UrlRequest(input_url, headers={"User-Agent": "Vireel/1.0"})
        opener = build_opener(_SSRFSafeRedirectHandler)
        with opener.open(request, timeout=45) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type.lower():
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "L'URL fournie a retourné une page HTML au lieu d'un fichier vidéo. "
                        "Les liens YouTube standard ne sont pas téléchargeables directement. "
                        "Veuillez fournir une URL directe vers un fichier vidéo (mp4, mov…)."
                    ),
                )
            with open(local_path, "wb") as f:
                shutil.copyfileobj(response, f)
    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error(
            "Failed to download input URL", e, status_code=404,
            detail="Impossible de telecharger l'URL fournie.",
        ) from e

    return local_path, filename

def _resolve_edit_clip_input_path(req: "EditRequest", job: Optional[Dict[str, Any]]):
    # Resolve Input Path: Prefer explict input_filename from frontend (chaining edits)
    if req.input_filename:
        # Security: Ensure just a filename, no paths or signed query params
        safe_name = _sanitize_input_filename(req.input_filename)
        if not safe_name:
            raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
        input_path = os.path.join(OUTPUT_DIR, req.job_id, safe_name)
        filename = safe_name
    else:
        if not job:
            raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
        if 'result' not in job or 'clips' not in job['result']:
            raise HTTPException(status_code=400, detail="Job result not available")
        # Fallback to original clip
        clip = job['result']['clips'][req.clip_index]
        filename = clip['video_url'].split('/')[-1]
        input_path = os.path.join(OUTPUT_DIR, req.job_id, filename)

    # Reels page may provide only a signed URL and no live in-memory job.
    if not os.path.exists(input_path) and req.input_url:
        input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

    if not os.path.exists(input_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    return input_path, filename


async def _load_transcript_for_edit(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        meta_files = glob.glob(os.path.join(OUTPUT_DIR, job_id, _METADATA_JSON_GLOB))
        if meta_files:
            async with aiofiles.open(meta_files[0], "r") as f:
                data = json.loads(await f.read())
                return data.get("transcript")
    except Exception as e:
        print(f"⚠️ Could not load transcript for editing context: {e}")
    return None


def _run_video_edit(final_api_key: str, job_id: str, input_path: str, output_path: str, transcript_for_edit, auto_edit_options):
    editor = VideoEditor(api_key=final_api_key)

    # SAFE FILE RENAMING STRATEGY (Avoid UnicodeEncodeError in Docker)
    # Create a safe ASCII filename in the same directory
    safe_filename = f"temp_input_{job_id}.mp4"
    safe_input_path = os.path.join(OUTPUT_DIR, job_id, safe_filename)

    # Copy original file to safe path
    # (Copy is safer than rename if something crashes, we keep original)
    shutil.copy(input_path, safe_input_path)
    auto_cleanup_paths: List[str] = []

    try:
        processed_input_path, media_steps, bad_take_candidates, generated_paths = _apply_auto_edit_media_steps(
            safe_input_path,
            job_id,
            transcript_for_edit,
            auto_edit_options,
        )
        auto_cleanup_paths.extend(generated_paths)

        # 1. Upload (using safe path)
        vid_file = editor.upload_video(processed_input_path)

        # 2. Get duration
        import cv2
        cap = cv2.VideoCapture(processed_input_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = frame_count / fps if fps else 0
        cap.release()

        # 3. Get Plan (Filter String)
        filter_data = editor.get_ffmpeg_filter(
            vid_file,
            duration,
            fps=fps,
            width=width,
            height=height,
            transcript=transcript_for_edit,
        )
        filter_data, applied_steps = _apply_auto_edit_options_to_filter_data(filter_data, auto_edit_options)

        # 4. Apply
        # Use safe output name first
        safe_output_path = os.path.join(OUTPUT_DIR, job_id, f"temp_output_{job_id}.mp4")
        editor.apply_edits(processed_input_path, safe_output_path, filter_data)

        # Move result to final destination (rename works even if dest name has unicode if filesystem supports it,
        # but python might still struggle if locale is broken? No, os.rename usually handles it better than subprocess args)
        # Actually, output_path is defined above: f"edited_{filename}"
        # If filename has unicode, output_path has unicode.
        # Let's hope shutil.move / os.rename works.
        if os.path.exists(safe_output_path):
            shutil.move(safe_output_path, output_path)

        return {
            "filter": filter_data,
            "applied_steps": applied_steps + media_steps,
            "bad_take_candidates": bad_take_candidates,
        }
    finally:
        # Cleanup temp safe input
        if os.path.exists(safe_input_path):
            os.remove(safe_input_path)
        for temp_path in auto_cleanup_paths:
            if temp_path != safe_input_path and os.path.exists(temp_path):
                os.remove(temp_path)


async def _debit_edit_credits_and_log(user_id: str, req: "EditRequest", edit_required_credits: float) -> None:
    if not (is_supabase_configured() and edit_required_credits > 0):
        return
    await supabase_deduct_user_credits(user_id, edit_required_credits)
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=edit_required_credits,
        storage=0.0,
        operation="output",
        operation_type="edition_auto",
        operation_id=f"{req.job_id}:edit:{req.clip_index}",
    )


@app.post("/api/edit", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def edit_clip(
    request: Request,
    req: EditRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
    x_gemini_key: Annotated[Optional[str], Header(alias="X-Gemini-Key")] = None,
):
    await _require_job_ownership(req.job_id, user_id)

    # Determine API Key
    final_api_key = req.api_key or x_gemini_key or os.environ.get("GEMINI_API_KEY")

    if not final_api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API Key (Header or Body)")

    edit_required_credits = 0.0

    job = jobs.get(req.job_id)

    try:
        input_path, filename = _resolve_edit_clip_input_path(req, job)

        input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
        input_duration_seconds = _probe_local_video_duration_seconds(input_path)
        edit_required_credits = _estimate_reel_required_credits(
            duration_seconds=input_duration_seconds,
            size_bytes=input_size_bytes,
            uses_youtube_source=False,
            uses_openai=False,
            uses_assembly=False,
            uses_gemini=True,
        )
        await _assert_user_has_required_credits(user_id, edit_required_credits)

        os.makedirs(os.path.join(OUTPUT_DIR, req.job_id), exist_ok=True)

        # Define output path for edited video
        edited_filename = f"edited_{filename}"
        output_path = os.path.join(OUTPUT_DIR, req.job_id, edited_filename)

        transcript_for_edit = await _load_transcript_for_edit(req.job_id)

        # Run editing in a thread to avoid blocking main loop
        # Since VideoEditor uses blocking calls (subprocess, API wait)
        loop = asyncio.get_event_loop()
        plan = await loop.run_in_executor(
            None, _run_video_edit, final_api_key, req.job_id, input_path, output_path, transcript_for_edit, req.auto_edit_options,
        )

        # Update clip URL in the job result?
        # Or return new URL and let frontend handle it?
        # Updating job result allows persistence if page refreshes.

        new_video_url = f"/videos/{req.job_id}/{edited_filename}"

        # Start a new "edited" clip entry or just update the current one?
        # Let's update the current one's video_url but keep backup?
        # Or return the new URL to the frontend to display.

        await _debit_edit_credits_and_log(user_id, req, edit_required_credits)

        return {
            "success": True,
            "new_video_url": new_video_url,
            "edit_plan": plan,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Edit Error", e)

async def _save_caption_upload_file(file: UploadFile, input_path: str, limit_bytes: float) -> int:
    size_bytes = 0
    try:
        async with aiofiles.open(input_path, "wb") as handle:
            while content := await file.read(1024 * 1024):
                size_bytes += len(content)
                if limit_bytes > 0 and size_bytes > limit_bytes:
                    raise HTTPException(status_code=413, detail=f"Fichier trop volumineux. Maximum autorise: {CAPTION_MAX_STORAGE_GB:.2f} Go")
                await handle.write(content)
    except HTTPException:
        if os.path.exists(input_path):
            os.remove(input_path)
        raise
    finally:
        await file.close()
    return size_bytes


async def _create_caption_endpoint_project(user_id: str, caption_job_id: str, source_name: str, input_path: str, size_bytes: int, local_duration: float):
    if not is_supabase_configured():
        return None
    try:
        project_name = _project_name_from_uploaded_file(source_name)
        project_description = _build_short_project_summary(project_name, fallback_title=project_name)
        # Upload source to S3 with project-based key structure
        bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
        s3_source_key = f"projects/{caption_job_id}/source/{source_name}"

        if os.path.exists(input_path):
            upload_file_to_s3(input_path, bucket_name, s3_source_key)
        project_thumbnail_ref = _generate_and_upload_project_thumbnail_from_source(
            input_path,
            bucket_name,
            user_id,
            caption_job_id,
        )

        # Create project record
        project = await supabase_create_project(
            user_id=user_id,
            name=project_name,
            description=project_description,
            project_type="caption",
            source_type="upload",
            source_s3_key=s3_source_key,
            source_size=size_bytes,
            source_duration=int(local_duration) if local_duration else None,
            thumbnail_url=project_thumbnail_ref,
            status="processing",
        )
        await _finalize_source_media_retention(caption_job_id, user_id, project, size_bytes, bucket_name, s3_source_key)
        return project
    except Exception as e:
        logger.warning(f"Failed to create project for caption job {caption_job_id}: {str(e)}")
        return None


async def _enqueue_caption_endpoint_job(
    caption_job_id: str, user_id: str, output_dir: str, input_path: str, source_name: str,
    job_priority: int, caption_required_credits: float, project, local_duration: float,
) -> None:
    runtime_payload = {
        "status": "queued",
        "logs": [f"Caption job {caption_job_id} queued."],
        "output_dir": output_dir,
        "input_path": input_path,
        "source_type": "file",
        "source_value": source_name,
        "source_name": source_name,
        "user_id": user_id,
        "priority": job_priority,
        "job_kind": "caption",
        "caption_required_credits": caption_required_credits,
        "project_id": project.get("id") if project else None,
        "source_duration_seconds": float(local_duration or 0.0),
    }

    jobs[caption_job_id] = dict(runtime_payload)
    reel_job_manager.runtime_jobs[caption_job_id] = dict(runtime_payload)
    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_SUBTITLES,
        pipeline_name="CaptionProcessingPipeline",
        job_id=caption_job_id,
        job_data={
            "source_type": "file",
            "source_value": source_name,
            "output_dir": output_dir,
            "input_path": input_path,
            "caption_max_duration_minutes": CAPTION_MAX_DURATION_MINUTES,
            "caption_max_storage_gb": CAPTION_MAX_STORAGE_GB,
            "project_id": project.get("id") if project else None,
            "source_duration_seconds": float(local_duration or 0.0),
            "caption_required_credits": caption_required_credits,
        },
        runtime_data=dict(runtime_payload),
        max_attempts=CAPTION_JOB_MAX_ATTEMPTS,
        reserved_quota=caption_required_credits,
        priority=job_priority,
        queue_name="captions",
    )
    await reel_job_manager.enqueue_job(caption_job_id)
    await CaptionProcessingPipeline(reel_job_manager, caption_job_id).step(0, "queued")
    await enqueue_reel_job(caption_job_id, priority=job_priority)


@app.post("/api/captions/process", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 413: {"description": "Payload Too Large"}, 429: {"description": "Too Many Requests"}})
async def process_caption_endpoint(
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(get_user_id_header)],
    acknowledged: Annotated[Optional[str], Form()] = None,
):
    if not file:
        raise HTTPException(status_code=400, detail="Must provide a video file")

    ack_flag = str(acknowledged).lower() in ("1", "true", "yes")
    if not ack_flag:
        raise HTTPException(status_code=400, detail="You must confirm you own the content or have rights to process it.")

    await _enforce_job_concurrency_limit(user_id)

    _validate_video_extension(file.filename if file else "", context_label="sous-titres")

    caption_job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, caption_job_id)
    os.makedirs(output_dir, exist_ok=True)

    source_name = os.path.basename(str(file.filename or "caption_source.mp4"))
    input_filename = f"caption_input_{int(time.time())}_{source_name}"
    input_path = os.path.join(output_dir, input_filename)

    limit_bytes = max(0.0, CAPTION_MAX_STORAGE_GB) * (1024 ** 3)
    size_bytes = await _save_caption_upload_file(file, input_path, limit_bytes)

    local_duration = _probe_local_video_duration_seconds(input_path)
    _validate_caption_source_constraints(
        duration_seconds=local_duration,
        size_bytes=float(size_bytes),
        source_label="fichier",
    )

    caption_required_credits = _estimate_caption_required_credits(
        duration_seconds=local_duration,
        size_bytes=float(size_bytes),
    )
    try:
        await _reserve_job_credits(user_id, caption_required_credits)
    except HTTPException:
        if os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(output_dir, ignore_errors=True)
        raise

    job_priority = await _resolve_user_job_priority(user_id)

    project = await _create_caption_endpoint_project(user_id, caption_job_id, source_name, input_path, size_bytes, local_duration)

    await _enqueue_caption_endpoint_job(
        caption_job_id, user_id, output_dir, input_path, source_name, job_priority, caption_required_credits, project, local_duration,
    )

    return {
        "job_id": caption_job_id,
        "project_id": project.get("id") if project else None,
        "status": "queued"
    }


class SubtitleRequest(BaseModel):
    job_id: str
    clip_index: int
    position: str = "bottom" # top, middle, bottom
    position_x: float = 50.0
    position_y: float = 82.0
    font_size: int = 16
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    highlight_color: str = "#FFDD00"
    border_color: str = "#000000"
    border_width: int = 2
    text_shadow_color: str = "#000000"
    shadow_blur: int = 6
    shadow_offset_x: int = 0
    shadow_offset_y: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    text_case: str = "none"
    bold: bool = True
    italic: bool = False
    words_per_line: int = 4
    animation: str = "pop"
    input_filename: Optional[str] = None
    input_url: Optional[str] = None


def _extract_clip_captions_from_transcript(transcript: Dict[str, Any], clip_start: float, clip_end: float) -> List[Dict[str, Any]]:
    captions = []
    for segment in transcript.get('segments', []):
        for word_info in segment.get('words', []):
            if word_info['end'] > clip_start and word_info['start'] < clip_end:
                captions.append({
                    "text": word_info.get('word', '').strip(),
                    "startMs": int((max(0, word_info['start'] - clip_start)) * 1000),
                    "endMs": int((max(0, word_info['end'] - clip_start)) * 1000),
                })
    return captions


def _saved_subtitle_captions_from_clip_data(clip_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not isinstance(clip_data, dict):
        return []

    subtitle_config = clip_data.get("subtitle_config")
    if isinstance(subtitle_config, dict):
        captions = subtitle_config.get("captions")
        if isinstance(captions, list):
            return captions

    remotion_layers = clip_data.get("remotion_layers")
    if isinstance(remotion_layers, dict):
        for layer_key in ("captions", "subtitles"):
            layer = remotion_layers.get(layer_key)
            if isinstance(layer, dict) and isinstance(layer.get("captions"), list):
                return layer.get("captions")

    return []


def _style_from_clip_subtitle_state(clip_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    if not isinstance(clip_data, dict):
        return {}, ""

    subtitle_config = clip_data.get("subtitle_config")
    if isinstance(subtitle_config, dict):
        style = subtitle_config.get("style")
        if isinstance(style, dict) and style:
            return style, "clip_data.subtitle_config"

    remotion_layers = clip_data.get("remotion_layers")
    if isinstance(remotion_layers, dict):
        for layer_key in ("captions", "subtitles"):
            layer = remotion_layers.get(layer_key)
            if isinstance(layer, dict):
                style = layer.get("style")
                if isinstance(style, dict) and style:
                    return style, f"clip_data.remotion_layers.{layer_key}"

    return {}, ""


async def _resolve_active_subtitle_style_for_clip(job_id: str, clip_index: int, user_id: str, clip_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Resolve subtitle style in explicit priority order for visuals re-burn:

    1. The last persisted clip-local subtitle payload (`subtitle_config`)
    2. Persisted Remotion layer style on the clip metadata
    3. The latest Supabase style_edit_versions row for this clip
    4. The user's saved global default (or factory default fallback)
    """
    clip_style, source = _style_from_clip_subtitle_state(clip_data)
    if clip_style:
        return {**_DEFAULT_AUTO_CAPTION_STYLE_KWARGS, **clip_style}, source

    if is_supabase_configured():
        try:
            versions = await supabase_list_style_edit_versions(job_id, int(clip_index), user_id)
            if versions:
                style_config = versions[-1].get("style_config")
                if isinstance(style_config, dict) and style_config:
                    return {**_DEFAULT_AUTO_CAPTION_STYLE_KWARGS, **style_config}, "style_edit_versions.latest"
        except Exception as exc:
            logger.warning("Failed to resolve latest subtitle style for job %s clip %s: %s", job_id, clip_index, exc)

    return await _get_user_default_caption_style(user_id), "user_default_or_factory_default"


def _write_saved_captions_to_srt(captions: List[Dict[str, Any]], srt_path: str) -> bool:
    lines: List[str] = []
    index = 1
    for caption in captions:
        text = str((caption or {}).get("text") or "").strip()
        start_ms = (caption or {}).get("startMs")
        end_ms = (caption or {}).get("endMs")
        if not text:
            continue
        try:
            start_seconds = max(0.0, float(start_ms) / 1000.0)
            end_seconds = max(start_seconds, float(end_ms) / 1000.0)
        except (TypeError, ValueError):
            continue
        lines.extend([
            str(index),
            f"{_srt_timestamp(start_seconds)} --> {_srt_timestamp(end_seconds)}",
            text,
            "",
        ])
        index += 1

    if index == 1:
        return False

    with open(srt_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines))
    return True


async def _generate_subtitle_srt_from_clip_context(
    input_path: str,
    filename: str,
    transcript: Optional[Dict[str, Any]],
    clip_data: Dict[str, Any],
    srt_path: str,
    words_per_line: int,
    animation: str = "none",
) -> bool:
    if transcript:
        return await _generate_subtitle_srt(
            input_path,
            filename,
            transcript,
            clip_data,
            srt_path,
            words_per_line,
            animation=animation,
        )
    saved_captions = _saved_subtitle_captions_from_clip_data(clip_data)
    if saved_captions:
        return _write_saved_captions_to_srt(saved_captions, srt_path)
    return False


def _build_subtitle_request_from_style(job_id: str, clip_index: int, style_config: Dict[str, Any]) -> SubtitleRequest:
    merged_style = {**_DEFAULT_AUTO_CAPTION_STYLE_KWARGS, **(style_config or {})}
    return SubtitleRequest(job_id=job_id, clip_index=clip_index, **merged_style)


@app.get("/api/clip/{job_id}/{clip_index}/transcript", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 404: {"description": "Not Found"}})
async def get_clip_transcript(job_id: str, clip_index: int, request: Request):
    """Return word-level captions for a specific clip, formatted for Remotion."""
    # Do not depend on in-memory jobs: Reels page must keep working after restarts.
    verified_user_id = _get_authenticated_user_id_optional(request)
    _, data = await _get_or_build_job_metadata(job_id, clip_index, user_id=verified_user_id)
    if not data:
        # Graceful fallback when metadata cannot be reconstructed.
        return {
            "captions": [],
            "durationSec": 0,
            "language": "en",
            "missing": "metadata",
        }

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[clip_index]
    clip_start = clip_data.get('start', 0)
    clip_end = clip_data.get('end', 0)

    saved_subtitle_config = clip_data.get("subtitle_config") if isinstance(clip_data, dict) else None
    saved_captions = []
    if isinstance(saved_subtitle_config, dict):
        maybe_captions = saved_subtitle_config.get("captions")
        if isinstance(maybe_captions, list):
            saved_captions = maybe_captions

    transcript = data.get('transcript')
    if not transcript and not saved_captions:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata")

    # Extract words within clip range and convert to CaptionWord format
    captions = saved_captions if saved_captions else _extract_clip_captions_from_transcript(transcript, clip_start, clip_end)

    duration_sec = clip_end - clip_start

    # The dashboard's client-side captions render (Remotion/WebCodecs, see
    # ResultCard.jsx's handleCaptions) composites a brand new subtitle layer
    # onto whatever video it's given -- if that's the already-captioned
    # default clip, the old captions stay baked into the pixels underneath
    # the new ones. Resolve the clean, pre-caption source here (same lookup
    # add_subtitles uses server-side, see _resolve_authoritative_clean_video_
    # source) so that render always starts from clean pixels.
    clean_original_s3_key = await _resolve_authoritative_clean_video_source(job_id, clip_index, verified_user_id)
    clean_video_url = _reel_media_url_from_s3_key(clean_original_s3_key) if clean_original_s3_key else ""

    return {
        "captions": captions,
        "durationSec": duration_sec,
        "language": (transcript or {}).get('language', 'en'),
        "subtitleConfig": saved_subtitle_config if isinstance(saved_subtitle_config, dict) else None,
        "remotionLayers": clip_data.get("remotion_layers") if isinstance(clip_data, dict) else None,
        "cleanVideoUrl": clean_video_url,
    }


@app.get("/api/clip/{job_id}/{clip_index}/preview-image/ensure", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def ensure_clip_preview_image(
    job_id: str,
    clip_index: int,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    preview_image_url = await _ensure_preview_image_for_clip(job_id, clip_index, user_id)
    return {
        "preview_image_url": preview_image_url,
        "ensured": bool(preview_image_url),
    }


async def _fetch_existing_caption_row_for_history(job_id: str, clip_index: int, user_id: str, fallback_url: str):
    try:
        existing_caption_row = await supabase_get_caption_by_job_clip(job_id, clip_index, user_id)
    except Exception:
        return None, fallback_url
    source_video_url = (
        _caption_media_url_from_s3_key((existing_caption_row or {}).get("caption_s3_key") or "")
        or str((existing_caption_row or {}).get("caption_url") or "")
        or fallback_url
    )
    return existing_caption_row, source_video_url


async def _fetch_existing_reel_url_for_history(job_id: str, clip_index: int, user_id: str, fallback_url: str) -> str:
    try:
        reel_row = await supabase_get_reel_by_job_clip(job_id, clip_index, user_id=user_id)
    except Exception:
        return fallback_url
    return (
        _reel_media_url_from_s3_key((reel_row or {}).get("reel_s3_key") or "")
        or str((reel_row or {}).get("reel_url") or "")
        or fallback_url
    )


async def _resolve_caption_persist_history_context(job_id: str, clip_index: int, user_id: str, clip_data: Dict[str, Any]):
    source_video_url_before_edit = str(clip_data.get("video_url") or "")
    if source_video_url_before_edit and not clip_data.get("original_video_url"):
        clip_data["original_video_url"] = source_video_url_before_edit
    source_video_url_for_history = source_video_url_before_edit
    existing_caption_row: Optional[Dict[str, Any]] = None
    if is_supabase_configured():
        existing_caption_row, source_video_url_for_history = await _fetch_existing_caption_row_for_history(
            job_id, clip_index, user_id, source_video_url_for_history
        )
        source_video_url_for_history = await _fetch_existing_reel_url_for_history(
            job_id, clip_index, user_id, source_video_url_for_history
        )
    return existing_caption_row, source_video_url_for_history


def _parse_json_dict_or_none(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    try:
        if raw:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return parsed
    except Exception:
        pass
    return None


async def _save_and_measure_captioned_render(file: UploadFile, output_path: str):
    def _copy_upload_to_path():
        with open(output_path, "wb") as handle:  # NOSONAR(S7493) runs off the event loop via asyncio.to_thread below
            shutil.copyfileobj(file.file, handle)

    try:
        # Off the event loop via to_thread rather than aiofiles: this reads
        # from file.file (the underlying sync SpooledTemporaryFile), not
        # file.read(), matching the original shutil.copyfileobj-based
        # behavior this endpoint's tests are written against.
        await asyncio.to_thread(_copy_upload_to_path)
    finally:
        await file.close()

    rendered_size_bytes = float(os.path.getsize(output_path) if os.path.exists(output_path) else 0)
    rendered_storage_gb = _bytes_to_gb(rendered_size_bytes)
    rendered_duration_seconds = _probe_local_video_duration_seconds(output_path)
    caption_persist_cost_breakdown = _estimate_caption_cost_breakdown(
        duration_seconds=rendered_duration_seconds,
        size_bytes=rendered_size_bytes,
        uses_assembly=False,
        uses_openai=False,
        uses_gemini=False,
    )
    caption_required_credits = _estimate_caption_required_credits(
        duration_seconds=rendered_duration_seconds,
        size_bytes=rendered_size_bytes,
        uses_assembly=False,
        uses_openai=False,
        uses_gemini=False,
    )
    return rendered_storage_gb, caption_persist_cost_breakdown, caption_required_credits


def _apply_local_video_url_to_clip(
    job: Optional[Dict[str, Any]], clip_index: int, clip_data: Dict[str, Any], clips: List[Any], data: Dict[str, Any],
    local_video_url: str, subtitle_config_payload: Optional[Dict[str, Any]], remotion_layers_payload: Optional[Dict[str, Any]],
) -> None:
    if job and clip_index < len(job.get('result', {}).get('clips', [])):
        job['result']['clips'][clip_index]['video_url'] = local_video_url

    clip_data['video_url'] = local_video_url
    if subtitle_config_payload:
        clip_data['subtitle_config'] = subtitle_config_payload
    if remotion_layers_payload:
        clip_data['remotion_layers'] = remotion_layers_payload
    clips[clip_index] = clip_data
    data['shorts'] = clips


def _upload_captioned_thumbnails(output_path: str, user_id: str, job_id: str, clip_index: int, bucket: str):
    caption_thumbnail_ref = ""
    reel_thumbnail_s3_key = ""
    # Keep a static visual for cards that should not autoplay the edited clip.
    thumb_local_path = _generate_reel_thumbnail_from_video(output_path, OUTPUT_DIR, job_id, clip_index)
    if not (thumb_local_path and os.path.exists(thumb_local_path)):
        return caption_thumbnail_ref, reel_thumbnail_s3_key

    thumb_suffix = int(time.time())
    caption_thumbnail_s3_key = f"captions/{user_id}/{job_id}/thumbnail_{clip_index}_{thumb_suffix}.jpg"
    reel_thumbnail_s3_key = f"reels/{user_id}/{job_id}/thumbnail_{clip_index}.jpg"

    try:
        if upload_file_to_s3(thumb_local_path, bucket, caption_thumbnail_s3_key):
            caption_thumbnail_ref = caption_thumbnail_s3_key
    except Exception as thumb_upload_error:
        logger.warning("Caption thumbnail upload failed for %s/%s: %s", job_id, clip_index, thumb_upload_error)

    try:
        if not upload_file_to_s3(thumb_local_path, bucket, reel_thumbnail_s3_key):
            reel_thumbnail_s3_key = ""
    except Exception as thumb_upload_error:
        reel_thumbnail_s3_key = ""
        logger.warning("Reel thumbnail upload failed for %s/%s: %s", job_id, clip_index, thumb_upload_error)

    try:
        os.remove(thumb_local_path)
    except Exception:
        pass

    return caption_thumbnail_ref, reel_thumbnail_s3_key


def _upload_captioned_video_and_thumbnails(output_path: str, user_id: str, job_id: str, clip_index: int, output_filename: str, local_video_url: str):
    caption_s3_key = ""
    persisted_video_url = local_video_url
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not (bucket and os.path.exists(output_path)):
        return persisted_video_url, caption_s3_key, "", ""

    caption_s3_key = f"captions/{user_id}/{job_id}/{output_filename}"
    if upload_file_to_s3(output_path, bucket, caption_s3_key):
        persisted_video_url = _caption_media_url_from_s3_key(caption_s3_key) or local_video_url

    caption_thumbnail_ref, reel_thumbnail_s3_key = _upload_captioned_thumbnails(output_path, user_id, job_id, clip_index, bucket)

    return persisted_video_url, caption_s3_key, caption_thumbnail_ref, reel_thumbnail_s3_key


def _resolve_and_apply_preview_image(
    job: Optional[Dict[str, Any]], clip_index: int, clip_data: Dict[str, Any], clips: List[Any], data: Dict[str, Any],
    persisted_video_url: str, local_video_url: str, caption_thumbnail_ref: str, reel_thumbnail_s3_key: str,
) -> str:
    preview_image_url = ""
    if caption_thumbnail_ref.startswith(_CAPTIONS_PREFIX):
        preview_image_url = _caption_media_url_from_s3_key(caption_thumbnail_ref) or ""
    if not preview_image_url and reel_thumbnail_s3_key:
        preview_image_url = _reel_thumbnail_url_from_s3_key(reel_thumbnail_s3_key) or ""
    if not preview_image_url:
        preview_image_url = persisted_video_url or local_video_url

    if job and clip_index < len(job.get('result', {}).get('clips', [])):
        if persisted_video_url != local_video_url:
            job['result']['clips'][clip_index]['video_url'] = persisted_video_url
        job['result']['clips'][clip_index]['thumbnail_url'] = preview_image_url
        job['result']['clips'][clip_index]['preview_image_url'] = preview_image_url

    if persisted_video_url != local_video_url:
        clip_data['video_url'] = persisted_video_url
    clip_data['thumbnail_url'] = preview_image_url
    clip_data['preview_image_url'] = preview_image_url
    clips[clip_index] = clip_data
    data['shorts'] = clips

    return preview_image_url


async def _sync_supabase_after_caption_persist(
    job_id: str, clip_index: int, user_id: str, existing_caption_row: Optional[Dict[str, Any]],
    local_video_url: str, persisted_video_url: str, caption_s3_key: str, caption_thumbnail_ref: str,
    reel_thumbnail_s3_key: str, caption_persist_cost_breakdown: Dict[str, Any], caption_required_credits: float, rendered_storage_gb: float,
) -> None:
    if not is_supabase_configured():
        return

    caption_row = existing_caption_row or await supabase_get_caption_by_job_clip(job_id, clip_index, user_id)
    if caption_row:
        caption_updates: Dict[str, Any] = {
            "caption_url": local_video_url,
            "caption_status": "termine",
            "billing_details": _build_billing_details(
                "sous_titre",
                caption_persist_cost_breakdown,
                actual_credit=caption_required_credits,
                actual_storage_gb=rendered_storage_gb,
                extra={"stage": "persist"},
            ),
            "total_cost_usd": 0,
        }
        if caption_s3_key:
            caption_updates["caption_s3_key"] = caption_s3_key
            caption_updates["caption_url"] = persisted_video_url
        if caption_thumbnail_ref:
            caption_updates["caption_thumbnail_url"] = caption_thumbnail_ref
        await supabase_update_caption(str(caption_row.get("id")), user_id, caption_updates)

    if persisted_video_url:
        try:
            await supabase_update_reel_media_by_job_clip(
                job_id=job_id,
                clip_index=clip_index,
                reel_url=persisted_video_url,
                reel_s3_key=caption_s3_key or None,
                reel_thumbnail_url=reel_thumbnail_s3_key or None,
                user_id=user_id,
            )
        except Exception as e:
            print(f"⚠️ Failed to sync reel URL after captions persist: {e}")


async def _debit_caption_persist_credits(user_id: str, caption_required_credits: float, rendered_storage_gb: float, job_id: str, clip_index: int) -> None:
    if not (is_supabase_configured() and (caption_required_credits > 0 or rendered_storage_gb > 0)):
        return
    debited = await supabase_deduct_user_credits(user_id, caption_required_credits, -rendered_storage_gb)
    if not debited:
        raise HTTPException(status_code=500, detail="Failed to debit credit/storage for captions")
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=caption_required_credits,
        storage=round(rendered_storage_gb, 6),
        operation="output",
        operation_type="sous_titre",
        operation_id=f"{job_id}:captions:{clip_index}",
    )


async def _persist_style_edit_version_after_captions(
    user_id: str, job_id: str, clip_index: int, version_number: Optional[int], style_config_for_history: Optional[Dict[str, Any]],
    source_video_url_for_history: str, persisted_video_url: str, caption_persist_cost_breakdown: Dict[str, Any],
    caption_required_credits: float, rendered_storage_gb: float,
) -> None:
    if not (is_supabase_configured() and style_config_for_history is not None and version_number is not None):
        return
    try:
        await supabase_insert_style_edit_version(
            {
                "user_id": user_id,
                "job_id": job_id,
                "clip_index": int(clip_index),
                "version_number": int(version_number),
                "operation_type": "subtitle_style",
                "source_video_url": source_video_url_for_history,
                "output_video_url": persisted_video_url,
                "style_config": style_config_for_history,
                "billing_details": _build_billing_details(
                    "sous_titre",
                    caption_persist_cost_breakdown,
                    actual_credit=caption_required_credits,
                    actual_storage_gb=rendered_storage_gb,
                    extra={"stage": "style_edit"},
                ),
            }
        )
    except Exception as e:
        print(f"⚠️ Failed to persist style edit version: {e}")


def _validate_captioned_reel_upload(file: Optional[UploadFile]) -> None:
    if not file:
        raise HTTPException(status_code=400, detail="Missing rendered video file")
    content_type = str(file.content_type or "").lower()
    if content_type and not content_type.startswith("video/"):
        raise HTTPException(status_code=400, detail="Invalid rendered video content type")


async def _load_clip_for_caption_persist(job_id: str, clip_index: int):
    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)
    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)
    clip_data = clips[clip_index] if isinstance(clips[clip_index], dict) else {}
    return metadata_path, data, clips, clip_data


def _resolve_captioned_reel_output_path(job_id: str, clip_index: int, filename: Optional[str]):
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    os.makedirs(output_dir, exist_ok=True)
    upload_name = str(filename or "captioned.mp4")
    ext = os.path.splitext(upload_name)[1].lower()
    if ext not in _COMMON_VIDEO_EXTENSIONS:
        ext = ".mp4"
    output_filename = f"captioned_{clip_index}_{int(time.time())}{ext}"
    output_path = os.path.join(output_dir, output_filename)
    return output_filename, output_path


async def _assert_credits_or_cleanup_output(user_id: str, caption_required_credits: float, output_path: str) -> None:
    try:
        await _assert_user_has_required_credits(user_id, caption_required_credits)
    except HTTPException:
        if os.path.exists(output_path):
            os.remove(output_path)
        raise


@app.post("/api/reels/{job_id}/{clip_index}/captions/persist", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}})
async def persist_captioned_reel(
    job_id: str,
    clip_index: int,
    file: Annotated[UploadFile, File()],
    user_id: Annotated[str, Depends(get_user_id_header)],
    subtitle_config: Annotated[Optional[str], Form()] = None,
    remotion_layers: Annotated[Optional[str], Form()] = None,
):
    _validate_captioned_reel_upload(file)

    metadata_path, data, clips, clip_data = await _load_clip_for_caption_persist(job_id, clip_index)
    existing_caption_row, source_video_url_for_history = await _resolve_caption_persist_history_context(job_id, clip_index, user_id, clip_data)

    subtitle_config_payload = _parse_json_dict_or_none(subtitle_config)
    remotion_layers_payload = _parse_json_dict_or_none(remotion_layers)

    output_filename, output_path = _resolve_captioned_reel_output_path(job_id, clip_index, file.filename)

    rendered_storage_gb, caption_persist_cost_breakdown, caption_required_credits = await _save_and_measure_captioned_render(file, output_path)
    await _assert_credits_or_cleanup_output(user_id, caption_required_credits, output_path)

    local_video_url = f"/videos/{job_id}/{output_filename}"
    job = jobs.get(job_id)
    _apply_local_video_url_to_clip(job, clip_index, clip_data, clips, data, local_video_url, subtitle_config_payload, remotion_layers_payload)

    style_config_for_history: Optional[Dict[str, Any]] = None
    if subtitle_config_payload:
        style_config_for_history = subtitle_config_payload.get("style") if isinstance(subtitle_config_payload.get("style"), dict) else {}

    persisted_video_url, caption_s3_key, caption_thumbnail_ref, reel_thumbnail_s3_key = _upload_captioned_video_and_thumbnails(
        output_path, user_id, job_id, clip_index, output_filename, local_video_url,
    )

    preview_image_url = _resolve_and_apply_preview_image(
        job, clip_index, clip_data, clips, data, persisted_video_url, local_video_url, caption_thumbnail_ref, reel_thumbnail_s3_key,
    )

    version_number: Optional[int] = None
    if style_config_for_history is not None:
        version_number = _append_style_version_to_metadata(
            data,
            clip_index,
            source_video_url_for_history,
            persisted_video_url,
            style_config_for_history,
        )

    _persist_metadata_json(metadata_path, data)

    await _sync_supabase_after_caption_persist(
        job_id, clip_index, user_id, existing_caption_row, local_video_url, persisted_video_url,
        caption_s3_key, caption_thumbnail_ref, reel_thumbnail_s3_key, caption_persist_cost_breakdown, caption_required_credits, rendered_storage_gb,
    )

    await _debit_caption_persist_credits(user_id, caption_required_credits, rendered_storage_gb, job_id, clip_index)

    await _persist_style_edit_version_after_captions(
        user_id, job_id, clip_index, version_number, style_config_for_history,
        source_video_url_for_history, persisted_video_url, caption_persist_cost_breakdown, caption_required_credits, rendered_storage_gb,
    )

    return {
        "success": True,
        "new_video_url": persisted_video_url,
        "preview_image_url": preview_image_url,
        "persisted": True,
        "job_id": job_id,
        "clip_index": clip_index,
        "user_id": user_id,
    }


# --- Remotion Render Proxy ---
# Sonar false positive (S5332): default only reachable over the internal Docker
# Compose network (service name "renderer", never exposed publicly -- see
# docker-compose.yml, bound to 127.0.0.1 for local debugging only), and
# every request to it carries RENDER_SERVICE_API_KEY. TLS on that internal
# hop isn't the control that matters here; the network boundary + API key
# are. Override with RENDER_SERVICE_URL for any deployment that differs.
RENDER_SERVICE_URL = os.getenv("RENDER_SERVICE_URL", "http://renderer:3100")  # NOSONAR
RENDER_SERVICE_API_KEY = os.getenv("RENDER_SERVICE_API_KEY")
if not RENDER_SERVICE_API_KEY and not _is_pytest_runtime():
    raise RuntimeError(
        "RENDER_SERVICE_API_KEY manquant dans l'environnement -- requis pour "
        "s'authentifier aupres du render-service interne."
    )
_RENDER_SERVICE_HEADERS = {"x-internal-api-key": RENDER_SERVICE_API_KEY or "unit-test-render-key"}


@app.post("/api/render", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def proxy_render(request: Request, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Proxy render requests to the Node.js Remotion render service.

    Security: this endpoint used to forward the raw client body to an
    internal service with no authentication of its own -- requiring a
    verified session here, and authenticating to render-service with a
    shared internal API key, closes both the unauthenticated-proxy and the
    unauthenticated-render-service issues together.
    """
    import httpx
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{RENDER_SERVICE_URL}/render", json=body, headers=_RENDER_SERVICE_HEADERS
            )
            return resp.json()
    except Exception as e:
        raise _generic_error(
            "Render service unavailable (proxy_render)", e, status_code=502,
            detail="Le service de rendu est indisponible.",
        )

@app.get("/api/render/{render_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def proxy_render_status(render_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Proxy render status polling to the Node.js Remotion render service."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{RENDER_SERVICE_URL}/render/{render_id}", headers=_RENDER_SERVICE_HEADERS
            )
            return resp.json()
    except Exception as e:
        raise _generic_error(
            "Render service unavailable (proxy_render_status)", e, status_code=502,
            detail="Le service de rendu est indisponible.",
        )


class EffectsGenerateRequest(BaseModel):
    job_id: str
    clip_index: int
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    auto_edit_options: Optional[Dict[str, bool]] = None

def _probe_video_stream_for_effects(safe_input_path: str):
    probe_cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,r_frame_rate,duration',
        '-show_entries', 'format=duration',
        '-of', 'json',
        safe_input_path
    ]
    probe_result = subprocess.check_output(probe_cmd, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
    probe_data = json.loads(probe_result)

    # `.get('streams', [{}])` only supplies the default when the key is
    # missing entirely -- an existing-but-empty list (a file ffprobe can
    # read but finds no video stream in) would still index-error here.
    streams = probe_data.get('streams') or [{}]
    stream = streams[0]
    width = int(stream.get('width', 1080))
    height = int(stream.get('height', 1920))

    # Parse fps from r_frame_rate (e.g. "30/1")
    r_frame_rate = stream.get('r_frame_rate', '30/1')
    num, den = r_frame_rate.split('/')
    fps = round(int(num) / int(den), 2)

    # Get duration from stream or format
    duration = float(stream.get('duration', 0))
    if duration == 0:
        duration = float(probe_data.get('format', {}).get('duration', 0))

    return width, height, fps, duration


def _load_transcript_for_effects(job_id: str) -> Optional[Dict[str, Any]]:
    try:
        meta_files = glob.glob(os.path.join(OUTPUT_DIR, job_id, _METADATA_JSON_GLOB))
        if meta_files:
            # Sonar false positive (S7493): this is
            # inside a nested sync def (see below, run via
            # loop.run_in_executor in a thread pool), not
            # actually executing on the event loop despite
            # being lexically inside an async endpoint.
            with open(meta_files[0], 'r') as f:  # NOSONAR
                data = json.load(f)
                return data.get('transcript')
    except Exception as e:
        print(f"⚠️ Could not load transcript for effects config: {e}")
    return None


def _run_effects_generation(final_api_key: str, job_id: str, input_path: str):
    editor = VideoEditor(api_key=final_api_key)

    # Create safe ASCII filename to avoid encoding issues
    safe_filename = f"temp_effects_{job_id}.mp4"
    safe_input_path = os.path.join(OUTPUT_DIR, job_id, safe_filename)
    shutil.copy(input_path, safe_input_path)

    try:
        # Upload video to Gemini
        vid_file = editor.upload_video(safe_input_path)
        width, height, fps, duration = _probe_video_stream_for_effects(safe_input_path)
        transcript = _load_transcript_for_effects(job_id)

        # Generate effects config
        return editor.get_effects_config(
            vid_file, duration, fps=fps, width=width, height=height, transcript=transcript
        )
    finally:
        if os.path.exists(safe_input_path):
            os.remove(safe_input_path)


@app.post("/api/effects/generate", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}})
async def generate_effects_config(
    req: EffectsGenerateRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
    x_gemini_key: Annotated[Optional[str], Header(alias="X-Gemini-Key")] = None,
):
    """Generate structured EffectsConfig JSON for Remotion rendering via Gemini AI."""
    await _require_job_ownership(req.job_id, user_id)

    final_api_key = x_gemini_key or os.environ.get("GEMINI_API_KEY")

    if not final_api_key:
        raise HTTPException(status_code=400, detail="Missing Gemini API Key (Header)")

    job = jobs.get(req.job_id)

    try:
        input_path, _filename = _resolve_edit_clip_input_path(req, job)

        input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
        input_duration_seconds = _probe_local_video_duration_seconds(input_path)
        effects_required_credits = _estimate_reel_required_credits(
            duration_seconds=input_duration_seconds,
            size_bytes=input_size_bytes,
            uses_youtube_source=False,
            uses_openai=False,
            uses_assembly=False,
            uses_gemini=True,
        )
        await _assert_user_has_required_credits(user_id, effects_required_credits)

        os.makedirs(os.path.join(OUTPUT_DIR, req.job_id), exist_ok=True)

        loop = asyncio.get_event_loop()
        effects_config = await loop.run_in_executor(None, _run_effects_generation, final_api_key, req.job_id, input_path)

        if effects_config is None:
            raise HTTPException(status_code=500, detail="Failed to generate effects config from Gemini")

        normalized_effects, applied_steps = _apply_auto_edit_options_to_effects_config(
            effects_config,
            req.auto_edit_options,
        )
        return {
            "effects": normalized_effects,
            "applied_steps": applied_steps,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Effects Generation Error", e)


async def _resolve_subtitle_source_video_history(job_id: str, clip_index: int, user_id: str, clip_data: Dict[str, Any]) -> str:
    source_video_url_before_edit = str(clip_data.get("video_url") or "")
    source_video_url_for_history = source_video_url_before_edit
    if not clip_data.get("original_video_url"):
        clip_data["original_video_url"] = source_video_url_before_edit

    if not is_supabase_configured():
        return source_video_url_for_history

    try:
        caption_row = await supabase_get_caption_by_job_clip(job_id, clip_index, user_id)
        source_video_url_for_history = (
            _caption_media_url_from_s3_key((caption_row or {}).get("caption_s3_key") or "")
            or str((caption_row or {}).get("caption_url") or "")
            or source_video_url_for_history
        )
    except Exception:
        pass
    try:
        reel_row = await supabase_get_reel_by_job_clip(job_id, clip_index, user_id=user_id)
        source_video_url_for_history = (
            _reel_media_url_from_s3_key((reel_row or {}).get("reel_s3_key") or "")
            or str((reel_row or {}).get("reel_url") or "")
            or source_video_url_for_history
        )
    except Exception:
        pass
    return source_video_url_for_history


async def _resolve_authoritative_clean_video_source(job_id: str, clip_index: int, user_id: str) -> str:
    """Resolves the S3 key of the clean, pre-caption clip stored at
    generation time (see _build_reel_row_for_clip's original_s3_key /
    _burn_default_captions_for_clip's caption-job equivalent).

    The app now shows/works off a single video URL per clip -- there's no
    "original vs captioned" distinction exposed anywhere anymore (see
    _normalize_reel_row/_normalize_caption_row) -- so a subtitle burn can no
    longer trust whatever URL the request carries to be caption-free. This
    looks the clean source up server-side instead, so re-burning always
    starts from clean pixels and replaces the default captions rather than
    drawing a second layer on top of them. Returns "" when there is none
    (clip was never auto-captioned, or Supabase isn't configured), in which
    case the caller falls back to the request's own video reference, which
    is clean in that case anyway."""
    if not is_supabase_configured():
        return ""
    try:
        reel_row = await supabase_get_reel_by_job_clip(job_id, clip_index, user_id=user_id)
        original_s3_key = str(((reel_row or {}).get("billing_details") or {}).get("original_s3_key") or "")
        if original_s3_key:
            return original_s3_key
    except Exception:
        pass
    try:
        caption_row = await supabase_get_caption_by_job_clip(job_id, clip_index, user_id)
        original_s3_key = str(((caption_row or {}).get("generation_inputs") or {}).get("original_s3_key") or "")
        if original_s3_key:
            return original_s3_key
    except Exception:
        pass
    return ""


async def _resolve_burn_source_input_path(
    req, output_dir: str, clip_data: Dict[str, Any], metadata_path: str, user_id: str,
):
    """Like _resolve_add_subtitles_input_path, but prefers the clean,
    pre-caption source recorded at generation time over whatever video the
    request points at -- used by endpoints that burn a *new* subtitle track
    (add_subtitles, translate_clip), so a restyle/translation always
    replaces the default captions instead of stacking on top of them."""
    original_s3_key = await _resolve_authoritative_clean_video_source(req.job_id, req.clip_index, user_id)
    if original_s3_key:
        clean_source_url = _reel_media_url_from_s3_key(original_s3_key)
        if clean_source_url:
            return _download_input_url_to_job_dir(clean_source_url, req.job_id)
    return _resolve_add_subtitles_input_path(req, output_dir, clip_data, metadata_path)


def _resolve_add_subtitles_input_path(req: SubtitleRequest, output_dir: str, clip_data: Dict[str, Any], metadata_path: str):
    if req.input_filename:
        filename = _sanitize_input_filename(req.input_filename)
        if not filename:
            raise HTTPException(status_code=400, detail=_INVALID_INPUT_FILENAME)
    else:
        # Fallback to standard naming
        filename = clip_data.get('video_url', '').split('/')[-1]
        if not filename:
            base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, '')
            filename = f"{base_name}_clip_{req.clip_index+1}.mp4"

    input_path = os.path.join(output_dir, filename)
    if not os.path.exists(input_path) and req.input_url:
        input_path, filename = _download_input_url_to_job_dir(req.input_url, req.job_id)

    if not os.path.exists(input_path):
        # Try looking for edited version if url implied it?
        # Just fail if not found.
        raise HTTPException(status_code=404, detail=f"Video file not found: {input_path}")

    return input_path, filename


async def _generate_subtitle_srt(input_path: str, filename: str, transcript: Dict[str, Any], clip_data: Dict[str, Any], srt_path: str, words_per_line: int, animation: str = "none") -> bool:
    # Any animation other than "none" highlights the currently-spoken word
    # (see Subtitles.tsx's isActive -> color = highlightColor) -- mark up
    # the SRT so burn_subtitles reproduces that in the burned-in video.
    highlight = animation != "none"

    # Check if this is a dubbed video - if so, transcribe it fresh
    is_dubbed = filename.startswith("translated_")
    if is_dubbed:
        print("🎙️ Dubbed video detected, transcribing audio for subtitles...")

        def run_transcribe_srt():
            return generate_srt_from_video(input_path, srt_path, max_words_per_line=words_per_line, highlight=highlight)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, run_transcribe_srt)

    srt_generator = generate_highlighted_srt if highlight else generate_srt
    return srt_generator(
        transcript,
        clip_data['start'],
        clip_data['end'],
        srt_path,
        max_words_per_line=words_per_line,
    )


async def _reel_visual_windows_for_job_clip(job_id: str, clip_index: int, user_id: str) -> List[Dict[str, Any]]:
    """The reel's currently-configured manual visuals (see the "Reel
    visuals" section above), as the [{"position","start","end"}, ...]
    shape burn_subtitles expects -- so a subtitle burned in AFTER visuals
    are applied repositions lines away from the image (spec section 9).
    Best-effort: returns [] on anything short of a clean lookup, since a
    missing reel row must never block subtitle burning."""
    if not is_supabase_configured():
        return []
    try:
        reel = await supabase_get_reel_by_job_clip(job_id, clip_index, user_id=user_id)
        if not reel:
            return []
        rows = await supabase_list_reel_visuals(str(reel["id"]))
    except Exception:
        return []
    return [
        {
            "position": row.get("position"),
            "start": float(row.get("start_time") or 0),
            "end": float(row.get("start_time") or 0) + float(row.get("duration") or 0),
        }
        for row in rows
    ]


def _burn_subtitles_for_request(
    req: SubtitleRequest, input_path: str, srt_path: str, output_path: str,
    visual_windows: Optional[List[Dict[str, Any]]] = None,
) -> None:
    style_options = SubtitleStyleOptions(
        font_name=req.font_name,
        font_color=req.font_color,
        border_color=req.border_color,
        border_width=req.border_width,
        bg_color=req.bg_color,
        bg_opacity=req.bg_opacity,
        text_shadow_color=req.text_shadow_color,
        shadow_blur=req.shadow_blur,
        shadow_offset_x=req.shadow_offset_x,
        shadow_offset_y=req.shadow_offset_y,
        bold=req.bold,
        italic=req.italic,
        text_case=req.text_case,
        highlight_color=req.highlight_color,
    )
    burn_subtitles(
        input_path,
        srt_path,
        output_path,
        alignment=req.position,
        fontsize=req.font_size,
        style_options=style_options,
        visual_windows=visual_windows,
    )


def _upload_subtitled_video(output_path: str, user_id: str, job_id: str, output_filename: str, local_subtitle_url: str):
    persisted_subtitle_url = local_subtitle_url
    subtitle_s3_key = ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if bucket and os.path.exists(output_path):
        subtitle_s3_key = f"captions/{user_id}/{job_id}/{output_filename}"
        if upload_file_to_s3(output_path, bucket, subtitle_s3_key):
            persisted_subtitle_url = _caption_media_url_from_s3_key(subtitle_s3_key) or local_subtitle_url
    return persisted_subtitle_url, subtitle_s3_key


async def _sync_reel_after_subtitle_edit(job_id: str, clip_index: int, user_id: str, persisted_subtitle_url: str, subtitle_s3_key: str) -> None:
    if not (is_supabase_configured() and persisted_subtitle_url):
        return
    try:
        await supabase_update_reel_media_by_job_clip(
            job_id=job_id,
            clip_index=clip_index,
            reel_url=persisted_subtitle_url,
            reel_s3_key=subtitle_s3_key or None,
            user_id=user_id,
        )
    except Exception as e:
        print(f"⚠️ Failed to sync reel URL after subtitle edit: {e}")


def _update_clip_after_subtitle_edit(job: Optional[Dict[str, Any]], clip_index: int, clips: List[Any], data: Dict[str, Any], metadata_path: str, persisted_subtitle_url: str) -> None:
    # Update InMemory Jobs (only if the job is still alive in memory)
    if job and clip_index < len(job.get('result', {}).get('clips', [])):
        job['result']['clips'][clip_index]['video_url'] = persisted_subtitle_url

    # Update Metadata on Disk (Persistence)
    try:
        if clip_index < len(clips):
            clips[clip_index]['video_url'] = persisted_subtitle_url
            # Update the main data structure
            data['shorts'] = clips

            # Write back
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with subtitled video for clip {clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")
        # Non-critical, but good for persistence


def _build_subtitle_style_config(req: SubtitleRequest) -> Dict[str, Any]:
    return {
        "position": req.position,
        "position_x": req.position_x,
        "position_y": req.position_y,
        "font_size": req.font_size,
        "font_name": req.font_name,
        "font_color": req.font_color,
        "highlight_color": req.highlight_color,
        "border_color": req.border_color,
        "border_width": req.border_width,
        "text_shadow_color": req.text_shadow_color,
        "shadow_blur": req.shadow_blur,
        "shadow_offset_x": req.shadow_offset_x,
        "shadow_offset_y": req.shadow_offset_y,
        "bg_color": req.bg_color,
        "bg_opacity": req.bg_opacity,
        "text_case": req.text_case,
        "bold": req.bold,
        "italic": req.italic,
        "words_per_line": req.words_per_line,
        "animation": req.animation,
    }


async def _debit_subtitle_credits_and_persist_version(
    user_id: str, req: SubtitleRequest, subtitle_required_credits: float, version_number: int,
    source_video_url_for_history: str, persisted_subtitle_url: str, style_config: Dict[str, Any],
) -> None:
    subtitle_style_billing_details = _build_billing_details(
        "sous_titre",
        None,
        actual_credit=subtitle_required_credits,
        actual_storage_gb=0.0,
        extra={"stage": "style_edit"},
    )

    if is_supabase_configured() and subtitle_required_credits > 0:
        await supabase_deduct_user_credits(user_id, subtitle_required_credits)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=subtitle_required_credits,
            storage=0.0,
            operation="output",
            operation_type="sous_titre",
            operation_id=f"{req.job_id}:subtitle:{req.clip_index}",
        )

    if is_supabase_configured():
        try:
            await supabase_insert_style_edit_version(
                {
                    "user_id": user_id,
                    "job_id": req.job_id,
                    "clip_index": int(req.clip_index),
                    "version_number": int(version_number),
                    "operation_type": "subtitle_style",
                    "source_video_url": source_video_url_for_history,
                    "output_video_url": persisted_subtitle_url,
                    "style_config": style_config,
                    "billing_details": subtitle_style_billing_details,
                }
            )
        except Exception as e:
            print(f"⚠️ Failed to persist style edit version: {e}")


@app.post("/api/subtitle", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def add_subtitles(req: SubtitleRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    await _require_job_ownership(req.job_id, user_id)
    subtitle_required_credits = 0.0
    await _assert_user_has_required_credits(user_id, subtitle_required_credits)

    # Reload job data from disk just in case metadata was updated.
    # The in-memory job may be gone on the Reels page; metadata on disk is enough.
    job = jobs.get(req.job_id)

    # We need to access metadata.json to get the transcript
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    transcript = data.get('transcript')
    if not transcript:
        raise HTTPException(status_code=400, detail="Transcript not found in metadata. Please process a new video.")

    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[req.clip_index]
    source_video_url_for_history = await _resolve_subtitle_source_video_history(req.job_id, req.clip_index, user_id, clip_data)

    input_path, filename = await _resolve_burn_source_input_path(req, output_dir, clip_data, metadata_path, user_id)

    # Define outputs
    srt_filename = f"subs_{req.clip_index}_{int(time.time())}.srt"
    srt_path = os.path.join(output_dir, srt_filename)

    # Output video
    # We create a new file "subtitled_..."
    output_filename = f"subtitled_{filename}"
    output_path = os.path.join(output_dir, output_filename)

    try:
        words_per_line = max(2, min(8, int(req.words_per_line or 4)))
        success = await _generate_subtitle_srt(input_path, filename, transcript, clip_data, srt_path, words_per_line, animation=req.animation)
        if not success:
            raise HTTPException(status_code=400, detail="No words found for this clip range.")

        visual_windows = await _reel_visual_windows_for_job_clip(req.job_id, req.clip_index, user_id)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _burn_subtitles_for_request, req, input_path, srt_path, output_path, visual_windows)

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Subtitle Error", e)

    local_subtitle_url = f"/videos/{req.job_id}/{output_filename}"
    persisted_subtitle_url, subtitle_s3_key = _upload_subtitled_video(output_path, user_id, req.job_id, output_filename, local_subtitle_url)

    await _sync_reel_after_subtitle_edit(req.job_id, req.clip_index, user_id, persisted_subtitle_url, subtitle_s3_key)

    _update_clip_after_subtitle_edit(job, req.clip_index, clips, data, metadata_path, persisted_subtitle_url)

    style_config = _build_subtitle_style_config(req)

    version_number = _append_style_version_to_metadata(
        data,
        req.clip_index,
        source_video_url_for_history,
        persisted_subtitle_url,
        style_config,
    )
    _persist_metadata_json(metadata_path, data)

    await _debit_subtitle_credits_and_persist_version(
        user_id, req, subtitle_required_credits, version_number, source_video_url_for_history, persisted_subtitle_url, style_config,
    )

    return {
        "success": True,
        "new_video_url": persisted_subtitle_url,
        "version": int(version_number),
    }

class HookRequest(BaseModel):
    job_id: str
    clip_index: int
    text: str
    input_filename: Optional[str] = None
    input_url: Optional[str] = None
    position: Optional[str] = "top" # top, center, bottom
    size: Optional[str] = "M" # S, M, L


def _reset_clip_metadata_to_original(
    metadata_path: str, data: Dict[str, Any], clip_index: int, default_video_url: Optional[str] = None,
) -> str:
    clips = data.get("shorts") or []
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip = clips[clip_index]
    history = data.get("style_history") or {}
    history_key = str(int(clip_index))
    entries = history.get(history_key) if isinstance(history, dict) else None

    # Prefer the clip's recorded default style version (the auto-captioned
    # video, properly sized/fonted -- see _record_default_style_version)
    # over the bare, uncaptioned original: "reset" should bring back the
    # default look, not strip captions off entirely.
    reset_video_url = str(default_video_url or "").strip()
    if not reset_video_url:
        reset_video_url = str(clip.get("original_video_url") or "").strip()
    if not reset_video_url and isinstance(entries, list) and entries:
        reset_video_url = str(entries[0].get("source_video_url") or "").strip()
    if not reset_video_url:
        raise HTTPException(status_code=400, detail="No original video reference found for reset")

    clip["video_url"] = reset_video_url
    clips[clip_index] = clip
    data["shorts"] = clips
    if isinstance(history, dict):
        history.pop(history_key, None)
        data["style_history"] = history
    _persist_metadata_json(metadata_path, data)

    return reset_video_url


async def _find_default_style_version(job_id: str, clip_index: int, user_id: str) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    try:
        versions = await supabase_list_style_edit_versions(job_id, int(clip_index), user_id)
    except Exception as e:
        print(f"⚠️ Failed to load default style version: {e}")
        return None
    return next(
        (v for v in versions if int(v.get("version_number") or 0) == _DEFAULT_STYLE_VERSION_NUMBER), None,
    )


@app.post("/api/reels/{job_id}/{clip_index}/captions/reset", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def reset_caption_style_history(
    job_id: str,
    clip_index: int,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    default_version = await _find_default_style_version(job_id, clip_index, user_id)
    default_video_url = str((default_version or {}).get("output_video_url") or "")
    reset_video_url = _reset_clip_metadata_to_original(metadata_path, data, clip_index, default_video_url=default_video_url)

    if is_supabase_configured():
        try:
            # Clears every manual restyle, then restores the default version
            # (rather than leaving the clip with no history row at all) so a
            # later reset or a captions-editor "history" view still finds it.
            await supabase_delete_style_edit_versions(job_id, int(clip_index), user_id)
            if default_version:
                await supabase_insert_style_edit_version({
                    "user_id": user_id,
                    "job_id": job_id,
                    "clip_index": int(clip_index),
                    "version_number": _DEFAULT_STYLE_VERSION_NUMBER,
                    "operation_type": default_version.get("operation_type") or "subtitle_style",
                    "source_video_url": default_version.get("source_video_url") or "",
                    "output_video_url": default_version.get("output_video_url") or "",
                    "style_config": default_version.get("style_config") or dict(_DEFAULT_AUTO_CAPTION_STYLE_KWARGS),
                    "billing_details": default_version.get("billing_details") or {},
                })
        except Exception as e:
            print(f"⚠️ Failed to reset style history versions: {e}")

    return {
        "success": True,
        "job_id": job_id,
        "clip_index": clip_index,
        "video_url": reset_video_url,
        "history_cleared": True,
    }


@app.get("/api/reels/{job_id}/{clip_index}/style-history", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def get_caption_style_history_debug(
    job_id: str,
    clip_index: int,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get("shorts") or []
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip = clips[clip_index] if isinstance(clips[clip_index], dict) else {}
    history = data.get("style_history") if isinstance(data.get("style_history"), dict) else {}
    metadata_versions = history.get(str(int(clip_index))) if isinstance(history.get(str(int(clip_index))), list) else []

    db_versions: List[Dict[str, Any]] = []
    if is_supabase_configured():
        try:
            db_versions = await supabase_list_style_edit_versions(job_id, int(clip_index), user_id)
        except Exception as e:
            print(f"⚠️ Failed to load style history versions from Supabase: {e}")

    def _looks_amazon_url(value: Any) -> bool:
        text = str(value or "").strip().lower()
        return text.startswith(_HTTPS_SCHEME_PREFIX) and "amazonaws.com" in text

    metadata_last = metadata_versions[-1] if metadata_versions else {}
    db_last = db_versions[-1] if db_versions else {}

    return {
        "job_id": job_id,
        "clip_index": int(clip_index),
        "metadata_path": metadata_path,
        "clip_video_url": clip.get("video_url"),
        "clip_original_video_url": clip.get("original_video_url"),
        "metadata_versions_count": len(metadata_versions),
        "db_versions_count": len(db_versions),
        "metadata_versions": metadata_versions,
        "db_versions": db_versions,
        "checks": {
            "clip_video_url_is_amazon": _looks_amazon_url(clip.get("video_url")),
            "metadata_latest_source_is_amazon": _looks_amazon_url(metadata_last.get("source_video_url")),
            "metadata_latest_output_is_amazon": _looks_amazon_url(metadata_last.get("output_video_url")),
            "db_latest_source_is_amazon": _looks_amazon_url(db_last.get("source_video_url")),
            "db_latest_output_is_amazon": _looks_amazon_url(db_last.get("output_video_url")),
        },
    }


# --- Custom reels: manual start/end selection on the source video, for
# when the AI-generated clips aren't satisfying (see _preserve_source_video_
# for_manual_clipping) ---

_CUSTOM_REEL_CLIP_MIN_SECONDS = float(os.environ.get("CUSTOM_REEL_CLIP_MIN_SECONDS", "3"))
_CUSTOM_REEL_CLIP_MAX_SECONDS = float(os.environ.get("CUSTOM_REEL_CLIP_MAX_SECONDS", "120"))


class CustomReelClipRequest(BaseModel):
    start_ms: int
    end_ms: int
    title: Optional[str] = None
    # Explicit override for callers reaching this endpoint long after the
    # generation job finished (see the project-level "Creation manuelle"
    # scene view), when the in-memory `jobs[job_id]` entry this endpoint
    # would otherwise read project_id from has long since expired/been
    # dropped by a worker restart -- validated against the caller's own
    # projects below, never trusted blindly.
    project_id: Optional[str] = None


@app.get("/api/reels/{job_id}/source", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def get_reel_job_source_endpoint(job_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Tells the frontend whether the full source video is still available
    for this reel job (see _preserve_source_video_for_manual_clipping), so
    it can offer the "Reel personnalise" manual-trim option, and if so, the
    URL/duration to load into the trimmer. Never 404s -- a job whose source
    was never preserved or has since been swept by the retention cleanup
    just reports itself unavailable, which the UI treats as "hide the
    button" rather than an error."""
    await _require_job_ownership(job_id, user_id)
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    source_path = _ensure_preserved_source_video_available(job_id, user_id, output_dir)
    if not source_path:
        return {"available": False}
    return {
        "available": True,
        "source_url": f"/videos/{job_id}/{os.path.basename(source_path)}",
        "duration_seconds": _probe_local_video_duration_seconds(source_path),
    }


async def _cut_and_verticalize_custom_clip(
    source_path: str, start_seconds: float, end_seconds: float, output_dir: str, clip_filename: str,
) -> str:
    """Cuts [start_seconds, end_seconds] out of source_path and reframes it
    to vertical the exact same way the AI pipeline does for each of its own
    clips (main.py's process_video_to_vertical, scene-aware face tracking),
    so a manually-picked reel looks consistent with an AI-generated one
    instead of a plain center-crop. Both steps are blocking/CPU-bound
    subprocess work, run off the event loop."""
    from main import process_video_to_vertical, EXPORT_VIDEO_CRF, EXPORT_VIDEO_PRESET, EXPORT_AUDIO_BITRATE

    temp_path = os.path.join(output_dir, f"temp_{clip_filename}")
    final_path = os.path.join(output_dir, clip_filename)

    def _cut() -> None:
        cmd = [
            "ffmpeg", "-y",
            "-ss", str(start_seconds), "-to", str(end_seconds),
            "-i", source_path,
            "-c:v", "libx264", "-crf", EXPORT_VIDEO_CRF, "-preset", EXPORT_VIDEO_PRESET,
            "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", EXPORT_AUDIO_BITRATE,
            temp_path,
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS)
        if result.returncode != 0 or not os.path.exists(temp_path):
            raise RuntimeError(f"FFmpeg cut failed: {result.stderr.decode(errors='replace')[-1000:]}")

    def _verticalize() -> None:
        try:
            success = process_video_to_vertical(temp_path, final_path)
        finally:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
        if not success or not os.path.exists(final_path):
            raise RuntimeError("Vertical reframing failed")

    await asyncio.to_thread(_cut)
    await asyncio.to_thread(_verticalize)
    return final_path


def _validate_custom_reel_clip_timing(req: "CustomReelClipRequest") -> tuple:
    """Validates the user-picked start/end range for a custom reel clip.
    Returns (duration_seconds, start_seconds, end_seconds)."""
    start_ms = max(0, int(req.start_ms))
    end_ms = int(req.end_ms)
    if end_ms <= start_ms:
        raise HTTPException(status_code=400, detail="end_ms doit etre superieur a start_ms")
    duration_seconds = (end_ms - start_ms) / 1000.0
    if duration_seconds < _CUSTOM_REEL_CLIP_MIN_SECONDS or duration_seconds > _CUSTOM_REEL_CLIP_MAX_SECONDS:
        raise HTTPException(
            status_code=400,
            detail=f"La duree du clip doit etre comprise entre {_CUSTOM_REEL_CLIP_MIN_SECONDS:.0f} et {_CUSTOM_REEL_CLIP_MAX_SECONDS:.0f} secondes",
        )
    return duration_seconds, start_ms / 1000.0, end_ms / 1000.0


def _resolve_custom_reel_clip_source_path(job_id: str, user_id: str, output_dir: str, end_seconds: float) -> str:
    """Resolves the preserved source video for a custom-clip cut and checks
    that the requested range actually fits within it."""
    source_path = _ensure_preserved_source_video_available(job_id, user_id, output_dir)
    if not source_path:
        raise HTTPException(status_code=404, detail="La video source n'est plus disponible pour ce job")
    source_duration = _probe_local_video_duration_seconds(source_path)
    if source_duration > 0 and end_seconds > source_duration + 0.5:
        raise HTTPException(status_code=400, detail="La plage selectionnee depasse la duree de la video source")
    return source_path


async def _resolve_custom_reel_project_id(job_data: Dict[str, Any], req: "CustomReelClipRequest", user_id: str) -> Optional[str]:
    """Defaults to the job's own project, but lets the request target a
    different (still user-owned) project instead."""
    if not req.project_id:
        return job_data.get("project_id")
    if not await supabase_get_project(req.project_id, user_id):
        raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)
    return req.project_id


async def _finalize_custom_reel_clip_creation(
    job_id: str, user_id: str, project_id: Optional[str],
    reel_row: Dict[str, Any], saved_row: Dict[str, Any],
    clip_entry: Dict[str, Any], next_index: int,
) -> None:
    """Debits the actual cost, bumps the project's output count, and mirrors
    the new clip into the job's in-memory result -- the bookkeeping
    _persist_reels_for_job already does for AI-generated clips, done here
    explicitly since a custom clip is a single reel saved outside that
    batch path."""
    billing_details = reel_row.get("billing_details") or {}
    total_credits = float(billing_details.get("final_credits") or 0.0) + float((billing_details.get("auto_caption") or {}).get("credit_cost") or 0.0)
    storage_gb = _bytes_to_gb(float(reel_row.get("reel_size_bytes") or 0))
    retention = await _finalize_retention_billing_batch(job_id, user_id, [
        {
            "content_kind": CONTENT_KIND_REEL,
            "content_id": saved_row.get("id"),
            "media_type": MEDIA_TYPE_PRODUCED,
            "size_bytes": reel_row.get("reel_size_bytes"),
            "s3_bucket": os.environ.get("AWS_S3_BUCKET", "my-clips-bucket"),
            "s3_key": reel_row.get("reel_s3_key"),
        }
    ])
    total_credits = round(total_credits + retention["retention_storage_credit_cost"], 2)
    debit_ok = await reel_job_manager.debit_credits_for_job(
        job_id=job_id, user_id=user_id, credits=total_credits, storage_delta=-storage_gb,
        operation_type="generation_reel", reserved_credits=0.0,
    )
    if not debit_ok:
        logger.warning("Failed to debit credits for custom reel clip (job %s, user %s)", job_id, user_id)

    if project_id:
        try:
            await supabase_increment_project_output_count(project_id, user_id=user_id)
        except Exception as e:
            logger.warning("Failed to increment project output count: %s", e)

    if job_id not in jobs or not isinstance(jobs[job_id].get("result"), dict):
        return
    jobs[job_id]["result"].setdefault("clips", []).append({
        **clip_entry,
        "video_url": saved_row.get("reel_playback_url"),
        "reel_clip_index": next_index - 1,
        "reel_job_id": job_id,
    })
    jobs[job_id]["result"].setdefault("reels", []).append(saved_row)


@app.post("/api/reels/{job_id}/custom-clip", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}, 503: {"description": "Service Unavailable"}})
async def create_custom_reel_clip_endpoint(
    job_id: str, req: CustomReelClipRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Cuts a reel clip from the exact start/end range the user picked by
    hand on the source video, instead of one of the AI-selected scenes --
    the "Reel personnalise" option for when the AI generation isn't
    satisfying. Produces and bills the clip the same way an AI-generated
    one is (same _build_reel_row_for_clip path: S3 upload, thumbnail,
    default captions, credits/storage debit)."""
    await _require_job_ownership(job_id, user_id)
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    duration_seconds, start_seconds, end_seconds = _validate_custom_reel_clip_timing(req)

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    source_path = _resolve_custom_reel_clip_source_path(job_id, user_id, output_dir, end_seconds)

    metadata_path, data = await _get_or_build_job_metadata(job_id, 0, user_id=user_id)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    # Rough upfront sanity check (fixed bitrate assumption -- we don't have
    # a real file yet) before spending CPU on the cut/vertical-reframe
    # pipeline. The precise charge (base cost + any auto-caption add-on) is
    # computed and debited below from the actual produced file.
    job_data = jobs.get(job_id) or {}
    uses_youtube_source = _job_uses_remote_source(job_data) if job_data else False
    precheck_credits = _estimate_reel_required_credits(
        duration_seconds=duration_seconds, size_bytes=duration_seconds * 1_000_000, uses_youtube_source=uses_youtube_source,
    )
    await _assert_user_has_required_credits(user_id, precheck_credits)

    clips = data.get("shorts") or []
    next_index = len(clips) + 1
    base_name = os.path.basename(metadata_path).replace(_METADATA_JSON_SUFFIX, "")
    clip_filename = f"{base_name}_clip_{next_index}.mp4"

    try:
        await _cut_and_verticalize_custom_clip(source_path, start_seconds, end_seconds, output_dir, clip_filename)
    except Exception as exc:
        raise _generic_error("Custom reel clip cut failed", exc, detail="Impossible de generer ce reel personnalise.")

    title = (req.title or "").strip() or f"Reel personnalise {next_index}"
    clip_entry = {
        "title": title,
        "start": start_seconds,
        "end": end_seconds,
        "duration": duration_seconds,
        "video_title_for_youtube_short": title,
        "video_description_for_instagram": "",
        "video_description_for_tiktok": "",
        "is_custom": True,
    }
    clips.append(clip_entry)
    data["shorts"] = clips
    _persist_metadata_json(metadata_path, data)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise HTTPException(status_code=503, detail="AWS_S3_BUCKET is required for reel persistence")

    project_id = await _resolve_custom_reel_project_id(job_data, req, user_id)
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    reel_row = await _build_reel_row_for_clip(
        job_id, user_id, output_dir, bucket, base_name, clip_entry, next_index, now_iso,
        uses_youtube_source, project_id, data.get("transcript"),
    )
    if not reel_row:
        raise HTTPException(status_code=500, detail="Echec de la creation du reel personnalise")

    saved_rows = await supabase_insert_reels([reel_row])
    if not saved_rows:
        raise HTTPException(status_code=500, detail="Echec de l'enregistrement du reel personnalise")
    saved_row = _normalize_reel_row(saved_rows[0])

    await _finalize_custom_reel_clip_creation(job_id, user_id, project_id, reel_row, saved_row, clip_entry, next_index)

    return saved_row


def _flatten_transcript_words(transcript: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Flattens a job's whole-source transcript (metadata.json's `transcript`
    field) into one word list at absolute times, in milliseconds -- unlike
    _extract_clip_captions_from_transcript, this is not windowed/offset to a
    single AI-picked clip's range, since the "Creation manuelle" scene view
    needs every word across the full source video."""
    words: List[Dict[str, Any]] = []
    if not isinstance(transcript, dict):
        return words
    for segment in (transcript.get("segments") or []):
        for word_info in (segment.get("words") or []):
            text = str(word_info.get("word") or "").strip()
            if not text:
                continue
            try:
                start_ms = int(float(word_info.get("start", 0) or 0) * 1000)
                end_ms = int(float(word_info.get("end", 0) or 0) * 1000)
            except (TypeError, ValueError):
                continue
            words.append({"text": text, "startMs": start_ms, "endMs": end_ms})
    return words


def _generate_scene_waveform_png(source_path: str, output_dir: str) -> Optional[str]:
    """Renders a static waveform image for the manual-creation scene view
    via ffmpeg's showwavespic (a single frame -- fast even for a several-
    minute source), so the frontend doesn't have to download and decode the
    whole video client-side with the Web Audio API just to draw one.
    Cached alongside the source video; regenerated only if missing or
    older than it. Returns None (no waveform, not a hard failure) if the
    source has no audio track or ffmpeg otherwise fails."""
    waveform_path = os.path.join(output_dir, "waveform.png")
    try:
        if os.path.exists(waveform_path) and os.path.getmtime(waveform_path) >= os.path.getmtime(source_path):
            return waveform_path
        cmd = [
            "ffmpeg", "-y", "-i", source_path,
            "-filter_complex", "[0:a]aformat=channel_layouts=mono,showwavespic=s=1600x200:colors=0x10B981",
            "-frames:v", "1", waveform_path,
        ]
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS)
        if result.returncode != 0 or not os.path.exists(waveform_path):
            logger.warning("Waveform generation failed for %s: %s", source_path, result.stderr.decode(errors="replace")[-500:])
            return None
        return waveform_path
    except Exception as exc:
        logger.warning("Waveform generation errored for %s: %s", source_path, exc)
        return None


@app.get("/api/projects/{project_id}/manual-scene", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_manual_scene(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Backs the project-level "Creation manuelle" view: the full source
    video (or its S3 backup, re-downloaded on demand -- see
    _ensure_preserved_source_video_available), a waveform image, and the
    whole-source word-level transcript, so a user can hand-pick a range to
    cut into a reel straight from the project page instead of only right
    after a specific generation job completes (see /api/reels/{job_id}/
    source, the job-scoped equivalent this builds on)."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

    project = await supabase_get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

    job_row = await supabase_get_latest_job_record_by_project(project_id, user_id)
    job_id = str(job_row.get("id") or "") if job_row else ""
    if not job_id:
        return {"available": False, "job_id": None}

    output_dir = os.path.join(OUTPUT_DIR, job_id)
    source_path = _ensure_preserved_source_video_available(job_id, user_id, output_dir)
    if not source_path:
        return {"available": False, "job_id": job_id}

    waveform_path = _generate_scene_waveform_png(source_path, output_dir)
    _, data = await _get_or_build_job_metadata(job_id, 0, user_id=user_id)
    words = _flatten_transcript_words((data or {}).get("transcript"))

    return {
        "available": True,
        "job_id": job_id,
        "source_url": f"/videos/{job_id}/{os.path.basename(source_path)}",
        "duration_seconds": _probe_local_video_duration_seconds(source_path),
        "waveform_url": f"/videos/{job_id}/{os.path.basename(waveform_path)}" if waveform_path else None,
        "words": words,
    }


def _run_add_hook(input_path: str, text: str, output_path: str, position: str, font_scale: float) -> None:
    add_hook_to_video(input_path, text, output_path, position=position, font_scale=font_scale)


def _persist_new_video_url_to_clip(job: Optional[Dict[str, Any]], clip_index: int, clips: List[Any], data: Dict[str, Any], metadata_path: str, new_video_url: str, log_label: str) -> None:
    # Update InMemory Jobs
    if job and clip_index < len(job.get('result', {}).get('clips', [])):
        job['result']['clips'][clip_index]['video_url'] = new_video_url

    # Update Metadata on Disk
    try:
        if clip_index < len(clips):
            clips[clip_index]['video_url'] = new_video_url
            data['shorts'] = clips
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with {log_label} video for clip {clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")


@app.post("/api/hook", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def add_hook(req: HookRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    await _require_job_ownership(req.job_id, user_id)

    job = jobs.get(req.job_id)
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get('shorts', [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[req.clip_index]
    input_path, filename = _resolve_add_subtitles_input_path(req, output_dir, clip_data, metadata_path)

    input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
    input_duration_seconds = _probe_local_video_duration_seconds(input_path)
    hook_required_credits = _estimate_reel_required_credits(
        duration_seconds=input_duration_seconds,
        size_bytes=input_size_bytes,
        uses_youtube_source=False,
        uses_openai=False,
        uses_assembly=False,
        uses_gemini=False,
    )
    await _assert_user_has_required_credits(user_id, hook_required_credits)

    # Output video
    output_filename = f"hook_{filename}"
    output_path = os.path.join(output_dir, output_filename)

    # Map Size to Scale
    size_map = {"S": 0.8, "M": 1.0, "L": 1.3}
    font_scale = size_map.get(req.size, 1.0)

    try:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _run_add_hook, input_path, req.text, output_path, req.position, font_scale)
    except Exception as e:
        raise _generic_error("Hook Error", e)

    new_video_url = f"/videos/{req.job_id}/{output_filename}"
    _persist_new_video_url_to_clip(job, req.clip_index, clips, data, metadata_path, new_video_url, "hook")

    if is_supabase_configured() and hook_required_credits > 0:
        await supabase_deduct_user_credits(user_id, hook_required_credits)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=hook_required_credits,
            storage=0.0,
            operation="output",
            operation_type="hook",
            operation_id=f"{req.job_id}:hook:{req.clip_index}",
        )

    return {
        "success": True,
        "new_video_url": new_video_url,
    }


# ---------------------------------------------------------------------------
# Reel visuals (manual image split-screen overlays -- see visuals.py).
# Entirely manual: no AI is ever involved in choosing the image, its
# position, or its timing -- the user controls every one of those.
# ---------------------------------------------------------------------------

_REEL_VISUAL_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
_REEL_VISUAL_ALLOWED_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
REEL_VISUAL_MAX_IMAGE_BYTES = int(os.environ.get("REEL_VISUAL_MAX_IMAGE_BYTES", str(8 * 1024 * 1024)))
_REEL_VISUAL_POSITIONS = {"TOP", "BOTTOM"}


def _validate_reel_visual_image_upload(file: Optional[UploadFile]) -> None:
    if not file:
        raise HTTPException(status_code=400, detail="Missing image file")
    content_type = str(file.content_type or "").lower()
    if content_type and content_type not in _REEL_VISUAL_ALLOWED_CONTENT_TYPES:
        raise _coded_error(400, "invalid_image_format", "Only JPG, PNG and WebP images are supported")


async def _save_reel_visual_image_upload(file: UploadFile, local_path: str) -> None:
    async with aiofiles.open(local_path, "wb") as buffer:
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > REEL_VISUAL_MAX_IMAGE_BYTES:
                raise _coded_error(
                    400, "image_too_large",
                    f"Image is too large (max {REEL_VISUAL_MAX_IMAGE_BYTES // (1024 * 1024)} MB)",
                )
            await buffer.write(chunk)


def _validate_reel_visual_timing(
    start_time: float, duration: float, reel_duration_seconds: float,
    existing_visuals: List[Dict[str, Any]], exclude_visual_id: Optional[str] = None,
) -> float:
    """Validates one visual's timing against the spec's hard rules
    (section 10: startTime >= 0, duration > 0, startTime+duration <=
    reel duration, no overlap with another visual on the same reel) and
    returns its end_time. Raises a _coded_error on any violation.

    Overlap check is a plain pairwise compare against `existing_visuals`
    (not the sort+merge idiom used elsewhere in this codebase for an
    unsorted incoming batch -- see _merge_overlapping_bad_take_candidates)
    because `existing_visuals` is already known non-overlapping (enforced
    by this same function at creation time), so only the ONE new/edited
    interval needs checking against that already-valid set."""
    if start_time < 0:
        raise _coded_error(400, "invalid_visual_timing", "startTime must be >= 0")
    if duration <= 0:
        raise _coded_error(400, "invalid_visual_timing", "duration must be > 0")
    end_time = start_time + duration
    if reel_duration_seconds and end_time > reel_duration_seconds + 0.01:
        raise _coded_error(
            400, "visual_exceeds_reel_duration",
            f"This visual would run until {end_time:.1f}s, past the reel's {reel_duration_seconds:.1f}s duration",
        )

    for existing in existing_visuals:
        if exclude_visual_id and str(existing.get("id")) == str(exclude_visual_id):
            continue
        other_start = float(existing.get("start_time") or 0)
        other_end = other_start + float(existing.get("duration") or 0)
        if start_time < other_end and other_start < end_time:
            raise _coded_error(
                409, "visual_overlap",
                "This visual's time window overlaps an existing visual -- visuals can never overlap",
            )

    return end_time


async def _resolve_reel_for_visuals(job_id: str, clip_index: int, user_id: str) -> Dict[str, Any]:
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    reel = await supabase_get_reel_by_job_clip(job_id, clip_index, user_id=user_id)
    if not reel:
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)
    return reel


def _reel_visual_image_url(image_s3_key: str) -> str:
    if not image_s3_key:
        return ""
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        return ""
    return generate_presigned_url(bucket, image_s3_key, expiration=7200) or ""


def _normalize_reel_visual_row(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        **row,
        "image_url": _reel_visual_image_url(row.get("image_s3_key") or ""),
        "end_time": float(row.get("start_time") or 0) + float(row.get("duration") or 0),
    }


@app.get("/api/reels/{job_id}/{clip_index}/visuals", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def list_reel_visuals_endpoint(job_id: str, clip_index: int, user_id: Annotated[str, Depends(get_user_id_header)]):
    reel = await _resolve_reel_for_visuals(job_id, clip_index, user_id)
    rows = await supabase_list_reel_visuals(str(reel["id"]))
    return {"items": [_normalize_reel_visual_row(row) for row in rows]}


@app.post("/api/reels/{job_id}/{clip_index}/visuals", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}, 503: {"description": "Service Unavailable"}})
async def create_reel_visual(
    job_id: str, clip_index: int, user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[UploadFile, File()],
    position: Annotated[str, Form()],
    start_time: Annotated[float, Form()],
    duration: Annotated[float, Form()],
):
    """Adds one manual visual to a reel: uploads the image to S3 (the
    same mechanism every other upload in this app uses, see
    s3_uploader.py) and creates its reel_visuals row. Entirely manual --
    the caller supplies the image, position and timing; nothing here
    infers any of it."""
    reel = await _resolve_reel_for_visuals(job_id, clip_index, user_id)

    position = str(position or "").upper()
    if position not in _REEL_VISUAL_POSITIONS:
        raise _coded_error(400, "invalid_visual_position", "position must be TOP or BOTTOM")

    _validate_reel_visual_image_upload(file)

    reel_duration = float(reel.get("reel_duration") or 0)
    existing = await supabase_list_reel_visuals(str(reel["id"]))
    _validate_reel_visual_timing(float(start_time), float(duration), reel_duration, existing)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise HTTPException(status_code=503, detail="AWS_S3_BUCKET is required for image uploads")

    safe_name = _sanitize_input_filename(file.filename) or "visual.jpg"
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in _REEL_VISUAL_ALLOWED_EXTENSIONS:
        ext = ".jpg"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    visual_id = uuid.uuid4().hex
    local_path = os.path.join(UPLOAD_DIR, f"reel_visual_{visual_id}{ext}")
    try:
        await _save_reel_visual_image_upload(file, local_path)
        s3_key = f"reels/{user_id}/{job_id}/visual_{clip_index}_{visual_id}{ext}"
        if not upload_file_to_s3(local_path, bucket, s3_key):
            raise HTTPException(status_code=503, detail="Failed to upload image")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass

    row = await supabase_insert_reel_visual(
        str(reel["id"]), user_id, position, float(start_time), float(duration), s3_key,
    )
    return _normalize_reel_visual_row(row)


class UpdateReelVisualRequest(BaseModel):
    position: Optional[str] = None
    start_time: Optional[float] = None
    duration: Optional[float] = None


@app.patch("/api/reels/{job_id}/{clip_index}/visuals/{visual_id}", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}, 503: {"description": "Service Unavailable"}})
async def update_reel_visual_endpoint(
    job_id: str, clip_index: int, visual_id: str, payload: UpdateReelVisualRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Updates a visual's position and/or timing -- never its image (swap
    the image by deleting and re-adding the visual instead)."""
    reel = await _resolve_reel_for_visuals(job_id, clip_index, user_id)
    existing_visual = await supabase_get_reel_visual(visual_id, user_id)
    if not existing_visual or str(existing_visual.get("reel_id")) != str(reel["id"]):
        raise _coded_error(404, "visual_not_found", "Visual not found")

    updates: Dict[str, Any] = {}
    if payload.position is not None:
        position = str(payload.position).upper()
        if position not in _REEL_VISUAL_POSITIONS:
            raise _coded_error(400, "invalid_visual_position", "position must be TOP or BOTTOM")
        updates["position"] = position

    if payload.start_time is not None or payload.duration is not None:
        start_time = payload.start_time if payload.start_time is not None else float(existing_visual.get("start_time") or 0)
        duration = payload.duration if payload.duration is not None else float(existing_visual.get("duration") or 0)
        reel_duration = float(reel.get("reel_duration") or 0)
        other_visuals = await supabase_list_reel_visuals(str(reel["id"]))
        _validate_reel_visual_timing(float(start_time), float(duration), reel_duration, other_visuals, exclude_visual_id=visual_id)
        updates["start_time"] = float(start_time)
        updates["duration"] = float(duration)

    if not updates:
        return _normalize_reel_visual_row(existing_visual)

    row = await supabase_update_reel_visual(visual_id, user_id, updates)
    if not row:
        raise _coded_error(404, "visual_not_found", "Visual not found")
    return _normalize_reel_visual_row(row)


@app.delete("/api/reels/{job_id}/{clip_index}/visuals/{visual_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def delete_reel_visual_endpoint(
    job_id: str, clip_index: int, visual_id: str, user_id: Annotated[str, Depends(get_user_id_header)],
):
    reel = await _resolve_reel_for_visuals(job_id, clip_index, user_id)
    existing_visual = await supabase_get_reel_visual(visual_id, user_id)
    if not existing_visual or str(existing_visual.get("reel_id")) != str(reel["id"]):
        raise _coded_error(404, "visual_not_found", "Visual not found")

    deleted = await supabase_delete_reel_visual(visual_id, user_id)
    if not deleted:
        raise _coded_error(404, "visual_not_found", "Visual not found")

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    image_s3_key = deleted.get("image_s3_key")
    if bucket and image_s3_key:
        try:
            delete_s3_object(bucket, image_s3_key)
        except Exception:
            logger.warning("Failed to delete reel visual image %s from S3", image_s3_key, exc_info=True)

    return {"deleted": True}


class ApplyReelVisualsRequest(BaseModel):
    input_filename: Optional[str] = None
    input_url: Optional[str] = None


@app.post("/api/reels/{job_id}/{clip_index}/visuals/apply", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def apply_reel_visuals(
    job_id: str, clip_index: int, payload: ApplyReelVisualsRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Burns every currently-configured visual for this clip into its
    current video (see visuals.py) -- the explicit, deliberate "Générer"
    step after the user has finished previewing their visuals, matching
    how /api/hook and /api/subtitle already work (configure in a modal,
    then burn via a separate call)."""
    await _require_job_ownership(job_id, user_id)
    reel = await _resolve_reel_for_visuals(job_id, clip_index, user_id)

    rows = await supabase_list_reel_visuals(str(reel["id"]))
    if not rows:
        raise _coded_error(400, "no_visuals_configured", "No visuals are configured for this reel")

    job = jobs.get(job_id)
    output_dir = os.path.join(OUTPUT_DIR, job_id)
    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index, payload.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get('shorts', [])
    if clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)
    clip_data = clips[clip_index]

    transcript = data.get('transcript') if isinstance(data.get('transcript'), dict) else None
    subtitle_style_config, subtitle_style_source = await _resolve_active_subtitle_style_for_clip(
        job_id,
        clip_index,
        user_id,
        clip_data,
    )
    has_subtitle_material = bool(transcript) or bool(_saved_subtitle_captions_from_clip_data(clip_data))

    # _resolve_burn_source_input_path already resolves the clean, pre-caption
    # source when one exists, so visuals render onto clean pixels first and
    # subtitles can be re-burned afterward with the persisted style.
    resolve_req = types.SimpleNamespace(
        job_id=job_id, clip_index=clip_index,
        input_filename=payload.input_filename, input_url=payload.input_url,
    )
    input_path, filename = await _resolve_burn_source_input_path(resolve_req, output_dir, clip_data, metadata_path, user_id)

    input_size_bytes = float(os.path.getsize(input_path) if os.path.exists(input_path) else 0)
    input_duration_seconds = _probe_local_video_duration_seconds(input_path)
    visuals_required_credits = _estimate_reel_required_credits(
        duration_seconds=input_duration_seconds,
        size_bytes=input_size_bytes,
        uses_youtube_source=False,
        uses_openai=False,
        uses_assembly=False,
        uses_gemini=False,
    )
    await _assert_user_has_required_credits(user_id, visuals_required_credits)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    local_image_paths: List[str] = []
    visuals_stage_path = ""
    srt_path = ""
    subtitle_reapplied = False
    try:
        burn_visuals = []
        for row in rows:
            image_s3_key = row.get("image_s3_key")
            ext = os.path.splitext(image_s3_key or "")[1] or ".jpg"
            local_image_path = os.path.join(output_dir, f"visual_src_{row['id']}{ext}")
            if not bucket or not image_s3_key or not download_s3_object(bucket, image_s3_key, local_image_path):
                raise HTTPException(status_code=503, detail="Failed to download a visual's image")
            local_image_paths.append(local_image_path)
            burn_visuals.append({
                "image_path": local_image_path,
                "position": row.get("position"),
                "start_time": float(row.get("start_time") or 0),
                "duration": float(row.get("duration") or 0),
            })

        visuals_stage_filename = f"visuals_stage_{filename}"
        visuals_stage_path = os.path.join(output_dir, visuals_stage_filename)
        output_filename = f"visuals_{filename}"
        output_path = os.path.join(output_dir, output_filename)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, apply_visuals_to_video, input_path, burn_visuals, visuals_stage_path)

        if has_subtitle_material:
            subtitle_req = _build_subtitle_request_from_style(job_id, clip_index, subtitle_style_config)
            words_per_line = max(2, min(8, int(subtitle_req.words_per_line or 4)))
            srt_path = os.path.join(output_dir, f"visuals_subs_{clip_index}_{int(time.time())}.srt")
            has_srt = await _generate_subtitle_srt_from_clip_context(
                visuals_stage_path,
                filename,
                transcript,
                clip_data,
                srt_path,
                words_per_line,
                animation=subtitle_req.animation,
            )
            if has_srt:
                visual_windows = await _reel_visual_windows_for_job_clip(job_id, clip_index, user_id)
                await loop.run_in_executor(
                    None,
                    _burn_subtitles_for_request,
                    subtitle_req,
                    visuals_stage_path,
                    srt_path,
                    output_path,
                    visual_windows,
                )
                subtitle_reapplied = True

        if not subtitle_reapplied:
            shutil.move(visuals_stage_path, output_path)
    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Visuals Error", e)
    finally:
        for path in local_image_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        try:
            if srt_path and os.path.exists(srt_path):
                os.remove(srt_path)
        except Exception:
            pass
        try:
            if visuals_stage_path and os.path.exists(visuals_stage_path):
                os.remove(visuals_stage_path)
        except Exception:
            pass

    if subtitle_reapplied:
        logger.info(
            "Visuals apply re-burned subtitles for job %s clip %s using style source %s",
            job_id,
            clip_index,
            subtitle_style_source,
        )

    existing_reel_base_url = str(reel.get("reel_base_url") or "").strip()
    existing_reel_base_s3_key = str(reel.get("reel_base_s3_key") or "").strip()
    if is_supabase_configured() and not existing_reel_base_url:
        current_reel_s3_key = str(reel.get("reel_s3_key") or "").strip()
        baseline_video_url = _reel_media_url_from_s3_key(current_reel_s3_key) or str(reel.get("reel_url") or "").strip()
        if baseline_video_url:
            try:
                await supabase_update_reel_base_media_by_job_clip(
                    job_id=job_id,
                    clip_index=clip_index,
                    reel_base_url=baseline_video_url,
                    reel_base_s3_key=current_reel_s3_key or None,
                    user_id=user_id,
                )
                existing_reel_base_url = baseline_video_url
                existing_reel_base_s3_key = current_reel_s3_key
            except Exception as e:
                print(f"⚠️ Failed to persist visuals reset baseline: {e}")

    new_video_url = f"/videos/{job_id}/{output_filename}"
    persisted_video_url = new_video_url
    visuals_s3_key = ""
    if bucket and os.path.exists(output_path):
        visuals_s3_key = f"reels/{user_id}/{job_id}/{output_filename}"
        if upload_file_to_s3(output_path, bucket, visuals_s3_key):
            persisted_video_url = _reel_media_url_from_s3_key(visuals_s3_key) or new_video_url

    _persist_new_video_url_to_clip(job, clip_index, clips, data, metadata_path, persisted_video_url, "visuals")

    if is_supabase_configured() and persisted_video_url:
        try:
            await supabase_update_reel_media_by_job_clip(
                job_id=job_id,
                clip_index=clip_index,
                reel_url=persisted_video_url,
                reel_s3_key=visuals_s3_key or None,
                user_id=user_id,
            )
            # Keep baseline sticky once initialized so reset consistently
            # restores the pre-visuals media.
            if existing_reel_base_url:
                await supabase_update_reel_base_media_by_job_clip(
                    job_id=job_id,
                    clip_index=clip_index,
                    reel_base_url=existing_reel_base_url,
                    reel_base_s3_key=existing_reel_base_s3_key or None,
                    user_id=user_id,
                )
        except Exception as e:
            print(f"⚠️ Failed to sync reel URL after visuals apply: {e}")

    if is_supabase_configured() and visuals_required_credits > 0:
        await supabase_deduct_user_credits(user_id, visuals_required_credits)
        await supabase_insert_user_data_history(
            user_id=user_id,
            credit=visuals_required_credits,
            storage=0.0,
            operation="output",
            operation_type="reel_visuals",
            operation_id=f"{job_id}:visuals:{clip_index}",
        )

    return {
        "success": True,
        "new_video_url": persisted_video_url,
    }


@app.post("/api/reels/{job_id}/{clip_index}/visuals/reset", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def reset_reel_visuals(
    job_id: str,
    clip_index: int,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    await _require_job_ownership(job_id, user_id)
    reel = await _resolve_reel_for_visuals(job_id, clip_index, user_id)

    metadata_path, data = await _get_or_build_job_metadata(job_id, clip_index)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)

    clips = data.get("shorts") or []
    if clip_index < 0 or clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[clip_index] if isinstance(clips[clip_index], dict) else {}
    base_s3_key = str(reel.get("reel_base_s3_key") or "").strip()
    reset_video_url = _reel_media_url_from_s3_key(base_s3_key) or str(reel.get("reel_base_url") or "").strip()
    if not reset_video_url:
        reset_video_url = str(clip_data.get("original_video_url") or "").strip()
    if not reset_video_url:
        raise _coded_error(400, "missing_visuals_reset_source", "No baseline video reference found for visuals reset")

    rows = await supabase_list_reel_visuals(str(reel["id"]))
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    deleted_count = 0
    for row in rows:
        visual_id = str(row.get("id") or "")
        if visual_id:
            deleted = await supabase_delete_reel_visual(visual_id, user_id)
            if deleted:
                deleted_count += 1

        image_s3_key = str(row.get("image_s3_key") or "").strip()
        if bucket and image_s3_key:
            try:
                delete_s3_object(bucket, image_s3_key)
            except Exception:
                logger.warning("Failed to delete reel visual image %s from S3", image_s3_key, exc_info=True)

    job = jobs.get(job_id)
    _persist_new_video_url_to_clip(job, clip_index, clips, data, metadata_path, reset_video_url, "visuals reset")

    if is_supabase_configured():
        try:
            await supabase_update_reel_media_by_job_clip(
                job_id=job_id,
                clip_index=clip_index,
                reel_url=reset_video_url,
                reel_s3_key=base_s3_key or None,
                user_id=user_id,
            )
        except Exception as e:
            print(f"⚠️ Failed to sync reel URL after visuals reset: {e}")

    return {
        "success": True,
        "new_video_url": reset_video_url,
        "deleted_visuals": deleted_count,
    }


# --- Translation (subtitles-only, keep original voice) ---

class TranslateRequest(BaseModel):
    job_id: str
    clip_index: int
    target_language: str
    source_language: Optional[str] = None
    input_filename: Optional[str] = None
    input_url: Optional[str] = None

    # Subtitle style options (same spirit as SubtitleRequest)
    position: str = "bottom"  # top, middle, bottom
    font_size: int = 16
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0


def _srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h = ms // 3600000
    ms %= 3600000
    m = ms // 60000
    ms %= 60000
    s = ms // 1000
    ms %= 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _normalize_lang(lang: Optional[str]) -> str:
    if not lang:
        return ""
    l = lang.strip().lower()
    mapping = {
        "en-us": "en",
        "en-gb": "en",
        "fr-fr": "fr",
        "es-es": "es",
        "pt-br": "pt",
    }
    return mapping.get(l, l)


def _segment_to_text(segment: Dict) -> str:
    words = segment.get("words") or []
    if words:
        parts = []
        for w in words:
            t = (w.get("word") or "").strip()
            if t:
                parts.append(t)
        txt = " ".join(parts).strip()
        if txt:
            return txt
    return (segment.get("text") or "").strip()


def _load_clip_segments_from_metadata(data: Dict[str, Any], clip_index: int) -> List[Dict[str, Any]]:
    transcript = data.get("transcript") or {}
    all_segments = transcript.get("segments") or []
    shorts = data.get("shorts") or []
    if not shorts:
        return []

    if clip_index < 0 or clip_index >= len(shorts):
        clip_index = min(max(clip_index, 0), len(shorts) - 1)

    clip = shorts[clip_index]
    clip_start = float(clip.get("start", 0))
    clip_end = float(clip.get("end", 0))

    selected: List[Dict[str, Any]] = []
    for seg in all_segments:
        s = float(seg.get("start", 0))
        e = float(seg.get("end", 0))
        if e > clip_start and s < clip_end:
            rel_start = max(0.0, s - clip_start)
            rel_end = max(rel_start, e - clip_start)
            text = _segment_to_text(seg)
            if text:
                selected.append({"start": rel_start, "end": rel_end, "text": text})
    return selected


def _translate_text_openai(text: str, source_lang: str, target_lang: str) -> tuple[str, Dict[str, Any]]:
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_TRANSLATE_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    if not api_key or api_key == "your_openai_key":
        raise RuntimeError("OPENAI_API_KEY missing or placeholder")

    client = OpenAI(api_key=api_key)
    system = (
        "You are a professional subtitle translator. "
        "Translate naturally, keep meaning, keep short subtitle style, "
        "do not add commentary, return only translated text."
    )
    user = (
        f"Source language: {source_lang or 'auto'}\n"
        f"Target language: {target_lang}\n"
        f"Text:\n{text}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
        max_tokens=600
    )
    out = (resp.choices[0].message.content or "").strip()
    if not out:
        raise RuntimeError("OpenAI returned empty translation")
    usage = getattr(resp, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
    total_tokens = int(getattr(usage, "total_tokens", prompt_tokens + completion_tokens) or 0)
    usage_payload = {
        "provider": "openai",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": estimate_llm_usage_cost_usd("openai", prompt_tokens, completion_tokens),
    }
    return out, usage_payload


def _translate_text_gemini(text: str, source_lang: str, target_lang: str) -> tuple[str, Dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY")
    model = os.environ.get("GEMINI_TRANSLATE_MODEL", os.environ.get("GEMINI_MODEL"))
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing")

    from google import genai
    client = genai.Client(api_key=api_key)

    prompt = (
        "You are a professional subtitle translator.\n"
        "Translate naturally, keep meaning, keep short subtitle style,\n"
        "do not add commentary, return only translated text.\n\n"
        f"Source language: {source_lang or 'auto'}\n"
        f"Target language: {target_lang}\n"
        "Text:\n"
        f"{text}"
    )

    resp = client.models.generate_content(
        model=model,
        contents=prompt
    )
    out = (resp.text or "").strip()
    if not out:
        raise RuntimeError("Gemini returned empty translation")

    return out, _parse_gemini_translation_usage(resp)


def _read_gemini_usage_field(source: Any, *names: str) -> int:
    for name in names:
        if isinstance(source, dict) and name in source:
            return int(source.get(name) or 0)
        if source is not None and hasattr(source, name):
            return int(getattr(source, name) or 0)
    return 0


def _parse_gemini_translation_usage(resp: Any) -> Dict[str, Any]:
    usage_meta = getattr(resp, "usage_metadata", None)
    if usage_meta is None and hasattr(resp, "usageMetadata"):
        usage_meta = getattr(resp, "usageMetadata")

    prompt_tokens = _read_gemini_usage_field(usage_meta, "prompt_token_count", "promptTokenCount")
    completion_tokens = _read_gemini_usage_field(usage_meta, "candidates_token_count", "candidatesTokenCount")
    total_tokens = _read_gemini_usage_field(usage_meta, "total_token_count", "totalTokenCount")
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "provider": "gemini",
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": estimate_llm_usage_cost_usd("gemini", prompt_tokens, completion_tokens),
    }


def _get_translation_cache(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    cache = data.get("translation_cache")
    if not isinstance(cache, dict):
        cache = {}
        data["translation_cache"] = cache
    return cache


def _build_translation_cache_key(source_lang: str, target_lang: str, text: str) -> str:
    normalized_source = _normalize_lang(source_lang) or "auto"
    normalized_target = _normalize_lang(target_lang)
    normalized_text = " ".join((text or "").split())
    digest = hashlib.sha256(
        f"{normalized_source}:{normalized_target}:{normalized_text}".encode("utf-8")
    ).hexdigest()
    return f"{normalized_source}:{normalized_target}:{digest}"


def _persist_metadata_json(metadata_path: str, data: Dict[str, Any]) -> None:
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


def _translate_segments_with_fallback(segments: List[Dict], source_lang: str, target_lang: str) -> List[Dict]:
    translated = []
    for seg in segments:
        src_text = seg["text"]
        try:
            # Primary: OpenAI
            dst, usage = _translate_text_openai(src_text, source_lang, target_lang)
            provider = "openai"
        except Exception as e_openai:
            print(f"⚠️ OpenAI translation failed, fallback Gemini. Reason: {e_openai}")
            # Fallback: Gemini
            dst, usage = _translate_text_gemini(src_text, source_lang, target_lang)
            provider = "gemini"

        translated.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": dst,
            "provider": provider,
            "usage": usage,
        })
    return translated


def _cached_translated_segment(seg: Dict[str, Any], cached_entry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "start": seg["start"],
        "end": seg["end"],
        "text": cached_entry["text"],
        "provider": cached_entry.get("provider") or "cache",
        "usage": cached_entry.get("usage") or {},
    }


def _store_translation_in_cache(cache_store: Dict[str, Any], cache_key: str, translated_segment: Dict[str, Any], source_lang: str, target_lang: str) -> None:
    cache_store[cache_key] = {
        "text": translated_segment["text"],
        "provider": translated_segment.get("provider") or "unknown",
        "usage": translated_segment.get("usage") or {},
        "source_language": _normalize_lang(source_lang) or "auto",
        "target_language": _normalize_lang(target_lang),
        "cached_at": int(time.time()),
    }


def _accumulate_translation_usage(usage_totals: Dict[str, Dict[str, Any]], translated_segment: Dict[str, Any]) -> None:
    usage = translated_segment.get("usage") or {}
    provider = (usage.get("provider") or translated_segment.get("provider") or "").lower()
    bucket = usage_totals.get(provider)
    if bucket is None:
        return
    bucket["prompt_tokens"] += int(usage.get("prompt_tokens") or 0)
    bucket["completion_tokens"] += int(usage.get("completion_tokens") or 0)
    bucket["total_tokens"] += int(usage.get("total_tokens") or 0)
    bucket["cost_usd"] = round(float(bucket["cost_usd"]) + float(usage.get("cost_usd") or 0.0), 6)


def _translate_segments_with_cache(
    segments: List[Dict],
    source_lang: str,
    target_lang: str,
    translation_cache: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[List[Dict], Dict[str, Any]]:
    translated: List[Dict] = []
    cache_hits = 0
    cache_misses = 0
    usage_totals = {
        "openai": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
        "gemini": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0},
    }
    cache_store = translation_cache if isinstance(translation_cache, dict) else None

    for seg in segments:
        src_text = seg.get("text") or ""
        cache_key = _build_translation_cache_key(source_lang, target_lang, src_text)
        cached_entry = cache_store.get(cache_key) if cache_store is not None else None

        if isinstance(cached_entry, dict) and (cached_entry.get("text") or "").strip():
            translated.append(_cached_translated_segment(seg, cached_entry))
            cache_hits += 1
            continue

        translated_segment = _translate_segments_with_fallback([seg], source_lang, target_lang)[0]
        translated.append(translated_segment)
        cache_misses += 1

        if cache_store is not None:
            _store_translation_in_cache(cache_store, cache_key, translated_segment, source_lang, target_lang)

        _accumulate_translation_usage(usage_totals, translated_segment)

    total_cost_usd = round(
        float(usage_totals["openai"]["cost_usd"]) + float(usage_totals["gemini"]["cost_usd"]),
        6,
    )
    return translated, {
        "hits": cache_hits,
        "misses": cache_misses,
        "usage": usage_totals,
        "cost_usd": total_cost_usd,
    }


def _caption_words_from_segment(seg: Dict[str, Any]) -> List[Dict[str, Any]]:
    text = (seg.get("text") or "").strip()
    if not text:
        return []

    words = [token for token in text.split() if token]
    if not words:
        return []

    start_ms = int(round(float(seg.get("start", 0)) * 1000))
    end_ms = int(round(float(seg.get("end", 0)) * 1000))
    if end_ms <= start_ms:
        end_ms = start_ms + 200

    total_duration_ms = max(1, end_ms - start_ms)
    step_ms = max(1, total_duration_ms // len(words))

    captions = []
    for index, word in enumerate(words):
        word_start_ms = start_ms + (index * step_ms)
        if index == len(words) - 1:
            word_end_ms = end_ms
        else:
            word_end_ms = min(end_ms, start_ms + ((index + 1) * step_ms))
        if word_end_ms <= word_start_ms:
            word_end_ms = word_start_ms + 1

        captions.append({
            "text": word,
            "startMs": word_start_ms,
            "endMs": word_end_ms,
        })
    return captions


def _translated_segments_to_caption_words(segments: List[Dict]) -> List[Dict]:
    captions: List[Dict] = []
    for seg in segments:
        captions.extend(_caption_words_from_segment(seg))
    return captions


def _write_translated_srt(segments: List[Dict], srt_path: str) -> bool:
    if not segments:
        return False
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, seg in enumerate(segments, start=1):
            f.write(f"{i}\n")
            f.write(f"{_srt_timestamp(seg['start'])} --> {_srt_timestamp(seg['end'])}\n")
            f.write(f"{seg['text'].strip()}\n\n")
    return True


@app.get("/api/translate/languages")
def get_languages():
    """
    Return supported languages.
    Kept for frontend compatibility.
    """
    # You can expand this list if needed.
    return {
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "fr", "name": "French"},
            {"code": "es", "name": "Spanish"},
            {"code": "de", "name": "German"},
            {"code": "it", "name": "Italian"},
            {"code": "pt", "name": "Portuguese"},
            {"code": "nl", "name": "Dutch"},
            {"code": "ar", "name": "Arabic"},
            {"code": "hi", "name": "Hindi"},
            {"code": "ja", "name": "Japanese"},
            {"code": "ko", "name": "Korean"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ru", "name": "Russian"},
            {"code": "tr", "name": "Turkish"},
            {"code": "id", "name": "Indonesian"},
        ]
    }


class CaptionStyleThemeRequest(BaseModel):
    name: str
    style: Dict[str, Any]


@app.get("/api/caption-style-default", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def get_default_caption_style_endpoint(user_id: Annotated[str, Depends(get_user_id_header)]):
    return {"style": await _get_user_default_caption_style(user_id)}


@app.put("/api/caption-style-default", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def set_default_caption_style_endpoint(
    payload: DefaultCaptionStyleRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    existing = await supabase_list_style_edit_versions(
        _DEFAULT_STYLE_SENTINEL_JOB_ID, _DEFAULT_STYLE_SENTINEL_CLIP_INDEX, user_id,
    )
    next_version = max((int(v.get("version_number") or 0) for v in existing), default=0) + 1
    style_config = payload.model_dump()

    await supabase_insert_style_edit_version({
        "user_id": user_id,
        "job_id": _DEFAULT_STYLE_SENTINEL_JOB_ID,
        "clip_index": _DEFAULT_STYLE_SENTINEL_CLIP_INDEX,
        "version_number": next_version,
        "operation_type": "subtitle_style_default",
        "source_video_url": "",
        "output_video_url": "",
        "style_config": style_config,
    })
    return {"success": True, "style": style_config}


@app.get("/api/caption-style-themes", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def list_caption_style_themes_endpoint(user_id: Annotated[str, Depends(get_user_id_header)]):
    """The user's own saved subtitle style presets ("themes") for the
    CaptionsModal theme picker. Built-in themes are static frontend data
    (dashboard/src/lib/captionThemes.js) and never appear here -- this only
    ever returns what the user explicitly saved."""
    if not is_supabase_configured():
        return {"themes": []}
    rows = await supabase_list_caption_style_themes(user_id)
    return {"themes": [{"id": row.get("id"), "name": row.get("name"), "style": row.get("style") or {}} for row in rows]}


@app.post("/api/caption-style-themes", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def save_caption_style_theme_endpoint(req: CaptionStyleThemeRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Saves a custom theme under `name` -- overwrites the caller's own
    theme of the same name if one already exists (see
    upsert_caption_style_theme), so re-saving under a name already used is
    how a saved theme gets updated."""
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Theme name is required")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    saved = await supabase_upsert_caption_style_theme(user_id, name, req.style or {})
    if not saved:
        raise HTTPException(status_code=503, detail="Failed to save theme")
    return {"id": saved.get("id"), "name": saved.get("name"), "style": saved.get("style") or {}}


@app.delete("/api/caption-style-themes/{theme_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def delete_caption_style_theme_endpoint(theme_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    deleted = await supabase_delete_caption_style_theme(theme_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Theme not found")
    return {"success": True}


async def _resolve_translation_cache_and_owner(user_id: str, job_id: str, clip_index: int, translation_cache: Dict[str, Any]):
    transcription_row = None
    if is_supabase_configured():
        transcription_row = await _load_cached_transcription(user_id, job_id, clip_index)
        db_cache = (transcription_row or {}).get("translations_cache") or {}
        if isinstance(db_cache, dict) and db_cache:
            translation_cache = db_cache
    return user_id, transcription_row, translation_cache


async def _persist_translation_usage_billing(
    owner_user_id: str, req: "TranslateRequest", normalized_clip_index: int, transcription_row: Optional[Dict[str, Any]],
    translation_cache: Dict[str, Any], source_lang: str, target_lang: str, transcript: Dict[str, Any], cache_stats: Dict[str, Any],
    operation: str = "translation",
) -> None:
    if not (owner_user_id and is_supabase_configured()):
        return
    usage_payload = {
        "operation": operation,
        "source_language": source_lang or "auto",
        "target_language": target_lang,
        "cache": {"hits": cache_stats.get("hits", 0), "misses": cache_stats.get("misses", 0)},
        "usage": cache_stats.get("usage", {}),
        "total_cost_usd": cache_stats.get("cost_usd", 0.0),
    }
    if not transcription_row:
        await _persist_transcription_cache(
            user_id=owner_user_id,
            job_id=req.job_id,
            clip_index=normalized_clip_index,
            source_type="translation",
            source_value=req.input_url or req.input_filename or req.job_id,
            transcript=transcript,
            billing_details=usage_payload,
        )
    await supabase_update_transcription_translations_cache(
        req.job_id,
        normalized_clip_index,
        owner_user_id,
        translation_cache,
        billing_details=usage_payload,
    )


@app.post("/api/translate/captions", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}})
async def translate_captions(req: TranslateRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Translate reel transcript into Remotion-friendly timed word captions."""
    await _require_job_ownership(req.job_id, user_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)
    translation_cache = _get_translation_cache(data)

    clips = data.get("shorts", [])
    if not clips:
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    normalized_clip_index = req.clip_index
    if normalized_clip_index < 0 or normalized_clip_index >= len(clips):
        normalized_clip_index = min(max(normalized_clip_index, 0), len(clips) - 1)

    clip_data = clips[normalized_clip_index]
    source_lang = _normalize_lang(req.source_language) or _normalize_lang((data.get("transcript") or {}).get("language"))
    target_lang = _normalize_lang(req.target_language)
    if not target_lang:
        raise HTTPException(status_code=400, detail="target_language is required")

    source_segments = _load_clip_segments_from_metadata(data, normalized_clip_index)
    if not source_segments:
        raise HTTPException(status_code=400, detail="No transcript segments found for this clip range")

    owner_user_id, transcription_row, translation_cache = await _resolve_translation_cache_and_owner(
        user_id, req.job_id, normalized_clip_index, translation_cache,
    )

    loop = asyncio.get_event_loop()
    translated_segments, cache_stats = await loop.run_in_executor(
        None, _translate_segments_with_cache, source_segments, source_lang, target_lang, translation_cache,
    )

    if cache_stats["misses"] > 0:
        try:
            _persist_metadata_json(metadata_path, data)
        except Exception as e:
            print(f"⚠️ Failed to persist translation cache: {e}")

    await _persist_translation_usage_billing(
        owner_user_id, req, normalized_clip_index, transcription_row, translation_cache,
        source_lang, target_lang, data.get("transcript") or {}, cache_stats,
    )

    captions = _translated_segments_to_caption_words(translated_segments)
    if not captions:
        raise HTTPException(status_code=500, detail="Failed to build translated captions")

    providers = sorted({seg.get("provider", "unknown") for seg in translated_segments if seg.get("provider")})

    return {
        "success": True,
        "mode": "remotion_subtitles",
        "captions": captions,
        "durationSec": max(0, float(clip_data.get("end", 0)) - float(clip_data.get("start", 0))),
        "source_language": source_lang or "auto",
        "target_language": target_lang,
        "providers": providers,
        "cache": cache_stats,
        "billing": {
            "usage": cache_stats.get("usage", {}),
            "total_cost_usd": cache_stats.get("cost_usd", 0.0),
        },
    }


def _burn_translated_subtitles(req: "TranslateRequest", input_path: str, srt_path: str, output_path: str) -> None:
    style_options = SubtitleStyleOptions(
        font_name=req.font_name,
        font_color=req.font_color,
        border_color=req.border_color,
        border_width=req.border_width,
        bg_color=req.bg_color,
        bg_opacity=req.bg_opacity,
    )
    burn_subtitles(
        input_path,
        srt_path,
        output_path,
        alignment=req.position,
        fontsize=req.font_size,
        style_options=style_options,
    )


async def _translate_and_burn_clip_subtitles(
    req: "TranslateRequest", source_segments: List[Dict[str, Any]], source_lang: str, target_lang: str,
    translation_cache: Dict[str, Any], input_path: str, filename: str, output_dir: str,
):
    # 1) Translate text segments (OpenAI primary, Gemini fallback)
    loop = asyncio.get_event_loop()
    translated_segments, cache_stats = await loop.run_in_executor(
        None, _translate_segments_with_cache, source_segments, source_lang, target_lang, translation_cache,
    )

    # 2) Write translated SRT
    base, ext = os.path.splitext(filename)
    srt_filename = f"translated_subs_{target_lang}_{req.clip_index}_{int(time.time())}.srt"
    srt_path = os.path.join(output_dir, srt_filename)

    if not _write_translated_srt(translated_segments, srt_path):
        raise HTTPException(status_code=500, detail="Failed to write translated SRT")

    # 3) Burn subtitles on original video (audio unchanged)
    output_filename = f"translated_{target_lang}_{base}{ext}"
    output_path = os.path.join(output_dir, output_filename)

    await loop.run_in_executor(None, _burn_translated_subtitles, req, input_path, srt_path, output_path)

    return cache_stats, srt_filename, output_filename


def _update_clip_after_translation(job: Optional[Dict[str, Any]], job_id: str, clip_index: int, clips: List[Any], data: Dict[str, Any], metadata_path: str, output_filename: str, target_lang: str) -> None:
    # Update in-memory job result if the job is still alive in memory.
    if job and clip_index < len(job.get("result", {}).get("clips", [])):
        job["result"]["clips"][clip_index]["video_url"] = f"/videos/{job_id}/{output_filename}"

    # Persist metadata
    try:
        if clip_index < len(clips):
            clips[clip_index]["video_url"] = f"/videos/{job_id}/{output_filename}"
            clips[clip_index]["translated_subtitles_language"] = target_lang
            data["shorts"] = clips
            _persist_metadata_json(metadata_path, data)
            print(f"✅ Metadata updated with translated-subtitle video for clip {clip_index}")
    except Exception as e:
        print(f"⚠️ Failed to update metadata.json: {e}")


@app.post("/api/translate", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}})
async def translate_clip(req: TranslateRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    """
    Translate subtitles only (OpenAI first, Gemini fallback),
    keep original voice/audio track unchanged.
    """
    await _require_job_ownership(req.job_id, user_id)
    job = jobs.get(req.job_id)
    output_dir = os.path.join(OUTPUT_DIR, req.job_id)
    metadata_path, data = await _get_or_build_job_metadata(req.job_id, req.clip_index, req.input_url)
    if not metadata_path or not data:
        raise HTTPException(status_code=404, detail=_METADATA_NOT_FOUND)
    translation_cache = _get_translation_cache(data)
    owner_user_id, transcription_row, translation_cache = await _resolve_translation_cache_and_owner(
        user_id, req.job_id, req.clip_index, translation_cache,
    )

    clips = data.get("shorts", [])
    if req.clip_index >= len(clips):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)

    clip_data = clips[req.clip_index]
    input_path, filename = await _resolve_burn_source_input_path(req, output_dir, clip_data, metadata_path, user_id)

    # Load clip transcript segments from existing metadata transcript (no re-transcription)
    source_lang = _normalize_lang(req.source_language) or _normalize_lang((data.get("transcript") or {}).get("language"))
    target_lang = _normalize_lang(req.target_language)
    if not target_lang:
        raise HTTPException(status_code=400, detail="target_language is required")

    source_segments = _load_clip_segments_from_metadata(data, req.clip_index)
    if not source_segments:
        raise HTTPException(status_code=400, detail="No transcript segments found for this clip range")

    try:
        cache_stats, srt_filename, output_filename = await _translate_and_burn_clip_subtitles(
            req, source_segments, source_lang, target_lang, translation_cache, input_path, filename, output_dir,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Translation(subtitles-only) Error", e)

    _update_clip_after_translation(job, req.job_id, req.clip_index, clips, data, metadata_path, output_filename, target_lang)

    await _persist_translation_usage_billing(
        owner_user_id, req, req.clip_index, transcription_row, translation_cache,
        source_lang, target_lang, data.get("transcript") or {}, cache_stats,
        operation="translation_subtitles_only",
    )

    return {
        "success": True,
        "mode": "subtitles_only",
        "new_video_url": f"/videos/{req.job_id}/{output_filename}",
        "srt_url": f"/videos/{req.job_id}/{srt_filename}",
        "source_language": source_lang or "auto",
        "target_language": target_lang,
        "cache": cache_stats,
        "billing": {
            "usage": cache_stats.get("usage", {}),
            "total_cost_usd": cache_stats.get("cost_usd", 0.0),
        },
    }


class SocialPostRequest(BaseModel):
    job_id: str
    clip_index: int
    user_id: Optional[str] = None
    account_ids: List[str] = []
    # Optional overrides if frontend wants to edit them
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None # ISO-8601 string
    timezone: Optional[str] = "UTC"

import httpx


def _resolve_request_user_id(explicit_user_id: Optional[str], user_id: str) -> str:  # NOSONAR(S1172)
    # Security: `explicit_user_id` comes from a client-supplied request body
    # field and must never override the verified identity resolved from the
    # authenticated session (`user_id`, from get_user_id_header). Otherwise a
    # client could act on behalf of an arbitrary victim simply by setting
    # `user_id` in the JSON body. Kept as a named (but deliberately unused)
    # parameter -- rather than dropped or renamed to `_` -- so every call
    # site visibly shows the untrusted value being discarded, instead of
    # silently omitting it in a way a future edit could "helpfully" start
    # trusting again.
    resolved = (user_id or "").strip()
    if not resolved:
        raise HTTPException(status_code=400, detail="Missing authenticated user id")
    return resolved


_SHARE_PLATFORMS = {"tiktok", "instagram", "youtube", "facebook", "linkedin"}
_SOCIAL_POST_PLATFORMS = {"facebook", "linkedin"}


async def _resolve_accounts_for_publish(
    user_id: str, account_ids: Optional[List[str]], allowed_platforms: set,
) -> List[Dict[str, Any]]:
    """Resolves each requested account id to its connected-account row,
    ownership-checked -- lets a single publish/share/schedule request target
    several specific connected accounts at once (e.g. two Facebook Pages),
    each billed and tracked as its own publish_jobs row. Shared by every
    publish surface (composer, reel/caption/film-summary share, anonymous
    stories); only the allowed platform set differs per surface."""
    ids: List[str] = []
    seen = set()
    for raw in account_ids or []:
        account_id = str(raw or "").strip()
        if account_id and account_id not in seen:
            seen.add(account_id)
            ids.append(account_id)
    if not ids:
        raise HTTPException(status_code=400, detail="account_ids must include at least one connected account")

    accounts: List[Dict[str, Any]] = []
    for account_id in ids:
        account = await _get_social_account_by_id(user_id, account_id)
        if not account:
            raise HTTPException(status_code=404, detail=f"Connected account not found: {account_id}")
        if account.get("platform") not in allowed_platforms:
            raise HTTPException(status_code=400, detail=f"Unsupported platform for account {account_id}")
        accounts.append(account)
    return accounts


def _resolve_local_video_path(job_id: str, video_ref: str, clip_index: int) -> Optional[str]:
    ref = (video_ref or "").split("?")[0]
    filename = ref.split("/")[-1] or f"{job_id}_{clip_index + 1}.mp4"
    candidate = os.path.join(OUTPUT_DIR, job_id, filename)
    if not os.path.exists(candidate):
        return None
    return candidate


async def _resolve_clip_for_social_post(job_id: str, clip_index: int) -> Dict[str, Any]:
    """Resolve clip data from live in-memory job first, then persisted metadata fallback."""
    job = jobs.get(job_id)
    if job and "result" in job and isinstance(job["result"].get("clips"), list):
        try:
            return job["result"]["clips"][clip_index]
        except Exception:
            pass

    _, metadata = await _get_or_build_job_metadata(job_id, clip_index)
    shorts = (metadata or {}).get("shorts") or []
    if not isinstance(shorts, list) or clip_index < 0 or clip_index >= len(shorts):
        raise HTTPException(status_code=404, detail=_JOB_NOT_FOUND)
    clip = shorts[clip_index]
    if not isinstance(clip, dict):
        raise HTTPException(status_code=404, detail=_CLIP_NOT_FOUND)
    return clip


def _resolve_public_video_url(video_ref: str, request: Request, job_id: str) -> str:
    ref = (video_ref or "").strip()
    # Sonar false positive (S5332): this detects whether `ref` is already an
    # absolute URL (any scheme) so it isn't re-prefixed with a base URL --
    # it never issues a request with a hardcoded http:// endpoint.
    if ref.startswith((_HTTPS_SCHEME_PREFIX, "http://")):  # NOSONAR
        return ref
    if not ref:
        raise HTTPException(status_code=404, detail="Video URL not found for this clip")

    if ref.startswith("/"):
        base_url = SOCIAL_BASE_URL or str(request.base_url).rstrip("/")
        return f"{base_url}{ref}"

    # Fallback to built-in static route pattern.
    base_url = SOCIAL_BASE_URL or str(request.base_url).rstrip("/")
    return f"{base_url}/videos/{job_id}/{ref}"

async def _schedule_reel_social_post_job(
    user_id: str, account: Dict[str, Any], req: "SocialPostRequest", publish_priority: int,
    scheduled_for, final_title: str, final_description: str, public_video_url: str,
) -> Dict[str, Any]:
    publish_job_id = await _insert_publish_job(
        user_id=user_id,
        platform=str(account.get("platform") or ""),
        external_id="scheduled",
        status="queued",
        priority=publish_priority,
        scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
        timezone=req.timezone or "UTC",
        payload={
            "source_type": "job_clip",
            "account_id": account.get("id"),
            "source_id": req.job_id,
            "clip_index": req.clip_index,
            "title": final_title,
            "description": final_description,
            "media_url": public_video_url,
        },
    )
    return {
        "success": True,
        "scheduled": True,
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        "publish_job_id": publish_job_id,
    }


async def _publish_reel_social_post_now(
    user_id: str, account: Dict[str, Any], publish_priority: int,
    final_title: str, final_description: str, public_video_url: str, local_video_path: str,
) -> Dict[str, Any]:
    platform_name = str(account.get("platform") or "")
    base_payload = {
        "source_type": "job_clip",
        "account_id": account.get("id"),
        "title": final_title,
        "description": final_description,
        "media_url": public_video_url,
    }
    try:
        # Sonar false positive (S5332): validates the URL is absolute (any
        # scheme) before submitting it to the platform API -- not a
        # hardcoded http:// request of our own.
        if platform_name in {"tiktok", "instagram"} and not public_video_url.startswith((_HTTPS_SCHEME_PREFIX, "http://")):  # NOSONAR
            raise HTTPException(status_code=400, detail=f"{platform_name} requires a public video URL")

        publish_payload = PublishRequest(
            user_id=user_id,
            title=final_title,
            description=final_description,
            text=final_description,
            caption=final_description,
            video_url=public_video_url,
            video_file=local_video_path or "",
        )

        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
        post_url = _build_social_post_url(platform_name, platform_result)
        await _insert_publish_job(
            user_id=user_id, platform=platform_name, external_id=external_id, status="done", priority=publish_priority,
            payload={**base_payload, "post_url": post_url} if post_url else base_payload,
        )
        return {
            "success": True,
            "result": platform_result,
        }
    except Exception as exc:
        err_msg = str(exc)
        await _insert_publish_job(
            user_id=user_id, platform=platform_name, external_id="n/a", status="failed", error_message=err_msg,
            priority=publish_priority, payload=base_payload,
        )
        return {
            "success": False,
            "error": err_msg,
        }


@app.post("/api/social/post", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def post_to_socials(req: SocialPostRequest, request: Request, user_id_header: Annotated[str, Depends(get_user_id_header)]):
    user_id = _resolve_request_user_id(req.user_id, user_id_header)
    await _assert_user_has_active_subscription_for_publish(user_id)
    accounts = await _resolve_accounts_for_publish(user_id, req.account_ids, _SHARE_PLATFORMS)
    await _assert_user_can_publish(user_id, len(accounts))
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(req.scheduled_date, req.timezone)
    if req.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    clip = await _resolve_clip_for_social_post(req.job_id, req.clip_index)

    video_ref = str(clip.get('video_url') or '').strip()
    if not video_ref:
        raise HTTPException(status_code=404, detail="Video URL not found for this clip")

    local_video_path = _resolve_local_video_path(req.job_id, video_ref, req.clip_index)
    public_video_url = _resolve_public_video_url(video_ref, request, req.job_id)

    final_title = req.title or clip.get('video_title_for_youtube_short') or clip.get('title') or 'Vireel Short'
    final_description = req.description or clip.get('video_description_for_instagram') or clip.get('video_description_for_tiktok') or "Check this out!"

    results: Dict[str, Any] = {}
    overall_success = True

    for account in accounts:
        result_key = str(account.get("id") or account.get("platform"))
        if is_scheduled:
            results[result_key] = await _schedule_reel_social_post_job(
                user_id, account, req, publish_priority, scheduled_for, final_title, final_description, public_video_url,
            )
            continue

        result = await _publish_reel_social_post_now(
            user_id, account, publish_priority, final_title, final_description, public_video_url, local_video_path,
        )
        results[result_key] = result
        if not result["success"]:
            overall_success = False

    return {
        "success": overall_success,
        "results": results,
    }


# --- Thumbnail Studio Endpoints ---

@app.post("/api/thumbnail/upload", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def thumbnail_upload(
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[Optional[UploadFile], File()] = None,
    url: Annotated[Optional[str], Form()] = None,
):
    """Upload video and start background Whisper transcription immediately."""
    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL or File")

    session_id = str(uuid.uuid4())
    transcript_event = asyncio.Event()

    # Save file if uploaded directly
    video_path = None
    if file:
        safe_thumb_name = _sanitize_input_filename(file.filename) or _DEFAULT_UPLOAD_FILENAME
        video_path = os.path.join(UPLOAD_DIR, f"thumb_{session_id}_{safe_thumb_name}")
        async with aiofiles.open(video_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)

    # Initialize session
    thumbnail_sessions[session_id] = {
        "video_path": video_path,
        "transcript_event": transcript_event,
        "transcript_ready": False,
        "transcript": None,
        "transcript_segments": [],
        "video_duration": 0,
        "language": "en",
        "context": "",
        "titles": [],
        "conversation": [],
        "_url": url,  # Store URL for deferred download
    }

    async def run_background_whisper():
        try:
            vpath = video_path
            # Download YouTube video if URL was provided
            if not vpath and url:
                from main import download_youtube_video
                loop = asyncio.get_event_loop()
                vpath, _ = await loop.run_in_executor(None, download_youtube_video, url, UPLOAD_DIR)
                thumbnail_sessions[session_id]["video_path"] = vpath

            from main import transcribe_video
            loop = asyncio.get_event_loop()
            transcript = await loop.run_in_executor(None, transcribe_video, vpath)
            segments = transcript.get("segments", [])
            duration = segments[-1]["end"] if segments else 0

            thumbnail_sessions[session_id].update({
                "transcript_ready": True,
                "transcript": transcript,
                "transcript_segments": segments,
                "video_duration": duration,
                "language": transcript.get("language", "en"),
            })
            print(f"✅ [Thumbnail] Background Whisper complete for session {session_id}")
        except Exception as e:
            print(f"❌ [Thumbnail] Background Whisper failed: {e}")
            thumbnail_sessions[session_id]["transcript_error"] = str(e)
        finally:
            transcript_event.set()

    _spawn_background_task(run_background_whisper())

    return {"session_id": session_id}


async def _resolve_existing_thumbnail_session(session_id: str):
    session = thumbnail_sessions[session_id]

    # Wait for background Whisper to complete
    transcript_event = session.get("transcript_event")
    if transcript_event:
        print("⏳ [Thumbnail] Waiting for background Whisper to finish...")
        await transcript_event.wait()

    if session.get("transcript_error"):
        raise HTTPException(status_code=500, detail=f"Transcription failed: {session['transcript_error']}")

    video_path = session["video_path"]
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video file not found in session")

    pre_transcript = session["transcript"] if session.get("transcript_ready") else None
    return video_path, pre_transcript


async def _create_thumbnail_session_from_input(url: Optional[str], file: Optional[UploadFile]):
    # No pre-existing session — need file or URL
    if not url and not file:
        raise HTTPException(status_code=400, detail="Must provide URL, File, or session_id")

    session_id = str(uuid.uuid4())

    if url:
        from main import download_youtube_video
        video_path, _ = download_youtube_video(url, UPLOAD_DIR)
    else:
        safe_thumb_name = _sanitize_input_filename(file.filename) or _DEFAULT_UPLOAD_FILENAME
        video_path = os.path.join(UPLOAD_DIR, f"thumb_{session_id}_{safe_thumb_name}")
        async with aiofiles.open(video_path, "wb") as buffer:
            content = await file.read()
            await buffer.write(content)

    return session_id, video_path


@app.post("/api/thumbnail/analyze", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}})
async def thumbnail_analyze(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[Optional[UploadFile], File()] = None,
    url: Annotated[Optional[str], Form()] = None,
    session_id: Annotated[Optional[str], Form()] = None,
    x_gemini_key: Annotated[Optional[str], Header(alias="X-Gemini-Key")] = None,
):
    """Analyze a video and suggest viral YouTube titles."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    pre_transcript = None

    # Check for pre-existing session with background Whisper
    if session_id and session_id in thumbnail_sessions:
        video_path, pre_transcript = await _resolve_existing_thumbnail_session(session_id)
    else:
        session_id, video_path = await _create_thumbnail_session_from_input(url, file)

    try:
        # Run analysis in thread pool (skips Whisper if pre_transcript is available)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, analyze_video_for_titles, api_key, video_path, pre_transcript)

        # Store/update session context
        if session_id not in thumbnail_sessions:
            thumbnail_sessions[session_id] = {}

        thumbnail_sessions[session_id].update({
            "context": result.get("transcript_summary", ""),
            "titles": result.get("titles", []),
            "language": result.get("language", "en"),
            "conversation": thumbnail_sessions[session_id].get("conversation", []),
            "video_path": video_path,
            "transcript_segments": result.get("segments", []),
            "video_duration": result.get("video_duration", 0)
        })

        return {
            "session_id": session_id,
            "titles": result.get("titles", []),
            "context": result.get("transcript_summary", ""),
            "language": result.get("language", "en"),
            "recommended": result.get("recommended", [])
        }

    except Exception as e:
        raise _generic_error("Thumbnail Analyze Error", e)


class ThumbnailTitlesRequest(BaseModel):
    session_id: Optional[str] = None
    message: Optional[str] = None
    title: Optional[str] = None

@app.post("/api/thumbnail/titles", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def thumbnail_titles(
    req: ThumbnailTitlesRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
    x_gemini_key: Annotated[Optional[str], Header(alias="X-Gemini-Key")] = None,
):
    """Refine title suggestions or accept a manual title."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    # Manual title mode - just create a session with the user's title
    if req.title:
        session_id = req.session_id or str(uuid.uuid4())
        if session_id not in thumbnail_sessions:
            thumbnail_sessions[session_id] = {
                "context": "",
                "titles": [req.title],
                "language": "en",
                "conversation": []
            }
        return {"session_id": session_id, "titles": [req.title]}

    # Refinement mode
    if not req.session_id or req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

    if not req.message:
        raise HTTPException(status_code=400, detail="Must provide message or title")

    session = thumbnail_sessions[req.session_id]

    # Add user message to conversation history
    session["conversation"].append({"role": "user", "content": req.message})

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            refine_titles,
            api_key,
            session["context"],
            req.message,
            session["conversation"]
        )

        new_titles = result.get("titles", [])
        session["titles"] = new_titles
        session["conversation"].append({"role": "assistant", "content": json.dumps(new_titles)})

        return {"titles": new_titles}

    except Exception as e:
        raise _generic_error("Thumbnail Titles Error", e)


@app.post("/api/thumbnail/generate", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 500: {"description": "Internal Server Error"}})
async def thumbnail_generate(
    request: Request,
    session_id: Annotated[str, Form()],
    title: Annotated[str, Form()],
    user_id: Annotated[str, Depends(get_user_id_header)],
    extra_prompt: Annotated[str, Form()] = "",
    count: Annotated[int, Form()] = 3,
    face: Annotated[Optional[UploadFile], File()] = None,
    background: Annotated[Optional[UploadFile], File()] = None,
    x_gemini_key: Annotated[Optional[str], Header(alias="X-Gemini-Key")] = None,
):
    """Generate YouTube thumbnails with Gemini image generation."""
    # Security: session_id is client-supplied and gets joined into a
    # filesystem path below -- reject anything that isn't a well-formed
    # identifier before it ever reaches os.path.join (path traversal guard).
    if not _JOB_ID_PATTERN.match(session_id or ""):
        raise HTTPException(status_code=400, detail="Invalid session_id")

    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    # Clamp count
    count = min(max(1, count), 6)

    # Save optional uploaded images
    face_path = None
    bg_path = None
    thumb_upload_dir = os.path.join(UPLOAD_DIR, f"thumb_{session_id}")
    os.makedirs(thumb_upload_dir, exist_ok=True)

    try:
        if face and face.filename:
            safe_face_name = _sanitize_input_filename(face.filename) or "face.jpg"
            face_path = os.path.join(thumb_upload_dir, f"face_{safe_face_name}")
            async with aiofiles.open(face_path, "wb") as f:
                await f.write(await face.read())

        if background and background.filename:
            safe_bg_name = _sanitize_input_filename(background.filename) or "background.jpg"
            bg_path = os.path.join(thumb_upload_dir, f"bg_{safe_bg_name}")
            async with aiofiles.open(bg_path, "wb") as f:
                await f.write(await background.read())

        # Get video context from session (transcript summary from analysis step)
        video_context = ""
        if session_id in thumbnail_sessions:
            video_context = thumbnail_sessions[session_id].get("context", "")

        # Run generation in thread pool
        loop = asyncio.get_event_loop()
        thumbnails = await loop.run_in_executor(
            None,
            generate_thumbnail,
            api_key,
            title,
            session_id,
            face_path,
            bg_path,
            extra_prompt,
            count,
            video_context
        )

        if not thumbnails:
            raise HTTPException(status_code=500, detail="Thumbnail generation failed. Please check your Gemini API key has access to image generation (gemini-3.1-flash-image-preview model).")

        return {"thumbnails": thumbnails}

    except HTTPException:
        raise
    except Exception as e:
        raise _generic_error("Thumbnail Generate Error", e)


class ThumbnailDescribeRequest(BaseModel):
    session_id: str
    title: str

@app.post("/api/thumbnail/describe", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def thumbnail_describe(
    req: ThumbnailDescribeRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
    x_gemini_key: Annotated[Optional[str], Header(alias="X-Gemini-Key")] = None,
):
    """Generate a YouTube description with chapters from the transcript."""
    # Use .env configuration (ignore header for security)
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=400, detail=_GEMINI_API_KEY_NOT_CONFIGURED)

    if req.session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

    session = thumbnail_sessions[req.session_id]
    segments = session.get("transcript_segments", [])
    if not segments:
        raise HTTPException(status_code=400, detail="No transcript segments available. Please analyze a video first.")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            generate_youtube_description,
            api_key,
            req.title,
            segments,
            session.get("language", "en"),
            session.get("video_duration", 0)
        )
        return {"description": result.get("description", "")}

    except Exception as e:
        raise _generic_error("Thumbnail Describe Error", e)


@app.post("/api/thumbnail/publish", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
def thumbnail_publish(
    background_tasks: BackgroundTasks,
    session_id: Annotated[str, Form()],
    title: Annotated[str, Form()],
    description: Annotated[str, Form()],
    thumbnail_url: Annotated[str, Form()],
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Kick off a background upload to YouTube using the user's connected social account."""
    if session_id not in thumbnail_sessions:
        raise HTTPException(status_code=404, detail=_SESSION_NOT_FOUND)

    session = thumbnail_sessions[session_id]
    video_path = session.get("video_path")
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Original video file not found")

    # Resolve thumbnail path from URL (kept for future YouTube thumbnail API support)
    thumb_relative = thumbnail_url.lstrip("/")
    if thumb_relative.startswith("thumbnails/"):
        thumb_path = os.path.join(OUTPUT_DIR, thumb_relative)
    else:
        thumb_path = os.path.join(THUMBNAILS_DIR, thumb_relative)

    if not os.path.exists(thumb_path):
        raise HTTPException(status_code=404, detail=f"Thumbnail file not found: {thumb_path}")

    # Generate a unique ID for this publish job so the frontend can poll
    publish_id = str(uuid.uuid4())
    publish_jobs[publish_id] = {"status": "uploading", "result": None, "error": None, "user_id": user_id}

    def do_upload():
        """Runs in a thread via BackgroundTasks — does the actual multipart upload."""
        try:
            print(f"📡 [Thumbnail] Publishing to YouTube with connected account... (publish_id={publish_id})")

            account = asyncio.run(_get_social_account(user_id, "youtube"))
            if not account:
                raise RuntimeError("No connected youtube account found")

            payload = PublishRequest(
                user_id=user_id,
                title=title,
                description=description,
                text=description,
                video_file=video_path,
            )
            result = asyncio.run(publish_post(account, payload))
            publish_jobs[publish_id]["status"] = "done"
            publish_jobs[publish_id]["result"] = result
            external_id = str(result.get("video_id") or result.get("id") or "n/a")
            post_url = _build_social_post_url("youtube", result)
            publish_priority = asyncio.run(_resolve_user_job_priority(user_id))
            asyncio.run(_insert_publish_job(
                user_id=user_id, platform="youtube", external_id=external_id, status="done", priority=publish_priority,
                payload={"post_url": post_url} if post_url else None,
            ))

        except Exception as e:
            err = str(e)
            print(f"❌ Thumbnail Publish Background Error: {err}")
            publish_jobs[publish_id]["status"] = "failed"
            publish_jobs[publish_id]["error"] = err

    background_tasks.add_task(do_upload)
    return {"publish_id": publish_id, "status": "uploading"}


@app.get("/api/thumbnail/publish/status/{publish_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
def thumbnail_publish_status(publish_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Poll the status of a background publish job."""
    job = publish_jobs.get(publish_id)
    # Security: unlike its sibling /api/render/{render_id}, this endpoint had
    # no auth at all -- anyone holding a publish_id (a UUID4, but still)
    # could read another user's publish result. 404 (not 403) on a mismatch
    # so a caller can't tell a real-but-foreign publish_id apart from one
    # that was never created.
    if not job or job.get("user_id") != user_id:
        raise HTTPException(status_code=404, detail="Publish job not found")
    return {"status": job.get("status"), "result": job.get("result"), "error": job.get("error")}


# --- Reels API (Supabase-backed only) ---


class ReelShareRequest(BaseModel):
    account_ids: List[str] = []
    title: Optional[str] = None
    description: Optional[str] = None
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"



class StripeCheckoutRequest(BaseModel):
    plan_id: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    billing_interval: Literal["month", "year"] = "month"


def _require_stripe_ready() -> None:
    if stripe is None:
        raise HTTPException(status_code=503, detail="Stripe SDK not installed on server")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe is not configured")


def _frontend_base_url(request: Request) -> str:
    configured = os.environ.get("FRONTEND_URL", "").strip().rstrip("/")
    if configured:
        return configured
    origin = request.headers.get("origin", "").strip().rstrip("/")
    if origin:
        return origin
    return "http://localhost:5175"


def _stripe_field(obj: Any, key: str, default: Any = None) -> Any:
    """Safe bracket access for a Stripe resource object (Customer,
    PaymentMethod, Card, Subscription, ...), a plain dict, or None.
    Stripe's resource objects support obj[key] but not the dict method
    obj.get(key) -- calling .get() raises a guided AttributeError ("...
    is not a dict. Use .to_dict() to convert it.") since StripeObject
    isn't a dict (see also _extract_subscription_period_end, which has
    the same constraint inlined)."""
    if obj is None:
        return default
    try:
        value = obj[key]
    except (KeyError, TypeError):
        return default
    return default if value is None else value


async def _existing_stripe_customer_id(user_id: str) -> Optional[str]:
    """The Stripe Customer tied to this user's last paid plan, if any.
    Reusing it everywhere a Checkout Session is created for this user
    (subscribing, changing plan, buying credits) -- instead of always
    passing a bare customer_email, which lets Stripe silently create a
    brand new guest Customer each time -- keeps a single Stripe Customer
    per user, so a card saved in one of those flows shows up as reusable
    in the others too."""
    previous_subscription = await supabase_get_latest_user_paid_subscription(user_id)
    return previous_subscription.get("stripe_customer_id") if previous_subscription else None


def _annual_price_for_plan(plan: Dict[str, Any]) -> float:
    """annual_price = monthly_price * 12 * (1 - reduction_annuelle/100).

    `reduction_annuelle` is stored as an integer percentage on the plan
    (5 => 5%). During rollout we still accept legacy fractional values
    strictly between 0 and 1 (0.05 => 5%) so older rows keep pricing
    correctly until the migration is applied everywhere.
    """
    monthly_price = float(plan.get("price") or 0)
    raw_discount = float(plan.get("reduction_annuelle") or 0)
    if 0 < raw_discount < 1:
        raw_discount *= 100.0
    discount_rate = min(1.0, max(0.0, raw_discount / 100.0))
    return round(monthly_price * 12 * (1 - discount_rate), 2)


async def _create_recurring_subscription_checkout(
    request: Request, user_id: str, plan: Dict[str, Any], *,
    success_url: str, cancel_url: str, previous_souscription_id: Optional[str] = None,
    billing_interval: str = "month",
) -> Dict[str, Any]:
    """Creates a mode="subscription" Checkout Session for `plan`, reusing
    the user's existing Stripe Customer when there is one (see
    _existing_stripe_customer_id). previous_souscription_id, when given,
    is carried in the session/subscription metadata so
    _handle_subscription_purchase can close that row out once this
    Checkout actually completes -- used when a plan change has to create
    a brand new Stripe subscription because the current one isn't
    Stripe-recurring (see change_souscription_plan). Never closes the old
    row itself: an abandoned Checkout must leave the current plan
    untouched.

    billing_interval selects Stripe's own recurring.interval ("month" or
    "year") and, for "year", the discounted annual price (see
    _annual_price_for_plan) instead of the plain monthly price."""
    billing_interval = billing_interval if billing_interval == "year" else "month"
    price_amount = _annual_price_for_plan(plan) if billing_interval == "year" else float(plan.get("price") or 0)
    try:
        unit_amount = int(round(price_amount * 100))
    except (TypeError, ValueError):
        raise _coded_error(400, "invalid_plan_price", _INVALID_PLAN_PRICE)

    if unit_amount <= 0:
        raise _coded_error(400, "invalid_plan_price", _INVALID_PLAN_PRICE)

    metadata = {
        "userid": user_id,
        "abonnement": str(plan.get("id")),
        "plan_name": str(plan.get("name") or ""),
        "payment_mode": "stripe",
        "billing_interval": billing_interval,
    }
    if previous_souscription_id:
        metadata["previous_souscription_id"] = previous_souscription_id

    existing_customer_id = await _existing_stripe_customer_id(user_id)

    description = (
        "Abonnement annuel, renouvele automatiquement chaque annee"
        if billing_interval == "year"
        else "Abonnement mensuel, renouvele automatiquement chaque mois"
    )

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            **(
                {"customer": existing_customer_id}
                if existing_customer_id
                else {"customer_email": request.headers.get("X-User-Email") or None}
            ),
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": STRIPE_CURRENCY,
                        "unit_amount": unit_amount,
                        "recurring": {"interval": billing_interval},
                        "product_data": {
                            "name": str(plan.get("name") or "Abonnement"),
                            "description": description,
                            "tax_code": "txcd_10103001",
                        },
                    },
                }
            ],
            metadata=metadata,
            # Copied onto every invoice this subscription raises (including
            # renewals), so _handle_subscription_renewal_invoice can read
            # userid/abonnement straight off the subscription without a
            # separate lookup table mapping Stripe subscriptions to users.
            subscription_data={"metadata": metadata},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout error: {exc}")

    return {"checkout_url": session.url, "session_id": session.id}


@app.post("/api/stripe/checkout-session", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def create_stripe_checkout_session(
    request: Request,
    payload: StripeCheckoutRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],   # ✅ ici, dans la signature
):
    """Create a hosted Stripe Checkout session for a subscription plan."""
    _require_stripe_ready()

    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    plan = await supabase_get_abonnement(payload.plan_id)
    if not plan:
        raise _coded_error(404, "plan_not_found", "Subscription plan not found")

    default_base_url = _frontend_base_url(request)
    success_url = (payload.success_url or STRIPE_SUCCESS_URL or f"{default_base_url}/dashboard/abonnement?payment=success").strip()
    cancel_url = (payload.cancel_url or STRIPE_CANCEL_URL or f"{default_base_url}/dashboard/abonnement?payment=cancel").strip()

    return await _create_recurring_subscription_checkout(
        request, user_id, plan, success_url=success_url, cancel_url=cancel_url,
        billing_interval=payload.billing_interval,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_and_parse_event(payload: bytes, signature: str) -> stripe.Event:
    """Validate the Stripe signature and return the parsed event."""
    try:
        return stripe.Webhook.construct_event(payload, signature, STRIPE_WEBHOOK_SECRET)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature") from exc


def _extract_session_context(session: "stripe.checkout.Session") -> dict:
    """Pull out everything the handlers need from a checkout session, as plain Python types."""
    metadata = session.metadata.to_dict() if session.metadata else {}
    created_ts = session.created

    return {
        "metadata": metadata,
        "user_id": metadata.get("userid"),
        "payment_mode": metadata.get("payment_mode", "stripe"),
        "billing_interval": metadata.get("billing_interval", "month"),
        "amount_total": (session.amount_total or 0) / 100,
        "payment_reference": session.payment_intent or session.id or "",
        "payment_date": (
            datetime.fromtimestamp(int(created_ts), tz=timezone.utc)
            if created_ts
            else datetime.now(timezone.utc)
        ),
        "session_id": session.id,
        "customer_email": (
            (session.customer_details.email if session.customer_details else None)
            or session.customer_email
        ),
        "stripe_subscription_id": session.subscription or None,
        "stripe_customer_id": session.customer or None,
    }


def _send_transactional_email(to_email: str, template_key: str, **context: Any) -> None:
    """Render and send one of email_templates.EMAIL_TEMPLATES via Brevo.
    Never raises -- a failed email must not fail the webhook (Stripe would
    retry it forever otherwise), and a bad template/context is a code bug
    to fix, not something that should ever take down billing."""
    if not to_email:
        logger.warning("Skipping %s email: no customer email on session", template_key)
        return
    if not BREVO_API_KEY:
        logger.warning("Skipping %s email: BREVO_API_KEY is not configured", template_key)
        return

    try:
        template = email_templates.render_email(template_key, **context)
    except Exception:
        logger.exception("Failed to render %s email template for %s", template_key, to_email)
        return

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = BREVO_API_KEY
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": to_email}],
        sender={"email": BREVO_FROM_EMAIL},
        subject=template.subject,
        html_content=template.html,
    )

    try:
        api_instance.send_transac_email(send_smtp_email)
    except ApiException:
        # Log and swallow: email failure should never turn a successful payment
        # into a 500, which would make Stripe retry the whole webhook.
        logger.exception("Failed to send %s email to %s", template_key, to_email)


async def _handle_credit_purchase(ctx: dict) -> dict:
    """Handle a one-off credit purchase (payment_mode == 'stripe_credits').
    Granted as its own expiring tier-2 batch (CREDIT_BATCH_TIER_PURCHASED,
    in promotional_credit_batches -- see the credit-tiers migration)
    rather than a plain delta into user_data.credit: that used to leave a
    purchased top-up indistinguishable from subscription credit, with no
    expiration of its own, and silently WIPED by the next subscription
    renewal's reset-to-allowance (_reset_user_plan_balance always
    overwrites user_data.credit wholesale rather than adding to it). As
    its own batch it gets a configurable validity window
    (PURCHASED_CREDITS_EXPIRATION_DAYS) and is consumed after promotional
    credit but before subscription credit (see consume_promotional_credits'
    tier ordering), and is revocable on refund/chargeback the same way a
    referral reward batch already is (source_reference = this souscription
    row's id -- see _handle_charge_refund_or_dispute)."""
    if await supabase_get_souscription_by_reference(ctx["payment_reference"]):
        return {"received": True, "duplicate": True}

    policy_state = await _enforce_subscription_retention_policy(ctx["user_id"])
    if policy_state.get("state") != "active":
        return {
            "received": True,
            "ignored": "no_active_subscription",
            "policy_state": policy_state.get("state"),
        }

    credits_to_add = float(ctx["metadata"].get("credits_to_add", 0))
    if credits_to_add <= 0:
        credits_to_add = usd_to_credits(ctx["amount_total"])

    new_souscription = await supabase_insert_souscription(
        user_id=ctx["user_id"],
        abonnement=None,
        payment_mode="stripe_credits",
        payment_amount=ctx["amount_total"],
        payment_reference=ctx["payment_reference"],
        payment_status="completed",
        payment_comment=f"Credit purchase {credits_to_add} credits",
        payment_date=ctx["payment_date"],
    )
    souscription_id = str(new_souscription.get("id") or ctx["payment_reference"])

    await supabase_insert_promotional_credit_batch(
        ctx["user_id"], credits_to_add, "CREDIT_PURCHASE", PURCHASED_CREDITS_EXPIRATION_DAYS,
        source_reference=souscription_id, tier=CREDIT_BATCH_TIER_PURCHASED,
    )
    await supabase_insert_user_data_history(
        user_id=ctx["user_id"],
        credit=credits_to_add,
        storage=0.0,
        operation="input",
        operation_type="credit_purchase",
        operation_id=ctx["payment_reference"],
    )
    _send_transactional_email(
        ctx["customer_email"], "credit_purchase",
        amount=ctx["amount_total"], credits=credits_to_add,
    )
    return {"received": True, "credits_added": credits_to_add}


async def _reset_user_plan_balance(user_id: str, credit: float, storage: float, operation_id: str) -> None:
    """Reset a user's credit/storage balance (and their maxima) to exactly
    `credit`/`storage` -- the actual Supabase write shared by a fresh plan
    allocation (_allocate_plan_resources, using the live plan's values) and
    an annual subscription's monthly refill (process_annual_credit_refill_jobs,
    using that subscription's own snapshotted values instead)."""
    await supabase_set_user_data_balance(
        user_id=user_id,
        credit=credit,
        storage=storage,
        credit_max=credit,
        storage_max=storage,
        operation_type="subscription",
        operation_id=operation_id,
    )
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=credit,
        storage=storage,
        operation="input",
        operation_type="subscription",
        operation_id=operation_id,
    )


async def _allocate_plan_resources(
    user_id: str, abonnement: str, payment_reference: str, souscription_id: str, *,
    billing_interval: str = "month", period_start: Optional[datetime] = None,
) -> None:
    """Credit the user's account with whatever the plan grants (credits +
    storage), and snapshot those exact values onto the souscription row
    (plan_credit/plan_stockage) -- used instead of a live plan lookup
    anywhere credits/storage need to be granted again for this same
    subscription later, so a future change to the plan catalog never
    retroactively changes what an already-in-progress subscription grants.

    For an annual subscription (billing_interval == "year"), also schedules
    the next monthly credit/storage refill (next_credit_allocation_at):
    Stripe only raises this subscription's renewal invoice once a year, so
    process_annual_credit_refill_jobs is what actually applies that
    monthly-anniversary refill in between, straight off this snapshot."""
    plan = await supabase_get_abonnement(abonnement)
    if not plan:
        return

    plan_credit = float(plan.get("credit") or 0)
    plan_storage = float(plan.get("stockage") or 0)

    # A new/changed plan resets monthly allowances and their maxima to the plan limits.
    await _reset_user_plan_balance(user_id, plan_credit, plan_storage, souscription_id or payment_reference)
    # The daily publish-quota cap is snapshotted onto user_data itself
    # (depends on the user, never re-derived live from abonnement -- see
    # consume_publish_quota) rather than onto this souscription row.
    await supabase_set_user_max_daily_publications(user_id, plan.get("max_daily_publications") or 0)

    if souscription_id:
        snapshot_updates: Dict[str, Any] = {"plan_credit": plan_credit, "plan_stockage": plan_storage}
        if billing_interval == "year":
            anchor = period_start or datetime.now(timezone.utc)
            snapshot_updates["next_credit_allocation_at"] = supabase_add_one_month(anchor).isoformat()
        await supabase_update_souscription_row(souscription_id, snapshot_updates)


def _handle_payment_method_setup(session: "stripe.checkout.Session") -> dict:
    """Completes a card-replacement flow (see
    replace_souscription_payment_method): makes the newly collected card
    the customer's default for future invoices, then detaches whichever
    card was previously the default -- so this is a real swap, not just
    adding a second card on file."""
    customer_id = session.customer
    setup_intent_id = session.setup_intent
    if not customer_id or not setup_intent_id:
        return {"received": True, "ignored": "missing_customer_or_setup_intent"}

    setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
    new_payment_method_id = setup_intent.payment_method
    if not new_payment_method_id:
        return {"received": True, "ignored": "no_payment_method_on_setup_intent"}

    previous_payment_method = _get_stripe_default_payment_method(customer_id)
    previous_payment_method_id = previous_payment_method["id"] if previous_payment_method else None

    stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": new_payment_method_id})

    if previous_payment_method_id and previous_payment_method_id != new_payment_method_id:
        try:
            stripe.PaymentMethod.detach(previous_payment_method_id)
        except Exception:
            logger.warning(
                "Failed to detach replaced payment method %s for customer %s",
                previous_payment_method_id, customer_id,
            )

    return {"received": True}


def _sync_customer_default_payment_method(stripe_subscription_id: Optional[str], stripe_customer_id: Optional[str]) -> None:
    """A subscription-mode Checkout sets the Subscription's own
    default_payment_method to the card used, but -- unlike the dedicated
    card-replace flow above (_handle_payment_method_setup) -- never
    mirrors that onto the Customer's invoice_settings.default_payment_method.
    Without this, get_souscription_payment_method's "card on file" (read
    off the Customer, not the Subscription -- see
    _get_stripe_default_payment_method) stays empty for anyone who has
    only ever subscribed and never explicitly replaced their card.
    Best-effort: a failure here must never fail the purchase itself."""
    if not stripe_subscription_id or not stripe_customer_id:
        return
    try:
        subscription = stripe.Subscription.retrieve(stripe_subscription_id, expand=["default_payment_method"])
        payment_method = _stripe_field(subscription, "default_payment_method")
        # Unexpanded, Stripe would hand back a bare id string here instead
        # of an object -- expand=[...] above means that never happens in
        # practice, but staying defensive costs nothing.
        payment_method_id = payment_method if isinstance(payment_method, str) else _stripe_field(payment_method, "id")
        if not payment_method_id:
            return
        stripe.Customer.modify(stripe_customer_id, invoice_settings={"default_payment_method": payment_method_id})
    except Exception:
        logger.warning("Failed to sync default payment method for customer %s", stripe_customer_id)


async def _create_notification(
    user_id: str, type_: str, title: str, body: str = "", data: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort in-app notification -- must never fail the business
    operation that triggered it (signup association, reward grant, ...)."""
    try:
        await supabase_insert_notification(user_id, type_, title, body, data or {})
    except Exception:
        logger.warning("Failed to create notification %s for user %s", type_, user_id, exc_info=True)


async def _maybe_reward_referrer_for_first_subscription(
    referred_user_id: str, billing_interval: str, souscription_id: str,
) -> None:
    """Grants the referrer's reward the first time (and only the first
    time -- see claim_referral_subscription_reward's conditional-update
    idempotency guard, the same compare-and-swap pattern already used
    elsewhere in this file for debit concurrency) their referee pays for a
    plan. Only ever called from _handle_subscription_purchase for a
    confirmed first-ever paid subscription -- never on a renewal or plan
    change, and never on a failed/pending payment."""
    referral = await supabase_get_referral_by_referred_user(referred_user_id)
    if not referral or referral.get("status") == "invalid":
        return

    subscription_type = "year" if billing_interval == "year" else "month"
    reward_amount = REFERRAL_ANNUAL_BONUS_CREDITS if subscription_type == "year" else REFERRAL_MONTHLY_BONUS_CREDITS
    source = "REFERRAL_ANNUAL_SUBSCRIPTION" if subscription_type == "year" else "REFERRAL_MONTHLY_SUBSCRIPTION"

    claimed = await supabase_claim_referral_subscription_reward(referral["id"], subscription_type, souscription_id)
    if not claimed:
        return

    referrer_user_id = referral["referrer_user_id"]
    batch = await supabase_insert_promotional_credit_batch(
        referrer_user_id, reward_amount, source, PROMOTIONAL_CREDITS_EXPIRATION_DAYS,
        source_reference=souscription_id,
    )
    await supabase_update_referral_row(referral["id"], {"subscription_reward_batch_id": batch.get("id")})

    label = "annuel" if subscription_type == "year" else "mensuel"
    await _create_notification(
        referrer_user_id, "referral_reward_granted", "Ton ami s'est abonné !",
        f"Tu as reçu {reward_amount:.0f} crédits promotionnels car ton ami a choisi un abonnement {label}.",
        {"amount": reward_amount, "subscription_type": subscription_type},
    )
    await _create_notification(
        referred_user_id, "referral_referrer_rewarded", "Merci pour ton abonnement !",
        "Grâce à toi, ton parrain vient de recevoir une récompense.",
        {},
    )


async def _handle_subscription_purchase(ctx: dict) -> dict:
    """Handle a standard plan subscription checkout."""
    abonnement = ctx["metadata"].get("abonnement")
    if not abonnement:
        raise HTTPException(status_code=400, detail="Missing subscription metadata")

    if await supabase_get_souscription_by_reference(ctx["payment_reference"]):
        return {"received": True, "duplicate": True}

    previous_souscription_id = ctx["metadata"].get("previous_souscription_id")
    # Must be resolved BEFORE inserting the new souscription row below,
    # which would otherwise make this user look like they already have a
    # prior subscription (themselves). A plan change via a fresh Checkout
    # (previous_souscription_id set) is never a first subscription either
    # -- that path only exists for a user who already has one.
    is_first_subscription = False
    if not previous_souscription_id:
        prior_paid_subscription = await supabase_get_latest_user_paid_subscription(ctx["user_id"])
        is_first_subscription = not prior_paid_subscription

    _sync_customer_default_payment_method(ctx.get("stripe_subscription_id"), ctx.get("stripe_customer_id"))

    billing_interval = ctx.get("billing_interval", "month")
    new_souscription = await supabase_insert_souscription(
        user_id=ctx["user_id"],
        abonnement=abonnement,
        payment_mode="stripe",
        payment_amount=ctx["amount_total"],
        payment_reference=ctx["payment_reference"],
        payment_status="completed",
        payment_comment=f"Stripe checkout session {ctx['session_id']}".strip(),
        payment_date=ctx["payment_date"],
        stripe_subscription_id=ctx.get("stripe_subscription_id"),
        stripe_customer_id=ctx.get("stripe_customer_id"),
        billing_interval=billing_interval,
    )

    if previous_souscription_id:
        # Changing plan from a non-Stripe-recurring subscription goes
        # through a fresh Checkout (see change_souscription_plan /
        # _create_recurring_subscription_checkout) instead of modifying a
        # Stripe Subscription in place -- only now, once that Checkout has
        # actually completed, is it safe to retire the old row so it stops
        # matching get_user_abonnement's "active" filter alongside this new
        # one. Doing this before payment succeeded would risk leaving the
        # user with neither row if they abandoned the Checkout.
        await supabase_update_souscription_row(
            previous_souscription_id,
            {"payment_end_date": datetime.now(timezone.utc).isoformat()},
            user_id=ctx["user_id"],
        )

    await _allocate_plan_resources(
        user_id=ctx["user_id"],
        abonnement=abonnement,
        payment_reference=ctx["payment_reference"],
        souscription_id=str(new_souscription.get("id") or ctx["payment_reference"]),
        billing_interval=billing_interval,
        period_start=ctx["payment_date"],
    )

    if is_first_subscription:
        await _maybe_reward_referrer_for_first_subscription(
            ctx["user_id"], billing_interval, str(new_souscription.get("id") or ctx["payment_reference"]),
        )

    _send_transactional_email(
        ctx["customer_email"], "subscription_purchase",
        amount=ctx["amount_total"], plan_name=ctx["metadata"].get("plan_name") or abonnement,
    )
    return {"received": True}


def _invoice_line_period(invoice: "stripe.Invoice") -> Tuple[Optional[datetime], Optional[datetime]]:
    """The billing period a subscription renewal invoice actually covers,
    straight from Stripe rather than recomputed -- Stripe is the source of
    truth for the exact anniversary date (leap months, plan changes
    mid-cycle, etc.), so the stored payment_end_date must match it exactly
    instead of drifting from a locally-reapplied +1-month rule."""
    lines = (invoice.lines.data if invoice.lines else None) or []
    if not lines or not lines[0].period:
        return None, None
    period = lines[0].period
    start = datetime.fromtimestamp(period.start, tz=timezone.utc) if period.start else None
    end = datetime.fromtimestamp(period.end, tz=timezone.utc) if period.end else None
    return start, end


async def _handle_subscription_renewal_invoice(invoice: "stripe.Invoice") -> dict:
    """Credit a subscription's automatic renewal -- monthly for a monthly
    plan, once a year for an annual one (see _allocate_plan_resources for
    how an annual plan's credits/storage still get refilled every month in
    between). Stripe raises this invoice itself on the subscription's
    billing anniversary -- the first invoice (billing_reason
    "subscription_create") is instead handled by checkout.session.completed,
    which has already run by the time it fires, so only "subscription_cycle"
    reaches here (see the dispatch in stripe_webhook)."""
    subscription_id = invoice.subscription
    if not subscription_id:
        return {"received": True, "ignored": "no_subscription_on_invoice"}

    payment_reference = str(invoice.payment_intent or invoice.id or subscription_id)
    if await supabase_get_souscription_by_reference(payment_reference):
        return {"received": True, "duplicate": True}

    subscription = stripe.Subscription.retrieve(subscription_id)
    metadata = subscription.metadata.to_dict() if subscription.metadata else {}
    user_id = metadata.get("userid")
    abonnement = metadata.get("abonnement")
    if not user_id or not abonnement:
        logger.warning("Stripe subscription %s renewal invoice is missing userid/abonnement metadata", subscription_id)
        return {"received": True, "ignored": "missing_subscription_metadata"}

    period_start, period_end = _invoice_line_period(invoice)
    payment_date = period_start or datetime.fromtimestamp(invoice.created, tz=timezone.utc)
    amount_total = (invoice.amount_paid or 0) / 100
    billing_interval = metadata.get("billing_interval", "month")

    new_souscription = await supabase_insert_souscription(
        user_id=user_id,
        abonnement=abonnement,
        payment_mode="stripe",
        payment_amount=amount_total,
        payment_reference=payment_reference,
        payment_status="completed",
        payment_comment=f"Stripe subscription renewal {subscription_id}",
        payment_date=payment_date,
        period_end_date=period_end,
        stripe_subscription_id=subscription_id,
        stripe_customer_id=invoice.customer or None,
        billing_interval=billing_interval,
    )
    await _allocate_plan_resources(
        user_id=user_id,
        abonnement=abonnement,
        payment_reference=payment_reference,
        souscription_id=str(new_souscription.get("id") or payment_reference),
        billing_interval=billing_interval,
        period_start=payment_date,
    )
    _send_transactional_email(
        invoice.customer_email, "subscription_renewal",
        amount=amount_total, plan_name=metadata.get("plan_name") or abonnement,
    )
    return {"received": True}


async def _handle_subscription_payment_failed(invoice: "stripe.Invoice") -> dict:
    """Notify the customer when Stripe's automatic monthly/annual renewal
    charge fails (expired/declined card, insufficient funds, ...). Stripe
    keeps retrying the charge on its own schedule (Smart Retries)
    independently of this handler -- invoice.payment_failed fires again
    on each attempt, with invoice.next_payment_attempt set to the next
    scheduled retry. Only once Stripe gives up for good (this is the
    LAST attempt, next_payment_attempt is now null/None) does this zero
    the account's pure subscription credit (supabase_zero_subscription_credit
    -- never the promotional/purchased credit batches, which stay usable
    on their own terms regardless of the subscription's payment state).
    A subsequent successful renewal resets it back to the plan's full
    allowance as usual."""
    subscription_id = invoice.subscription
    if not subscription_id:
        return {"received": True, "ignored": "no_subscription_on_invoice"}

    subscription = stripe.Subscription.retrieve(subscription_id)
    metadata = subscription.metadata.to_dict() if subscription.metadata else {}
    plan_name = metadata.get("plan_name") or metadata.get("abonnement") or "Vireel"
    user_id = metadata.get("userid")

    is_final_attempt = not invoice.next_payment_attempt
    if is_final_attempt:
        retry_message = (
            "Aucune nouvelle tentative automatique n'est prévue -- merci de mettre à jour votre "
            "moyen de paiement dès que possible pour conserver l'accès à votre abonnement."
        )
        if user_id:
            await supabase_zero_subscription_credit(user_id, operation_id=str(invoice.id or subscription_id))
    else:
        retry_date = datetime.fromtimestamp(invoice.next_payment_attempt, tz=timezone.utc).strftime("%d/%m/%Y")
        retry_message = f"Une nouvelle tentative de prélèvement aura lieu automatiquement le {retry_date}."

    _send_transactional_email(
        invoice.customer_email, "payment_failed",
        amount=(invoice.amount_due or 0) / 100, plan_name=plan_name,
        retry_message=retry_message, update_payment_url=invoice.hosted_invoice_url or "",
    )
    return {"received": True}


async def _handle_charge_refund_or_dispute(stripe_object: Any, reason: str) -> dict:
    """A refund or chargeback landing on the exact charge that funded a
    subscription payment -- revoke whatever's still available in any
    promotional-credit batch a referral reward created from that payment
    (see section 11 -- never claws back credits already spent, see
    revoke_promotional_credit_batches_by_source_reference). A charge/
    dispute unrelated to any referral reward is a no-op here (there's
    simply nothing in promotional_credit_batches to match it)."""
    payment_intent_id = _stripe_field(stripe_object, "payment_intent")
    if not payment_intent_id:
        return {"received": True, "ignored": "no_payment_intent"}

    souscription = await supabase_get_souscription_by_reference(str(payment_intent_id))
    if not souscription:
        return {"received": True, "ignored": "no_matching_souscription"}

    revoked = await supabase_revoke_promotional_credit_batches_by_source_reference(
        str(souscription["id"]), reason,
    )
    return {"received": True, "revoked_batches": revoked}


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@app.post("/api/stripe/webhook", responses={400: {"description": "Bad Request"}, 503: {"description": "Service Unavailable"}})
async def stripe_webhook(request: Request):
    """Handle Stripe checkout.session.completed (new purchase/subscription),
    invoice.paid (automatic subscription renewal), invoice.payment_failed
    (failed automatic renewal charge), charge.refunded and
    charge.dispute.created (referral-reward clawback) events."""
    _require_stripe_ready()
    if not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook secret is not configured")
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")
    event = _verify_and_parse_event(payload, signature)

    if event.type == "invoice.paid":
        invoice = event.data.object
        # "subscription_create" (the very first invoice) is handled by
        # checkout.session.completed instead. "subscription_update" is
        # the invoice Stripe raises when a Subscription Schedule's phase
        # 2 takes over at the scheduled boundary (see
        # _create_or_replace_plan_change_schedule) -- it's a genuine
        # recurring charge on the subscription, same as "subscription_cycle",
        # just tagged differently because the price changed with it.
        # Never matches the custom one-off proration invoice this app
        # creates itself for an immediate upgrade (_charge_plan_change_
        # proration): that one has no `subscription` attached at all and
        # gets billing_reason "manual".
        if invoice.billing_reason not in ("subscription_cycle", "subscription_update"):
            return {"received": True, "ignored": f"invoice.paid:{invoice.billing_reason}"}
        return await _handle_subscription_renewal_invoice(invoice)

    if event.type == "invoice.payment_failed":
        return await _handle_subscription_payment_failed(event.data.object)

    if event.type == "charge.refunded":
        return await _handle_charge_refund_or_dispute(event.data.object, "refund")

    if event.type == "charge.dispute.created":
        return await _handle_charge_refund_or_dispute(event.data.object, "chargeback")

    if event.type != "checkout.session.completed":
        return {"received": True, "ignored": event.type}

    session = event.data.object
    if session.mode == "setup":
        # A card-replacement flow (see replace_souscription_payment_method)
        # carries no price/amount/subscription -- _extract_session_context
        # below assumes a purchase and must never see this kind of session.
        return _handle_payment_method_setup(session)

    ctx = _extract_session_context(session)
    if not ctx["user_id"]:
        raise HTTPException(status_code=400, detail="Missing user_id in metadata")

    if ctx["payment_mode"] == "stripe_credits":
        return await _handle_credit_purchase(ctx)

    return await _handle_subscription_purchase(ctx)


@app.get("/api/abonnements", responses={503: {"description": "Service Unavailable"}})
async def list_abonnements():
    """List available subscription plans from Supabase, in ascending
    "ordre" and excluding any plan with no ordre set -- that's how a plan
    is retired from sale without deleting its row (see the "ordre"
    migration), which would otherwise break plan-name lookups for
    existing subscribers on that plan."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    plans = await supabase_list_abonnements()
    visible_plans = [plan for plan in plans if plan.get("ordre") is not None]
    return {"plans": visible_plans}


@app.get("/api/souscription", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def get_current_souscription(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
) -> Optional[Dict[str, Any]]:
    """Get the current active subscription for a user -- also the data
    source for the subscription-management view (spec section 8): active
    plan, next billing/allocation dates, and any pending scheduled change
    with what it would switch to."""
    await _enforce_subscription_retention_policy(user_id)
    subscription = await get_user_abonnement(user_id)
    if not subscription:
        return None

    abonnement_id = str(subscription.get("abonnement") or "").strip()
    if abonnement_id:
        plan = await supabase_get_abonnement(abonnement_id)
        if plan:
            subscription = {
                **subscription,
                "abonnement_name": plan.get("name") or abonnement_id,
                "abonnement_credit": float(plan.get("credit") or 0.0),
            }

    billing_interval = subscription.get("billing_interval") or "month"
    subscription["next_billing_date"] = subscription.get("payment_end_date")
    subscription["next_credit_allocation_date"] = (
        subscription.get("next_credit_allocation_at") if billing_interval == "year"
        else subscription.get("payment_end_date")
    )

    scheduled_abonnement_id = str(subscription.get("scheduled_abonnement_id") or "").strip()
    if scheduled_abonnement_id:
        scheduled_plan = await supabase_get_abonnement(scheduled_abonnement_id)
        subscription["scheduled_abonnement_name"] = (scheduled_plan or {}).get("name") or scheduled_abonnement_id

    return subscription


@app.get("/api/souscription/history", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def get_souscription_history(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
):
    """Return subscription history only (excluding one-off credit purchases)."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    rows = await supabase_list_user_souscriptions(user_id, limit=limit)
    plans = await supabase_list_abonnements()
    plan_name_by_id = {
        str(plan.get("id")): str(plan.get("name") or "")
        for plan in (plans or [])
        if plan.get("id")
    }

    filtered: List[Dict[str, Any]] = []
    for row in rows:
        payment_mode = str(row.get("payment_mode") or "")
        if payment_mode == "stripe_credits":
            continue
        abonnement_id = str(row.get("abonnement") or "").strip()
        filtered.append(
            {
                **row,
                "abonnement_name": plan_name_by_id.get(abonnement_id) or abonnement_id or "-",
            }
        )

    return {"items": filtered}


class ChangeSubscriptionPlanRequest(BaseModel):
    plan_id: str


async def _get_active_stripe_souscription(user_id: str) -> Dict[str, Any]:
    """The active souscription row for a user, guaranteed to carry a
    stripe_subscription_id -- shared by cancel/reactivate/pause/resume and
    the payment-method endpoints, which all need one to act on. A row
    without it predates Stripe recurring billing (a one-off "payment" mode
    checkout from before mode="subscription") and has nothing on Stripe to
    manage -- change_souscription_plan handles that case itself (it
    creates a fresh recurring subscription instead of calling this), so by
    the time this raises, changing plan is the only way out for the user."""
    subscription = await get_user_abonnement(user_id)
    if not subscription:
        raise _coded_error(404, "no_active_subscription", "No active subscription")
    if not subscription.get("stripe_subscription_id"):
        raise _coded_error(
            400,
            "no_stripe_subscription",
            "This subscription is not a recurring Stripe subscription. "
            "Change plan to create a recurring subscription before using this action.",
        )
    return subscription


def _user_email_from_request(request: Optional[Request]) -> Optional[str]:
    """The caller's email, off the X-User-Email header the dashboard already
    sends on every subscription-lifecycle action (see Settings.jsx's
    runSubAction) -- used only to address a notification email, never for
    access control (identity/authorization is get_user_id_header's verified
    JWT). request is Optional only so a direct/internal call that isn't a
    real HTTP request (e.g. a test) can omit it and simply skip the email."""
    if request is None:
        return None
    return request.headers.get("X-User-Email") or None


async def _get_subscription_plan_name(subscription: Dict[str, Any]) -> str:
    plan = await supabase_get_abonnement(str(subscription.get("abonnement") or ""))
    return str((plan or {}).get("name") or "Vireel")


def _format_iso_date_fr(iso_value: Optional[str]) -> str:
    parsed = _parse_iso_datetime(iso_value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


@app.post("/api/souscription/cancel", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def cancel_souscription(user_id: Annotated[str, Depends(get_user_id_header)], request: Request = None):
    """Stop the subscription from auto-renewing -- access continues until
    the current period's payment_end_date, matching Stripe's own
    cancel_at_period_end semantics (no refund, no early cutoff)."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    try:
        stripe.Subscription.modify(subscription["stripe_subscription_id"], cancel_at_period_end=True)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    result = await supabase_update_souscription_row(
        str(subscription["id"]),
        {"auto_renew": False, "canceled_at": datetime.now(timezone.utc).isoformat()},
        user_id=user_id,
    )
    _send_transactional_email(
        _user_email_from_request(request), "subscription_canceled",
        plan_name=await _get_subscription_plan_name(subscription),
        period_end_date=_format_iso_date_fr(subscription.get("payment_end_date")),
    )
    return result


@app.post("/api/souscription/reactivate", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def reactivate_souscription(user_id: Annotated[str, Depends(get_user_id_header)], request: Request = None):
    """Undo a pending cancellation while the subscription is still within
    its current paid period -- the mirror of cancel_souscription."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    try:
        stripe.Subscription.modify(subscription["stripe_subscription_id"], cancel_at_period_end=False)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    result = await supabase_update_souscription_row(
        str(subscription["id"]),
        {"auto_renew": True, "canceled_at": None, "reactivated_at": datetime.now(timezone.utc).isoformat()},
        user_id=user_id,
    )
    _send_transactional_email(
        _user_email_from_request(request), "subscription_reactivated",
        plan_name=await _get_subscription_plan_name(subscription),
    )
    return result


@app.post("/api/souscription/pause", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def pause_souscription(user_id: Annotated[str, Depends(get_user_id_header)], request: Request = None):
    """Pause billing: Stripe still generates invoices on schedule but voids
    them immediately, so the customer is never charged while paused."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    try:
        stripe.Subscription.modify(subscription["stripe_subscription_id"], pause_collection={"behavior": "void"})
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    result = await supabase_update_souscription_row(
        str(subscription["id"]),
        {"paused_at": datetime.now(timezone.utc).isoformat()},
        user_id=user_id,
    )
    _send_transactional_email(
        _user_email_from_request(request), "subscription_paused",
        plan_name=await _get_subscription_plan_name(subscription),
    )
    return result


@app.post("/api/souscription/resume", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def resume_souscription(user_id: Annotated[str, Depends(get_user_id_header)], request: Request = None):
    """Undo pause_souscription -- billing resumes on the next scheduled invoice."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    try:
        # Stripe clears pause_collection only when explicitly set to "" --
        # omitting the field or passing None leaves the existing pause in place.
        stripe.Subscription.modify(subscription["stripe_subscription_id"], pause_collection="")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    result = await supabase_update_souscription_row(
        str(subscription["id"]),
        {"resumed_at": datetime.now(timezone.utc).isoformat()},
        user_id=user_id,
    )
    _send_transactional_email(
        _user_email_from_request(request), "subscription_resumed",
        plan_name=await _get_subscription_plan_name(subscription),
    )
    return result


def _get_stripe_default_payment_method(customer_id: str) -> Optional["stripe.PaymentMethod"]:
    """The card Stripe currently bills for this customer, falling back to
    the first attached card if no explicit default is set (e.g. a
    customer created before this feature, or one whose default was
    detached without a replacement). See _stripe_field: a Stripe resource
    object only reliably supports bracket access, never .get()."""
    customer = stripe.Customer.retrieve(customer_id, expand=["invoice_settings.default_payment_method"])
    invoice_settings = _stripe_field(customer, "invoice_settings")
    default_pm = _stripe_field(invoice_settings, "default_payment_method")
    if default_pm:
        return default_pm
    payment_methods = stripe.PaymentMethod.list(customer=customer_id, type="card")
    data = _stripe_field(payment_methods, "data") or []
    return data[0] if data else None


@app.get("/api/souscription/payment-method", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def get_souscription_payment_method(user_id: Annotated[str, Depends(get_user_id_header)]):
    """The card Stripe currently bills for this user's subscription, for a
    read-only preview in Settings (brand/last4/expiry only -- Stripe never
    exposes the full card number server-side, by design)."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    customer_id = subscription.get("stripe_customer_id")
    if not customer_id:
        return {"has_payment_method": False}

    try:
        payment_method = _get_stripe_default_payment_method(customer_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    if not payment_method:
        return {"has_payment_method": False}

    card = _stripe_field(payment_method, "card") or {}
    return {
        "has_payment_method": True,
        "brand": _stripe_field(card, "brand"),
        "last4": _stripe_field(card, "last4"),
        "exp_month": _stripe_field(card, "exp_month"),
        "exp_year": _stripe_field(card, "exp_year"),
    }


@app.post("/api/souscription/payment-method/revoke", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def revoke_souscription_payment_method(user_id: Annotated[str, Depends(get_user_id_header)]):
    """Detach the card Stripe currently bills. Future automatic renewal
    invoices will fail until a new default payment method is set (see
    replace_souscription_payment_method below) -- the same outcome as if
    the card had simply expired, which Stripe already handles via
    invoice.payment_failed (_handle_subscription_payment_failed)."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    customer_id = subscription.get("stripe_customer_id")
    if not customer_id:
        raise _coded_error(404, "no_stripe_customer", "No Stripe customer on file")

    try:
        payment_method = _get_stripe_default_payment_method(customer_id)
        if not payment_method:
            raise _coded_error(404, "no_payment_method", "No payment method on file")
        stripe.PaymentMethod.detach(payment_method["id"])
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return {"success": True}


@app.post("/api/souscription/payment-method/replace", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def replace_souscription_payment_method(
    request: Request, user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Starts a Stripe-hosted card collection flow (a Checkout Session in
    mode="setup") to replace the card on file. The actual swap -- making
    the new card the customer's default and detaching the old one --
    happens once Stripe confirms the setup, in the webhook
    (_handle_payment_method_setup), the same deferred-to-webhook pattern
    every other Stripe purchase/change in this app follows, since the
    frontend's redirect back here has no guarantee the webhook has
    already run."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await _get_active_stripe_souscription(user_id)
    customer_id = subscription.get("stripe_customer_id")
    if not customer_id:
        raise _coded_error(404, "no_stripe_customer", "No Stripe customer on file")

    default_base_url = _frontend_base_url(request)
    try:
        session = stripe.checkout.Session.create(
            mode="setup",
            customer=customer_id,
            payment_method_types=["card"],
            success_url=f"{default_base_url}/dashboard/settings?payment_method=success",
            cancel_url=f"{default_base_url}/dashboard/settings?payment_method=cancel",
            metadata={"userid": user_id},
            # Managed Payments (on by default for newer Stripe accounts)
            # only allows mode="subscription"/"payment" and rejects
            # mode="setup" outright ("Invalid mode: setup") -- it has
            # nothing to manage for a card-only setup session anyway, so
            # it's turned off for this specific request rather than for
            # the account.
            managed_payments={"enabled": False},
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")

    return {"checkout_url": session.url}


# ---------------------------------------------------------------------------
# Plan change classification + proration (plan-change rework spec, sections
# 1, 2, 3 and 6)
#
# Required Stripe account/dashboard configuration for this section:
#
#  - Stripe Billing must be enabled (Subscriptions + Subscription
#    Schedules -- both are part of the base Billing product, no separate
#    opt-in). Nothing here uses Stripe Tax; "tax_code": "txcd_10103001"
#    on every Price.create/product_data call is only there because
#    Subscription.modify/SubscriptionSchedule.modify reject an item with
#    "the product tax code is missing" once Stripe Tax or Managed
#    Payments is active on the account -- it's a defensive no-op on an
#    account that never turns Tax on, and the actual tax calculation (if
#    any) is entirely Stripe's own, outside this code's control.
#  - Managed Payments must stay OFF for mode="subscription"/"setup"
#    Checkout Sessions the way the rest of this file already disables it
#    (see create_recurring_subscription_checkout/replace_souscription_
#    payment_method) -- unrelated to this rework, called out here only
#    because a newer Stripe account may have it on by default.
#  - Webhook endpoint: no NEW event type is required beyond what this
#    app already subscribes to. invoice.paid is now dispatched for
#    BOTH billing_reason "subscription_cycle" (the pre-existing ordinary
#    monthly/annual renewal) AND "subscription_update" (the invoice
#    Stripe raises when a Subscription Schedule's phase 2 -- a deferred
#    downgrade/periodicity change, see _create_or_replace_plan_change_
#    schedule -- takes over at its start_date) -- see stripe_webhook's
#    dispatch. Make sure the webhook endpoint configured in the Stripe
#    Dashboard is subscribed to invoice.paid (already required before
#    this rework) with no event-type filtering narrower than that.
#  - Nothing here needs a Stripe-side "Customer portal" configuration --
#    every action (immediate upgrade, scheduling, cancelling a scheduled
#    change) is driven by this app's own endpoints, never a redirect to
#    Stripe's hosted portal.
#  - The off-session charge for an immediate upgrade's custom proration
#    (_charge_plan_change_proration: InvoiceItem + Invoice, collection_
#    method="charge_automatically") requires the customer to already
#    have a default_payment_method on file (set by a prior Checkout
#    Session or the explicit replace-card flow) -- an account with 3D
#    Secure (SCA) enforcement may still require the cardholder to
#    authenticate; Invoice.pay raises in that case same as a decline,
#    which this code already treats as a failed payment (spec section 3:
#    the current plan is left untouched).
# ---------------------------------------------------------------------------
PLAN_CHANGE_NOOP = "noop"
PLAN_CHANGE_UPGRADE_IMMEDIATE = "upgrade_immediate"
PLAN_CHANGE_DOWNGRADE_SCHEDULED = "downgrade_scheduled"
PLAN_CHANGE_PERIODICITY_SCHEDULED = "periodicity_scheduled"
PLAN_CHANGE_LATERAL_UNSUPPORTED = "lateral_unsupported"
PLAN_CHANGE_INVALID = "invalid"

# operation_type for the upgrade credit/storage supplement's user_data_history
# entry -- added to the standard credit/storage ledger via a plain delta (see
# _apply_immediate_upgrade), never a separate expiring batch: section 6 of
# the spec says this supplement shares "the normal lot of the current
# monthly cycle"'s own expiration, which in this codebase is simply "wiped
# at the next reset", exactly like the base monthly allocation already is
# (_reset_user_plan_balance) -- no new expiration mechanism to build.
PLAN_CHANGE_UPGRADE_OPERATION_TYPE = "plan_change_upgrade"


def _plan_change_ordre(plan: Dict[str, Any]) -> Optional[int]:
    """The plan's growth-order value (abonnement.ordre), used EXCLUSIVELY
    to classify a plan change -- never name, price or credit quota (spec
    section 1). None when absent or not a valid integer, which
    _classify_plan_change treats as a hard refusal: ordre is nullable by
    design (a plan retired from sale keeps its row but clears ordre --
    see the ordre migration), so a subscriber still on such a plan, or a
    target plan missing it, can't be safely auto-classified."""
    raw = plan.get("ordre")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _classify_plan_change(
    current_plan: Dict[str, Any], new_plan: Dict[str, Any],
    current_interval: str, new_interval: str,
) -> str:
    """Centralizes the one piece of logic the whole plan-change rework
    hinges on (spec section 1), reused by both the preview and the real
    change endpoint so their classification can never disagree. Adding a
    new plan only ever requires giving it the right abonnement.ordre --
    nothing here is a hardcoded list of plan ids."""
    same_plan = str(current_plan.get("id")) == str(new_plan.get("id"))
    interval_changed = current_interval != new_interval

    if same_plan and not interval_changed:
        return PLAN_CHANGE_NOOP

    current_ordre = _plan_change_ordre(current_plan)
    new_ordre = _plan_change_ordre(new_plan)
    if current_ordre is None or new_ordre is None:
        return PLAN_CHANGE_INVALID

    if not same_plan and current_ordre == new_ordre:
        return PLAN_CHANGE_LATERAL_UNSUPPORTED

    # A periodicity change always defers to the end of the already-paid
    # period, whatever the ordre direction -- even when the target plan
    # also outranks the current one (spec section 5) -- so this is
    # checked before the upgrade/downgrade split below.
    if interval_changed:
        return PLAN_CHANGE_PERIODICITY_SCHEDULED

    return PLAN_CHANGE_UPGRADE_IMMEDIATE if new_ordre > current_ordre else PLAN_CHANGE_DOWNGRADE_SCHEDULED


def _remaining_ratio(period_start: Optional[datetime], period_end: Optional[datetime], now: datetime) -> float:
    """Fraction of [period_start, period_end) still remaining at `now`,
    clamped to [0, 1] -- the one time-based ratio every proration formula
    below multiplies by."""
    if not period_start or not period_end:
        return 0.0
    total = (period_end - period_start).total_seconds()
    if total <= 0:
        return 0.0
    remaining = (period_end - now).total_seconds()
    return max(0.0, min(1.0, remaining / total))


def _round_credits(amount: float) -> int:
    """Floor to a whole credit (the spec requires "crédits entiers") --
    always rounding DOWN, never up, so a chain of successive upgrades/
    downgrades can never accumulate extra credits purely from rounding.
    The epsilon absorbs float representation error (e.g. 499.9999994 for
    an exact 500) without ever rounding a genuine fraction up."""
    return int(math.floor(float(amount) + 1e-6))


def _round_price(amount: float) -> float:
    """Floor to the cent, for the same determinism reason as
    _round_credits -- the displayed preview and the amount actually
    charged are always computed by this same function, so they can never
    disagree (spec section 3: "le montant présenté doit correspondre au
    montant réellement facturé")."""
    return math.floor(float(amount) * 100 + 1e-6) / 100.0


def _compute_monthly_upgrade_proration(
    *, current_plan_credit: float, current_plan_price: float, new_plan: Dict[str, Any],
    period_start: Optional[datetime], period_end: Optional[datetime], now: datetime,
) -> Dict[str, Any]:
    """Monthly same-periodicity upgrade (spec section 3): both the price
    difference and the credit-quota difference are prorated by the same
    ratio -- time remaining in the paid monthly period. Matches the
    spec's own worked example: Silver 10€/500 credits -> Gold 25€/1500
    credits at mid-cycle (ratio 0.5) charges 7.50€ and adds 500 credits."""
    ratio = _remaining_ratio(period_start, period_end, now)
    price_diff = float(new_plan.get("price") or 0) - float(current_plan_price or 0)
    credit_diff = float(new_plan.get("credit") or 0) - float(current_plan_credit or 0)
    return {
        "amount_due_today": _round_price(price_diff * ratio),
        "credits_to_add": _round_credits(credit_diff * ratio),
        "remaining_ratio": ratio,
    }


def _compute_annual_upgrade_proration(
    *, current_plan_credit: float, current_annual_price: float, new_plan: Dict[str, Any],
    annual_period_start: Optional[datetime], annual_period_end: Optional[datetime],
    credit_cycle_start: Optional[datetime], credit_cycle_end: Optional[datetime], now: datetime,
) -> Dict[str, Any]:
    """Annual same-periodicity upgrade (spec section 3): the ANNUAL price
    difference is prorated against time remaining in the paid annual
    period, but the credit difference is prorated against time remaining
    in the CURRENT MONTHLY allocation sub-cycle -- two distinct ratios,
    per the spec's explicit "deux calculs distincts" instruction."""
    price_ratio = _remaining_ratio(annual_period_start, annual_period_end, now)
    credit_ratio = _remaining_ratio(credit_cycle_start, credit_cycle_end, now)
    price_diff = _annual_price_for_plan(new_plan) - float(current_annual_price or 0)
    credit_diff = float(new_plan.get("credit") or 0) - float(current_plan_credit or 0)
    return {
        "amount_due_today": _round_price(price_diff * price_ratio),
        "credits_to_add": _round_credits(credit_diff * credit_ratio),
        "remaining_ratio": price_ratio,
        "credit_remaining_ratio": credit_ratio,
    }


def _assert_upgrade_amounts_are_consistent(amount_due_today: float, credits_to_add: int) -> None:
    """ordre says this is an upgrade -- if the resulting price or credit
    delta computes negative anyway, the catalog is misconfigured (ordre
    direction disagreeing with actual price/credit). Refuse outright
    rather than silently charging/crediting a negative amount or
    reinterpreting the request as a downgrade (spec section 3)."""
    if amount_due_today < 0 or credits_to_add < 0:
        raise _coded_error(
            409, "plan_change_inconsistent_configuration",
            "Cette offre est classee comme une montee en gamme, mais son prix ou son quota de "
            "credits calcule est inferieur a l'offre actuelle. Contactez le support.",
            amount_due_today=amount_due_today, credits_to_add=credits_to_add,
        )


async def _assert_plan_change_social_accounts_within_limits(user_id: str, new_plan: Dict[str, Any]) -> None:
    """Blocks a plan change that would leave the account over the new
    plan's connected-account allowance -- there's no generic "block new
    social account connections over limit" enforcement elsewhere, so this
    is the only safety net available and applies to every classification,
    including a SCHEDULED downgrade (it would be too late to catch this
    once the schedule fires on its own, unattended)."""
    new_max_social = max(1, int(new_plan.get("max_social_account") or 1))
    counts = await _count_social_accounts_by_platform(user_id)
    over_limit_platforms = {platform: count for platform, count in counts.items() if count > new_max_social}
    if over_limit_platforms:
        details = ", ".join(f"{platform} ({count}/{new_max_social})" for platform, count in over_limit_platforms.items())
        raise _coded_error(
            409, "plan_change_over_limit",
            f"Cette offre autorise au maximum {new_max_social} compte(s) par reseau social. "
            f"Supprimez les comptes en surplus avant de changer d'offre : {details}.",
            max=new_max_social, details=details,
        )


def _extract_subscription_period_end(stripe_subscription: "stripe.Subscription") -> Optional[int]:
    """current_period_end moved from the Subscription object to its items
    in a 2025 Stripe API version -- try both locations. A real
    stripe.StripeObject only reliably supports bracket access here:
    .get() raises a guided AttributeError ("is a dict method, but a
    Subscription is not a dict") since StripeObject isn't a dict, so this
    must never call it."""
    try:
        return stripe_subscription["current_period_end"]
    except (KeyError, TypeError):
        pass
    try:
        return stripe_subscription["items"]["data"][0]["current_period_end"]
    except (KeyError, IndexError, TypeError):
        return None


async def _change_plan_via_fresh_checkout(
    request: Request, user_id: str, subscription: Dict[str, Any], new_plan: Dict[str, Any],
) -> Dict[str, Any]:
    """Legacy pre-recurring-billing subscription (see
    _get_active_stripe_souscription's docstring) -- there is no Stripe
    Subscription to modify in place, so "changing plan" here means
    subscribing fresh via a real mode="subscription" Checkout.
    _create_recurring_subscription_checkout validates new_plan's price
    itself; the old row is only retired once that Checkout actually
    completes (see _handle_subscription_purchase)."""
    default_base_url = _frontend_base_url(request)
    return await _create_recurring_subscription_checkout(
        request, user_id, new_plan,
        success_url=f"{default_base_url}/dashboard/settings?plan_change=success",
        cancel_url=f"{default_base_url}/dashboard/settings?plan_change=cancel",
        previous_souscription_id=str(subscription["id"]),
        billing_interval=subscription.get("billing_interval") or "month",
    )


def _apply_recurring_plan_change(
    subscription: Dict[str, Any], new_plan: Dict[str, Any],
) -> "stripe.Subscription":
    """Swaps an already-recurring subscription's price in place for an
    IMMEDIATE upgrade -- the counterpart of _change_plan_via_fresh_checkout
    for a subscription that already has a real Stripe Subscription to
    modify. proration_behavior="none": the custom-computed proration
    (_compute_monthly_upgrade_proration/_compute_annual_upgrade_proration)
    is charged separately as its own exact invoice
    (_charge_plan_change_proration) -- letting Stripe ALSO auto-generate
    its own proration invoice item here would double-charge the
    difference and could disagree with the amount already shown to the
    user. Changing plan never changes billing_interval here -- the new
    price keeps whichever cadence (monthly/annual) the current
    subscription already bills on, re-priced for new_plan at that cadence
    (see _annual_price_for_plan)."""
    billing_interval = subscription.get("billing_interval") or "month"
    price_amount = _annual_price_for_plan(new_plan) if billing_interval == "year" else float(new_plan.get("price") or 0)
    try:
        unit_amount = int(round(price_amount * 100))
    except (TypeError, ValueError):
        raise _coded_error(400, "invalid_plan_price", _INVALID_PLAN_PRICE)
    if unit_amount <= 0:
        raise _coded_error(400, "invalid_plan_price", _INVALID_PLAN_PRICE)

    try:
        stripe_subscription = stripe.Subscription.retrieve(subscription["stripe_subscription_id"])
        item_id = stripe_subscription["items"]["data"][0]["id"]
        existing_metadata = stripe_subscription.metadata.to_dict() if stripe_subscription.metadata else {}
        # The next auto-renewal invoice reads abonnement off the
        # Subscription's own metadata (_handle_subscription_renewal_invoice)
        # -- without updating it here, the following month would still
        # credit the OLD plan even though this call charged for the new one.
        new_metadata = {
            **existing_metadata,
            "abonnement": str(new_plan.get("id")),
            "plan_name": str(new_plan.get("name") or ""),
            "billing_interval": billing_interval,
        }
        # Subscription items only accept an existing product id in
        # price_data (unlike Checkout Session line items, which allow
        # inline product_data) -- Stripe rejects product_data here with
        # "Received unknown parameter: items[0][price_data][product_data]".
        # Price.create does support product_data to create the product and
        # price together, giving a price id usable below.
        new_price = stripe.Price.create(
            currency=STRIPE_CURRENCY,
            unit_amount=unit_amount,
            recurring={"interval": billing_interval},
            product_data={
                "name": str(new_plan.get("name") or "Abonnement"),
                # Unlike Checkout Session's line_items[].price_data.product_data
                # (create_stripe_checkout_session), Price.create's product_data
                # does not accept "description" -- Stripe rejects it with
                # "Received unknown parameter: product_data[description]".
                # tax_code is required once Stripe Tax/Managed Payments is on
                # for the account, or Subscription.modify rejects the item
                # with "the product tax code is missing".
                "tax_code": "txcd_10103001",
            },
        )
        return stripe.Subscription.modify(
            subscription["stripe_subscription_id"],
            items=[{"id": item_id, "price": new_price.id}],
            proration_behavior="none",
            metadata=new_metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")


def _compute_plan_change_proration(
    subscription: Dict[str, Any], current_plan: Dict[str, Any], new_plan: Dict[str, Any],
    billing_interval: str, now: datetime,
) -> Dict[str, Any]:
    """Dispatches to the monthly or annual upgrade-proration formula
    (spec section 3) using this subscription's own stored dates --
    payment_start_date/payment_end_date for the paid period, and (for an
    annual subscription only) credit_cycle_start_at/credit_cycle_end_at
    for the current monthly credit sub-cycle. current_plan is read live
    from the catalog (its nominal price never needs its own snapshot,
    unlike plan_credit, since _assert_upgrade_amounts_are_consistent
    would catch a stale/misconfigured price anyway)."""
    current_plan_credit = float(subscription.get("plan_credit") or 0.0)
    period_start = _parse_iso_datetime(subscription.get("payment_start_date"))
    period_end = _parse_iso_datetime(subscription.get("payment_end_date"))
    if billing_interval == "year":
        credit_cycle_start = _parse_iso_datetime(subscription.get("credit_cycle_start_at")) or period_start
        credit_cycle_end = _parse_iso_datetime(subscription.get("credit_cycle_end_at")) or period_end
        return _compute_annual_upgrade_proration(
            current_plan_credit=current_plan_credit,
            current_annual_price=_annual_price_for_plan(current_plan),
            new_plan=new_plan,
            annual_period_start=period_start, annual_period_end=period_end,
            credit_cycle_start=credit_cycle_start, credit_cycle_end=credit_cycle_end, now=now,
        )
    return _compute_monthly_upgrade_proration(
        current_plan_credit=current_plan_credit, current_plan_price=float(current_plan.get("price") or 0),
        new_plan=new_plan, period_start=period_start, period_end=period_end, now=now,
    )


def _charge_plan_change_proration(
    customer_id: Optional[str], amount_due_today: float, description: str, idempotency_key: Optional[str] = None,
) -> None:
    """Charges exactly `amount_due_today` -- the custom proration
    computed by _compute_plan_change_proration, never Stripe's own
    proration engine -- off-session against the customer's card on file,
    via a one-off invoice. A no-op when there's nothing to charge (0,
    e.g. a plan with an identical price but more credits). Raises before
    anything else about the plan change is touched, so a declined card
    or any other payment failure leaves the current plan fully in place
    (spec section 3: "en cas d'echec de paiement... conserve l'offre
    actuelle"); there is no browser redirect step here to be fooled by a
    bare "return" from one -- this entire path is a synchronous
    server-side call.

    idempotency_key, when given, is suffixed per Stripe call (each needs
    its own) so a retried request for the SAME upgrade (double-submit, a
    client retry after a timeout, ...) reuses the same Stripe objects
    instead of charging the card twice -- this only protects the Stripe
    side; see change_souscription_plan's docstring for the remaining
    crash window between a successful charge and the local bookkeeping
    that follows it."""
    if amount_due_today <= 0:
        return
    if not customer_id:
        raise _coded_error(409, "plan_change_missing_payment_method", "Aucun moyen de paiement enregistre pour ce compte.")
    unit_amount = int(round(amount_due_today * 100))
    item_kwargs = {"idempotency_key": f"{idempotency_key}_item"} if idempotency_key else {}
    invoice_kwargs = {"idempotency_key": f"{idempotency_key}_invoice"} if idempotency_key else {}
    pay_kwargs = {"idempotency_key": f"{idempotency_key}_pay"} if idempotency_key else {}
    try:
        stripe.InvoiceItem.create(
            customer=customer_id, amount=unit_amount, currency=STRIPE_CURRENCY, description=description, **item_kwargs,
        )
        invoice = stripe.Invoice.create(
            customer=customer_id, auto_advance=True, collection_method="charge_automatically", description=description,
            **invoice_kwargs,
        )
        invoice = stripe.Invoice.finalize_invoice(invoice.id)
        stripe.Invoice.pay(invoice.id, **pay_kwargs)
    except stripe.error.CardError as exc:
        raise _coded_error(402, "plan_change_payment_failed", f"Paiement refuse : {getattr(exc, 'user_message', None) or exc}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")


async def _cancel_scheduled_plan_change(user_id: str, subscription: Dict[str, Any]) -> None:
    """Releases the Stripe Subscription Schedule driving a pending
    downgrade/periodicity change (see _create_or_replace_plan_change_
    schedule) and clears its local mirror columns -- the subscription
    reverts to auto-renewing on its current (unchanged) terms, exactly as
    if the change had never been scheduled."""
    schedule_id = subscription.get("stripe_schedule_id")
    if schedule_id:
        try:
            stripe.SubscriptionSchedule.release(schedule_id)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")
    await supabase_update_souscription_row(
        str(subscription["id"]),
        {
            "scheduled_abonnement_id": None, "scheduled_billing_interval": None,
            "scheduled_effective_at": None, "scheduled_created_at": None,
            "stripe_schedule_id": None,
        },
        user_id=user_id,
    )


def _create_or_replace_plan_change_schedule(
    subscription: Dict[str, Any], new_plan: Dict[str, Any], new_interval: str,
) -> Tuple[str, datetime]:
    """Creates (replacing one already pending, if any) the Stripe
    Subscription Schedule that defers a downgrade or periodicity change
    to the end of the already-paid period (spec sections 4/5): phase 1 is
    the subscription exactly as it is today, ending at its own current
    Stripe period end; phase 2 starts there with the new plan's price and
    metadata. Stripe raises the normal renewal invoice for phase 2 itself
    -- the EXISTING _handle_subscription_renewal_invoice webhook applies
    it unmodified, so there is no second, parallel billing path and the
    underlying Subscription object (and its id) never changes. Returns
    (schedule_id, effective_at)."""
    stripe_subscription_id = subscription["stripe_subscription_id"]
    try:
        stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        current_period_end = _extract_subscription_period_end(stripe_subscription)
        if not current_period_end:
            raise _coded_error(502, "plan_change_schedule_failed", "Impossible de determiner la date de fin de periode en cours.")

        existing_metadata = stripe_subscription.metadata.to_dict() if stripe_subscription.metadata else {}
        current_item = stripe_subscription["items"]["data"][0]
        current_price_id = current_item["price"]["id"]

        price_amount = _annual_price_for_plan(new_plan) if new_interval == "year" else float(new_plan.get("price") or 0)
        unit_amount = int(round(price_amount * 100))
        if unit_amount <= 0:
            raise _coded_error(400, "invalid_plan_price", _INVALID_PLAN_PRICE)
        new_price = stripe.Price.create(
            currency=STRIPE_CURRENCY, unit_amount=unit_amount, recurring={"interval": new_interval},
            product_data={"name": str(new_plan.get("name") or "Abonnement"), "tax_code": "txcd_10103001"},
        )
        new_metadata = {
            **existing_metadata,
            "abonnement": str(new_plan.get("id")),
            "plan_name": str(new_plan.get("name") or ""),
            "billing_interval": new_interval,
        }

        # A subscription already governed by a schedule can't be adopted
        # into a new one -- release whichever one this row was already
        # pending on (replacing it) before attaching the fresh pair of
        # phases below.
        existing_schedule_id = subscription.get("stripe_schedule_id")
        if existing_schedule_id:
            try:
                stripe.SubscriptionSchedule.release(existing_schedule_id)
            except Exception:
                logger.warning("Failed to release previous schedule %s before replacing it", existing_schedule_id, exc_info=True)

        schedule = stripe.SubscriptionSchedule.create(from_subscription=stripe_subscription_id)
        phase_zero_start = schedule["phases"][0]["start_date"]
        schedule = stripe.SubscriptionSchedule.modify(
            schedule.id,
            end_behavior="release",
            phases=[
                {
                    "items": [{"price": current_price_id, "quantity": 1}],
                    "start_date": phase_zero_start,
                    "end_date": current_period_end,
                    "metadata": existing_metadata,
                },
                {
                    "items": [{"price": new_price.id, "quantity": 1}],
                    "start_date": current_period_end,
                    "iterations": 1,
                    "proration_behavior": "none",
                    "metadata": new_metadata,
                },
            ],
        )
        return schedule.id, datetime.fromtimestamp(current_period_end, tz=timezone.utc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc}")


async def _apply_scheduled_plan_change(
    user_id: str, subscription: Dict[str, Any], new_plan: Dict[str, Any], new_interval: str, classification: str,
) -> Dict[str, Any]:
    """Schedules a downgrade or periodicity change (classifications
    PLAN_CHANGE_DOWNGRADE_SCHEDULED / PLAN_CHANGE_PERIODICITY_SCHEDULED).
    No charge, no credit/storage change now -- current_plan/features keep
    running unchanged until Stripe's own renewal invoice applies the new
    plan at the correct boundary (spec sections 4/5: next monthly renewal
    for a monthly subscription, next ANNUAL renewal -- never the monthly
    credit-allocation anniversary -- for an annual one)."""
    if not subscription.get("stripe_subscription_id"):
        raise _coded_error(
            409, "plan_change_requires_recurring_subscription",
            "Cet abonnement ne peut pas etre programme automatiquement. Contactez le support.",
        )
    if subscription.get("auto_renew") is False:
        raise _coded_error(
            409, "plan_change_subscription_cancelled",
            "Cet abonnement est deja resilie en fin de periode -- reactivez-le avant de programmer un changement d'offre.",
        )

    schedule_id, effective_at = _create_or_replace_plan_change_schedule(subscription, new_plan, new_interval)
    await supabase_update_souscription_row(
        str(subscription["id"]),
        {
            "scheduled_abonnement_id": str(new_plan.get("id")),
            "scheduled_billing_interval": new_interval,
            "scheduled_effective_at": effective_at.isoformat(),
            "scheduled_created_at": datetime.now(timezone.utc).isoformat(),
            "stripe_schedule_id": schedule_id,
        },
        user_id=user_id,
    )
    return {
        "classification": classification,
        "scheduled_abonnement_id": str(new_plan.get("id")),
        "scheduled_abonnement_name": str(new_plan.get("name") or ""),
        "scheduled_billing_interval": new_interval,
        "scheduled_effective_at": effective_at.isoformat(),
    }


async def _finalize_immediate_upgrade(
    user_id: str, request: Optional[Request], subscription: Dict[str, Any], new_plan: Dict[str, Any],
    updated_stripe_subscription: "stripe.Subscription", proration: Dict[str, Any],
) -> Dict[str, Any]:
    """Persists an immediate upgrade once its custom-prorated charge has
    already succeeded (_charge_plan_change_proration): retires the old
    row, records the new one carrying the SAME renewal/credit-cycle
    dates forward (spec section 3: "conserve les dates... existantes"),
    and tops up credit/storage by a DELTA on top of the current balance
    -- never a reset, so neither the existing balance nor its own
    expiration is touched (spec section 6)."""
    now = datetime.now(timezone.utc)
    billing_interval = subscription.get("billing_interval") or "month"

    current_period_end_ts = _extract_subscription_period_end(updated_stripe_subscription)
    period_end = (
        datetime.fromtimestamp(current_period_end_ts, tz=timezone.utc)
        if current_period_end_ts else _parse_iso_datetime(subscription.get("payment_end_date"))
    )
    credit_cycle_start = _parse_iso_datetime(subscription.get("credit_cycle_start_at")) or _parse_iso_datetime(subscription.get("payment_start_date")) or now
    credit_cycle_end = _parse_iso_datetime(subscription.get("credit_cycle_end_at")) or period_end
    next_allocation = _parse_iso_datetime(subscription.get("next_credit_allocation_at"))

    # Same "close the superseded row out" reasoning as before: both rows
    # would otherwise carry the same payment_end_date and both match
    # get_user_abonnement's "active" filter at once.
    await supabase_update_souscription_row(
        str(subscription["id"]), {"payment_end_date": now.isoformat()}, user_id=user_id,
    )

    new_plan_credit = float(new_plan.get("credit") or 0)
    new_plan_storage = float(new_plan.get("stockage") or 0)
    plan_amount = proration["amount_due_today"]

    new_souscription = await supabase_insert_souscription(
        user_id=user_id,
        abonnement=str(new_plan.get("id")),
        payment_mode="stripe",
        payment_amount=plan_amount,
        payment_reference=f"planchange_{subscription['stripe_subscription_id']}_{int(now.timestamp())}",
        payment_status="completed",
        payment_comment=f"Plan upgraded to {new_plan.get('name')} (prorated)",
        payment_date=now,
        period_end_date=period_end,
        stripe_subscription_id=subscription["stripe_subscription_id"],
        stripe_customer_id=subscription.get("stripe_customer_id"),
        billing_interval=billing_interval,
        plan_credit=new_plan_credit,
        plan_stockage=new_plan_storage,
        next_credit_allocation_at=next_allocation,
        credit_cycle_start_at=credit_cycle_start,
        credit_cycle_end_at=credit_cycle_end,
    )
    new_souscription_id = str(new_souscription.get("id") or "")

    storage_delta = new_plan_storage - float(subscription.get("plan_stockage") or 0.0)
    await supabase_upsert_user_data_credits(
        user_id=user_id,
        credit_delta=float(proration["credits_to_add"]),
        storage_delta=storage_delta,
        update_credit_max=True,
        update_stockage_max=True,
        operation_type=PLAN_CHANGE_UPGRADE_OPERATION_TYPE,
        operation_id=new_souscription_id,
    )
    await supabase_insert_user_data_history(
        user_id=user_id,
        credit=float(proration["credits_to_add"]),
        storage=storage_delta,
        operation="input",
        operation_type=PLAN_CHANGE_UPGRADE_OPERATION_TYPE,
        operation_id=new_souscription_id,
    )
    await supabase_set_user_max_daily_publications(user_id, new_plan.get("max_daily_publications") or 0)

    _send_transactional_email(
        _user_email_from_request(request), "subscription_plan_changed",
        plan_name=str(new_plan.get("name") or "Vireel"), amount=plan_amount,
    )
    return new_souscription


async def _apply_immediate_upgrade(
    user_id: str, request: Optional[Request], subscription: Dict[str, Any],
    current_plan: Dict[str, Any], new_plan: Dict[str, Any], confirm_cancel_scheduled: bool,
) -> Dict[str, Any]:
    """Applies classification PLAN_CHANGE_UPGRADE_IMMEDIATE (spec section
    3): computes the custom proration, refuses an internally-inconsistent
    catalog, requires explicit confirmation to proceed if it would cancel
    an already-scheduled change (spec section 4's last sentence), charges
    that exact amount, and only then mutates anything local or on Stripe."""
    billing_interval = subscription.get("billing_interval") or "month"
    now = datetime.now(timezone.utc)

    if not subscription.get("stripe_subscription_id"):
        raise _coded_error(
            409, "plan_change_requires_recurring_subscription",
            "Cet abonnement ne peut pas etre mis a niveau automatiquement. Contactez le support.",
        )

    proration = _compute_plan_change_proration(subscription, current_plan, new_plan, billing_interval, now)
    _assert_upgrade_amounts_are_consistent(proration["amount_due_today"], proration["credits_to_add"])

    has_scheduled_change = bool(subscription.get("scheduled_abonnement_id"))
    if has_scheduled_change and not confirm_cancel_scheduled:
        scheduled_plan = await supabase_get_abonnement(str(subscription.get("scheduled_abonnement_id")))
        raise _coded_error(
            409, "plan_change_scheduled_change_exists",
            "Un changement est deja programme sur cet abonnement. Confirmez pour l'annuler et appliquer "
            "cette montee immediatement.",
            scheduled_abonnement_name=(scheduled_plan or {}).get("name") or subscription.get("scheduled_abonnement_id"),
        )

    description = f"Montee vers {new_plan.get('name')} (prorata)"
    # Stable for as long as this exact upgrade (same subscription, same
    # target plan, same already-paid period) could be retried -- a
    # second attempt reuses the same Stripe objects instead of charging
    # twice (see _charge_plan_change_proration's docstring).
    idempotency_key = f"planchange_{subscription['stripe_subscription_id']}_{new_plan.get('id')}_{subscription.get('payment_end_date')}"
    _charge_plan_change_proration(
        subscription.get("stripe_customer_id"), proration["amount_due_today"], description, idempotency_key=idempotency_key,
    )

    if has_scheduled_change:
        await _cancel_scheduled_plan_change(user_id, subscription)

    updated_stripe_subscription = _apply_recurring_plan_change(subscription, new_plan)
    return await _finalize_immediate_upgrade(user_id, request, subscription, new_plan, updated_stripe_subscription, proration)


class ChangeSubscriptionPlanRequest(BaseModel):
    plan_id: str
    billing_interval: Optional[str] = None
    confirm_cancel_scheduled: bool = False


@app.post("/api/souscription/change-plan", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def change_souscription_plan(
    payload: ChangeSubscriptionPlanRequest, user_id: Annotated[str, Depends(get_user_id_header)],
    request: Request = None,
):
    """Centralized plan-change entry point (plan-change rework spec).
    Classifies the request using ONLY abonnement.ordre (_classify_plan_change)
    and dispatches: an upgrade at the same periodicity applies immediately
    with custom proration (_apply_immediate_upgrade); a downgrade or a
    periodicity change is deferred to the end of the already-paid period
    via a Stripe Subscription Schedule (_apply_scheduled_plan_change); the
    same plan+periodicity is a no-op; a lateral or unclassifiable (ordre
    absent/invalid) change is refused outright, with nothing touched."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await get_user_abonnement(user_id)
    if not subscription:
        raise _coded_error(404, "no_active_subscription", "No active subscription")

    current_plan = await supabase_get_abonnement(str(subscription.get("abonnement") or ""))
    if not current_plan:
        raise _coded_error(409, "plan_change_invalid_order", "L'offre actuelle n'est plus disponible pour evaluer ce changement.")

    new_plan = await supabase_get_abonnement(payload.plan_id)
    if not new_plan:
        raise _coded_error(404, "plan_not_found", "Subscription plan not found")

    current_interval = subscription.get("billing_interval") or "month"
    new_interval = payload.billing_interval or current_interval
    if new_interval not in ("month", "year"):
        raise _coded_error(400, "invalid_billing_interval", "billing_interval doit etre 'month' ou 'year'.")

    classification = _classify_plan_change(current_plan, new_plan, current_interval, new_interval)

    if classification == PLAN_CHANGE_NOOP:
        return {"classification": PLAN_CHANGE_NOOP, "changed": False}
    if classification == PLAN_CHANGE_INVALID:
        raise _coded_error(409, "plan_change_invalid_order", "Cette offre ne peut pas etre evaluee (ordre manquant ou invalide).")
    if classification == PLAN_CHANGE_LATERAL_UNSUPPORTED:
        raise _coded_error(409, "plan_change_lateral_unsupported", "Le changement vers une offre de meme rang n'est pas pris en charge.")

    await _assert_plan_change_social_accounts_within_limits(user_id, new_plan)

    if not subscription.get("stripe_subscription_id"):
        # Legacy pre-recurring-billing subscription (see
        # _get_active_stripe_souscription's docstring) -- there is no
        # Stripe Subscription to modify or schedule. Only a same-
        # periodicity upgrade can still go through a fresh Checkout;
        # a deferred change has no recurring object to attach to.
        if classification == PLAN_CHANGE_UPGRADE_IMMEDIATE:
            return await _change_plan_via_fresh_checkout(request, user_id, subscription, new_plan)
        raise _coded_error(
            409, "plan_change_requires_recurring_subscription",
            "Cet abonnement ne peut pas etre programme automatiquement. Contactez le support.",
        )

    if classification == PLAN_CHANGE_UPGRADE_IMMEDIATE:
        return await _apply_immediate_upgrade(user_id, request, subscription, current_plan, new_plan, payload.confirm_cancel_scheduled)

    return await _apply_scheduled_plan_change(user_id, subscription, new_plan, new_interval, classification)


@app.post("/api/souscription/change-plan/cancel-scheduled", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def cancel_scheduled_plan_change(user_id: Annotated[str, Depends(get_user_id_header)]):
    """Cancels this subscription's single pending scheduled change (spec
    section 4), reverting it to auto-renew on its current, unchanged
    terms."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    subscription = await get_user_abonnement(user_id)
    if not subscription:
        raise _coded_error(404, "no_active_subscription", "No active subscription")
    if not subscription.get("scheduled_abonnement_id"):
        raise _coded_error(404, "no_scheduled_change", "Aucun changement programme sur cet abonnement.")
    await _cancel_scheduled_plan_change(user_id, subscription)
    return {"cancelled": True}


@app.get("/api/souscription/change-plan/preview", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def preview_souscription_plan_change(
    user_id: Annotated[str, Depends(get_user_id_header)],
    plan_id: str,
    billing_interval: Optional[str] = None,
):
    """Backend-computed pre-confirmation summary (spec section 8) -- uses
    the EXACT same classification and proration functions as the real
    change endpoint, so the amount shown here can never disagree with
    what actually gets charged."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    subscription = await get_user_abonnement(user_id)
    if not subscription:
        raise _coded_error(404, "no_active_subscription", "No active subscription")

    current_plan = await supabase_get_abonnement(str(subscription.get("abonnement") or ""))
    if not current_plan:
        raise _coded_error(409, "plan_change_invalid_order", "L'offre actuelle n'est plus disponible pour evaluer ce changement.")

    new_plan = await supabase_get_abonnement(plan_id)
    if not new_plan:
        raise _coded_error(404, "plan_not_found", "Subscription plan not found")

    current_interval = subscription.get("billing_interval") or "month"
    new_interval = billing_interval or current_interval
    if new_interval not in ("month", "year"):
        raise _coded_error(400, "invalid_billing_interval", "billing_interval doit etre 'month' ou 'year'.")

    classification = _classify_plan_change(current_plan, new_plan, current_interval, new_interval)
    now = datetime.now(timezone.utc)

    summary: Dict[str, Any] = {
        "classification": classification,
        "current_plan_name": current_plan.get("name"),
        "current_billing_interval": current_interval,
        "new_plan_name": new_plan.get("name"),
        "new_billing_interval": new_interval,
        "will_cancel_scheduled_change": bool(subscription.get("scheduled_abonnement_id")),
        "annual_billing_copy_required": new_interval == "year",
    }

    if classification == PLAN_CHANGE_UPGRADE_IMMEDIATE:
        proration = _compute_plan_change_proration(subscription, current_plan, new_plan, current_interval, now)
        amount_due_today = proration["amount_due_today"]
        credits_to_add = proration["credits_to_add"]
        inconsistent = amount_due_today < 0 or credits_to_add < 0

        user_data = await supabase_get_user_data(user_id)
        current_credit = float((user_data or {}).get("credit") or 0.0)
        promotional_batches = await supabase_list_active_promotional_credit_batches(user_id)
        promotional_credit = sum(float(b.get("amount_remaining") or 0.0) for b in promotional_batches)

        next_price = _annual_price_for_plan(new_plan) if current_interval == "year" else float(new_plan.get("price") or 0)
        summary.update({
            "effective_at": now.isoformat(),
            "amount_due_today": amount_due_today,
            "inconsistent_configuration": inconsistent,
            "credits_added_now": credits_to_add,
            "credits_added_expires_at": subscription.get("credit_cycle_end_at") or subscription.get("payment_end_date"),
            "resulting_credit_balance": current_credit + promotional_credit + (credits_to_add if not inconsistent else 0),
            "future_monthly_credit_quota": float(new_plan.get("credit") or 0),
            "next_amount": next_price,
            "next_billing_date": subscription.get("payment_end_date"),
        })
    elif classification in (PLAN_CHANGE_DOWNGRADE_SCHEDULED, PLAN_CHANGE_PERIODICITY_SCHEDULED):
        effective_at = subscription.get("payment_end_date")
        summary.update({
            "effective_at": effective_at,
            "amount_due_today": 0.0,
            "credits_added_now": 0,
            "future_monthly_credit_quota": float(new_plan.get("credit") or 0),
            "next_amount": _annual_price_for_plan(new_plan) if new_interval == "year" else float(new_plan.get("price") or 0),
            "next_billing_date": effective_at,
        })
    else:
        summary.update({"effective_at": None, "amount_due_today": 0.0, "credits_added_now": 0})

    return summary


# ---------------------------------------------------------------------------
# User credits & history
# ---------------------------------------------------------------------------

@app.get("/api/user/credits", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def get_user_credits(request: Request, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Return the credit/storage balance for the authenticated user."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    await _enforce_subscription_retention_policy(user_id)

    abonnement = await get_user_abonnement(user_id)
    has_active_subscription = bool(abonnement)

    data = await supabase_get_user_data(user_id)
    bonus_batches = await supabase_list_active_promotional_credit_batches(user_id)
    # Two distinct, independently-expiring bonus pools sharing the same
    # table (see the credit-tiers migration) -- always consumed in order
    # promotional, then purchased, then (last) the plain subscription
    # `credit` field below. Keeping them split here (never summed into
    # one "bonus_credit") lets the wallet UI label each one correctly.
    promotional_batches = [b for b in bonus_batches if int(b.get("tier") or CREDIT_BATCH_TIER_PROMOTIONAL) == CREDIT_BATCH_TIER_PROMOTIONAL]
    purchased_batches = [b for b in bonus_batches if int(b.get("tier") or CREDIT_BATCH_TIER_PROMOTIONAL) == CREDIT_BATCH_TIER_PURCHASED]
    promotional_credit = sum(float(batch.get("amount_remaining") or 0.0) for batch in promotional_batches)
    purchased_credit = sum(float(batch.get("amount_remaining") or 0.0) for batch in purchased_batches)
    # Soonest-expiry-first, matching the batches' own FEFO consumption
    # order -- the wallet UI (section 15) shows this so a user understands
    # why Vireel is about to consume certain credits before others.
    promotional_credit_expirations = [
        {"amount": float(batch.get("amount_remaining") or 0.0), "expires_at": batch.get("expires_at")}
        for batch in promotional_batches
    ]
    purchased_credit_expirations = [
        {"amount": float(batch.get("amount_remaining") or 0.0), "expires_at": batch.get("expires_at")}
        for batch in purchased_batches
    ]

    if not data:
        return {
            "credit":   0.0,
            "credit_max": 0.0,
            "promotional_credit": promotional_credit,
            "promotional_credit_expirations": promotional_credit_expirations,
            "purchased_credit": purchased_credit,
            "purchased_credit_expirations": purchased_credit_expirations,
            "has_credits": (promotional_credit + purchased_credit) > 0,
            "has_active_subscription": has_active_subscription,
            "has_analytics_access": bool(abonnement) and int(abonnement.get("priorite") or 1) >= 2,
            "abo_costs": {
                "credit":  0.0,
            },
            "default_costs": {
                "reel":        DEFAULT_REEL_CREDITS,
                "caption":     DEFAULT_CAPTION_CREDITS,
                "publication": 0.0,
            },
        }

    credit = float(data.get("credit", 0) or 0.0)
    credit_max = float(data.get("credit_max", credit) or 0.0)

    if not abonnement:
        abo_costs = {
            "credit":  0.0,
        }
    else:
        abo_costs = {
            "credit":  float(abonnement.get("credit",   0)),
        }

    return {
        "credit":   credit,
        "credit_max": credit_max,
        "promotional_credit": promotional_credit,
        "promotional_credit_expirations": promotional_credit_expirations,
        "purchased_credit": purchased_credit,
        "purchased_credit_expirations": purchased_credit_expirations,
        "has_credits": (credit + promotional_credit + purchased_credit) > 0,
        "has_active_subscription": has_active_subscription,
        "has_analytics_access": bool(abonnement) and int(abonnement.get("priorite") or 1) >= 2,
        "abo_costs": abo_costs,
        "default_costs": {
            "reel":        DEFAULT_REEL_CREDITS,
            "caption":     DEFAULT_CAPTION_CREDITS,
            "publication": 0.0,
        },
    }


@app.get("/api/user/history", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def get_user_history(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Return paginated credit/storage history for the authenticated user."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    rows, total = await supabase_get_user_data_history(user_id, page=page, page_size=page_size)
    return {
        "items":     rows,
        "total":     total,
        "page":      page,
        "page_size": page_size,
    }


# ---------------------------------------------------------------------------
# Referral program
# ---------------------------------------------------------------------------

class AssociateReferralRequest(BaseModel):
    referral_code: str


@app.get("/api/referrals/config")
async def get_referral_config():
    """Public reward configuration -- the frontend must never hardcode
    these amounts (see spec section 3): it always reads them from here so
    the "invite a friend" copy stays in sync with whatever the backend
    actually grants. A later env var change only ever affects REWARDS
    GRANTED AFTER that change -- see insert_promotional_credit_batch,
    which always fixes amount_initial/expires_at at grant time."""
    return {
        "signup_bonus_credits": REFERRAL_SIGNUP_BONUS_CREDITS,
        "monthly_bonus_credits": REFERRAL_MONTHLY_BONUS_CREDITS,
        "annual_bonus_credits": REFERRAL_ANNUAL_BONUS_CREDITS,
        "expiration_days": PROMOTIONAL_CREDITS_EXPIRATION_DAYS,
    }


@app.get("/api/referrals/me", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def get_my_referrals(request: Request, user_id: Annotated[str, Depends(get_user_id_header)]):
    """The authenticated user's own referral link, plus a privacy-minded
    summary of who they've referred (section 14: ordinal labels only, no
    referee email/name -- see dashboard/src/pages/ParrainagePage.jsx)."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    code = await supabase_get_or_create_referral_code(user_id)
    default_base_url = _frontend_base_url(request)

    rows = await supabase_list_referrals_by_referrer(user_id)
    referrals = [
        {
            "label": f"Filleul #{index}",
            "created_at": row.get("created_at"),
            "status": row.get("status"),
            "first_subscription_type": row.get("first_subscription_type"),
            "subscription_reward_granted_at": row.get("subscription_reward_granted_at"),
        }
        for index, row in enumerate(rows, start=1)
    ]

    return {
        "code": code,
        "link": f"{default_base_url}/r/{code}",
        "referred_count": len(rows),
        "rewarded_count": sum(1 for row in rows if row.get("subscription_reward_granted_at")),
        "referrals": referrals,
    }


def _get_client_ip(request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        client_ip = fwd.split(",")[0].strip()
    return client_ip


@app.post("/api/referrals/associate", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def associate_referral(
    request: Request, payload: AssociateReferralRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Associates the authenticated user with a referrer and grants the
    referee's signup bonus -- exactly once per user, ever. Called by the
    frontend right after a genuinely new signup (email/password or
    OAuth) completes; the association itself is still verified
    server-side (see get_auth_user_created_at) rather than trusted from
    the frontend's own "is this a new account" guess, since the frontend
    is never authoritative for a reward (section 12).

    Idempotent and deliberately unrevealing: a repeat call, a call for an
    already-referred account, or a self-referral attempt all come back as
    {"associated": false} rather than a distinct error that would let a
    caller probe whether a code/account exists. Every grant and every
    suspicious rejection (self-referral, stale account) is logged with
    the caller's IP/user-agent -- not to block in real time, but so a
    later audit pass (mass account creation, the same IP farming many
    referred accounts, ...) has something to look at (section 12)."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    code = (payload.referral_code or "").strip()
    client_ip = _get_client_ip(request)
    user_agent = request.headers.get("user-agent", "")
    if not code:
        raise _coded_error(400, "invalid_referral_code", "Invalid referral code")

    referrer_user_id = await supabase_get_referral_code_owner(code)
    if not referrer_user_id:
        raise _coded_error(404, "referral_code_not_found", "Referral code not found")

    if referrer_user_id == user_id:
        logger.warning(
            "Self-referral attempt blocked for user %s (code=%s, ip=%s, ua=%s)",
            user_id, code, client_ip, user_agent,
        )
        return {"associated": False}

    if await supabase_get_referral_by_referred_user(user_id):
        return {"associated": False}

    created_at = await supabase_get_auth_user_created_at(user_id)
    if created_at is None or (datetime.now(timezone.utc) - created_at) > timedelta(minutes=REFERRAL_ASSOCIATION_WINDOW_MINUTES):
        logger.warning(
            "Referral association rejected for user %s: account not new enough "
            "(created_at=%s, ip=%s, ua=%s)",
            user_id, created_at, client_ip, user_agent,
        )
        return {"associated": False}

    referral, created = await supabase_insert_referral(referrer_user_id, user_id, code)
    if not created or not referral:
        return {"associated": False}

    logger.info(
        "Referral signup bonus granted: referrer=%s referee=%s code=%s ip=%s ua=%s",
        referrer_user_id, user_id, code, client_ip, user_agent,
    )

    batch = await supabase_insert_promotional_credit_batch(
        user_id, REFERRAL_SIGNUP_BONUS_CREDITS, "REFERRAL_SIGNUP", PROMOTIONAL_CREDITS_EXPIRATION_DAYS,
        source_reference=str(referral["id"]),
    )
    await supabase_update_referral_row(referral["id"], {
        "signup_reward_granted_at": datetime.now(timezone.utc).isoformat(),
        "signup_reward_batch_id": batch.get("id"),
    })

    await _create_notification(
        user_id, "referral_signup_bonus", "Bienvenue sur Vireel !",
        f"Tu as reçu {REFERRAL_SIGNUP_BONUS_CREDITS:.0f} crédits promotionnels de bienvenue.",
        {"amount": REFERRAL_SIGNUP_BONUS_CREDITS},
    )
    await _create_notification(
        referrer_user_id, "referral_referee_joined", "Un ami a rejoint Vireel !",
        "Quelqu'un vient de s'inscrire grâce à ton lien de parrainage.",
        {},
    )

    return {"associated": True, "signup_bonus_credits": REFERRAL_SIGNUP_BONUS_CREDITS}


def _require_admin_secret(x_admin_secret: Annotated[Optional[str], Header()] = None) -> None:
    """Minimal shared-secret gate for the handful of administrative
    endpoints this app has (see section 12: a referral can be
    invalidated administratively) -- consistent with this codebase's
    other secret-based protections (e.g. the Stripe webhook signature)
    rather than a new RBAC system for one endpoint."""
    if not ADMIN_API_SECRET or not x_admin_secret or not secrets.compare_digest(x_admin_secret, ADMIN_API_SECRET):
        raise HTTPException(status_code=403, detail="Forbidden")


class InvalidateReferralRequest(BaseModel):
    reason: str


@app.post("/api/admin/referrals/{referral_id}/invalidate", responses={403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def invalidate_referral_endpoint(
    referral_id: str, payload: InvalidateReferralRequest, _admin: Annotated[None, Depends(_require_admin_secret)],
):
    """Administrative kill switch for a fraudulent/abusive referral --
    never reachable by a normal user; see _require_admin_secret."""
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    row = await supabase_invalidate_referral(referral_id, payload.reason)
    if not row:
        raise _coded_error(404, "referral_not_found", "Referral not found")
    return row


# ---------------------------------------------------------------------------
# In-app notifications (generic, not email -- referrals are the first
# source of these, not the only one)
# ---------------------------------------------------------------------------

@app.get("/api/notifications", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def list_notifications_endpoint(
    user_id: Annotated[str, Depends(get_user_id_header)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    unread_only: bool = False,
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    items, unread_count = await supabase_list_notifications(user_id, limit=limit, unread_only=unread_only)
    return {"items": items, "unread_count": unread_count}


@app.post("/api/notifications/{notification_id}/read", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def mark_notification_read_endpoint(
    notification_id: str, user_id: Annotated[str, Depends(get_user_id_header)],
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    row = await supabase_mark_notification_read(notification_id, user_id)
    if not row:
        raise _coded_error(404, "notification_not_found", "Notification not found")
    return row


@app.post("/api/notifications/read-all", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def mark_all_notifications_read_endpoint(user_id: Annotated[str, Depends(get_user_id_header)]):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)
    count = await supabase_mark_all_notifications_read(user_id)
    return {"marked_read": count}


# ---------------------------------------------------------------------------
# Dashboard stats (internal KPI block) -- computed entirely from this app's
# own DB, no external calls.
# ---------------------------------------------------------------------------

_DASHBOARD_STATS_RANGE_TO_DAYS = {"7d": 7, "30d": 30, "90d": 90}
_DASHBOARD_STATS_MAX_DAILY_ENTRIES = 180


def _bucket_timestamps_by_day(timestamps: List[str]) -> Dict[str, int]:
    """Bucket a list of ISO-8601 timestamp strings into {"YYYY-MM-DD": count}.
    Postgres timestamptz ISO output always starts with the date, so a plain
    prefix slice is enough -- no timezone-aware parsing needed here."""
    buckets: Dict[str, int] = {}
    for ts in timestamps:
        if not ts or len(ts) < 10:
            continue
        day = ts[:10]
        buckets[day] = buckets.get(day, 0) + 1
    return buckets


def _bucket_credit_history_by_day(rows: List[Dict[str, Any]]) -> Dict[str, float]:
    buckets: Dict[str, float] = {}
    for row in rows:
        ts = row.get("created_at")
        if not ts or len(ts) < 10:
            continue
        day = ts[:10]
        buckets[day] = buckets.get(day, 0.0) + float(row.get("credit") or 0)
    return buckets


async def _fetch_dashboard_publish_rows(client, user_id: str, since_iso: Optional[str]) -> List[Dict[str, Any]]:
    query = client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).select("platform, created_at, status").eq("user_id", user_id)
    if since_iso:
        query = query.gte("created_at", since_iso)
    response = await query.execute()
    return response.data or []


async def _fetch_dashboard_credit_rows(client, user_id: str, since_iso: Optional[str]) -> List[Dict[str, Any]]:
    query = (
        client.table(SUPABASE_USER_DATA_HISTORY_TABLE)
        .select("credit, created_at, operation")
        .eq("user_id", user_id)
        .eq("operation", "output")
    )
    if since_iso:
        query = query.gte("created_at", since_iso)
    response = await query.execute()
    return response.data or []


def _aggregate_publication_rows(publish_rows: List[Dict[str, Any]]) -> Tuple[Dict[str, int], int, int, List[Dict[str, Any]]]:
    publications_daily: Dict[str, int] = {}
    publications_done = 0
    publications_failed = 0
    platform_counts: Dict[str, int] = {}
    for row in publish_rows:
        status = row.get("status")
        platform = str(row.get("platform") or "")
        if status == "done":
            publications_done += 1
            if platform:
                platform_counts[platform] = platform_counts.get(platform, 0) + 1
        elif status == "failed":
            publications_failed += 1
        ts = row.get("created_at")
        if ts and len(ts) >= 10:
            day = ts[:10]
            publications_daily[day] = publications_daily.get(day, 0) + 1

    publications_by_platform = sorted(
        ({"platform": platform, "count": count} for platform, count in platform_counts.items()),
        key=lambda entry: entry["count"],
        reverse=True,
    )
    return publications_daily, publications_done, publications_failed, publications_by_platform


def _resolve_dashboard_stats_start_date(since_dt: Optional[datetime], *daily_maps: Dict[str, Any]) -> Optional[date]:
    if since_dt is not None:
        return since_dt.date()
    all_days: set = set()
    for daily_map in daily_maps:
        all_days |= set(daily_map)
    if not all_days:
        return None
    return min(datetime.fromisoformat(day).date() for day in all_days)


def _build_dashboard_daily_series(
    start_date: date, today: date, reel_daily: Dict[str, int], caption_daily: Dict[str, int],
    story_daily: Dict[str, int], film_daily: Dict[str, int], publications_daily: Dict[str, int],
    credits_daily: Dict[str, float],
) -> List[Dict[str, Any]]:
    daily: List[Dict[str, Any]] = []
    day_cursor = start_date
    while day_cursor <= today:
        date_str = day_cursor.isoformat()
        daily.append({
            "date": date_str,
            "reels": reel_daily.get(date_str, 0),
            "captions": caption_daily.get(date_str, 0),
            "anonymous_stories": story_daily.get(date_str, 0),
            "film_summaries": film_daily.get(date_str, 0),
            "publications": publications_daily.get(date_str, 0),
            "credits_consumed": credits_daily.get(date_str, 0.0),
        })
        day_cursor += timedelta(days=1)
    if len(daily) > _DASHBOARD_STATS_MAX_DAILY_ENTRIES:
        daily = daily[-_DASHBOARD_STATS_MAX_DAILY_ENTRIES:]
    return daily


@app.get("/api/dashboard/stats", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def get_dashboard_stats(
    user_id: Annotated[str, Depends(get_user_id_header)],
    range: Annotated[str, Query()] = "30d",
):
    """Internal KPI/stats block for the dashboard home page: reels/captions/
    anonymous stories/film summaries created, publications by platform and
    credit consumption, bucketed per day. Computed entirely from this app's
    own DB -- no external (social platform) calls."""
    if range not in {"7d", "30d", "90d", "all"}:
        raise HTTPException(status_code=400, detail="range must be one of: 7d, 30d, 90d, all")

    empty_totals = {
        "reels": 0,
        "captions": 0,
        "anonymous_stories": 0,
        "film_summaries": 0,
        "publications_done": 0,
        "publications_failed": 0,
        "credits_consumed": 0.0,
    }

    if not is_supabase_configured():
        return {
            "range": range,
            "totals": empty_totals,
            "daily": [],
            "publications_by_platform": [],
        }

    since_dt: Optional[datetime] = None if range == "all" else _utcnow() - timedelta(days=_DASHBOARD_STATS_RANGE_TO_DAYS[range])
    since_iso = since_dt.isoformat() if since_dt else None

    reel_dates, caption_dates, story_dates, film_dates = await asyncio.gather(
        supabase_list_reel_dates_since(user_id, since_iso),
        supabase_list_caption_dates_since(user_id, since_iso),
        supabase_list_anonymous_story_dates_since(user_id, since_iso),
        supabase_list_film_summary_dates_since(user_id, since_iso),
    )

    client = await supabase_get_client()
    publish_rows = await _fetch_dashboard_publish_rows(client, user_id, since_iso)
    credit_rows = await _fetch_dashboard_credit_rows(client, user_id, since_iso)

    reel_daily = _bucket_timestamps_by_day(reel_dates)
    caption_daily = _bucket_timestamps_by_day(caption_dates)
    story_daily = _bucket_timestamps_by_day(story_dates)
    film_daily = _bucket_timestamps_by_day(film_dates)
    publications_daily, publications_done, publications_failed, publications_by_platform = _aggregate_publication_rows(publish_rows)
    credits_daily = _bucket_credit_history_by_day(credit_rows)

    totals = {
        "reels": len(reel_dates),
        "captions": len(caption_dates),
        "anonymous_stories": len(story_dates),
        "film_summaries": len(film_dates),
        "publications_done": publications_done,
        "publications_failed": publications_failed,
        "credits_consumed": sum(credits_daily.values()),
    }

    start_date = _resolve_dashboard_stats_start_date(
        since_dt, reel_daily, caption_daily, story_daily, film_daily, publications_daily, credits_daily,
    )
    if start_date is None:
        return {
            "range": range,
            "totals": totals,
            "daily": [],
            "publications_by_platform": publications_by_platform,
        }

    daily = _build_dashboard_daily_series(
        start_date, _utcnow().date(), reel_daily, caption_daily, story_daily, film_daily,
        publications_daily, credits_daily,
    )

    return {
        "range": range,
        "totals": totals,
        "daily": daily,
        "publications_by_platform": publications_by_platform,
    }


class BuyCreditsRequest(BaseModel):
    amount_usd: float
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@app.post("/api/stripe/buy-credits", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def buy_credits_checkout(
    request: Request,
    payload: BuyCreditsRequest,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Create a Stripe Checkout session for purchasing additional credits."""
    _require_stripe_ready()
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    policy_state = await _enforce_subscription_retention_policy(user_id)
    if policy_state.get("state") != "active":
        raise HTTPException(
            status_code=403,
            detail="Un abonnement actif est requis pour recharger des credits.",
        )

    amount_usd = float(payload.amount_usd)
    if amount_usd < 1.0:
        raise HTTPException(status_code=400, detail="Minimum purchase is 1 EUR")

    credits_to_add = int(usd_to_credits(amount_usd))
    unit_amount    = int(round(amount_usd * 100))  # in cents

    default_base_url = _frontend_base_url(request)
    success_url = (
        payload.success_url
        or f"{default_base_url}/dashboard/settings?credit_purchase=success"
    ).strip()
    cancel_url = (
        payload.cancel_url
        or f"{default_base_url}/dashboard/settings?credit_purchase=cancel"
    ).strip()

    metadata = {
        "userid":         user_id,
        "payment_mode":   "stripe_credits",
        "credits_to_add": str(credits_to_add),
        "amount_usd":     str(amount_usd),
    }

    # Reuse the subscription's Stripe Customer when there is one (see
    # _existing_stripe_customer_id) instead of a bare customer_email --
    # otherwise this mode="payment" Checkout risks creating a second,
    # disconnected guest Customer, so a card added here wouldn't be the
    # one Stripe already has on file for the subscription, and vice versa.
    existing_customer_id = await _existing_stripe_customer_id(user_id)

    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            **(
                {"customer": existing_customer_id}
                if existing_customer_id
                else {"customer_email": request.headers.get("X-User-Email") or None}
            ),
            # Attaches whatever card is used here to the Customer for
            # future reuse (instead of a one-off, forgotten payment
            # method), so it also shows up as a usable saved card next
            # time -- for another credit purchase or, via
            # replace_souscription_payment_method, as the subscription's
            # billing card.
            payment_intent_data={"setup_future_usage": "off_session"},
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": STRIPE_CURRENCY,
                        "unit_amount": unit_amount,
                        "product_data": {
                            "name": f"{credits_to_add} Vireel Credits",
                            "description": f"Achat de {credits_to_add} crédits Vireel",
                            "tax_code": "txcd_10103001"
                        },
                    },
                }
            ],
            metadata=metadata,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Stripe checkout error: {exc}")

    return {
        "checkout_url":  session.url,
        "session_id":    session.id,
        "credits_to_add": credits_to_add,
    }


@app.get("/api/captions", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def list_captions(
    user_id: Annotated[str, Depends(get_user_id_header)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase captions is not configured")

    rows, total = await supabase_list_captions(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    items = [_normalize_caption_row(row) for row in rows]
    await _attach_media_asset_fields(items, CONTENT_KIND_CAPTION)
    return {
        "items": items,
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@app.get("/api/captions/{caption_id}/media-url", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def caption_media_url(caption_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_caption(caption_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_CAPTION_NOT_FOUND)
    item = _normalize_caption_row(row)
    return {"media_url": item.get("media_url")}


@app.delete("/api/captions/{caption_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def delete_caption(caption_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    deleted = await supabase_soft_delete_caption(caption_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_CAPTION_NOT_FOUND)
    return {"deleted": True}


# ---------------------------------------------------------------------------
# Anonymous stories ("Temoignages") -- video testimonial -> transcript ->
# AI-generated anonymized story -> user edits -> copy. See
# anonymous_stories.py for the schema/validation/prompt/AI-call logic this
# section wires into the app's existing job/credits/S3 machinery.
# ---------------------------------------------------------------------------

class AnonymousStoryUpdateRequest(BaseModel):
    title: Optional[str] = None
    hook: Optional[str] = None
    introduction: Optional[str] = None
    story: Optional[str] = None
    questions: Optional[List[str]] = None


class AnonymousStoryPublishRequest(BaseModel):
    account_ids: List[str] = []
    background_id: Optional[str] = None
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"


def _normalize_anonymous_story_row(row: Dict[str, Any], *, include_content: bool = False) -> Dict[str, Any]:
    item = {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "source_type": row.get("source_type"),
        "status": row.get("status"),
        "stage": row.get("stage"),
        "job_id": row.get("job_id"),
        "source_duration_seconds": row.get("source_duration_seconds"),
        "error_code": row.get("error_code"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
    }
    if include_content:
        item["generated_content"] = row.get("generated_content") or {}
        item["edited_content"] = row.get("edited_content") or {}
        item["final_text"] = row.get("final_text") or ""
    return item


async def _reserve_story_credits_or_cleanup(
    user_id: str, required_credits: float, input_path: Optional[str], job_output_dir: str,
) -> None:
    try:
        await _reserve_job_credits(user_id, required_credits)
    except HTTPException:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(job_output_dir, ignore_errors=True)
        raise


async def _create_anonymous_story_endpoint_project(
    user_id: str, story_job_id: str, source_name: str, input_path: str, size_bytes: int,
    local_duration: float, source_type: str, source_url_value: Optional[str], story_title: str,
) -> Optional[Dict[str, Any]]:
    """Create the `projects` row backing this operation, same as reels and
    captions do (see _create_caption_endpoint_project) -- this is what
    makes anonymous stories show up in the shared project list/rename/
    delete UI instead of a separate one-off list."""
    if not is_supabase_configured():
        return None
    try:
        project_description = _build_short_project_summary(story_title, fallback_title=story_title)
        bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
        s3_source_key = f"{_STORIES_PREFIX}{user_id}/{story_job_id}/{source_name}"

        if os.path.exists(input_path):
            upload_file_to_s3(input_path, bucket_name, s3_source_key)
        project_thumbnail_ref = _generate_and_upload_project_thumbnail_from_source(
            input_path,
            bucket_name,
            user_id,
            story_job_id,
        )

        project = await supabase_create_project(
            user_id=user_id,
            name=story_title,
            description=project_description,
            project_type="anonymous_story",
            source_type=source_type,
            source_url=source_url_value,
            source_s3_key=s3_source_key,
            source_size=size_bytes,
            source_duration=int(local_duration) if local_duration else None,
            thumbnail_url=project_thumbnail_ref,
            status="processing",
        )
        await _finalize_source_media_retention(story_job_id, user_id, project, size_bytes, bucket_name, s3_source_key)
        return project
    except Exception as e:
        logger.warning(f"Failed to create project for anonymous story job {story_job_id}: {str(e)}")
        return None


async def _resolve_anonymous_story_source(
    file: Optional[UploadFile], url: Optional[str], output_dir: str,
) -> Dict[str, Any]:
    """Resolve the story's source video -- uploaded file or YouTube link --
    into a uniform shape. Pulled out of create_anonymous_story to keep that
    endpoint's cognitive complexity down: this file-vs-YouTube branch
    (including its nested try/except) was most of it."""
    if file:
        _validate_video_extension(file.filename if file else "", context_label="histoire anonyme")
        source_name = os.path.basename(str(file.filename or "story_source.mp4"))
        input_path = os.path.join(output_dir, f"story_input_{int(time.time())}_{source_name}")
        limit_bytes = max(0.0, CAPTION_MAX_STORAGE_GB) * (1024 ** 3)
        size_bytes = await _save_caption_upload_file(file, input_path, limit_bytes)
        return {
            "input_path": input_path,
            "source_name": source_name,
            "size_bytes": size_bytes,
            "source_type": anonymous_stories.AnonymousStorySourceType.UPLOAD,
            "source_url_value": None,
            "story_title": _project_name_from_uploaded_file(source_name),
        }

    if not _is_youtube_url(url):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Only YouTube links are supported for anonymous stories in V1.")

    try:
        youtube_source = await asyncio.to_thread(anonymous_stories.download_youtube_source, url, output_dir)
        input_path = youtube_source["path"]
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Le lien YouTube n'est pas valide ou ne peut pas etre traite.") from exc

    try:
        size_bytes = os.path.getsize(input_path)
    except OSError:
        size_bytes = 0

    return {
        "input_path": input_path,
        "source_name": "youtube_source.mp4",
        "size_bytes": size_bytes,
        "source_type": anonymous_stories.AnonymousStorySourceType.YOUTUBE,
        "source_url_value": url,
        "story_title": youtube_source.get("title") or "Temoignage YouTube",
    }


async def _resolve_anonymous_story_page_context(
    request: Request, page_name: Optional[str], target_language: Optional[str],
) -> Tuple[str, str]:
    """page_name/target_language (see anonymous_stories.build_story_prompt)
    arrive as Form fields for a multipart upload, or as JSON body fields
    for a URL submission -- mirrors _resolve_process_endpoint_url_and_ack's
    same content-type branching, kept as its own small helper since these
    two fields only exist for this endpoint. request.json() is cached by
    Starlette after _resolve_process_endpoint_url_and_ack's own read, so
    calling it again here re-parses nothing."""
    content_type = request.headers.get("content-type", "")
    if _CONTENT_TYPE_JSON in content_type:
        body = await request.json()
        page_name = body.get("page_name")
        target_language = body.get("target_language")
    return str(page_name or "").strip()[:200], str(target_language or "").strip()[:100]


@app.post("/api/anonymous-stories", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 413: {"description": "Payload Too Large"}, 429: {"description": "Too Many Requests"}})
async def create_anonymous_story(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[Optional[UploadFile], File()] = None,
    url: Annotated[Optional[str], Form()] = None,
    acknowledged: Annotated[Optional[str], Form()] = None,
    page_name: Annotated[Optional[str], Form()] = None,
    target_language: Annotated[Optional[str], Form()] = None,
):
    if not ANONYMOUS_STORIES_ENABLED:
        raise HTTPException(status_code=404, detail=_ANONYMOUS_STORIES_DISABLED)

    url, ack_flag = await _resolve_process_endpoint_url_and_ack(request, url, acknowledged)
    _validate_process_endpoint_inputs(url, file, ack_flag)
    page_name, target_language = await _resolve_anonymous_story_page_context(request, page_name, target_language)

    await _enforce_job_concurrency_limit(user_id)

    story_job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, story_job_id)
    os.makedirs(output_dir, exist_ok=True)

    source = await _resolve_anonymous_story_source(file, url, output_dir)
    input_path = source["input_path"]
    source_name = source["source_name"]
    size_bytes = source["size_bytes"]
    source_type = source["source_type"]
    source_url_value = source["source_url_value"]
    story_title = source["story_title"]

    local_duration = _probe_local_video_duration_seconds(input_path)
    _validate_caption_source_constraints(
        duration_seconds=local_duration, size_bytes=float(size_bytes), source_label="fichier",
        max_duration_minutes=ANONYMOUS_STORY_MAX_DURATION_MINUTES,
    )

    story_required_credits = _estimate_caption_required_credits(duration_seconds=local_duration, size_bytes=float(size_bytes))
    await _reserve_story_credits_or_cleanup(user_id, story_required_credits, input_path, output_dir)

    job_priority = await _resolve_user_job_priority(user_id)

    project = await _create_anonymous_story_endpoint_project(
        user_id, story_job_id, source_name, input_path, int(size_bytes), local_duration,
        source_type, source_url_value, story_title,
    )
    project_id = project.get("id") if project else None
    source_s3_key = project.get("source_s3_key") if project else None

    story_row = None
    if is_supabase_configured():
        story_row = await supabase_insert_anonymous_story({
            "user_id": user_id,
            "project_id": project_id,
            "title": story_title[:200],
            "source_type": source_type,
            "source_url": source_url_value,
            "source_s3_key": source_s3_key,
            "source_duration_seconds": int(local_duration or 0),
            "status": anonymous_stories.AnonymousStoryStatus.QUEUED,
            "stage": anonymous_stories.AnonymousStoryStage.UPLOAD,
            "job_id": story_job_id,
            "page_name": page_name,
            "target_language": target_language,
        })

    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_ANONYMOUS_STORY,
        pipeline_name="AnonymousStoryPipeline",
        job_id=story_job_id,
        job_data={
            "source_type": source_type,
            "source_value": source_url_value or source_name,
            "story_required_credits": story_required_credits,
            "project_id": project_id,
        },
        max_attempts=STORY_JOB_MAX_ATTEMPTS,
        reserved_quota=story_required_credits,
        priority=job_priority,
        queue_name="anonymous_stories",
    )
    await reel_job_manager.enqueue_job(story_job_id)

    _spawn_background_task(_run_anonymous_story_job(
        job_id=story_job_id,
        user_id=user_id,
        story_id=story_row.get("id") if story_row else None,
        project_id=project_id,
        source_s3_key=source_s3_key,
        input_path=input_path,
        output_dir=output_dir,
        local_duration=local_duration,
        size_bytes=float(size_bytes),
        story_required_credits=story_required_credits,
        page_name=page_name,
        target_language=target_language,
    ))

    return {
        "job_id": story_job_id,
        "story_id": story_row.get("id") if story_row else None,
        "project_id": project_id,
        "status": "queued",
    }


async def _mark_anonymous_story_job_failed(
    user_id: str, story_id: Optional[str], project_id: Optional[str], error_code: str, error_message: str,
) -> None:
    if story_id and is_supabase_configured():
        await supabase_update_anonymous_story(story_id, user_id, {
            "status": anonymous_stories.AnonymousStoryStatus.FAILED,
            "error_code": error_code,
            "error_message": error_message,
        })
    if project_id and is_supabase_configured():
        try:
            await supabase_update_project_status(project_id, "failed", user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to update project status to failed: {str(e)}")


async def _run_anonymous_story_job(
    job_id: str, user_id: str, story_id: Optional[str], project_id: Optional[str], source_s3_key: Optional[str],
    input_path: str, output_dir: str, local_duration: float, size_bytes: float,
    story_required_credits: float, page_name: str = "", target_language: str = "",
) -> None:
    try:
        await reel_job_manager.start_job(job_id)
        await _run_anonymous_story_pipeline_stages(
            job_id, user_id, story_id, project_id, source_s3_key, input_path,
            local_duration, size_bytes, story_required_credits, page_name, target_language,
        )
    except anonymous_stories.StoryValidationError as exc:
        await reel_job_manager.fail_job(job_id, str(exc), error_code=exc.code)
        await _mark_anonymous_story_job_failed(user_id, story_id, project_id, exc.code, str(exc))
        await reel_job_manager.refund_reservation(job_id, user_id, story_required_credits, operation_type=anonymous_stories.CREDIT_OPERATION_TYPE)
    except Exception as exc:  # noqa: BLE001 -- any unexpected failure must still fail the job and refund the user
        logger.exception(f"Anonymous story job {job_id} failed")
        await reel_job_manager.fail_job(job_id, "Technical failure while generating the story", error_code="GENERATION_INVALID")
        await _mark_anonymous_story_job_failed(user_id, story_id, project_id, "GENERATION_INVALID", str(exc))
        await reel_job_manager.refund_reservation(job_id, user_id, story_required_credits, operation_type=anonymous_stories.CREDIT_OPERATION_TYPE)
    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


async def _run_anonymous_story_pipeline_stages(
    job_id: str, user_id: str, story_id: Optional[str], project_id: Optional[str], source_s3_key: Optional[str],
    input_path: str, local_duration: float, size_bytes: float, story_required_credits: float,
    page_name: str = "", target_language: str = "",
) -> None:
    if story_id and is_supabase_configured():
        await supabase_update_anonymous_story(story_id, user_id, {
            "status": anonymous_stories.AnonymousStoryStatus.PROCESSING,
            "stage": anonymous_stories.AnonymousStoryStage.TRANSCRIPTION,
        })
    await reel_job_manager.update_progress(job_id, 20, "transcription")

    try:
        transcript = await anonymous_stories.transcribe_video(input_path)
    except Exception as exc:
        raise anonymous_stories.StoryValidationError(
            anonymous_stories.AnonymousStoryErrorCode.TRANSCRIPTION_FAILED, str(exc)
        ) from exc

    transcript_text = str(transcript.get("text") or "").strip()
    if not transcript_text:
        raise anonymous_stories.StoryValidationError(
            anonymous_stories.AnonymousStoryErrorCode.TRANSCRIPTION_FAILED, "Empty transcript"
        )

    if is_supabase_configured():
        await supabase_upsert_transcription({
            "user_id": user_id,
            "job_id": job_id,
            "clip_index": 0,
            "source_type": "video",
            "transcript_provider": "assemblyai",
            "transcript_language": transcript.get("language"),
            "transcript_text": transcript_text,
        })

    if story_id and is_supabase_configured():
        await supabase_update_anonymous_story(story_id, user_id, {"stage": anonymous_stories.AnonymousStoryStage.GENERATION})
    await reel_job_manager.update_progress(job_id, 55, "generation")

    story_content = await anonymous_stories.generate_story_from_transcript(
        transcript_text, page_name=page_name, source_language=str(transcript.get("language") or ""),
        target_language=target_language,
    )
    usage = story_content.pop("usage", {})

    await _finalize_anonymous_story_job(
        job_id, user_id, story_id, project_id, source_s3_key, local_duration, size_bytes,
        story_required_credits, story_content, usage,
    )


def _build_story_cost_breakdown(duration_seconds: float, size_bytes: float, usage: Dict[str, Any]) -> Dict[str, Any]:
    breakdown = estimate_caption_cost_usd(
        duration_minutes=max(1.0, float(duration_seconds or 0.0) / 60.0),
        video_size_gb=max(0.0, _bytes_to_gb(float(size_bytes or 0.0))),
        uses_assembly=True,
        uses_openai=True,
    )
    openai_usd = estimate_llm_usage_cost_usd(
        "openai", usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0),
    )
    breakdown["openai_usd"] = openai_usd
    breakdown["total_usd"] = round(
        breakdown["s3_usd"] + breakdown["vps_usd"] + breakdown["assembly_usd"] + openai_usd, 6
    )
    return calculate_credits_for_operation(breakdown)


async def _settle_anonymous_story_row(
    job_id: str, user_id: str, story_id: str, source_s3_key: Optional[str], story_content: Dict[str, Any],
    cost_breakdown: Dict[str, Any], final_credits: float, story_required_credits: float,
    generated_title: str, now_iso: str,
) -> None:
    story_updates: Dict[str, Any] = {
        "status": anonymous_stories.AnonymousStoryStatus.COMPLETED,
        "stage": anonymous_stories.AnonymousStoryStage.FINALIZATION,
        "source_s3_key": source_s3_key,
        "generated_content": story_content,
        "edited_content": story_content,
        "final_text": story_content.get("full_text", ""),
        "billing_details": cost_breakdown,
        "total_cost_usd": cost_breakdown.get("total_usd", 0.0),
        "completed_at": now_iso,
    }
    if generated_title:
        story_updates["title"] = generated_title
    await supabase_update_anonymous_story(story_id, user_id, story_updates)

    if not user_id:
        return
    debit_ok = await reel_job_manager.debit_credits_for_job(
        job_id=job_id,
        user_id=user_id,
        credits=final_credits,
        operation_type=anonymous_stories.CREDIT_OPERATION_TYPE,
        reserved_credits=story_required_credits,
    )
    if not debit_ok:
        logger.warning(f"Insufficient balance to settle anonymous story job {job_id}")


async def _settle_anonymous_story_project(
    project_id: str, user_id: str, story_content: Dict[str, Any], generated_title: str,
) -> None:
    try:
        await supabase_update_project_status(project_id, "completed", user_id=user_id)
        project_updates: Dict[str, Any] = {
            "description": _build_short_project_summary(story_content.get("hook") or story_content.get("story") or ""),
            "output_count": 1,
        }
        if generated_title:
            project_updates["name"] = generated_title
        await supabase_update_project(project_id, user_id, project_updates)
    except Exception as e:
        logger.warning(f"Failed to mark project {project_id} completed: {str(e)}")


async def _finalize_anonymous_story_job(
    job_id: str, user_id: str, story_id: Optional[str], project_id: Optional[str], source_s3_key: Optional[str],
    local_duration: float, size_bytes: float, story_required_credits: float,
    story_content: Dict[str, Any], usage: Dict[str, Any],
) -> None:
    # The source video was already uploaded to S3 (and the project row
    # created) at request time in _create_anonymous_story_endpoint_project,
    # so `source_s3_key` is threaded through rather than re-uploaded here.
    await reel_job_manager.update_progress(job_id, 85, "finalization")
    leftovers = anonymous_stories.find_possible_identifying_leftovers(story_content.get("full_text", ""))

    cost_breakdown = _build_story_cost_breakdown(local_duration, size_bytes, usage)
    final_credits = float(cost_breakdown.get("final_credits") or 0.0)
    now_iso = datetime.now(timezone.utc).isoformat()

    # Replace the placeholder title set at creation time (source filename or
    # YouTube video title) with one that actually reflects what was
    # generated. STORY_SYSTEM_PROMPT doesn't ask the model for a title, so
    # this is always anonymous_stories.derive_fallback_title's fallback.
    generated_title = str(story_content.get("title") or "").strip()

    if story_id and is_supabase_configured():
        await _settle_anonymous_story_row(
            job_id, user_id, story_id, source_s3_key, story_content, cost_breakdown,
            final_credits, story_required_credits, generated_title, now_iso,
        )

    if project_id and is_supabase_configured():
        await _settle_anonymous_story_project(project_id, user_id, story_content, generated_title)

    await reel_job_manager.complete_job(
        job_id,
        {
            "story_id": story_id,
            "project_id": project_id,
            "final_text": story_content.get("full_text", ""),
            "pii_leftover_flags": leftovers,
        },
        actual_credit=final_credits,
        cost_breakdown=cost_breakdown,
        consumed_quota=1.0,
    )


@app.get("/api/anonymous-stories", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def list_anonymous_stories_endpoint(
    user_id: Annotated[str, Depends(get_user_id_header)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    rows, total = await supabase_list_anonymous_stories(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    items = [_normalize_anonymous_story_row(row) for row in rows]
    await _attach_media_asset_fields(items, CONTENT_KIND_ANONYMOUS_STORY)
    return {
        "items": items,
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@app.get("/api/anonymous-stories/backgrounds", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def list_anonymous_story_backgrounds(user_id: Annotated[str, Depends(get_user_id_header)]):
    items = [
        {"id": preset["id"], "name": preset["name"], "colors": preset["colors"], "text_color": preset["text_color"]}
        for preset in anonymous_stories.BACKGROUND_PRESETS
    ]
    # Appended last so the frontend's "pick items[0] as the default
    # selection" logic still lands on a color preset, not "no background".
    items.append({"id": anonymous_stories.NO_BACKGROUND_ID, "name": "No background", "colors": [], "text_color": None})
    return {"items": items}


# Registered before /api/anonymous-stories/{story_id}: FastAPI/Starlette
# matches routes in registration order, so a literal-segment route like
# this one must come first or a request to /api/anonymous-stories/backgrounds
# gets swallowed by {story_id}="backgrounds" and 500s trying to look up a
# story with that as its id (see production incident: postgrest rejects
# "backgrounds" as an invalid uuid).
@app.get("/api/anonymous-stories/{story_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def get_anonymous_story_endpoint(story_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_anonymous_story(story_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)
    return _normalize_anonymous_story_row(row, include_content=True)


@app.patch("/api/anonymous-stories/{story_id}", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def update_anonymous_story_endpoint(
    story_id: str, payload: AnonymousStoryUpdateRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    row = await supabase_get_anonymous_story(story_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)

    current_content = row.get("edited_content") or row.get("generated_content") or {}
    merged = {
        "hook": payload.hook if payload.hook is not None else current_content.get("hook"),
        "introduction": payload.introduction if payload.introduction is not None else current_content.get("introduction"),
        "story": payload.story if payload.story is not None else current_content.get("story"),
        "questions": payload.questions if payload.questions is not None else current_content.get("questions"),
    }
    try:
        normalized = anonymous_stories.validate_edited_story_content(merged)
    except anonymous_stories.StoryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    updates: Dict[str, Any] = {
        "edited_content": normalized,
        "final_text": normalized["full_text"],
    }
    if payload.title is not None:
        updates["title"] = payload.title.strip()[:200]

    updated = await supabase_update_anonymous_story(story_id, user_id, updates)
    if not updated:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)
    return _normalize_anonymous_story_row(updated, include_content=True)


@app.delete("/api/anonymous-stories/{story_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def delete_anonymous_story_endpoint(story_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_anonymous_story(story_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)

    deleted = await supabase_soft_delete_anonymous_story(story_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)

    source_s3_key = row.get("source_s3_key")
    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if source_s3_key and bucket:
        delete_s3_object(bucket, source_s3_key)

    return {"deleted": True}


async def _load_anonymous_story_for_regenerate(story_id: str, user_id: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Fetch the story row and its cached transcript, or raise the same
    404/400 the endpoint always has. Pulled out of
    regenerate_anonymous_story_endpoint to keep its cognitive complexity
    down."""
    row = await supabase_get_anonymous_story(story_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)

    job_id = row.get("job_id") or ""
    transcript_row = await supabase_get_transcription_by_job_clip(job_id, 0, user_id) or {}
    transcript_text = str(transcript_row.get("transcript_text") or "").strip()
    if not transcript_text:
        raise HTTPException(status_code=400, detail="No cached transcript available for this story; recreate it from the source video instead.")

    return row, transcript_row, transcript_text


async def _regenerate_story_content(
    story_id: str, user_id: str, job_id: str, row: Dict[str, Any], transcript_row: Dict[str, Any],
    transcript_text: str, regen_credits: float,
) -> Dict[str, Any]:
    """Run the actual regeneration, refunding the reservation and marking
    the story failed on a validation error (re-raised as the same 400 the
    endpoint always returned). Pulled out of
    regenerate_anonymous_story_endpoint to keep its cognitive complexity
    down."""
    await supabase_update_anonymous_story(story_id, user_id, {
        "status": anonymous_stories.AnonymousStoryStatus.PROCESSING,
        "stage": anonymous_stories.AnonymousStoryStage.GENERATION,
    })

    try:
        return await anonymous_stories.generate_story_from_transcript(
            transcript_text,
            page_name=str(row.get("page_name") or ""),
            source_language=str(transcript_row.get("transcript_language") or ""),
            target_language=str(row.get("target_language") or ""),
        )
    except anonymous_stories.StoryValidationError as exc:
        await reel_job_manager.refund_reservation(job_id, user_id, regen_credits, operation_type=anonymous_stories.CREDIT_OPERATION_TYPE)
        await supabase_update_anonymous_story(story_id, user_id, {
            "status": anonymous_stories.AnonymousStoryStatus.FAILED,
            "error_code": exc.code,
            "error_message": str(exc),
        })
        raise HTTPException(status_code=400, detail=exc.code) from exc


async def _finalize_regenerated_story(
    story_id: str, user_id: str, project_id: Optional[str], story_content: Dict[str, Any],
) -> Dict[str, Any]:
    """Persist the regenerated content and, when it yielded a real title,
    rename the project to match -- same title-propagation behavior as a
    first-time generation (_settle_anonymous_story_project). Pulled out of
    regenerate_anonymous_story_endpoint to keep its cognitive complexity
    down."""
    story_content.pop("usage", None)
    generated_title = str(story_content.get("title") or "").strip()
    story_updates: Dict[str, Any] = {
        "status": anonymous_stories.AnonymousStoryStatus.COMPLETED,
        "stage": anonymous_stories.AnonymousStoryStage.FINALIZATION,
        "generated_content": story_content,
        "edited_content": story_content,
        "final_text": story_content.get("full_text", ""),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }
    if generated_title:
        story_updates["title"] = generated_title
    updated = await supabase_update_anonymous_story(story_id, user_id, story_updates)

    if generated_title and project_id and is_supabase_configured():
        try:
            await supabase_update_project(project_id, user_id, {"name": generated_title})
        except Exception as e:
            logger.warning(f"Failed to update project {project_id} name after regenerate: {str(e)}")

    return updated


@app.post("/api/anonymous-stories/{story_id}/regenerate", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 429: {"description": "Too Many Requests"}})
async def regenerate_anonymous_story_endpoint(story_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    if not ANONYMOUS_STORIES_ENABLED:
        raise HTTPException(status_code=404, detail=_ANONYMOUS_STORIES_DISABLED)

    row, transcript_row, transcript_text = await _load_anonymous_story_for_regenerate(story_id, user_id)
    job_id = row.get("job_id") or ""

    await _enforce_job_concurrency_limit(user_id)
    regen_credits = _estimate_caption_required_credits(
        duration_seconds=float(row.get("source_duration_seconds") or 60.0),
        size_bytes=0.0,
        uses_assembly=False,
    )
    await _reserve_job_credits(user_id, regen_credits)

    story_content = await _regenerate_story_content(
        story_id, user_id, job_id, row, transcript_row, transcript_text, regen_credits,
    )
    updated = await _finalize_regenerated_story(story_id, user_id, row.get("project_id"), story_content)

    await reel_job_manager.debit_credits_for_job(
        job_id=job_id, user_id=user_id, credits=regen_credits,
        operation_type=anonymous_stories.CREDIT_OPERATION_TYPE, reserved_credits=regen_credits,
    )
    return _normalize_anonymous_story_row(updated, include_content=True)


# Anonymous stories may only be published to the platforms the user
# explicitly asked for ("la publication dois se faire entre facebook et
# Linkedin") -- unlike reels/captions, which fan out to whatever the
# account has connected among tiktok/instagram/youtube/facebook/linkedin.
# Reuses _SOCIAL_POST_PLATFORMS (the composer's own set is identical).


async def _publish_anonymous_story_now(
    user_id: str, account: Dict[str, Any], publish_priority: int, text_value: str,
    background_id: Optional[str] = None,
) -> Dict[str, Any]:
    platform_name = str(account.get("platform") or "")
    publish_job_id = await _insert_publish_job(
        user_id=user_id,
        platform=platform_name,
        external_id="n/a",
        status="queued",
        priority=publish_priority,
        payload={
            "source_type": "anonymous_story",
            "account_id": account.get("id"),
            "text": text_value,
            "background_id": background_id,
        },
    )
    try:
        await _update_publish_job_status(publish_job_id, "processing")

        publish_payload = PublishRequest(
            user_id=user_id,
            title="Vireel",
            description=text_value,
            text=text_value,
            caption=text_value,
            facebook_text_format_preset_id=anonymous_stories.get_facebook_text_format_preset_id(background_id),
        )
        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or "n/a")
        post_url = _build_social_post_url(platform_name, platform_result)
        await _update_publish_job_status(publish_job_id, "done", external_id=external_id, post_url=post_url)
        return {
            "success": True,
            "result": platform_result,
            "publish_job_id": publish_job_id,
        }
    except Exception as exc:
        err_msg = str(exc)
        await _update_publish_job_status(publish_job_id, "failed", error_message=err_msg)
        return {
            "success": False,
            "error": err_msg,
            "publish_job_id": publish_job_id,
        }


def _resolve_anonymous_story_schedule(payload: "AnonymousStoryPublishRequest"):
    """Resolve and validate the requested schedule, returning
    (scheduled_for, is_scheduled). Pulled out of
    publish_anonymous_story_endpoint to keep its cognitive complexity
    down."""
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())
    return scheduled_for, is_scheduled


async def _dispatch_anonymous_story_publish(
    user_id: str, story_id: str, story_title: str, text_value: str, background_id: str,
    accounts: List[Dict[str, Any]], publish_priority: int, scheduled_for, timezone: Optional[str],
    is_scheduled: bool,
) -> Dict[str, Any]:
    """Publish (or schedule) the story across every selected account.
    Pulled out of publish_anonymous_story_endpoint to keep its cognitive
    complexity down."""
    results: Dict[str, Any] = {}
    for account in accounts:
        result_key = str(account.get("id") or account.get("platform"))
        if is_scheduled:
            results[result_key] = await _schedule_share_publish_job(
                user_id, account, "anonymous_story", story_id, publish_priority,
                scheduled_for, timezone, story_title, text_value, "",
                background_id=background_id,
            )
            continue

        results[result_key] = await _publish_anonymous_story_now(
            user_id, account, publish_priority, text_value, background_id,
        )
    return results


@app.post("/api/anonymous-stories/{story_id}/publish", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def publish_anonymous_story_endpoint(
    story_id: str, payload: AnonymousStoryPublishRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    if not ANONYMOUS_STORIES_ENABLED:
        raise HTTPException(status_code=404, detail=_ANONYMOUS_STORIES_DISABLED)

    await _assert_user_has_active_subscription_for_publish(user_id)

    row = await supabase_get_anonymous_story(story_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_STORY_NOT_FOUND)

    text_value = str(row.get("final_text") or "").strip()
    if not text_value:
        raise HTTPException(status_code=400, detail="Story has no generated text to publish yet")

    accounts = await _resolve_accounts_for_publish(user_id, payload.account_ids, _SOCIAL_POST_PLATFORMS)
    await _assert_user_can_publish(user_id, len(accounts))
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for, is_scheduled = _resolve_anonymous_story_schedule(payload)
    background_id = payload.background_id or anonymous_stories.BACKGROUND_PRESETS[0]["id"]

    results = await _dispatch_anonymous_story_publish(
        user_id, story_id, str(row.get("title") or "Vireel"), text_value, background_id,
        accounts, publish_priority, scheduled_for, payload.timezone, is_scheduled,
    )
    overall_success = all(result.get("success") for result in results.values())

    return {
        "success": overall_success,
        "results": results,
        "background_id": background_id,
        "scheduled": is_scheduled,
    }


async def _schedule_share_publish_job(
    user_id: str, account: Dict[str, Any], source_type: str, source_id: str, publish_priority: int,
    scheduled_for, timezone: Optional[str], final_title: str, final_description: str, media_url: str,
    background_id: Optional[str] = None,
) -> Dict[str, Any]:
    publish_job_id = await _insert_publish_job(
        user_id=user_id,
        platform=str(account.get("platform") or ""),
        external_id="scheduled",
        status="queued",
        priority=publish_priority,
        scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
        timezone=timezone or "UTC",
        payload={
            "source_type": source_type,
            "account_id": account.get("id"),
            "source_id": source_id,
            "title": final_title,
            "description": final_description,
            "media_url": media_url,
            "background_id": background_id,
        },
    )
    return {
        "success": True,
        "scheduled": True,
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        "publish_job_id": publish_job_id,
    }


# ---------------------------------------------------------------------------
# Social posts: a user-authored post (with an optional Facebook background
# theme, reusing anonymous_stories.BACKGROUND_PRESETS) published together
# with zero or more follow-up comments, posted by the connected Page/account
# itself right after the post goes live. Publishing is free (no credit
# debit, no user_data_history entry) but still requires an active
# subscription -- see _assert_user_has_active_subscription_for_publish.
# ---------------------------------------------------------------------------

class SocialPostCommentInput(BaseModel):
    text: str = ""
    link: Optional[str] = None
    image_url: Optional[str] = None


class CreateSocialPostRequest(BaseModel):
    text: str
    account_ids: List[str] = []
    background_id: Optional[str] = None
    media_url: Optional[str] = None
    media_type: Optional[str] = None  # "image" or "video" -- see upload_social_post_media
    comments: List[SocialPostCommentInput] = []
    scheduled_date: Optional[str] = None
    timezone: Optional[str] = "UTC"


def _build_comment_message(comment: "SocialPostCommentInput") -> str:
    text = (comment.text or "").strip()
    link = (comment.link or "").strip()
    if link and link not in text:
        text = f"{text}\n{link}".strip()
    return text


async def _post_facebook_comment(access_token: str, object_id: str, message: str, attachment_url: Optional[str] = None) -> Dict[str, Any]:
    if not object_id or object_id == "n/a":
        raise HTTPException(status_code=400, detail="Missing Facebook post id to comment on")
    if not access_token:
        raise HTTPException(status_code=401, detail=_FACEBOOK_TOKEN_EXPIRED_OR_MISSING)

    data = {"message": message, "access_token": access_token}
    if attachment_url:
        data["attachment_url"] = attachment_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(f"https://graph.facebook.com/v19.0/{object_id}/comments", data=data)
    await _raise_for_status_or_502(response, "Facebook")
    return response.json()


async def _post_linkedin_comment(access_token: str, owner_urn: str, share_urn: str, message: str) -> Dict[str, Any]:
    # LinkedIn's Social Actions comments API is text-only -- unlike Facebook's
    # /comments, it has no attachment_url equivalent, so a comment's link is
    # folded into the message text (see _build_comment_message) and any
    # comment.image_url is simply not usable here.
    if not share_urn or share_urn == "n/a":
        raise HTTPException(status_code=400, detail="Missing LinkedIn post id to comment on")

    encoded_urn = quote(share_urn, safe="")
    payload = {"actor": owner_urn, "message": {"text": message}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://api.linkedin.com/rest/socialActions/{encoded_urn}/comments",
            headers=_linkedin_headers(access_token),
            json=payload,
        )
    await _raise_for_status_or_502(response, "LinkedIn")
    comment_id = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
    return {"id": comment_id}


async def _post_platform_comment(
    platform_name: str, account: Dict[str, Any], token: str, post_external_id: str, comment: "SocialPostCommentInput",
) -> Dict[str, Any]:
    message = _build_comment_message(comment)
    if platform_name == "facebook":
        # attachment_url must be an actual image -- Facebook's Graph API
        # rejects it with a misleading "(#200) Permissions error" when it's
        # a plain webpage link instead, so only ever pass a real uploaded
        # image here. The link itself is never dropped: _build_comment_message
        # already folded it into the comment text above.
        return await _post_facebook_comment(token, post_external_id, message, comment.image_url)
    if platform_name == "linkedin":
        owner_urn = f"urn:li:person:{account.get('platform_user_id')}"
        return await _post_linkedin_comment(token, owner_urn, post_external_id, message)
    raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)


async def _post_comments_sequence(
    platform_name: str, account: Dict[str, Any], post_external_id: str, comments: List["SocialPostCommentInput"],
) -> List[Dict[str, Any]]:
    """Posts every comment, in order, as the connected account itself. A
    comment that fails is recorded and skipped rather than aborting the rest
    -- the post itself already succeeded by the time this runs, so a single
    rejected comment (rate limit, moderation, ...) shouldn't take the
    remaining ones down with it."""
    if not comments:
        return []
    if platform_name == "linkedin":
        # LinkedIn's Social Actions (comments) API requires a restricted
        # partner product (Marketing Developer Platform) that this app's
        # standard "Share on LinkedIn" access doesn't include -- every
        # attempt fails with a 403 ACCESS_DENIED
        # (partnerApiSocialActions.CREATE). This is permanent, not a
        # transient failure worth surfacing as one (see
        # SocialPostComposerModal.jsx, which hides the comments option
        # once only LinkedIn accounts are selected for the same reason),
        # so skip outright instead of attempting and recording a failure.
        return []
    results: List[Dict[str, Any]] = []
    token = await get_valid_token(account)
    for comment in comments:
        try:
            comment_result = await _post_platform_comment(platform_name, account, token, post_external_id, comment)
            results.append({"success": True, "id": comment_result.get("id"), "text": comment.text})
        except Exception as exc:
            logger.warning("Failed to post comment on %s post %s: %s", platform_name, post_external_id, exc)
            results.append({"success": False, "error": str(exc), "text": comment.text})
    return results


def _build_social_post_publish_payload(
    text_value: str, background_id: Optional[str], media_url: Optional[str] = None, media_type: Optional[str] = None,
) -> "PublishRequest":
    # A background (Facebook's native colored-background text) can never be
    # combined with a photo or video -- Facebook silently drops the
    # background style the moment any media is attached (see
    # publish_to_facebook_text_with_background) -- so an attached media
    # takes priority and the background is simply not set in that case.
    if media_url:
        return PublishRequest(
            user_id="",
            title="Vireel",
            description=text_value,
            text=text_value,
            caption=text_value,
            video_url=media_url if media_type == "video" else None,
            image_url=media_url if media_type != "video" else None,
        )
    return PublishRequest(
        user_id="",
        title="Vireel",
        description=text_value,
        text=text_value,
        caption=text_value,
        facebook_text_format_preset_id=anonymous_stories.get_facebook_text_format_preset_id(background_id),
    )


async def _publish_social_post_now(
    user_id: str, account: Dict[str, Any], publish_priority: int, text_value: str,
    background_id: Optional[str], comments: List["SocialPostCommentInput"],
    media_url: Optional[str] = None, media_type: Optional[str] = None,
) -> Dict[str, Any]:
    platform_name = str(account.get("platform") or "")
    publish_job_id = await _insert_publish_job(
        user_id=user_id,
        platform=platform_name,
        external_id="n/a",
        status="queued",
        priority=publish_priority,
        payload={
            "source_type": "social_post",
            "account_id": account.get("id"),
            "text": text_value,
            "background_id": background_id,
            "media_url": media_url,
            "media_type": media_type,
            "comments": [c.model_dump() for c in comments],
        },
    )
    try:
        await _update_publish_job_status(publish_job_id, "processing")

        publish_payload = _build_social_post_publish_payload(text_value, background_id, media_url, media_type)
        publish_payload.user_id = user_id
        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or "n/a")
        post_url = _build_social_post_url(platform_name, platform_result)

        comments_results = await _post_comments_sequence(platform_name, account, external_id, comments)

        await _update_publish_job_status(
            publish_job_id, "done", external_id=external_id, post_url=post_url,
            extra_payload={"comments_results": comments_results},
        )
        return {
            "success": True,
            "result": platform_result,
            "publish_job_id": publish_job_id,
            "comments_results": comments_results,
        }
    except Exception as exc:
        err_msg = str(exc)
        await _update_publish_job_status(publish_job_id, "failed", error_message=err_msg)
        return {
            "success": False,
            "error": err_msg,
            "publish_job_id": publish_job_id,
        }


async def _schedule_social_post_job(
    user_id: str, account: Dict[str, Any], publish_priority: int, scheduled_for, timezone: Optional[str],
    text_value: str, background_id: Optional[str], comments: List["SocialPostCommentInput"],
    media_url: Optional[str] = None, media_type: Optional[str] = None,
) -> Dict[str, Any]:
    publish_job_id = await _insert_publish_job(
        user_id=user_id,
        platform=str(account.get("platform") or ""),
        external_id="scheduled",
        status="queued",
        priority=publish_priority,
        scheduled_for=scheduled_for.isoformat() if scheduled_for else None,
        timezone=timezone or "UTC",
        payload={
            "source_type": "social_post",
            "account_id": account.get("id"),
            "text": text_value,
            "background_id": background_id,
            "media_url": media_url,
            "media_type": media_type,
            "comments": [c.model_dump() for c in comments],
        },
    )
    return {
        "success": True,
        "scheduled": True,
        "scheduled_for": scheduled_for.isoformat() if scheduled_for else None,
        "publish_job_id": publish_job_id,
    }


async def _execute_scheduled_social_post_job(job_id: str, user_id: str, platform: str, task_payload: Dict[str, Any]) -> None:
    try:
        await _update_publish_job_status(job_id, "processing", error_message=None)

        # account_id is only present on jobs scheduled after multi-account
        # support was added -- fall back to "any account of this platform"
        # for older in-flight jobs that don't have it.
        account_id = task_payload.get("account_id")
        account = await _get_social_account_by_id(user_id, account_id) if account_id else None
        if not account:
            account = await _get_social_account(user_id, platform)
        if not account:
            raise HTTPException(status_code=404, detail=f"No connected {platform} account found")

        text_value = str(task_payload.get("text") or "")
        background_id = task_payload.get("background_id")
        media_url = task_payload.get("media_url")
        media_type = task_payload.get("media_type")
        comments = [
            SocialPostCommentInput(**c) for c in (task_payload.get("comments") or []) if isinstance(c, dict)
        ]

        publish_payload = _build_social_post_publish_payload(text_value, background_id, media_url, media_type)
        publish_payload.user_id = user_id
        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or "n/a")
        post_url = _build_social_post_url(platform, platform_result)

        comments_results = await _post_comments_sequence(platform, account, external_id, comments)

        await _update_publish_job_status(
            job_id, "done", external_id=external_id, post_url=post_url,
            extra_payload={"comments_results": comments_results},
        )
    except Exception as exc:
        await _update_publish_job_status(job_id, "failed", error_message=str(exc))


async def _publish_or_schedule_social_post(
    user_id: str, account: Dict[str, Any], publish_priority: int, is_scheduled: bool,
    scheduled_for: Optional[datetime], tz: Optional[str], text_value: str, background_id: Optional[str],
    comments: List["SocialPostCommentInput"], media_url: Optional[str], media_type: Optional[str],
) -> Dict[str, Any]:
    if is_scheduled:
        return await _schedule_social_post_job(
            user_id, account, publish_priority, scheduled_for, tz,
            text_value, background_id, comments, media_url, media_type,
        )
    return await _publish_social_post_now(
        user_id, account, publish_priority, text_value, background_id, comments, media_url, media_type,
    )


@app.post("/api/social/posts", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def create_social_post(payload: CreateSocialPostRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    await _assert_user_has_active_subscription_for_publish(user_id)

    comments = payload.comments or []
    max_comments = await _get_user_max_comments_per_post(user_id)
    if len(comments) > max_comments:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Votre offre autorise au maximum {max_comments} commentaire(s) par publication. "
                "Reduisez le nombre de commentaires ou passez a une offre superieure."
            ),
        )

    text_value = (payload.text or "").strip()
    media_url = (payload.media_url or "").strip() or None
    # Meta's own APIs only require text on a plain text-only post (Graph API
    # rejects an empty /feed message with no attachment) -- a photo or video
    # carries the caption/message as optional, so text is only mandatory
    # here when there is no media to publish instead.
    if not text_value and not media_url:
        raise HTTPException(status_code=400, detail="text is required when no media is attached")

    accounts = await _resolve_accounts_for_publish(user_id, payload.account_ids, _SOCIAL_POST_PLATFORMS)
    await _assert_user_can_publish(user_id, len(accounts))
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())
    media_type = payload.media_type if media_url else None
    # A background can't be combined with a photo/video (Facebook drops the
    # background style the moment media is attached), so only default to
    # the first preset when there's no attached media at all.
    background_id = (payload.background_id or anonymous_stories.BACKGROUND_PRESETS[0]["id"]) if not media_url else None

    # Keyed by account id (not platform) so publishing to several accounts
    # of the same platform (e.g. two Facebook Pages) reports each one
    # separately instead of the second silently overwriting the first.
    results: Dict[str, Any] = {}
    for account in accounts:
        result_key = str(account.get("id") or account.get("platform"))
        results[result_key] = await _publish_or_schedule_social_post(
            user_id, account, publish_priority, is_scheduled, scheduled_for, payload.timezone,
            text_value, background_id, comments, media_url, media_type,
        )

    overall_success = all(result.get("success") for result in results.values())

    return {
        "success": overall_success,
        "results": results,
        "background_id": background_id,
        "scheduled": is_scheduled,
    }


_COMMENT_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
_COMMENT_IMAGE_MAX_BYTES = 10 * 1024 * 1024
# Longest a presigned S3 URL signed with static IAM credentials (SigV4) can
# live -- AWS's own hard cap, not a choice made here. A comment's image_url
# is stored as-is in the publish job's payload (see _schedule_social_post_job)
# and only resolved by Facebook/LinkedIn when the scheduled post actually
# goes out, so a post scheduled further out than this window would find its
# comment image link expired by then.
_COMMENT_IMAGE_URL_EXPIRATION_SECONDS = 7 * 24 * 3600


def _validate_comment_image_upload(file: Optional[UploadFile]) -> None:
    if not file:
        raise HTTPException(status_code=400, detail="Missing image file")
    content_type = str(file.content_type or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Invalid image content type")


async def _save_comment_image_upload(file: UploadFile, local_path: str) -> None:
    async with aiofiles.open(local_path, "wb") as buffer:
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > _COMMENT_IMAGE_MAX_BYTES:
                raise HTTPException(status_code=400, detail="Image is too large (max 10 MB)")
            await buffer.write(chunk)


@app.post("/api/social/comment-image/upload", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 503: {"description": "Service Unavailable"}})
async def upload_social_comment_image(
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[UploadFile, File()],
):
    """Uploads an image drag-and-dropped (or picked) onto a follow-up comment
    in the "Faire une publication" composer (see SocialPostComposerModal)
    and returns a URL Facebook can fetch server-side as the comment's
    attachment_url -- a local blob: URL wouldn't survive the browser tab
    closing, let alone a post scheduled for later."""
    _validate_comment_image_upload(file)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise HTTPException(status_code=503, detail="AWS_S3_BUCKET is required for image uploads")

    safe_name = _sanitize_input_filename(file.filename) or "image.jpg"
    ext = os.path.splitext(safe_name)[1].lower()
    if ext not in _COMMENT_IMAGE_EXTENSIONS:
        ext = ".jpg"

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    local_path = os.path.join(UPLOAD_DIR, f"comment_image_{uuid.uuid4().hex}{ext}")
    try:
        await _save_comment_image_upload(file, local_path)
        s3_key = f"social_comment_images/{user_id}/{uuid.uuid4().hex}{ext}"
        if not upload_file_to_s3(local_path, bucket, s3_key):
            raise HTTPException(status_code=503, detail="Failed to upload image")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass

    image_url = generate_presigned_url(bucket, s3_key, expiration=_COMMENT_IMAGE_URL_EXPIRATION_SECONDS) or ""
    if not image_url:
        raise HTTPException(status_code=503, detail="Failed to generate image URL")

    return {"image_url": image_url}


_POST_MEDIA_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
_POST_MEDIA_IMAGE_MAX_BYTES = 10 * 1024 * 1024
_POST_MEDIA_VIDEO_MAX_BYTES = 200 * 1024 * 1024
# Matches _COMMENT_IMAGE_URL_EXPIRATION_SECONDS: a scheduled post's
# media_url is stored as-is in the publish job's payload (see
# _schedule_social_post_job) and only resolved when the post actually goes
# out, so it needs to survive as long as a post can be scheduled for.
_POST_MEDIA_URL_EXPIRATION_SECONDS = 7 * 24 * 3600


def _detect_post_media_type(file: Optional[UploadFile]) -> str:
    """Returns "video" or "image", from the browser-supplied content_type
    first and the filename extension as a fallback (some OSes/browsers send
    application/octet-stream for common video containers)."""
    if not file:
        raise HTTPException(status_code=400, detail="Missing media file")
    content_type = str(file.content_type or "").lower()
    if content_type.startswith("video/"):
        return "video"
    if content_type.startswith("image/"):
        return "image"
    ext = os.path.splitext(_sanitize_input_filename(file.filename) or "")[1].lower()
    if ext in _COMMON_VIDEO_EXTENSIONS:
        return "video"
    if ext in _POST_MEDIA_IMAGE_EXTENSIONS:
        return "image"
    raise HTTPException(status_code=400, detail="Unsupported media type (use an image or a video)")


async def _save_post_media_upload(file: UploadFile, local_path: str, max_bytes: int) -> None:
    async with aiofiles.open(local_path, "wb") as buffer:
        total = 0
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise HTTPException(status_code=400, detail=f"File is too large (max {max_bytes // (1024 * 1024)} MB)")
            await buffer.write(chunk)


@app.post("/api/social/post-media/upload", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 503: {"description": "Service Unavailable"}})
async def upload_social_post_media(
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[UploadFile, File()],
):
    """Uploads the photo or video attached to a "Faire une publication" post
    (see SocialPostComposerModal) and returns a URL Facebook/LinkedIn can
    fetch server-side, plus the detected media_type so the caller can route
    it as PublishRequest.video_url or .image_url (see
    _build_social_post_publish_payload)."""
    media_type = _detect_post_media_type(file)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if not bucket:
        raise HTTPException(status_code=503, detail="AWS_S3_BUCKET is required for media uploads")

    default_name = "video.mp4" if media_type == "video" else "image.jpg"
    safe_name = _sanitize_input_filename(file.filename) or default_name
    ext = os.path.splitext(safe_name)[1].lower()
    allowed_extensions = _COMMON_VIDEO_EXTENSIONS if media_type == "video" else _POST_MEDIA_IMAGE_EXTENSIONS
    if ext not in allowed_extensions:
        ext = ".mp4" if media_type == "video" else ".jpg"
    max_bytes = _POST_MEDIA_VIDEO_MAX_BYTES if media_type == "video" else _POST_MEDIA_IMAGE_MAX_BYTES

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    local_path = os.path.join(UPLOAD_DIR, f"post_media_{uuid.uuid4().hex}{ext}")
    try:
        await _save_post_media_upload(file, local_path, max_bytes)
        s3_key = f"social_post_media/{user_id}/{uuid.uuid4().hex}{ext}"
        if not upload_file_to_s3(local_path, bucket, s3_key):
            raise HTTPException(status_code=503, detail="Failed to upload media")
    finally:
        try:
            if os.path.exists(local_path):
                os.remove(local_path)
        except Exception:
            pass

    media_url = generate_presigned_url(bucket, s3_key, expiration=_POST_MEDIA_URL_EXPIRATION_SECONDS) or ""
    if not media_url:
        raise HTTPException(status_code=503, detail="Failed to generate media URL")

    return {"media_url": media_url, "media_type": media_type}


async def _publish_caption_now(user_id: str, account: Dict[str, Any], publish_priority: int, final_title: str, final_description: str, media_url: str) -> Dict[str, Any]:
    platform_name = str(account.get("platform") or "")
    publish_job_id = await _insert_publish_job(
        user_id=user_id,
        platform=platform_name,
        external_id="n/a",
        status="queued",
        priority=publish_priority,
        payload={
            "source_type": "caption",
            "account_id": account.get("id"),
            "title": final_title,
            "description": final_description,
            "media_url": media_url,
        },
    )
    try:
        await _update_publish_job_status(publish_job_id, "processing")

        publish_payload = PublishRequest(
            user_id=user_id,
            title=final_title,
            description=final_description,
            text=final_description,
            caption=final_description,
            video_url=media_url,
        )
        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
        post_url = _build_social_post_url(platform_name, platform_result)
        await _update_publish_job_status(publish_job_id, "done", external_id=external_id, post_url=post_url)
        return {
            "success": True,
            "result": platform_result,
            "publish_job_id": publish_job_id,
        }
    except Exception as exc:
        err_msg = str(exc)
        await _update_publish_job_status(publish_job_id, "failed", error_message=err_msg)
        return {
            "success": False,
            "error": err_msg,
            "publish_job_id": publish_job_id,
        }


@app.post("/api/captions/{caption_id}/share", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def share_caption(caption_id: str, payload: ReelShareRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    await _assert_user_has_active_subscription_for_publish(user_id)

    row = await supabase_get_caption(caption_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_CAPTION_NOT_FOUND)

    item = _normalize_caption_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail=_NO_MEDIA_URL_AVAILABLE)

    final_title = payload.title or row.get("caption_title") or "Sous-titres"
    final_description = payload.description or row.get("caption_description") or ""
    accounts = await _resolve_accounts_for_publish(user_id, payload.account_ids, _SHARE_PLATFORMS)
    await _assert_user_can_publish(user_id, len(accounts))
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    results: Dict[str, Any] = {}
    overall_success = True
    for account in accounts:
        result_key = str(account.get("id") or account.get("platform"))
        if is_scheduled:
            results[result_key] = await _schedule_share_publish_job(
                user_id, account, "caption", caption_id, publish_priority, scheduled_for, payload.timezone, final_title, final_description, media_url,
            )
            continue

        result = await _publish_caption_now(user_id, account, publish_priority, final_title, final_description, media_url)
        results[result_key] = result
        if not result["success"]:
            overall_success = False

    return {
        "success": overall_success,
        "results": results,
    }


# --------------------------------------------------------------------------
# Film Summary ("Resume de film") -- movie (upload/YouTube) -> technical +
# narrative-film validation -> transcript + scene index -> AI edit plan ->
# user review -> TTS voice-over + FFmpeg assembly. See film_summary.py /
# film_summary_render.py for the validation/prompt/AI-call/ffmpeg logic
# this section wires into the app's existing job/credits/S3 machinery,
# same convention as the anonymous-stories section above.
# --------------------------------------------------------------------------

class FilmSummaryPlanUpdateRequest(BaseModel):
    plan: Dict[str, Any]


class FilmSummaryRenderRequest(BaseModel):
    voice_id: Optional[str] = None


class FilmSummaryAudioSettingsUpdateRequest(BaseModel):
    subtitles_enabled: Optional[bool] = None
    subtitle_style: Optional[Dict[str, Any]] = None


class FilmSummaryTranslateNarrationRequest(BaseModel):
    narration_language: str


def _normalize_film_summary_row(row: Dict[str, Any], *, include_content: bool = False) -> Dict[str, Any]:
    item = {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "source_type": row.get("source_type"),
        "status": row.get("status"),
        "stage": row.get("stage"),
        "job_id": row.get("job_id"),
        "source_duration_seconds": row.get("source_duration_seconds"),
        "target_duration_seconds": row.get("target_duration_seconds"),
        "source_language": row.get("source_language"),
        "narration_language": row.get("narration_language"),
        "narration_style": row.get("narration_style"),
        "voice_id": row.get("voice_id"),
        "film_confidence": row.get("film_confidence"),
        "rejection_reason": row.get("rejection_reason"),
        "error_code": row.get("error_code"),
        "error_message": row.get("error_message"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "completed_at": row.get("completed_at"),
        "edit_mode": row.get("edit_mode") or "automatic",
        "subtitles_enabled": bool(row.get("subtitles_enabled") or False),
        "subtitle_style": row.get("subtitle_style") or None,
    }
    if include_content:
        item["classification"] = row.get("classification") or {}
        item["scene_index"] = row.get("scene_index") or []
        item["edit_plan"] = row.get("edit_plan") or {}
        item["validation_report"] = row.get("validation_report") or {}
        item["manual_selection"] = row.get("manual_selection") or []
        bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
        # The review panel's video preview and clip-swap picker need the
        # original source video (not just the preview/final render) to let
        # the user see and seek through the whole film -- source_s3_key is
        # always populated by the time analysis finishes (even for a
        # youtube source, see _run_film_summary_analysis_pipeline) and only
        # cleared once the final render completes
        # (_finalize_film_summary_render), so it's reliably available
        # throughout the awaiting_review window.
        if row.get("source_s3_key"):
            item["source_url"] = generate_presigned_url(bucket_name, row["source_s3_key"], expiration=3600)
        if row.get("preview_s3_key"):
            item["preview_url"] = generate_presigned_url(bucket_name, row["preview_s3_key"], expiration=3600)
        if row.get("final_s3_key"):
            item["final_url"] = generate_presigned_url(bucket_name, row["final_s3_key"], expiration=3600)
    return item


def _estimate_film_summary_analysis_required_credits(duration_seconds: float, size_bytes: float) -> float:
    breakdown = estimate_film_summary_analysis_cost_usd(
        duration_minutes=max(1.0, float(duration_seconds or 0.0) / 60.0),
        video_size_gb=max(0.0, _bytes_to_gb(float(size_bytes or 0.0))),
    )
    return float(calculate_credits_for_operation(breakdown)["final_credits"])


def _plan_target_duration_seconds(plan: Dict[str, Any]) -> int:
    # target_duration_seconds is stored as an integer column -- Postgres's
    # integer input parser rejects fractional text ("367.0") outright, so
    # this must round rather than just cast plan["target_duration_ms"] / 1000.
    return int(round((plan.get("target_duration_ms") or 0) / 1000.0))


def _estimate_film_summary_render_required_credits(target_duration_seconds: float, narration_character_count: float) -> float:
    breakdown = estimate_film_summary_render_cost_usd(
        target_duration_minutes=max(1.0, float(target_duration_seconds or 0.0) / 60.0),
        narration_character_count=narration_character_count,
    )
    return float(calculate_credits_for_operation(breakdown)["final_credits"])


def _total_narration_character_count(plan: Dict[str, Any]) -> int:
    return sum(
        len(seg.get("narration") or "")
        for seg in (plan.get("segments") or [])
        if seg.get("type") == film_summary.SEGMENT_TYPE_VOICE_OVER
    )


async def _reserve_film_summary_credits_or_cleanup(
    user_id: str, required_credits: float, input_path: Optional[str], job_output_dir: str,
) -> None:
    try:
        await _reserve_job_credits(user_id, required_credits)
    except HTTPException:
        if input_path and os.path.exists(input_path):
            os.remove(input_path)
        shutil.rmtree(job_output_dir, ignore_errors=True)
        raise


async def _create_film_summary_endpoint_project(
    user_id: str, film_job_id: str, source_name: str, input_path: str, size_bytes: int,
    local_duration: float, source_type: str, source_url_value: Optional[str], film_title: str,
) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    try:
        project_description = _build_short_project_summary(film_title, fallback_title=film_title)
        bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
        s3_source_key = f"{_FILM_SUMMARIES_PREFIX}{user_id}/{film_job_id}/{source_name}"

        if os.path.exists(input_path):
            upload_file_to_s3(input_path, bucket_name, s3_source_key)
        project_thumbnail_ref = _generate_and_upload_project_thumbnail_from_source(
            input_path,
            bucket_name,
            user_id,
            film_job_id,
        )

        project = await supabase_create_project(
            user_id=user_id,
            name=film_title,
            description=project_description,
            project_type="film_summary",
            source_type=source_type,
            source_url=source_url_value,
            source_s3_key=s3_source_key,
            source_size=size_bytes,
            source_duration=int(local_duration) if local_duration else None,
            thumbnail_url=project_thumbnail_ref,
            status="processing",
        )
        await _finalize_source_media_retention(film_job_id, user_id, project, size_bytes, bucket_name, s3_source_key)
        return project
    except Exception as e:
        logger.warning(f"Failed to create project for film summary job {film_job_id}: {str(e)}")
        return None


async def _resolve_film_summary_source(
    file: Optional[UploadFile], url: Optional[str], output_dir: str,
) -> Dict[str, Any]:
    if file:
        _validate_video_extension(file.filename if file else "", context_label="resume de film")
        source_name = os.path.basename(str(file.filename or "film_source.mp4"))
        input_path = os.path.join(output_dir, f"film_input_{int(time.time())}_{source_name}")
        size_bytes = await _save_caption_upload_file(file, input_path, FILM_SUMMARY_MAX_UPLOAD_SIZE_BYTES)
        return {
            "input_path": input_path,
            "source_name": source_name,
            "size_bytes": size_bytes,
            "source_type": film_summary.FilmSummarySourceType.UPLOAD,
            "source_url_value": None,
            "film_title": _project_name_from_uploaded_file(source_name),
        }

    if not _is_youtube_url(url):
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Only YouTube links are supported for film summaries in V1.")

    try:
        youtube_source = await asyncio.to_thread(film_summary.download_youtube_source, url, output_dir)
        input_path = youtube_source["path"]
    except Exception as exc:
        shutil.rmtree(output_dir, ignore_errors=True)
        raise HTTPException(status_code=400, detail="Le lien YouTube n'est pas valide ou ne peut pas etre traite.") from exc

    try:
        size_bytes = os.path.getsize(input_path)
    except OSError:
        size_bytes = 0

    return {
        "input_path": input_path,
        "source_name": "youtube_source.mp4",
        "size_bytes": size_bytes,
        "source_type": film_summary.FilmSummarySourceType.YOUTUBE,
        "source_url_value": url,
        "film_title": youtube_source.get("title") or "Resume de film YouTube",
    }


async def _resolve_film_summary_request_fields(
    request: Request, title: Optional[str], target_duration_seconds: Optional[float],
    source_language: Optional[str], narration_language: Optional[str], narration_style: Optional[str],
    voice_id: Optional[str],
) -> Tuple[Optional[str], Optional[float], Optional[str], Optional[str], Optional[str], Optional[str]]:
    """JSON-body submissions (YouTube link, no multipart) carry the extra
    fields in the body instead of Form() -- same content-type branching as
    _resolve_anonymous_story_page_context. Pulled out of create_film_summary
    to keep its cognitive complexity down."""
    content_type = request.headers.get("content-type", "")
    if _CONTENT_TYPE_JSON not in content_type:
        return title, target_duration_seconds, source_language, narration_language, narration_style, voice_id
    body = await request.json()
    return (
        body.get("title", title),
        body.get("target_duration_seconds", target_duration_seconds),
        body.get("source_language", source_language),
        body.get("narration_language", narration_language),
        body.get("narration_style", narration_style),
        body.get("voice_id", voice_id),
    )


def _resolve_film_summary_title(title: Optional[str], source_title: str) -> str:
    resolved = title or source_title or "Resume de film"
    return resolved.strip()[:200]


def _cleanup_film_summary_upload(input_path: Optional[str], output_dir: str) -> None:
    if input_path and os.path.exists(input_path):
        os.remove(input_path)
    shutil.rmtree(output_dir, ignore_errors=True)


def _validate_film_summary_technical_constraints_or_cleanup(
    input_path: str, size_bytes: float, output_dir: str,
) -> float:
    """Probe technical metadata and run Niveau 1 validation, cleaning up the
    partially-uploaded source on rejection. Pulled out of
    create_film_summary to keep its cognitive complexity down."""
    local_duration = _probe_local_video_duration_seconds(input_path)
    tech_meta = film_summary.probe_technical_metadata(input_path)
    duration_seconds = local_duration or tech_meta["duration_seconds"]
    try:
        film_summary.validate_technical_constraints(
            duration_seconds=duration_seconds,
            size_bytes=float(size_bytes),
            has_video_track=tech_meta["has_video"],
            has_audio_track=tech_meta["has_audio"],
            max_upload_size_bytes=FILM_SUMMARY_MAX_UPLOAD_SIZE_BYTES,
            min_source_duration_seconds=FILM_SUMMARY_MIN_SOURCE_DURATION_SECONDS,
            max_source_duration_seconds=FILM_SUMMARY_MAX_SOURCE_DURATION_SECONDS,
        )
    except film_summary.FilmSummaryValidationError as exc:
        _cleanup_film_summary_upload(input_path, output_dir)
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
    return local_duration


def _resolve_film_summary_target_duration(target_duration_seconds: Optional[float], local_duration: float) -> int:
    if target_duration_seconds:
        return int(target_duration_seconds)
    return film_summary.derive_target_duration_seconds(
        local_duration, FILM_SUMMARY_MIN_TARGET_DURATION_SECONDS, FILM_SUMMARY_MAX_TARGET_DURATION_SECONDS,
    )


def _row_field(row: Optional[Dict[str, Any]], key: str) -> Optional[Any]:
    if not row:
        return None
    return row.get(key)


def _resolve_film_summary_narration_settings(narration_language: Optional[str], narration_style: Optional[str]) -> Tuple[str, str]:
    resolved_language = (narration_language or "").strip()[:50]
    resolved_style = (narration_style or "cinematic").strip()[:50]
    return resolved_language, resolved_style or "cinematic"


async def _persist_film_summary_row(
    user_id: str, project_id: Optional[str], film_title: str, source_type: str, source_url_value: Optional[str],
    source_s3_key: Optional[str], local_duration: float, resolved_target_duration: int, source_language: Optional[str],
    resolved_narration_language: str, resolved_narration_style: str, resolved_voice_id: str, film_job_id: str,
) -> Optional[Dict[str, Any]]:
    if not is_supabase_configured():
        return None
    return await supabase_insert_film_summary({
        "user_id": user_id,
        "project_id": project_id,
        "title": film_title,
        "source_type": source_type,
        "source_url": source_url_value,
        "source_s3_key": source_s3_key,
        # Truncating to an int here used to lose up to ~1s of precision --
        # a segment whose end_ms was valid against the full-precision
        # duration used for the original plan (_run_planning_and_validation_
        # stages' duration_ms) could then fail render_film_summary_
        # endpoint's "timecode hors limites" check, which recomputes
        # source_duration_ms from this same stored value.
        "source_duration_seconds": float(local_duration or 0.0),
        "target_duration_seconds": resolved_target_duration,
        "source_language": (source_language or "").strip()[:50] or None,
        "narration_language": resolved_narration_language or None,
        "narration_style": resolved_narration_style,
        "voice_id": resolved_voice_id,
        "status": film_summary.FilmSummaryStatus.QUEUED,
        "stage": film_summary.FilmSummaryStage.UPLOADING,
        "job_id": film_job_id,
    })


@app.post("/api/film-summaries", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 413: {"description": "Payload Too Large"}, 429: {"description": "Too Many Requests"}})
async def create_film_summary(
    request: Request,
    user_id: Annotated[str, Depends(get_user_id_header)],
    file: Annotated[Optional[UploadFile], File()] = None,
    url: Annotated[Optional[str], Form()] = None,
    acknowledged: Annotated[Optional[str], Form()] = None,
    title: Annotated[Optional[str], Form()] = None,
    target_duration_seconds: Annotated[Optional[float], Form()] = None,
    source_language: Annotated[Optional[str], Form()] = None,
    narration_language: Annotated[Optional[str], Form()] = None,
    narration_style: Annotated[Optional[str], Form()] = None,
    voice_id: Annotated[Optional[str], Form()] = None,
):
    if not FILM_SUMMARY_ENABLED:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_DISABLED)

    url, ack_flag = await _resolve_process_endpoint_url_and_ack(request, url, acknowledged)
    _validate_process_endpoint_inputs(url, file, ack_flag)

    title, target_duration_seconds, source_language, narration_language, narration_style, voice_id = (
        await _resolve_film_summary_request_fields(
            request, title, target_duration_seconds, source_language, narration_language, narration_style, voice_id,
        )
    )

    try:
        film_summary.validate_target_duration_seconds(
            target_duration_seconds, FILM_SUMMARY_MIN_TARGET_DURATION_SECONDS, FILM_SUMMARY_MAX_TARGET_DURATION_SECONDS,
        )
    except film_summary.FilmSummaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await _enforce_job_concurrency_limit(user_id)

    film_job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, film_job_id)
    os.makedirs(output_dir, exist_ok=True)

    source = await _resolve_film_summary_source(file, url, output_dir)
    input_path = source["input_path"]
    source_name = source["source_name"]
    size_bytes = source["size_bytes"]
    source_type = source["source_type"]
    source_url_value = source["source_url_value"]
    film_title = _resolve_film_summary_title(title, source["film_title"])

    local_duration = _validate_film_summary_technical_constraints_or_cleanup(input_path, size_bytes, output_dir)
    resolved_target_duration = _resolve_film_summary_target_duration(target_duration_seconds, local_duration)

    analysis_required_credits = _estimate_film_summary_analysis_required_credits(local_duration, float(size_bytes))
    await _reserve_film_summary_credits_or_cleanup(user_id, analysis_required_credits, input_path, output_dir)

    job_priority = await _resolve_user_job_priority(user_id)

    project = await _create_film_summary_endpoint_project(
        user_id, film_job_id, source_name, input_path, int(size_bytes), local_duration,
        source_type, source_url_value, film_title,
    )
    project_id = _row_field(project, "id")
    source_s3_key = _row_field(project, "source_s3_key")

    resolved_narration_language, resolved_narration_style = _resolve_film_summary_narration_settings(narration_language, narration_style)
    resolved_voice_id = film_summary.resolve_tts_voice(voice_id, FILM_SUMMARY_TTS_DEFAULT_VOICE)

    film_row = await _persist_film_summary_row(
        user_id, project_id, film_title, source_type, source_url_value, source_s3_key, local_duration,
        resolved_target_duration, source_language, resolved_narration_language, resolved_narration_style,
        resolved_voice_id, film_job_id,
    )

    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_FILM_SUMMARY,
        pipeline_name="FilmSummaryAnalysisPipeline",
        job_id=film_job_id,
        job_data={
            "phase": "analysis",
            "source_type": source_type,
            "source_value": source_url_value or source_name,
            "analysis_required_credits": analysis_required_credits,
            "project_id": project_id,
        },
        max_attempts=FILM_SUMMARY_JOB_MAX_ATTEMPTS,
        reserved_quota=analysis_required_credits,
        priority=job_priority,
        queue_name="film_summaries",
    )
    await reel_job_manager.enqueue_job(film_job_id)

    film_summary_id = _row_field(film_row, "id")
    _spawn_background_task(_run_film_summary_analysis_job(
        job_id=film_job_id,
        user_id=user_id,
        film_summary_id=film_summary_id,
        project_id=project_id,
        input_path=input_path,
        output_dir=output_dir,
        local_duration=local_duration,
        size_bytes=float(size_bytes),
        analysis_required_credits=analysis_required_credits,
        target_duration_seconds=resolved_target_duration,
        narration_language=resolved_narration_language,
        narration_style=resolved_narration_style,
        source_language=source_language,
    ))

    return {
        "job_id": film_job_id,
        "film_summary_id": film_summary_id,
        "project_id": project_id,
        "status": "queued",
    }


_FILM_SUMMARY_REJECTION_CODES = {
    film_summary.FilmSummaryErrorCode.SOURCE_TOO_LARGE,
    film_summary.FilmSummaryErrorCode.SOURCE_TOO_LONG,
    film_summary.FilmSummaryErrorCode.SOURCE_TOO_SHORT,
    film_summary.FilmSummaryErrorCode.NO_VIDEO_TRACK,
    film_summary.FilmSummaryErrorCode.NO_AUDIO_TRACK,
    film_summary.FilmSummaryErrorCode.INVALID_FORMAT,
    film_summary.FilmSummaryErrorCode.NOT_A_FILM,
}


async def _mark_film_summary_job_terminal(
    user_id: str, film_summary_id: Optional[str], project_id: Optional[str],
    status: str, stage: str, error_code: str, error_message: str,
) -> None:
    if film_summary_id and is_supabase_configured():
        updates: Dict[str, Any] = {"status": status, "stage": stage, "error_code": error_code, "error_message": error_message}
        if status == film_summary.FilmSummaryStatus.REJECTED:
            updates["rejection_reason"] = error_message
        await supabase_update_film_summary(film_summary_id, user_id, updates)
    if project_id and is_supabase_configured():
        try:
            await supabase_update_project_status(project_id, "failed", user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to update project status to failed: {str(e)}")


async def _run_film_summary_analysis_job(
    job_id: str, user_id: str, film_summary_id: Optional[str], project_id: Optional[str],
    input_path: str, output_dir: str, local_duration: float,
    size_bytes: float, analysis_required_credits: float, target_duration_seconds: float,
    narration_language: str, narration_style: str, source_language: Optional[str] = None,
) -> None:
    try:
        await reel_job_manager.start_job(job_id)
        await _run_film_summary_analysis_pipeline_stages(
            job_id, user_id, film_summary_id, project_id, input_path,
            local_duration, size_bytes, analysis_required_credits, target_duration_seconds,
            narration_language, narration_style, source_language=source_language,
        )
    except film_summary.FilmSummaryValidationError as exc:
        await _handle_film_summary_validation_failure(exc, job_id, user_id, film_summary_id, project_id, analysis_required_credits)
    except Exception as exc:  # noqa: BLE001 -- any unexpected failure must still fail the job and refund the user
        await _handle_film_summary_unexpected_failure(
            exc, job_id, user_id, film_summary_id, project_id, analysis_required_credits,
            f"Film summary analysis job {job_id} failed",
        )
    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


async def _run_transcription_and_scene_detection_stages(
    job_id: str, user_id: str, film_summary_id: Optional[str], input_path: str,
    source_language: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {
            "status": film_summary.FilmSummaryStatus.PROCESSING,
            "stage": film_summary.FilmSummaryStage.TRANSCRIBING,
        })
    await reel_job_manager.update_progress(job_id, 20, film_summary.FilmSummaryStage.TRANSCRIBING)

    try:
        transcript = await film_summary.transcribe_video_with_timecodes(input_path, language_hint=source_language)
    except Exception as exc:
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.TRANSCRIPTION_FAILED, str(exc)) from exc

    transcript_segments = transcript.get("segments") or []
    transcript_text = str(transcript.get("text") or "").strip()
    if not transcript_text or not transcript_segments:
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.TRANSCRIPTION_FAILED, "Empty transcript")

    # The user's own choice always wins -- only fall back to whatever
    # AssemblyAI reports when they left source_language on auto-detect, so
    # an explicit choice can never be silently stomped by a (mis)detected
    # value.
    effective_source_language = source_language or transcript.get("language")

    if is_supabase_configured():
        await supabase_upsert_transcription({
            "user_id": user_id,
            "job_id": job_id,
            "clip_index": 0,
            "source_type": "video",
            "transcript_provider": "assemblyai",
            "transcript_language": effective_source_language,
            "transcript_text": transcript_text,
        })

    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {
            "stage": film_summary.FilmSummaryStage.DETECTING_SCENES,
            "transcript_segments": transcript_segments,
            "source_language": effective_source_language,
        })
    await reel_job_manager.update_progress(job_id, 40, film_summary.FilmSummaryStage.DETECTING_SCENES)

    try:
        scenes = await asyncio.wait_for(
            asyncio.to_thread(film_summary.detect_scenes, input_path, FILM_SUMMARY_SCENE_THRESHOLD),
            timeout=FILM_SUMMARY_SCENE_DETECTION_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise film_summary.FilmSummaryValidationError(
            film_summary.FilmSummaryErrorCode.SCENE_DETECTION_FAILED,
            f"Scene detection timed out after {FILM_SUMMARY_SCENE_DETECTION_TIMEOUT_SECONDS}s",
        ) from exc
    except Exception as exc:
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.SCENE_DETECTION_FAILED, str(exc)) from exc

    scene_index = film_summary.build_scene_index(scenes, transcript_segments)
    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {"scene_index": scene_index})

    return transcript_segments, scene_index, str(transcript.get("language") or "")


async def _run_classification_gate(
    job_id: str, user_id: str, film_summary_id: Optional[str], local_duration: float, narration_language: str,
    input_path: str, transcript_segments: List[Dict[str, Any]], scene_index: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {"stage": film_summary.FilmSummaryStage.VALIDATING_FILM})
    await reel_job_manager.update_progress(job_id, 50, film_summary.FilmSummaryStage.VALIDATING_FILM)

    scene_stats = {
        "scene_count": len(scene_index),
        "average_scene_seconds": (
            sum(s.get("duration_ms", 0) for s in scene_index) / len(scene_index) / 1000.0
        ) if scene_index else 0.0,
    }
    transcript_sample = film_summary.build_transcript_sample(transcript_segments)
    keyframe_data_urls = await asyncio.to_thread(film_summary.extract_classification_keyframes, input_path, scene_index)

    verdict = await film_summary.classify_media_type(
        metadata={"duration_seconds": local_duration, "narration_language": narration_language},
        transcript_sample=transcript_sample, scene_stats=scene_stats, keyframe_data_urls=keyframe_data_urls,
    )
    usage = verdict.pop("usage", {})
    decision = film_summary.decide_film_verdict(verdict, FILM_SUMMARY_VALIDATION_THRESHOLD)

    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {
            "classification": verdict, "film_confidence": verdict.get("confidence"),
        })

    if decision != "ACCEPTED":
        message = verdict.get("user_message") or "This video does not appear to be a narrative film."
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.NOT_A_FILM, message)

    return usage


async def _run_planning_and_validation_stages(
    job_id: str, user_id: str, film_summary_id: Optional[str], local_duration: float, target_duration_seconds: float,
    source_language: str, narration_language: str, narration_style: str,
    transcript_segments: List[Dict[str, Any]], scene_index: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {"stage": film_summary.FilmSummaryStage.PLANNING})
    await reel_job_manager.update_progress(job_id, 70, film_summary.FilmSummaryStage.PLANNING)

    duration_ms = int((local_duration or 0) * 1000)
    target_duration_ms = int((target_duration_seconds or 0) * 1000)
    movie_metadata = {
        "title": "",
        "source_duration_ms": duration_ms,
        "source_language": source_language or "",
        "narration_language": narration_language or source_language or "",
    }
    generation_constraints = film_summary.build_generation_constraints(target_duration_ms, FILM_SUMMARY_DURATION_TOLERANCE_RATIO)

    try:
        plan_result = await film_summary.generate_edit_plan(
            movie_metadata=movie_metadata, target_duration_ms=target_duration_ms,
            narration_language=movie_metadata["narration_language"], narration_style=narration_style,
            transcript_segments=transcript_segments, scene_index=scene_index,
            generation_constraints=generation_constraints,
        )
    except film_summary.FilmSummaryValidationError:
        raise
    except Exception as exc:
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.PLANNING_FAILED, str(exc)) from exc

    plan = plan_result["plan"]
    usage = plan_result["usage"]

    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {"stage": film_summary.FilmSummaryStage.VALIDATING_PLAN})
    await reel_job_manager.update_progress(job_id, 90, film_summary.FilmSummaryStage.VALIDATING_PLAN)

    valid_scene_ids = [s.get("scene_id") for s in scene_index]
    # The corrective retry inside generate_edit_plan already gave the model
    # its best shot at the requested target -- if segmentation still landed
    # outside tolerance, realign the target to what was actually produced
    # rather than presenting the user a plan they're blocked from ever
    # generating (see realign_plan_target_duration).
    plan, validation_report = film_summary.realign_plan_target_duration(
        plan, source_duration_ms=duration_ms, valid_scene_ids=valid_scene_ids,
        duration_tolerance_ratio=FILM_SUMMARY_DURATION_TOLERANCE_RATIO,
    )
    return plan, validation_report, usage


async def _run_film_summary_analysis_pipeline_stages(
    job_id: str, user_id: str, film_summary_id: Optional[str], project_id: Optional[str], input_path: str,
    local_duration: float, size_bytes: float, analysis_required_credits: float, target_duration_seconds: float,
    narration_language: str, narration_style: str, source_language: Optional[str] = None,
) -> None:
    # Niveau 1 technical validation already ran synchronously in
    # create_film_summary, before the job/credits reservation even
    # existed -- spec section 5's requirement that it be blocking and run
    # before the costly multimodal analysis is satisfied there.
    # Transcription and scene detection run next since the Niveau 2
    # classifier below needs their output as its own "signals" anyway;
    # they gate the expensive planning call, preserving the spirit of
    # "processing continues only if validation succeeds" for the one stage
    # that actually dominates cost.
    transcript_segments, scene_index, detected_language = await _run_transcription_and_scene_detection_stages(
        job_id, user_id, film_summary_id, input_path, source_language=source_language,
    )
    classification_usage = await _run_classification_gate(
        job_id, user_id, film_summary_id, local_duration, narration_language or detected_language,
        input_path, transcript_segments, scene_index,
    )
    plan, validation_report, planning_usage = await _run_planning_and_validation_stages(
        job_id, user_id, film_summary_id, local_duration, target_duration_seconds,
        detected_language, narration_language, narration_style, transcript_segments, scene_index,
    )
    total_usage = {
        "prompt_tokens": classification_usage.get("prompt_tokens", 0) + planning_usage.get("prompt_tokens", 0),
        "completion_tokens": classification_usage.get("completion_tokens", 0) + planning_usage.get("completion_tokens", 0),
    }
    await _finalize_film_summary_analysis(
        job_id, user_id, film_summary_id, project_id, local_duration, size_bytes,
        analysis_required_credits, plan, validation_report, total_usage,
    )


def _build_film_summary_analysis_cost_breakdown(duration_seconds: float, size_bytes: float, usage: Dict[str, Any]) -> Dict[str, Any]:
    breakdown = estimate_film_summary_analysis_cost_usd(
        duration_minutes=max(1.0, float(duration_seconds or 0.0) / 60.0),
        video_size_gb=max(0.0, _bytes_to_gb(float(size_bytes or 0.0))),
    )
    openai_usd = estimate_llm_usage_cost_usd("openai", usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
    breakdown["openai_usd"] = openai_usd
    breakdown["total_usd"] = round(breakdown["s3_usd"] + breakdown["vps_usd"] + breakdown["assembly_usd"] + openai_usd, 6)
    return calculate_credits_for_operation(breakdown)


async def _finalize_film_summary_analysis(
    job_id: str, user_id: str, film_summary_id: Optional[str], project_id: Optional[str],
    local_duration: float, size_bytes: float, analysis_required_credits: float,
    plan: Dict[str, Any], validation_report: Dict[str, Any], usage: Dict[str, Any],
) -> None:
    cost_breakdown = _build_film_summary_analysis_cost_breakdown(local_duration, size_bytes, usage)
    final_credits = float(cost_breakdown.get("final_credits") or 0.0)

    if film_summary_id and is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {
            "status": film_summary.FilmSummaryStatus.AWAITING_REVIEW,
            "stage": film_summary.FilmSummaryStage.AWAITING_USER_REVIEW,
            "edit_plan": plan,
            "validation_report": validation_report,
            # target_duration_seconds is the authoritative target the PATCH
            # /plan endpoint rebuilds from (film_summary.validate_edited_
            # plan_patch never trusts the plan's own copy) -- keep it in
            # sync with plan["target_duration_ms"], which realign_plan_
            # target_duration may just have moved.
            "target_duration_seconds": _plan_target_duration_seconds(plan),
            "billing_details": cost_breakdown,
            "total_cost_usd": cost_breakdown.get("total_usd", 0.0),
        })
        # No storage_delta here: the source video is transient (deleted once
        # the render finishes -- see _run_film_summary_render_pipeline_stages),
        # so it must never count against the user's persistent storage quota.
        # Only the preview/final outputs the user actually keeps are billed
        # for storage (_finalize_film_summary_render).
        debit_ok = await reel_job_manager.debit_credits_for_job(
            job_id=job_id, user_id=user_id, credits=final_credits,
            operation_type=film_summary.CREDIT_OPERATION_TYPE, reserved_credits=analysis_required_credits,
        )
        if not debit_ok:
            logger.warning(f"Insufficient balance to settle film summary analysis job {job_id}")

    if project_id and is_supabase_configured():
        try:
            await supabase_update_project_status(project_id, "processing", user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to update project {project_id} status: {str(e)}")

    await reel_job_manager.complete_job(
        job_id,
        {"film_summary_id": film_summary_id, "project_id": project_id, "validation_report": validation_report},
        actual_credit=final_credits,
        cost_breakdown=cost_breakdown,
        consumed_quota=1.0,
    )


@app.get("/api/film-summaries", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def list_film_summaries_endpoint(
    user_id: Annotated[str, Depends(get_user_id_header)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
    q: Optional[str] = None,
    status: Optional[str] = None,
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_NOT_CONFIGURED)

    rows, total = await supabase_list_film_summaries(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    items = [_normalize_film_summary_row(row) for row in rows]
    await _attach_media_asset_fields(items, CONTENT_KIND_FILM_SUMMARY)
    return {
        "items": items,
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@app.get("/api/film-summaries/voice-previews/{voice_id}", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 502: {"description": "Bad Gateway"}})
async def get_film_summary_voice_preview_endpoint(voice_id: str, _user_id: Annotated[str, Depends(get_user_id_header)]):
    """Returns a cached URL to a short demo line spoken by `voice_id`, so the
    create-form can let the user listen before choosing a narrator voice.
    Generated once per voice (OpenAI TTS) and cached on disk under
    FILM_SUMMARY_VOICE_PREVIEWS_DIR -- every request after the first for a
    given voice is a static file read, no OpenAI call.

    Declared before the /{film_summary_id} route below so this static
    "voice-previews" segment isn't swallowed as a film_summary_id."""
    resolved_voice = str(voice_id or "").strip().lower()
    if resolved_voice not in film_summary.ALLOWED_TTS_VOICES:
        raise HTTPException(status_code=400, detail="Unknown voice")

    preview_path = os.path.join(FILM_SUMMARY_VOICE_PREVIEWS_DIR, f"{resolved_voice}.mp3")
    # An empty/missing file is treated as "not cached yet" so a previous
    # generation that failed partway through (see synthesize_tts_segment)
    # and left nothing playable behind gets regenerated instead of being
    # served -- and permanently broken -- forever.
    if not os.path.exists(preview_path) or os.path.getsize(preview_path) == 0:
        try:
            await film_summary.synthesize_tts_segment(
                text=FILM_SUMMARY_VOICE_PREVIEW_TEXT, voice=resolved_voice, model=FILM_SUMMARY_TTS_MODEL,
                instructions=film_summary.build_tts_instructions("French"), output_path=preview_path,
            )
        except film_summary.FilmSummaryValidationError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return {"preview_url": f"/voice-previews/{resolved_voice}.mp3"}


@app.get("/api/film-summaries/{film_summary_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def get_film_summary_endpoint(film_summary_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    return _normalize_film_summary_row(row, include_content=True)


@app.get("/api/film-summaries/{film_summary_id}/plan", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def get_film_summary_plan_endpoint(film_summary_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    return {
        "edit_plan": row.get("edit_plan") or {},
        "validation_report": row.get("validation_report") or {},
        "scene_index": row.get("scene_index") or [],
    }


@app.patch("/api/film-summaries/{film_summary_id}/plan", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}})
async def update_film_summary_plan_endpoint(
    film_summary_id: str, payload: FilmSummaryPlanUpdateRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") != film_summary.FilmSummaryStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=409, detail="Plan can only be edited while awaiting review")

    movie_metadata = (row.get("edit_plan") or {}).get("movie") or {}
    target_duration_ms = int((row.get("target_duration_seconds") or 0) * 1000)
    try:
        normalized_plan = film_summary.validate_edited_plan_patch(
            payload.plan, movie_metadata=movie_metadata, target_duration_ms=target_duration_ms,
        )
    except film_summary.FilmSummaryValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    valid_scene_ids = [s.get("scene_id") for s in (row.get("scene_index") or [])]
    # A narration edit can move the total enough to fall outside tolerance
    # around the original target -- realign rather than block the user on a
    # number their edit doesn't give them a direct way to hit exactly.
    normalized_plan, validation_report = film_summary.realign_plan_target_duration(
        normalized_plan, source_duration_ms=int((row.get("source_duration_seconds") or 0) * 1000),
        valid_scene_ids=valid_scene_ids, duration_tolerance_ratio=FILM_SUMMARY_DURATION_TOLERANCE_RATIO,
    )

    updated = await supabase_update_film_summary(film_summary_id, user_id, {
        "edit_plan": normalized_plan, "validation_report": validation_report,
        "target_duration_seconds": _plan_target_duration_seconds(normalized_plan),
    })
    return _normalize_film_summary_row(updated, include_content=True)


@app.patch("/api/film-summaries/{film_summary_id}/audio-settings", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}})
async def update_film_summary_audio_settings_endpoint(
    film_summary_id: str, payload: FilmSummaryAudioSettingsUpdateRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Persists the user's subtitle toggle/style -- applied at render time
    (see render_edit_plan / _run_film_summary_render_pipeline_stages).
    Editable up to the same point as the plan itself."""
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") != film_summary.FilmSummaryStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=409, detail="Audio/subtitle settings can only be edited while awaiting review")

    updates = payload.model_dump(exclude_unset=True)

    if not updates:
        return _normalize_film_summary_row(row, include_content=True)

    updated = await supabase_update_film_summary(film_summary_id, user_id, updates)
    return _normalize_film_summary_row(updated, include_content=True)


@app.post("/api/film-summaries/{film_summary_id}/translate-narration", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}, 502: {"description": "Bad Gateway"}})
async def translate_film_summary_narration_endpoint(
    film_summary_id: str, payload: FilmSummaryTranslateNarrationRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    """Lets the user fix a wrong narration-language choice on an already-
    generated plan after the fact (see film_summary.translate_edit_plan_
    narration's docstring): footage, timing and segment structure are
    untouched, only each voice_over segment's narration text is
    retranslated. Persists the translated plan plus the row's own
    narration_language (so any later TTS/regeneration reflects the
    correction too), same 404/409/502 conventions as the sibling
    generate_film_summary_narration_endpoint."""
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") != film_summary.FilmSummaryStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=409, detail="Narration language can only be edited while awaiting review")

    resolved_language, _ = _resolve_film_summary_narration_settings(payload.narration_language, row.get("narration_style"))
    if not resolved_language:
        raise HTTPException(status_code=400, detail="narration_language is required")

    movie_metadata = {
        "title": row.get("title") or "",
        "source_duration_ms": int((row.get("source_duration_seconds") or 0) * 1000),
        "narration_style": row.get("narration_style") or "",
    }
    try:
        result = await film_summary.translate_edit_plan_narration(
            plan=row.get("edit_plan") or {}, target_language=resolved_language, movie_metadata=movie_metadata,
            duration_tolerance_ratio=FILM_SUMMARY_DURATION_TOLERANCE_RATIO,
        )
    except Exception as exc:
        # Same 502 convention as generate_film_summary_narration_endpoint's
        # own try/except: any failure here (OpenAI transport/config error,
        # malformed JSON after exhausting the retry, or the model breaking
        # the translation invariant) is a planning failure, never the
        # user's fault.
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    plan, validation_report = result["plan"], result["validation_report"]
    updated = await supabase_update_film_summary(film_summary_id, user_id, {
        "edit_plan": plan, "validation_report": validation_report, "narration_language": resolved_language,
    })
    return _normalize_film_summary_row(updated, include_content=True)


@app.post("/api/film-summaries/{film_summary_id}/validate", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def validate_film_summary_plan_endpoint(film_summary_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)

    plan = row.get("edit_plan") or {}
    valid_scene_ids = [s.get("scene_id") for s in (row.get("scene_index") or [])]
    # Realigns the target to the actual total when it's still outside
    # tolerance (e.g. a plan generated before this existed) instead of
    # leaving "Revalider" report the same unfixable duration mismatch.
    plan, validation_report = film_summary.realign_plan_target_duration(
        plan, source_duration_ms=int((row.get("source_duration_seconds") or 0) * 1000),
        valid_scene_ids=valid_scene_ids, duration_tolerance_ratio=FILM_SUMMARY_DURATION_TOLERANCE_RATIO,
    )
    await supabase_update_film_summary(film_summary_id, user_id, {
        "edit_plan": plan, "validation_report": validation_report,
        "target_duration_seconds": _plan_target_duration_seconds(plan),
    })
    return validation_report


@app.post("/api/film-summaries/{film_summary_id}/render", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}})
async def render_film_summary_endpoint(
    film_summary_id: str, payload: FilmSummaryRenderRequest, user_id: Annotated[str, Depends(get_user_id_header)],
):
    if not FILM_SUMMARY_ENABLED:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_DISABLED)

    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") != film_summary.FilmSummaryStatus.AWAITING_REVIEW:
        raise HTTPException(status_code=409, detail="Film summary is not awaiting review")

    plan = row.get("edit_plan") or {}
    valid_scene_ids = [s.get("scene_id") for s in (row.get("scene_index") or [])]
    plan, validation_report = film_summary.realign_plan_target_duration(
        plan, source_duration_ms=int((row.get("source_duration_seconds") or 0) * 1000),
        valid_scene_ids=valid_scene_ids, duration_tolerance_ratio=FILM_SUMMARY_DURATION_TOLERANCE_RATIO,
    )
    if not validation_report["valid"]:
        raise HTTPException(status_code=400, detail={"validation_report": validation_report})
    if plan is not row.get("edit_plan"):
        await supabase_update_film_summary(film_summary_id, user_id, {
            "edit_plan": plan, "validation_report": validation_report,
            "target_duration_seconds": _plan_target_duration_seconds(plan),
        })

    await _enforce_job_concurrency_limit(user_id)

    voice_id = film_summary.resolve_tts_voice(payload.voice_id or row.get("voice_id"), FILM_SUMMARY_TTS_DEFAULT_VOICE)
    character_count = _total_narration_character_count(plan)
    # Use the (possibly just-realigned) target so credits reflect the video's
    # actual planned length rather than a stale pre-alignment number.
    render_required_credits = _estimate_film_summary_render_required_credits(
        _plan_target_duration_seconds(plan), character_count,
    )
    await _reserve_job_credits(user_id, render_required_credits)

    render_job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, render_job_id)
    os.makedirs(output_dir, exist_ok=True)

    job_priority = await _resolve_user_job_priority(user_id)
    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_FILM_SUMMARY,
        pipeline_name="FilmSummaryRenderPipeline",
        job_id=render_job_id,
        job_data={"phase": "render", "film_summary_id": film_summary_id, "render_required_credits": render_required_credits},
        max_attempts=FILM_SUMMARY_JOB_MAX_ATTEMPTS,
        reserved_quota=render_required_credits,
        priority=job_priority,
        queue_name="film_summaries",
    )
    await reel_job_manager.enqueue_job(render_job_id)

    await supabase_update_film_summary(film_summary_id, user_id, {
        "status": film_summary.FilmSummaryStatus.RENDERING,
        "stage": film_summary.FilmSummaryStage.GENERATING_VOICE,
        "job_id": render_job_id,
        "voice_id": voice_id,
    })

    _spawn_background_task(_run_film_summary_render_job(
        job_id=render_job_id,
        user_id=user_id,
        film_summary_id=film_summary_id,
        project_id=row.get("project_id"),
        source_s3_key=row.get("source_s3_key"),
        output_dir=output_dir,
        plan=plan,
        voice_id=voice_id,
        render_required_credits=render_required_credits,
        narration_language=row.get("narration_language") or "",
        subtitles_enabled=bool(row.get("subtitles_enabled")),
        subtitle_style=row.get("subtitle_style"),
    ))

    return {"job_id": render_job_id, "film_summary_id": film_summary_id, "status": "rendering"}


async def _run_film_summary_render_job(
    job_id: str, user_id: str, film_summary_id: str, project_id: Optional[str], source_s3_key: Optional[str],
    output_dir: str, plan: Dict[str, Any], voice_id: str, render_required_credits: float, narration_language: str,
    subtitles_enabled: bool = False, subtitle_style: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        await reel_job_manager.start_job(job_id)
        await _run_film_summary_render_pipeline_stages(
            job_id, user_id, film_summary_id, project_id, source_s3_key, output_dir, plan, voice_id, narration_language,
            subtitles_enabled=subtitles_enabled, subtitle_style=subtitle_style,
        )
    except film_summary.FilmSummaryValidationError as exc:
        await reel_job_manager.fail_job(job_id, str(exc), error_code=exc.code)
        await _mark_film_summary_job_terminal(
            user_id, film_summary_id, project_id, film_summary.FilmSummaryStatus.FAILED,
            film_summary.FilmSummaryStage.FAILED, exc.code, str(exc),
        )
        await reel_job_manager.refund_reservation(job_id, user_id, render_required_credits, operation_type=film_summary.CREDIT_OPERATION_TYPE)
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"Film summary render job {job_id} failed")
        await reel_job_manager.fail_job(job_id, "Technical failure while rendering the film summary", error_code=film_summary.FilmSummaryErrorCode.RENDER_FAILED)
        await _mark_film_summary_job_terminal(
            user_id, film_summary_id, project_id, film_summary.FilmSummaryStatus.FAILED,
            film_summary.FilmSummaryStage.FAILED, film_summary.FilmSummaryErrorCode.RENDER_FAILED, str(exc),
        )
        await reel_job_manager.refund_reservation(job_id, user_id, render_required_credits, operation_type=film_summary.CREDIT_OPERATION_TYPE)
    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


# Maps a film_summaries row's camelCase subtitle_style snapshot (the shape
# CaptionsModal.jsx's DEFAULT_STYLE / caption_style_themes.style uses) to the
# snake_case keys _DEFAULT_AUTO_CAPTION_STYLE_KWARGS/SubtitleRequest use.
# Mirrors CaptionsModal.jsx's handleSetAsDefaultStyle mapping exactly -- copy
# it, don't invent a new one -- except that `position` itself is hardcoded
# to "bottom" below rather than read from the row, the same established
# convention that call site uses.
_FILM_SUMMARY_SUBTITLE_STYLE_FIELD_MAP: Dict[str, str] = {
    "position_x": "positionX",
    "position_y": "positionY",
    "font_size": "fontSize",
    "font_name": "fontFamily",
    "font_color": "fontColor",
    "highlight_color": "highlightColor",
    "border_color": "borderColor",
    "border_width": "borderWidth",
    "text_shadow_color": "textShadowColor",
    "shadow_blur": "shadowBlur",
    "shadow_offset_x": "shadowOffsetX",
    "shadow_offset_y": "shadowOffsetY",
    "bg_color": "bgColor",
    "bg_opacity": "bgOpacity",
    "text_case": "textCase",
    "bold": "bold",
    "italic": "italic",
    "words_per_line": "wordsPerLine",
    "animation": "animation",
}


def _map_film_summary_subtitle_style(subtitle_style: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Resolves a film_summaries row's subtitle_style into the same
    snake_case kwargs shape _DEFAULT_AUTO_CAPTION_STYLE_KWARGS has, falling
    back to that factory default's own values for any key the row's
    subtitle_style is missing (including when it is None/empty, e.g.
    subtitles_enabled was turned on without ever opening the style
    editor)."""
    camel_style = subtitle_style if isinstance(subtitle_style, dict) else {}
    kwargs = {"position": "bottom"}
    for snake_key, camel_key in _FILM_SUMMARY_SUBTITLE_STYLE_FIELD_MAP.items():
        kwargs[snake_key] = camel_style.get(camel_key, _DEFAULT_AUTO_CAPTION_STYLE_KWARGS[snake_key])
    return kwargs


def _build_film_summary_subtitle_style(subtitle_style: Optional[Dict[str, Any]]) -> SubtitleStyleOptions:
    """Builds the subtitles.SubtitleStyleOptions burn_subtitles needs from a
    film_summaries row's camelCase subtitle_style snapshot (see
    _map_film_summary_subtitle_style for the field mapping)."""
    kwargs = _map_film_summary_subtitle_style(subtitle_style)
    return SubtitleStyleOptions(
        font_name=kwargs["font_name"],
        font_color=kwargs["font_color"],
        border_color=kwargs["border_color"],
        border_width=kwargs["border_width"],
        bg_color=kwargs["bg_color"],
        bg_opacity=kwargs["bg_opacity"],
        text_shadow_color=kwargs["text_shadow_color"],
        shadow_blur=kwargs["shadow_blur"],
        shadow_offset_x=kwargs["shadow_offset_x"],
        shadow_offset_y=kwargs["shadow_offset_y"],
        bold=kwargs["bold"],
        italic=kwargs["italic"],
        text_case=kwargs["text_case"],
        highlight_color=kwargs["highlight_color"],
    )


async def _apply_film_summary_subtitle_burn_in(
    output_dir: str, final_path: str, subtitles_enabled: bool, subtitle_style: Optional[Dict[str, Any]],
) -> str:
    """Phase 3 post-processing: if subtitles_enabled, transcribes
    final_path fresh -- generate_srt_from_video
    is the same "no pre-existing transcript matches this exact audio"
    codepath _generate_subtitle_srt's is_dubbed branch already uses for a
    produced video whose exact spoken timing cannot be assumed to match any
    existing transcript -- and burns it in with the row's mapped style.
    Returns final_path unchanged when subtitles_enabled is false, so the
    pipeline behaves exactly as today for any film summary without this
    setting. Temporary .srt/.ass files are cleaned up before returning,
    mirroring _burn_default_captions_for_clip's own cleanup.

    "s'assurer qu'une transcription existe pour la video finale et baser
    les sous titres sur cela": generate_srt_from_video's own return value
    (previously discarded here) is checked explicitly -- when it comes
    back False (no transcript/no speech detected), this raises
    TRANSCRIPTION_FAILED instead of calling burn_subtitles against a
    .srt file that was never written, which otherwise either crashed on
    a confusing "no such file" or, if the video genuinely had no
    duration to transcribe against, silently shipped the final video
    with no subtitles burned in at all."""
    if not subtitles_enabled:
        return final_path
    style_kwargs = _map_film_summary_subtitle_style(subtitle_style)
    srt_path = os.path.join(output_dir, "film_summary_subtitles.srt")
    new_path = os.path.join(output_dir, "final_with_subtitles.mp4")
    try:
        transcribed = await asyncio.to_thread(
            generate_srt_from_video, final_path, srt_path, max_words_per_line=style_kwargs["words_per_line"],
        )
        if not transcribed:
            raise film_summary.FilmSummaryValidationError(
                film_summary.FilmSummaryErrorCode.TRANSCRIPTION_FAILED,
                "La transcription de la video finale n'a produit aucun sous-titre",
            )
        style_options = _build_film_summary_subtitle_style(subtitle_style)
        await asyncio.to_thread(
            burn_subtitles, final_path, srt_path, new_path,
            alignment=style_kwargs["position"], fontsize=style_kwargs["font_size"], style_options=style_options,
        )
    except film_summary.FilmSummaryValidationError:
        raise
    except Exception as exc:
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.RENDER_FAILED, f"Subtitle burn-in failed: {exc}") from exc
    finally:
        for temp_path in (srt_path, f"{os.path.splitext(srt_path)[0]}.ass"):
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except Exception:
                pass
    return new_path


async def _run_film_summary_render_pipeline_stages(
    job_id: str, user_id: str, film_summary_id: str, project_id: Optional[str], source_s3_key: Optional[str],
    output_dir: str, plan: Dict[str, Any], voice_id: str, narration_language: str,
    subtitles_enabled: bool = False, subtitle_style: Optional[Dict[str, Any]] = None,
) -> None:
    bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
    source_path = os.path.join(output_dir, "source.mp4")
    if not source_s3_key or not download_s3_object(bucket_name, source_s3_key, source_path):
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.RENDER_FAILED, "Source video is not available for rendering")

    await reel_job_manager.update_progress(job_id, 10, film_summary.FilmSummaryStage.GENERATING_VOICE)
    tts_instructions = film_summary.build_tts_instructions(narration_language)
    voiceover_dir = os.path.join(output_dir, "voiceover")
    os.makedirs(voiceover_dir, exist_ok=True)

    actual_durations_ms: Dict[str, int] = {}
    voiceover_paths: Dict[str, str] = {}
    voice_over_segments = [s for s in plan.get("segments") or [] if s.get("type") == film_summary.SEGMENT_TYPE_VOICE_OVER]
    for i, segment in enumerate(voice_over_segments):
        text = segment.get("narration") or ""
        if not text.strip():
            continue
        segment_output_path = os.path.join(voiceover_dir, f"{segment['id']}.mp3")
        duration_seconds = await film_summary.synthesize_tts_segment(
            text=text, voice=voice_id, model=FILM_SUMMARY_TTS_MODEL, instructions=tts_instructions,
            output_path=segment_output_path,
        )
        voiceover_paths[segment["id"]] = segment_output_path
        actual_durations_ms[segment["id"]] = int(duration_seconds * 1000)
        await reel_job_manager.update_progress(
            job_id, 10 + int(30 * (i + 1) / max(1, len(voice_over_segments))), film_summary.FilmSummaryStage.GENERATING_VOICE,
        )

    plan_with_actual_durations = film_summary.apply_actual_tts_durations(plan, actual_durations_ms)

    if is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {
            "edit_plan": plan_with_actual_durations, "stage": film_summary.FilmSummaryStage.RENDERING_PREVIEW,
        })
    await reel_job_manager.update_progress(job_id, 45, film_summary.FilmSummaryStage.RENDERING_PREVIEW)

    # render_edit_plan builds every segment's clip sequentially (each its
    # own ffmpeg re-encode) inside a single asyncio.to_thread call -- with
    # no feedback in between, a plan with many segments can legitimately
    # take a long time while looking indistinguishable from a genuine hang
    # (reported as "stuck with no error"). on_segment_done runs on the
    # worker thread, so it hops back onto this coroutine's event loop via
    # run_coroutine_threadsafe rather than awaiting directly.
    render_loop = asyncio.get_running_loop()

    def _on_segment_done(index: int, total: int) -> None:
        pct = 45 + int(40 * (index + 1) / max(1, total))
        asyncio.run_coroutine_threadsafe(
            reel_job_manager.update_progress(job_id, min(pct, 85), film_summary.FilmSummaryStage.RENDERING_PREVIEW),
            render_loop,
        )

    final_path = os.path.join(output_dir, "final.mp4")
    preview_path = os.path.join(output_dir, "preview.mp4")
    try:
        render_result = await asyncio.to_thread(
            film_summary_render.render_edit_plan,
            plan=plan_with_actual_durations, source_video_path=source_path,
            voiceover_paths_by_segment_id=voiceover_paths, work_dir=os.path.join(output_dir, "work"),
            final_output_path=final_path, preview_output_path=preview_path,
            on_segment_done=_on_segment_done,
        )
    except film_summary.FilmSummaryValidationError:
        raise
    except Exception as exc:
        raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.RENDER_FAILED, str(exc)) from exc

    await reel_job_manager.update_progress(job_id, 90, film_summary.FilmSummaryStage.RENDERING_FINAL)

    # Subtitle burn-in over the final video is the last content-producing
    # step before upload, and -- only when the user actually enabled
    # subtitles -- gets its own dedicated, user-visible progress stage
    # rather than being silently folded into RENDERING_FINAL ("il dois y a
    # voir une etape dans la generation du resume dediee a l'ajout du sous
    # titres... l'etape finale devrait etre l'ajout du sous titre"). When
    # subtitles_enabled is false, final_path is untouched and the preview
    # render_edit_plan already built stays valid as-is -- no extra stage is
    # reported, since nothing happens here in that case.
    if subtitles_enabled:
        await reel_job_manager.update_progress(job_id, 95, film_summary.FilmSummaryStage.ADDING_SUBTITLES)
    path_before_post_processing = final_path
    final_path = await _apply_film_summary_subtitle_burn_in(
        output_dir, final_path, subtitles_enabled, subtitle_style,
    )
    if final_path != path_before_post_processing:
        await asyncio.to_thread(film_summary_render.encode_preview, final_path, preview_path)

    preview_s3_key = f"{_FILM_SUMMARIES_PREFIX}{user_id}/{film_summary_id}/preview.mp4"
    final_s3_key = f"{_FILM_SUMMARIES_PREFIX}{user_id}/{film_summary_id}/final.mp4"
    # Read before upload, while both files still exist locally -- output_dir
    # (and everything under it, including these) is removed in the calling
    # job runner's `finally` block right after this coroutine returns.
    output_storage_bytes = (
        (os.path.getsize(final_path) if os.path.exists(final_path) else 0)
        + (os.path.getsize(preview_path) if os.path.exists(preview_path) else 0)
    )
    upload_file_to_s3(preview_path, bucket_name, preview_s3_key)
    upload_file_to_s3(final_path, bucket_name, final_s3_key)

    await _finalize_film_summary_render(
        job_id, user_id, film_summary_id, project_id, plan_with_actual_durations,
        preview_s3_key, final_s3_key, render_result, output_storage_bytes,
        source_s3_key=source_s3_key, bucket_name=bucket_name,
    )


async def _finalize_film_summary_render(
    job_id: str, user_id: str, film_summary_id: str, project_id: Optional[str], plan: Dict[str, Any],
    preview_s3_key: str, final_s3_key: str, render_result: Dict[str, Any], output_storage_bytes: float = 0.0,
    source_s3_key: Optional[str] = None, bucket_name: str = "",
) -> None:
    character_count = _total_narration_character_count(plan)
    final_duration_seconds = float(render_result.get("final_duration_seconds") or 0.0)
    cost_breakdown = calculate_credits_for_operation(estimate_film_summary_render_cost_usd(
        target_duration_minutes=max(1.0, final_duration_seconds / 60.0), narration_character_count=character_count,
    ))
    final_credits = float(cost_breakdown.get("final_credits") or 0.0)
    now_iso = datetime.now(timezone.utc).isoformat()

    job_row = await supabase_get_job_record(job_id, user_id=user_id)
    reserved_credits = float((job_row or {}).get("reserved_quota") or 0.0)

    if is_supabase_configured():
        await supabase_update_film_summary(film_summary_id, user_id, {
            "status": film_summary.FilmSummaryStatus.COMPLETED,
            "stage": film_summary.FilmSummaryStage.COMPLETED,
            "edit_plan": plan,
            "preview_s3_key": preview_s3_key,
            "final_s3_key": final_s3_key,
            "completed_at": now_iso,
            # The source is only ever read again by /render (requires
            # awaiting_review) or /retry (requires failed) -- neither is
            # reachable once the summary is completed, so it can't be
            # needed again. It must never count against the user's
            # persistent storage: only the preview/final they actually
            # keep does (billed below).
            "source_s3_key": None,
        })
        if source_s3_key and bucket_name:
            delete_s3_object(bucket_name, source_s3_key)
            # The source's own media_assets row (created at project upload
            # time, see _create_film_summary_endpoint_project) now points at
            # a file we just deleted ourselves -- DELETED (volitional),
            # never EXPIRED (that status is reserved for the retention
            # sweep itself, see process_media_expiration_jobs).
            if project_id:
                try:
                    source_media_asset = await supabase_get_media_asset_by_content(CONTENT_KIND_PROJECT_SOURCE, project_id)
                    if source_media_asset and source_media_asset.get("id"):
                        await supabase_mark_media_asset_deleted(source_media_asset["id"])
                except Exception:
                    logger.exception("Failed to mark film summary source media_asset deleted (job %s)", job_id)

        # One combined media_assets row for both produced outputs (preview
        # + final share the same film_summary_id and are always deleted/
        # expired together) -- size_bytes is their combined total.
        retention = await _finalize_retention_billing_batch(job_id, user_id, [
            {
                "content_kind": CONTENT_KIND_FILM_SUMMARY,
                "content_id": film_summary_id,
                "media_type": MEDIA_TYPE_PRODUCED,
                "size_bytes": output_storage_bytes,
                "s3_bucket": bucket_name,
                "s3_key": final_s3_key,
            }
        ])
        final_credits = round(final_credits + retention["retention_storage_credit_cost"], 2)
        if retention["retention_storage_cost_usd"] or retention["retention_storage_credit_cost"]:
            cost_breakdown = {
                **cost_breakdown,
                "retention_storage_cost_usd": retention["retention_storage_cost_usd"],
                "retention_storage_credit_cost": retention["retention_storage_credit_cost"],
                "media_assets": retention["media_assets"],
            }

        debit_ok = await reel_job_manager.debit_credits_for_job(
            job_id=job_id, user_id=user_id, credits=final_credits,
            storage_delta=-_bytes_to_gb(float(output_storage_bytes or 0.0)),
            operation_type=film_summary.CREDIT_OPERATION_TYPE, reserved_credits=reserved_credits,
        )
        if not debit_ok:
            logger.warning(f"Insufficient balance to settle film summary render job {job_id}")

    if project_id and is_supabase_configured():
        try:
            await supabase_update_project_status(project_id, "completed", user_id=user_id)
            await supabase_update_project(project_id, user_id, {"output_count": 1})
        except Exception as e:
            logger.warning(f"Failed to mark project {project_id} completed: {str(e)}")

    await reel_job_manager.complete_job(
        job_id,
        {"film_summary_id": film_summary_id, "project_id": project_id, "preview_s3_key": preview_s3_key, "final_s3_key": final_s3_key},
        actual_credit=final_credits,
        cost_breakdown=cost_breakdown,
        consumed_quota=1.0,
    )


@app.post("/api/film-summaries/{film_summary_id}/cancel", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}})
async def cancel_film_summary_endpoint(film_summary_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") in (film_summary.FilmSummaryStatus.COMPLETED, film_summary.FilmSummaryStatus.CANCELLED):
        raise HTTPException(status_code=409, detail="Film summary cannot be cancelled from its current status")

    job_id = row.get("job_id") or ""
    reserved_credits = 0.0
    if job_id:
        job_row = await supabase_get_job_record(job_id, user_id=user_id)
        reserved_credits = float((job_row or {}).get("reserved_quota") or 0.0)
        await reel_job_manager.cancel_job(job_id, reason="Cancelled by user")
        await reel_job_manager.refund_reservation(job_id, user_id, reserved_credits, operation_type=film_summary.CREDIT_OPERATION_TYPE)

    await supabase_update_film_summary(film_summary_id, user_id, {
        "status": film_summary.FilmSummaryStatus.CANCELLED,
        "stage": film_summary.FilmSummaryStage.CANCELLED,
        "error_code": film_summary.FilmSummaryErrorCode.JOB_CANCELLED,
    })
    project_id = row.get("project_id")
    if project_id and is_supabase_configured():
        try:
            await supabase_update_project_status(project_id, "cancelled", user_id=user_id)
        except Exception as e:
            logger.warning(f"Failed to update project status to cancelled: {str(e)}")

    return {"cancelled": True}


def _retry_film_summary_status_updates(previous_status: str, retry_job_id: str) -> Dict[str, Any]:
    """Status/stage reset applied by retry_film_summary_endpoint on every
    retry (automatic or failed/failed resubmission), plus -- only when
    retriggered from awaiting_review -- clearing any stale manual-editor
    state, since a full automatic regenerate makes it meaningless against
    the brand-new plan about to replace it. subtitles_enabled/
    subtitle_style are independent user preferences and are left
    untouched here."""
    updates: Dict[str, Any] = {
        "status": film_summary.FilmSummaryStatus.QUEUED,
        "stage": film_summary.FilmSummaryStage.UPLOADING,
        "job_id": retry_job_id,
        "error_code": None,
        "error_message": None,
    }
    if previous_status == film_summary.FilmSummaryStatus.AWAITING_REVIEW:
        updates["manual_selection"] = None
        updates["edit_mode"] = "automatic"
    return updates


@app.post("/api/film-summaries/{film_summary_id}/retry", responses={401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 409: {"description": "Conflict"}})
async def retry_film_summary_endpoint(film_summary_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    if not FILM_SUMMARY_ENABLED:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_DISABLED)

    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") not in (film_summary.FilmSummaryStatus.FAILED, film_summary.FilmSummaryStatus.AWAITING_REVIEW):
        raise HTTPException(status_code=409, detail="Only a failed or awaiting-review film summary can be retried")

    await _enforce_job_concurrency_limit(user_id)

    local_duration = float(row.get("source_duration_seconds") or 0.0)
    analysis_required_credits = _estimate_film_summary_analysis_required_credits(local_duration, 0.0)
    await _reserve_job_credits(user_id, analysis_required_credits)

    retry_job_id = str(uuid.uuid4())
    output_dir = os.path.join(OUTPUT_DIR, retry_job_id)
    os.makedirs(output_dir, exist_ok=True)

    job_priority = await _resolve_user_job_priority(user_id)
    await reel_job_manager.create_job(
        user_id=user_id,
        job_type=JobType.GENERATE_FILM_SUMMARY,
        pipeline_name="FilmSummaryAnalysisPipeline",
        job_id=retry_job_id,
        job_data={"phase": "analysis_retry", "film_summary_id": film_summary_id, "analysis_required_credits": analysis_required_credits},
        max_attempts=FILM_SUMMARY_JOB_MAX_ATTEMPTS,
        reserved_quota=analysis_required_credits,
        priority=job_priority,
        queue_name="film_summaries",
    )
    await reel_job_manager.enqueue_job(retry_job_id)

    await supabase_update_film_summary(
        film_summary_id, user_id, _retry_film_summary_status_updates(row.get("status"), retry_job_id),
    )

    _spawn_background_task(_run_film_summary_retry_job(
        job_id=retry_job_id,
        user_id=user_id,
        film_summary_id=film_summary_id,
        project_id=row.get("project_id"),
        source_s3_key=row.get("source_s3_key"),
        output_dir=output_dir,
        local_duration=local_duration,
        analysis_required_credits=analysis_required_credits,
        target_duration_seconds=row.get("target_duration_seconds") or 0,
        source_language=row.get("source_language") or "",
        narration_language=row.get("narration_language") or "",
        narration_style=row.get("narration_style") or "cinematic",
        cached={
            "transcript_segments": row.get("transcript_segments") or [],
            "scene_index": row.get("scene_index") or [],
            "classification": row.get("classification") or {},
        },
    ))

    return {"job_id": retry_job_id, "film_summary_id": film_summary_id, "status": "queued"}


async def _handle_film_summary_validation_failure(
    exc: "film_summary.FilmSummaryValidationError", job_id: str, user_id: str,
    film_summary_id: Optional[str], project_id: Optional[str], required_credits: float,
) -> None:
    """Shared terminal-state handling for a FilmSummaryValidationError caught
    by the analysis or retry job runner: rejected-source codes land the row
    in `rejected` (terminal, not retryable), everything else in `failed`
    (retryable). Pulled out of both runners to keep their cognitive
    complexity down and avoid duplicating this branch."""
    status = film_summary.FilmSummaryStatus.REJECTED if exc.code in _FILM_SUMMARY_REJECTION_CODES else film_summary.FilmSummaryStatus.FAILED
    stage = film_summary.FilmSummaryStage.REJECTED if status == film_summary.FilmSummaryStatus.REJECTED else film_summary.FilmSummaryStage.FAILED
    await reel_job_manager.fail_job(job_id, str(exc), error_code=exc.code)
    await _mark_film_summary_job_terminal(user_id, film_summary_id, project_id, status, stage, exc.code, str(exc))
    await reel_job_manager.refund_reservation(job_id, user_id, required_credits, operation_type=film_summary.CREDIT_OPERATION_TYPE)


async def _handle_film_summary_unexpected_failure(
    exc: Exception, job_id: str, user_id: str, film_summary_id: Optional[str], project_id: Optional[str],
    required_credits: float, log_message: str,
) -> None:
    logger.exception(log_message)
    await reel_job_manager.fail_job(job_id, "Technical failure while processing the film summary", error_code="GENERATION_INVALID")
    await _mark_film_summary_job_terminal(
        user_id, film_summary_id, project_id, film_summary.FilmSummaryStatus.FAILED,
        film_summary.FilmSummaryStage.FAILED, "GENERATION_INVALID", str(exc),
    )
    await reel_job_manager.refund_reservation(job_id, user_id, required_credits, operation_type=film_summary.CREDIT_OPERATION_TYPE)


async def _resume_film_summary_analysis_from_cache(
    job_id: str, user_id: str, film_summary_id: str, input_path: str, local_duration: float,
    target_duration_seconds: float, source_language: str, narration_language: str, narration_style: str,
    cached: Dict[str, Any],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """Resume a failed analysis job at the first stage whose cached output
    is missing ("une reprise apres echec ne regenere pas les etapes deja
    valides", spec section 19), instead of always restarting from
    transcription. Pulled out of _run_film_summary_retry_job to keep its
    cognitive complexity down."""
    cached_transcript_segments = cached.get("transcript_segments") or []
    cached_scene_index = cached.get("scene_index") or []
    cached_classification = cached.get("classification") or {}

    if cached_transcript_segments and cached_scene_index and cached_classification:
        return await _run_planning_and_validation_stages(
            job_id, user_id, film_summary_id, local_duration, target_duration_seconds,
            source_language, narration_language, narration_style, cached_transcript_segments, cached_scene_index,
        )

    if cached_transcript_segments and cached_scene_index:
        transcript_segments, scene_index = cached_transcript_segments, cached_scene_index
    else:
        transcript_segments, scene_index, detected_language = await _run_transcription_and_scene_detection_stages(
            job_id, user_id, film_summary_id, input_path, source_language=source_language,
        )
        source_language = source_language or detected_language

    classification_usage = await _run_classification_gate(
        job_id, user_id, film_summary_id, local_duration, narration_language or source_language,
        input_path, transcript_segments, scene_index,
    )
    plan, validation_report, planning_usage = await _run_planning_and_validation_stages(
        job_id, user_id, film_summary_id, local_duration, target_duration_seconds,
        source_language, narration_language, narration_style, transcript_segments, scene_index,
    )
    usage = {
        "prompt_tokens": classification_usage.get("prompt_tokens", 0) + planning_usage.get("prompt_tokens", 0),
        "completion_tokens": classification_usage.get("completion_tokens", 0) + planning_usage.get("completion_tokens", 0),
    }
    return plan, validation_report, usage


async def _run_film_summary_retry_job(
    job_id: str, user_id: str, film_summary_id: str, project_id: Optional[str], source_s3_key: Optional[str],
    output_dir: str, local_duration: float, analysis_required_credits: float, target_duration_seconds: float,
    source_language: str, narration_language: str, narration_style: str, cached: Dict[str, Any],
) -> None:
    try:
        await reel_job_manager.start_job(job_id)
        bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
        input_path = os.path.join(output_dir, "source.mp4")
        if not source_s3_key or not download_s3_object(bucket_name, source_s3_key, input_path):
            raise film_summary.FilmSummaryValidationError(film_summary.FilmSummaryErrorCode.RENDER_FAILED, "Source video is not available for retry")

        plan, validation_report, usage = await _resume_film_summary_analysis_from_cache(
            job_id, user_id, film_summary_id, input_path, local_duration, target_duration_seconds,
            source_language, narration_language, narration_style, cached,
        )

        await _finalize_film_summary_analysis(
            job_id, user_id, film_summary_id, project_id, local_duration, 0.0,
            analysis_required_credits, plan, validation_report, usage,
        )
    except film_summary.FilmSummaryValidationError as exc:
        await _handle_film_summary_validation_failure(exc, job_id, user_id, film_summary_id, project_id, analysis_required_credits)
    except Exception as exc:  # noqa: BLE001
        await _handle_film_summary_unexpected_failure(
            exc, job_id, user_id, film_summary_id, project_id, analysis_required_credits,
            f"Film summary retry job {job_id} failed",
        )
    finally:
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir, ignore_errors=True)


@app.delete("/api/film-summaries/{film_summary_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def delete_film_summary_endpoint(film_summary_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)

    deleted = await supabase_soft_delete_film_summary(film_summary_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    if bucket:
        total_freed_bytes = 0
        for key_field, label in (
            ("source_s3_key", "film summary source S3 file"),
            ("preview_s3_key", "film summary preview S3 file"),
            ("final_s3_key", "film summary final S3 file"),
        ):
            key = row.get(key_field)
            if key:
                total_freed_bytes += _delete_s3_and_get_freed_bytes(bucket, key, label)
        await _free_user_storage_after_project_deletion(user_id, total_freed_bytes)

    return {"deleted": True}


async def _publish_film_summary_now(
    user_id: str, account: Dict[str, Any], publish_priority: int, final_title: str, final_description: str, media_url: str,
) -> Dict[str, Any]:
    """Same immediate-publish flow as _publish_caption_now/_publish_reel_now
    (share_caption/share_reel) -- the only thing that differs per feature is
    where media_url/title/description come from, so this mirrors them
    exactly rather than introducing a fourth, subtly different variant."""
    platform_name = str(account.get("platform") or "")
    publish_job_id = await _insert_publish_job(
        user_id=user_id, platform=platform_name, external_id="n/a", status="queued", priority=publish_priority,
        payload={
            "source_type": "film_summary",
            "account_id": account.get("id"),
            "title": final_title,
            "description": final_description,
            "media_url": media_url,
        },
    )
    try:
        await _update_publish_job_status(publish_job_id, "processing")

        publish_payload = PublishRequest(
            user_id=user_id, title=final_title, description=final_description,
            text=final_description, caption=final_description, video_url=media_url,
        )
        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
        post_url = _build_social_post_url(platform_name, platform_result)
        await _update_publish_job_status(publish_job_id, "done", external_id=external_id, post_url=post_url)
        return {"success": True, "result": platform_result, "publish_job_id": publish_job_id}
    except Exception as exc:
        err_msg = str(exc)
        await _update_publish_job_status(publish_job_id, "failed", error_message=err_msg)
        return {"success": False, "error": err_msg, "publish_job_id": publish_job_id}


@app.post("/api/film-summaries/{film_summary_id}/share", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def share_film_summary(film_summary_id: str, payload: ReelShareRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    await _assert_user_has_active_subscription_for_publish(user_id)

    row = await supabase_get_film_summary(film_summary_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_FILM_SUMMARY_NOT_FOUND)
    if row.get("status") != film_summary.FilmSummaryStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Film summary is not completed yet")

    final_s3_key = row.get("final_s3_key")
    if not final_s3_key:
        raise HTTPException(status_code=400, detail=_NO_MEDIA_URL_AVAILABLE)
    bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
    media_url = generate_presigned_url(bucket_name, final_s3_key, expiration=3600)
    if not media_url:
        raise HTTPException(status_code=400, detail=_NO_MEDIA_URL_AVAILABLE)

    final_title = payload.title or row.get("title") or "Resume de film"
    final_description = payload.description or ""
    accounts = await _resolve_accounts_for_publish(user_id, payload.account_ids, _SHARE_PLATFORMS)
    await _assert_user_can_publish(user_id, len(accounts))
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    results: Dict[str, Any] = {}
    overall_success = True
    for account in accounts:
        result_key = str(account.get("id") or account.get("platform"))
        if is_scheduled:
            results[result_key] = await _schedule_share_publish_job(
                user_id, account, "film_summary", film_summary_id, publish_priority,
                scheduled_for, payload.timezone, final_title, final_description, media_url,
            )
            continue

        result = await _publish_film_summary_now(user_id, account, publish_priority, final_title, final_description, media_url)
        results[result_key] = result
        if not result["success"]:
            overall_success = False

    return {
        "success": overall_success,
        "results": results,
    }


# --------------------------------------------------------------------------
# Projects Endpoints
# --------------------------------------------------------------------------

def _normalize_project_row(row: Dict[str, Any]) -> Dict[str, Any]:
    thumbnail_ref = str((row or {}).get("thumbnail_url") or "").strip()
    return {
        **(row or {}),
        "thumbnail_url": _project_thumbnail_url_from_ref(thumbnail_ref),
    }


async def _ensure_project_thumbnail_for_row(row: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    project = dict(row or {})
    if not project:
        return project

    if str(project.get("thumbnail_url") or "").strip():
        return project

    if not is_supabase_configured():
        return project

    bucket = os.environ.get("AWS_S3_BUCKET", "")
    source_s3_key = str(project.get("source_s3_key") or "").strip()
    project_id = str(project.get("id") or "").strip()
    if not (bucket and source_s3_key and project_id):
        return project

    tmp_dir = os.path.join(OUTPUT_DIR, "project_thumbnails")
    os.makedirs(tmp_dir, exist_ok=True)
    ext = os.path.splitext(source_s3_key)[1] or ".mp4"
    source_local_path = os.path.join(tmp_dir, f"{project_id}_source{ext}")

    try:
        if not download_s3_object(bucket, source_s3_key, source_local_path):
            return project

        thumbnail_s3_key = _generate_and_upload_project_thumbnail_from_source(
            source_local_path,
            bucket,
            user_id,
            project_id,
        )
        if not thumbnail_s3_key:
            return project

        updated = await supabase_update_project(project_id, user_id, {"thumbnail_url": thumbnail_s3_key})
        return updated or {**project, "thumbnail_url": thumbnail_s3_key}
    except Exception:
        return project
    finally:
        try:
            if os.path.exists(source_local_path):
                os.remove(source_local_path)
        except Exception:
            pass

@app.get("/api/projects", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 503: {"description": "Service Unavailable"}})
async def list_projects(
  user_id: Annotated[str, Depends(get_user_id_header)],
  page: Annotated[int, Query(ge=1)] = 1,
  page_size: Annotated[int, Query(ge=1, le=100)] = 20,
  project_type: Annotated[Optional[str], Query()] = None,
  status: Annotated[Optional[str], Query()] = None,
  q: Optional[str] = None,
):
  if not is_supabase_configured():
    raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

  rows, total = await supabase_list_projects(
    user_id=user_id,
    page=page,
    page_size=page_size,
    project_type=project_type,
    status=status,
    query=q,
  )
  normalized_rows: List[Dict[str, Any]] = []
  for row in rows:
    ensured = await _ensure_project_thumbnail_for_row(row, user_id)
    normalized_rows.append(_normalize_project_row(ensured))
  return {
    "items": normalized_rows,
    "total": total,
    "page": max(page, 1),
    "page_size": min(max(page_size, 1), 100),
  }


@app.get("/api/projects/{project_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_endpoint(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
  if not is_supabase_configured():
    raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

  project = await supabase_get_project(project_id, user_id)
  if not project:
    raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

  project = await _ensure_project_thumbnail_for_row(project, user_id)
  return _normalize_project_row(project)


class ProjectUpdateRequest(BaseModel):
	name: Optional[str] = None
	description: Optional[str] = None


@app.put("/api/projects/{project_id}", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def update_project_endpoint(
	project_id: str,
	payload: ProjectUpdateRequest,
	user_id: Annotated[str, Depends(get_user_id_header)],
):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	# Only allow updating name and description
	updates = {}
	if payload.name is not None:
		updates["name"] = payload.name
	if payload.description is not None:
		updates["description"] = payload.description

	if not updates:
		raise HTTPException(status_code=400, detail="No valid fields to update")

	project = await supabase_update_project(project_id, user_id, updates)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	return project


def _delete_s3_and_get_freed_bytes(bucket_name: str, s3_key: str, label: str) -> int:
    try:
        size = get_s3_object_size(bucket_name, s3_key)
        if delete_s3_object(bucket_name, s3_key):
            logger.info(f"Deleted {label}: {s3_key} ({size} bytes)")
            return size
    except Exception as e:
        logger.warning(f"Failed to delete {label} {s3_key}: {str(e)}")
    return 0


def _delete_project_source_s3_file(project: Dict[str, Any], bucket_name: str) -> int:
    source_s3_key = project.get("source_s3_key")
    if not source_s3_key:
        return 0
    return _delete_s3_and_get_freed_bytes(bucket_name, source_s3_key, "project source S3 file")


async def _delete_project_reels_s3_files(project_id: str, bucket_name: str) -> int:
    freed = 0
    try:
        reels = await supabase_get_reels_by_project(project_id)
        for reel in reels:
            reel_s3_key = reel.get("reel_s3_key")
            if reel_s3_key:
                freed += _delete_s3_and_get_freed_bytes(bucket_name, reel_s3_key, "reel S3 file")

            reel_thumbnail_url = reel.get("reel_thumbnail_url") or reel.get("reel_thumbnail_s3_key")
            if reel_thumbnail_url and reel_thumbnail_url.startswith("reels/"):
                freed += _delete_s3_and_get_freed_bytes(bucket_name, reel_thumbnail_url, "reel thumbnail S3 file")

            # reel_visuals rows cascade-delete at the DB level (FK ON DELETE
            # CASCADE) once the reel row itself is deleted below in the
            # caller, but that would leave their S3 images orphaned --
            # clean those up here too, same as every other reel asset.
            try:
                visuals = await supabase_list_reel_visuals(str(reel.get("id") or ""))
                for visual in visuals:
                    image_s3_key = visual.get("image_s3_key")
                    if image_s3_key:
                        freed += _delete_s3_and_get_freed_bytes(bucket_name, image_s3_key, "reel visual image S3 file")
            except Exception as e:
                logger.warning(f"Failed to retrieve or delete visuals for reel {reel.get('id')}: {str(e)}")
    except Exception as e:
        logger.warning(f"Failed to retrieve or delete reels for project {project_id}: {str(e)}")
    return freed


async def _delete_project_captions_s3_files(project_id: str, bucket_name: str) -> int:
    freed = 0
    try:
        captions = await supabase_get_captions_by_project(project_id)
        for caption in captions:
            caption_s3_key = caption.get("caption_s3_key")
            if caption_s3_key:
                freed += _delete_s3_and_get_freed_bytes(bucket_name, caption_s3_key, "caption S3 file")

            caption_thumbnail_url = caption.get("caption_thumbnail_url")
            if caption_thumbnail_url and caption_thumbnail_url.startswith(_CAPTIONS_PREFIX):
                freed += _delete_s3_and_get_freed_bytes(bucket_name, caption_thumbnail_url, "caption thumbnail S3 file")
    except Exception as e:
        logger.warning(f"Failed to retrieve or delete captions for project {project_id}: {str(e)}")
    return freed


async def _delete_project_anonymous_stories_s3_files(project_id: str, bucket_name: str) -> int:
    freed = 0
    try:
        stories = await supabase_get_anonymous_stories_by_project(project_id)
        for story in stories:
            source_s3_key = story.get("source_s3_key")
            if source_s3_key:
                freed += _delete_s3_and_get_freed_bytes(bucket_name, source_s3_key, "anonymous story source S3 file")
    except Exception as e:
        logger.warning(f"Failed to retrieve or delete anonymous stories for project {project_id}: {str(e)}")
    return freed


async def _delete_project_film_summaries_s3_files(project_id: str, bucket_name: str) -> int:
    freed = 0
    try:
        summaries = await supabase_get_film_summaries_by_project(project_id)
        for summary in summaries:
            for key_field, label in (
                ("source_s3_key", "film summary source S3 file"),
                ("preview_s3_key", "film summary preview S3 file"),
                ("final_s3_key", "film summary final S3 file"),
            ):
                key = summary.get(key_field)
                if key:
                    freed += _delete_s3_and_get_freed_bytes(bucket_name, key, label)
    except Exception as e:
        logger.warning(f"Failed to retrieve or delete film summaries for project {project_id}: {str(e)}")
    return freed


async def _free_user_storage_after_project_deletion(user_id: str, total_storage_freed_bytes: int) -> None:
    if total_storage_freed_bytes <= 0:
        return
    storage_freed_gb = -total_storage_freed_bytes / (1024 ** 3)  # Negative value to free up space
    try:
        await supabase_deduct_user_credits(user_id, 0.0, storage_delta=storage_freed_gb)
        logger.info(f"Freed {abs(storage_freed_gb):.6f} GB for user {user_id}")
    except Exception as e:
        logger.warning(f"Failed to update user storage quota after project deletion: {str(e)}")


@app.delete("/api/projects/{project_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}, 503: {"description": "Service Unavailable"}})
async def delete_project_endpoint(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

    project = await supabase_get_project(project_id, user_id)
    if not project:
        raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

    bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
    total_storage_freed_bytes = 0
    total_storage_freed_bytes += _delete_project_source_s3_file(project, bucket_name)
    total_storage_freed_bytes += await _delete_project_reels_s3_files(project_id, bucket_name)
    total_storage_freed_bytes += await _delete_project_captions_s3_files(project_id, bucket_name)
    total_storage_freed_bytes += await _delete_project_anonymous_stories_s3_files(project_id, bucket_name)
    total_storage_freed_bytes += await _delete_project_film_summaries_s3_files(project_id, bucket_name)

    # Delete database records
    deleted = await supabase_soft_delete_project(project_id, user_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete project")

    # Free up user's storage quota (negative storage_delta = free up space)
    await _free_user_storage_after_project_deletion(user_id, total_storage_freed_bytes)

    return {"deleted": True}


@app.get("/api/projects/{project_id}/source-url", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 500: {"description": "Internal Server Error"}, 503: {"description": "Service Unavailable"}})
async def get_project_source_url(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	s3_key = project.get("source_s3_key")
	if not s3_key:
		raise HTTPException(status_code=400, detail="No source video available")

	# Generate presigned URL
	bucket_name = os.environ.get("AWS_S3_BUCKET", "my-clips-bucket")
	source_url = generate_presigned_url(bucket_name, s3_key, expiration=3600)

	if not source_url:
		raise HTTPException(status_code=500, detail="Failed to generate source URL")

	return {"source_url": source_url}


@app.get("/api/projects/{project_id}/job", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_job(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
  if not is_supabase_configured():
    raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

  project = await supabase_get_project(project_id, user_id)
  if not project:
    raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

  job_row = await supabase_get_latest_job_record_by_project(project_id, user_id)
  if not job_row:
    return {
      "project_id": project_id,
      "project_status": project.get("status"),
      "job": None,
    }

  job_id = str(job_row.get("id") or "")
  job_view = await reel_job_manager.get_job_view(job_id, user_id=user_id)
  return {
    "project_id": project_id,
    "project_status": project.get("status"),
    "job": job_view,
  }


@app.get("/api/projects/{project_id}/reels", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_reels(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
	"""Get all reels for a specific project."""
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	# Verify user owns the project
	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	reels = await supabase_get_reels_by_project(project_id)
	return {
		"project_id": project_id,
		"reels": [_normalize_reel_row(reel) for reel in reels],
		"count": len(reels),
	}


@app.get("/api/projects/{project_id}/captions", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_captions(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
	"""Get all captions for a specific project."""
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	# Verify user owns the project
	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	captions = await supabase_get_captions_by_project(project_id)
	return {
		"project_id": project_id,
		"captions": [_normalize_caption_row(caption) for caption in captions],
		"count": len(captions),
	}


@app.get("/api/projects/{project_id}/anonymous-stories", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_anonymous_stories(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
	"""Get the anonymous story generated for a specific project."""
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	stories = await supabase_get_anonymous_stories_by_project(project_id)
	return {
		"project_id": project_id,
		"anonymous_stories": [_normalize_anonymous_story_row(story, include_content=True) for story in stories],
		"count": len(stories),
	}


@app.get("/api/projects/{project_id}/film-summaries", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_project_film_summaries(project_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
	"""Get the film summary generated for a specific project."""
	if not is_supabase_configured():
		raise HTTPException(status_code=503, detail=_SUPABASE_PROJECTS_NOT_CONFIGURED)

	project = await supabase_get_project(project_id, user_id)
	if not project:
		raise HTTPException(status_code=404, detail=_PROJECT_NOT_FOUND)

	summaries = await supabase_get_film_summaries_by_project(project_id)
	return {
		"project_id": project_id,
		"film_summaries": [_normalize_film_summary_row(summary, include_content=True) for summary in summaries],
		"count": len(summaries),
	}


async def list_reels(user_id: Annotated[str, Depends(get_user_id_header)], page: Annotated[int, Query(ge=1)] = 1, page_size: Annotated[int, Query(ge=1, le=100)] = 10, q: Optional[str] = None, status: Optional[str] = None):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase reels is not configured")

    rows, total = await supabase_list_reels(user_id=user_id, page=page, page_size=page_size, status=status, query=q)
    items = [_normalize_reel_row(row) for row in rows]
    await _attach_media_asset_fields(items, CONTENT_KIND_REEL)
    return {
        "items": items,
        "total": total,
        "page": max(page, 1),
        "page_size": min(max(page_size, 1), 100),
    }


@app.get("/api/reels/{reel_id}/media-url", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def reel_media_url(reel_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    item = _normalize_reel_row(row)
    return {"media_url": item.get("media_url")}


@app.get("/api/reels/{reel_id}/thumbnail-url", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def reel_thumbnail_url(reel_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    item = _normalize_reel_row(row)
    return {"thumbnail_url": item.get("reel_thumbnail_url")}


@app.get("/api/reels/{reel_id}/preview-url", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def reel_preview_url(reel_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    item = _normalize_reel_row(row)
    return {"preview_url": item.get("reel_preview_url")}


@app.delete("/api/reels/{reel_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def delete_reel(reel_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    deleted = await supabase_soft_delete_reel(reel_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)
    return {"deleted": True}


async def _publish_reel_now(user_id: str, account: Dict[str, Any], publish_priority: int, final_title: str, final_description: str, media_url: str) -> Dict[str, Any]:
    platform_name = str(account.get("platform") or "")
    base_payload = {
        "source_type": "reel",
        "account_id": account.get("id"),
        "title": final_title,
        "description": final_description,
        "media_url": media_url,
    }
    try:
        publish_payload = PublishRequest(
            user_id=user_id,
            title=final_title,
            description=final_description,
            text=final_description,
            caption=final_description,
            video_url=media_url,
        )
        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
        post_url = _build_social_post_url(platform_name, platform_result)
        await _insert_publish_job(
            user_id=user_id, platform=platform_name, external_id=external_id, status="done", priority=publish_priority,
            payload={**base_payload, "post_url": post_url} if post_url else base_payload,
        )
        return {
            "success": True,
            "result": platform_result,
        }
    except Exception as exc:
        err_msg = str(exc)
        await _insert_publish_job(
            user_id=user_id, platform=platform_name, external_id="n/a", status="failed", error_message=err_msg,
            priority=publish_priority, payload=base_payload,
        )
        return {
            "success": False,
            "error": err_msg,
        }


@app.post("/api/reels/{reel_id}/share", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 402: {"description": "Payment Required"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def share_reel(reel_id: str, payload: ReelShareRequest, user_id: Annotated[str, Depends(get_user_id_header)]):
    await _assert_user_has_active_subscription_for_publish(user_id)

    row = await supabase_get_reel(reel_id, user_id)
    if not row:
        raise HTTPException(status_code=404, detail=_REEL_NOT_FOUND)

    item = _normalize_reel_row(row)
    media_url = item.get("media_url")
    if not media_url:
        raise HTTPException(status_code=400, detail=_NO_MEDIA_URL_AVAILABLE)

    final_title = payload.title or row.get("reel_title") or "Vireel"
    final_description = payload.description or row.get("reel_description") or ""
    accounts = await _resolve_accounts_for_publish(user_id, payload.account_ids, _SHARE_PLATFORMS)
    await _assert_user_can_publish(user_id, len(accounts))
    publish_priority = await _resolve_user_job_priority(user_id)
    scheduled_for = _resolve_scheduled_datetime(payload.scheduled_date, payload.timezone)
    if payload.scheduled_date and not scheduled_for:
        raise HTTPException(status_code=400, detail=_INVALID_SCHEDULED_DATE)
    is_scheduled = bool(scheduled_for and scheduled_for > _utcnow())

    results: Dict[str, Any] = {}
    overall_success = True
    for account in accounts:
        result_key = str(account.get("id") or account.get("platform"))
        if is_scheduled:
            results[result_key] = await _schedule_share_publish_job(
                user_id, account, "reel", reel_id, publish_priority, scheduled_for, payload.timezone, final_title, final_description, media_url,
            )
            continue

        result = await _publish_reel_now(user_id, account, publish_priority, final_title, final_description, media_url)
        results[result_key] = result
        if not result["success"]:
            overall_success = False

    return {
        "success": overall_success,
        "results": results,
    }


class SocialAccount(BaseModel):
    id: int
    user_id: int
    platform: str  # "tiktok", "facebook", "linkedin", "youtube"
    access_token: str  # chiffré (Fernet, ou vault)
    refresh_token: str | None
    expires_at: datetime
    platform_user_id: str
    scopes: str


class FacebookPageSelectionRequest(BaseModel):
    user_id: str
    page_id: str
    page_name: str
    page_access_token: str
    user_token_expires_in: int


SOCIAL_BASE_URL = os.environ.get("BASE_URL", "").strip().rstrip("/")
SUPABASE_SOCIAL_ACCOUNTS_TABLE = os.environ.get("SUPABASE_SOCIAL_ACCOUNTS_TABLE", "social_accounts")
SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE = os.environ.get("SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE", "publish_jobs")
_OAUTH_STATE_TTL_SECONDS = 600
_oauth_states: Dict[str, Dict[str, Any]] = {}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _derive_token_encryption_key() -> bytes:
    """Derive a 256-bit AES key from ENCRYPTION_KEY via HKDF-SHA256.

    Using a KDF (rather than the raw secret bytes) gives a full-entropy,
    fixed-length key regardless of the raw secret's length/format, and scopes
    it to this specific purpose via the `info` label.
    """
    hkdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"vireel-social-token-encryption-v1")
    return hkdf.derive(_ENCRYPTION_KEY_RAW.encode("utf-8"))


_TOKEN_ENCRYPTION_KEY = _derive_token_encryption_key()
_TOKEN_ENCRYPTION_PREFIX = "v1:"


def _encrypt_token(token: str) -> str:
    """Encrypt a social-platform OAuth token with AES-256-GCM (authenticated
    encryption) before storing it in Supabase. Replaces a previous XOR-based
    scheme that offered neither real confidentiality nor integrity, and that
    silently stored tokens in plaintext whenever ENCRYPTION_KEY was unset."""
    if not token:
        return ""
    nonce = secrets.token_bytes(12)  # AES-GCM standard nonce size; must never repeat for a given key
    ciphertext = AESGCM(_TOKEN_ENCRYPTION_KEY).encrypt(nonce, token.encode("utf-8"), None)
    return _TOKEN_ENCRYPTION_PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def _decrypt_token(token_encrypted: Optional[str]) -> str:
    if not token_encrypted:
        return ""
    if not token_encrypted.startswith(_TOKEN_ENCRYPTION_PREFIX):
        # Tokens written by the legacy XOR scheme are intentionally treated
        # as unusable rather than "best-effort" decoded: forcing a
        # reconnection is far safer than trusting a weaker/ambiguous format.
        logger.warning("Encountered a legacy-format encrypted token; treating as invalid (reconnect required).")
        return ""
    try:
        raw = base64.urlsafe_b64decode(token_encrypted[len(_TOKEN_ENCRYPTION_PREFIX):].encode("ascii"))
        nonce, ciphertext = raw[:12], raw[12:]
        plaintext = AESGCM(_TOKEN_ENCRYPTION_KEY).decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except Exception:
        return ""


def _resolve_platform_config(platform: str) -> Dict[str, Any]:
    key = (platform or "").strip().lower()
    if key not in PLATFORM_CONFIG:
        raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)
    config = PLATFORM_CONFIG[key]
    if not config.get("client_id") or not config.get("client_secret"):
        raise HTTPException(status_code=503, detail=f"{key} OAuth is not configured")
    return config


def _oauth_popup_response(
    success: bool,
    platform: str,
    message: Optional[str] = None,
    page_selection_data: Optional[Dict[str, Any]] = None,
) -> HTMLResponse:
    if page_selection_data:
        payload = _build_page_selection_payload(platform, page_selection_data)
    else:
        payload = {
            "type": "oauth_success" if success else "oauth_error",
            "platform": platform,
            "message": message or "",
        }

    return HTMLResponse(
        f"""
        <script>
          window.opener && window.opener.postMessage({json.dumps(payload)}, {json.dumps(FRONTEND_ORIGIN)});
          window.close();
        </script>
        """
    )


def _build_page_selection_payload(platform: str, page_selection_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sépare strictement ce qui part au navigateur (affichage seulement) de ce
    qui reste signé côté serveur (les tokens réels).
    """
    raw_pages: List[Dict[str, Any]] = page_selection_data.get("pages", [])

    display_pages = [
        {
            "page_id": p.get("page_id"),
            "page_name": p.get("page_name"),
            "page_picture": p.get("page_picture"),
            "page_category": p.get("page_category"),
        }
        for p in raw_pages
    ]

    selection_token = _page_selection_serializer.dumps({
        "platform": platform,
        # Map page_id -> page_access_token, jamais envoyée au client.
        "pages": {p.get("page_id"): p.get("page_access_token") for p in raw_pages},
        "user_token": page_selection_data.get("user_token"),
        "user_token_expires_in": page_selection_data.get("user_token_expires_in"),
        "user_id": page_selection_data.get("user_id"),
    })

    return {
        "type": "oauth_page_selection",
        "platform": platform,
        "pages": display_pages,
        "selection_token": selection_token,
    }


def _public_request_base_url(request: Request) -> str:
    """Build public base URL from proxy headers when available."""
    xf_proto = (request.headers.get("x-forwarded-proto") or "").split(",")[0].strip()
    xf_host = (request.headers.get("x-forwarded-host") or "").split(",")[0].strip()
    if xf_proto and xf_host:
        return f"{xf_proto}://{xf_host}".rstrip("/")
    return str(request.base_url).rstrip("/")


def _oauth_redirect_uri(platform: str, request: Optional[Request] = None) -> str:
    if SOCIAL_BASE_URL:
        return f"{SOCIAL_BASE_URL}/api/auth/{platform}/callback"
    if request:
        base = _public_request_base_url(request)
        return f"{base}/api/auth/{platform}/callback"
    return f"http://localhost:8000/api/auth/{platform}/callback"


def generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE verifier/challenge pair (S256) for OAuth providers like TikTok."""
    # token_urlsafe already produces URL-safe chars; trim to stay within PKCE recommended bounds.
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return verifier, challenge

async def fetch_facebook_granted_scopes(access_token: str) -> List[str]:
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/me/permissions",
            params={"access_token": access_token},
        )
    response.raise_for_status()
    data = response.json().get("data") or []
    return [
        item.get("permission")
        for item in data
        if item.get("status") == "granted" and item.get("permission")
    ]


async def fetch_facebook_pages(user_access_token: str) -> List[Dict[str, Any]]:
    """
    Récupère les pages gérées par l'utilisateur avec leurs access tokens.
    Les tokens de page sont long-lived si le user_access_token est long-lived.
    """
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/v19.0/me/accounts",
            params={
                "fields": "id,name,picture.width(200).height(200),access_token,category",
                "access_token": user_access_token,
            },
        )
    response.raise_for_status()
    data = response.json()

    pages = []
    for item in data.get("data", []):
        pages.append({
            "page_id": item.get("id"),
            "page_name": item.get("name"),
            "page_picture": item.get("picture", {}).get("data", {}).get("url"),
            "page_category": item.get("category"),
            "page_access_token": item.get("access_token"),
        })

    return pages


async def _extract_token_data(platform: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    if platform == "tiktok":
        token_data = token_data.get("data", token_data)

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="OAuth provider did not return access_token")

    scopes = token_data.get("scope") or token_data.get("scopes") or ""

    if platform == "facebook":
        try:
            granted_scopes = await fetch_facebook_granted_scopes(access_token)
            if granted_scopes:
                scopes = " ".join(granted_scopes)
        except Exception:
            # On garde le fallback éventuel renvoyé par le provider
            pass

    return {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "expires_in": int(token_data.get("expires_in") or 3600),
        "scopes": scopes,
    }

async def _get_social_account(user_id: str, platform: str) -> Optional[Dict[str, Any]]:
    """Returns one representative account for this platform (the most
    recently touched one) -- used by call sites that haven't yet been
    updated to let the user pick a specific one of several connected
    accounts of the same platform. Prefer _get_social_account_by_id or
    _list_social_accounts in any new code."""
    accounts = await _list_social_accounts(user_id, platform)
    return accounts[0] if accounts else None


async def _list_social_accounts(user_id: str, platform: Optional[str] = None) -> List[Dict[str, Any]]:
    client = await supabase_get_client()
    query = client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE).select("*").eq("user_id", user_id)
    if platform:
        query = query.eq("platform", platform)
    response = await query.order("updated_at", desc=True).execute()
    return response.data or []


async def _get_social_account_by_id(user_id: str, account_id: str) -> Optional[Dict[str, Any]]:
    """Scoped to user_id so one user can never target another's connected
    account by guessing/reusing an id."""
    if not account_id:
        return None
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .select("*")
        .eq("id", account_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None


async def _count_social_accounts_by_platform(user_id: str) -> Dict[str, int]:
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .select("platform")
        .eq("user_id", user_id)
        .execute()
    )
    counts: Dict[str, int] = {}
    for row in response.data or []:
        platform = str(row.get("platform") or "")
        if platform:
            counts[platform] = counts.get(platform, 0) + 1
    return counts


async def _get_active_plan_for_user(user_id: str) -> Optional[Dict[str, Any]]:
    subscription = await get_user_abonnement(user_id)
    abonnement_id = str((subscription or {}).get("abonnement") or "").strip()
    if not abonnement_id:
        return None
    return await supabase_get_abonnement(abonnement_id)


async def _get_user_max_social_accounts(user_id: str) -> int:
    """How many accounts of EACH platform the user's active plan allows --
    defaults to 1 (the lowest tier) with no active paid subscription,
    matching get_user_abonnement's own priorite fallback."""
    plan = await _get_active_plan_for_user(user_id)
    try:
        return max(1, int((plan or {}).get("max_social_account") or 1))
    except (TypeError, ValueError):
        return 1


async def _get_user_max_comments_per_post(user_id: str) -> int:
    """How many follow-up comments a single publication can carry under
    the user's active plan (abonnement.commentaire) -- defaults to 0 (no
    comments) when there is no active plan/the column is unset, since
    create_social_post already requires an active subscription before
    this is ever checked (see _assert_user_has_active_subscription_for_publish)."""
    plan = await _get_active_plan_for_user(user_id)
    try:
        return max(0, int((plan or {}).get("commentaire") or 0))
    except (TypeError, ValueError):
        return 0


async def _find_social_account_by_platform_user(
    user_id: str, platform: str, platform_user_id: str
) -> Optional[Dict[str, Any]]:
    client = await supabase_get_client()
    query = client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE).select("*").eq("user_id", user_id).eq("platform", platform)
    if platform_user_id:
        query = query.eq("platform_user_id", platform_user_id)
    response = await query.order("updated_at", desc=True).limit(1).execute()
    rows = response.data or []
    return rows[0] if rows else None


async def _upsert_social_account(
    user_id: str,
    platform: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
    platform_user_id: str,
    platform_account_name: str,
    scopes: str,
) -> None:
    """Reconnecting/reauthorizing the same external account (matched on
    platform_user_id) always just refreshes its row. Connecting a genuinely
    new one for this platform is gated behind the user's plan allowance
    (see _get_user_max_social_accounts) -- e.g. Silver allows 1 Facebook
    Page, Gold 3, Ultimate 10 -- so the only way to connect more is to
    upgrade, and downgrading below what's already connected is blocked in
    change_souscription_plan instead of silently dropping accounts here."""
    client = await supabase_get_client()
    expires_at = datetime.fromtimestamp(time.time() + max(expires_in, 60), tz=timezone.utc).isoformat()
    payload = {
        "user_id": user_id,
        "platform": platform,
        "access_token_encrypted": _encrypt_token(access_token),
        "refresh_token_encrypted": _encrypt_token(refresh_token or ""),
        "platform_user_id": platform_user_id,
        "platform_account_name": platform_account_name,
        "scopes": scopes,
        "expires_at": expires_at,
        "updated_at": _utcnow_iso(),
    }

    existing = await _find_social_account_by_platform_user(user_id, platform, platform_user_id)
    if existing and existing.get("id"):
        await (
            client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
            .update(payload)
            .eq("id", existing["id"])
            .execute()
        )
        return

    counts = await _count_social_accounts_by_platform(user_id)
    max_allowed = await _get_user_max_social_accounts(user_id)
    if counts.get(platform, 0) >= max_allowed:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Votre offre autorise au maximum {max_allowed} compte(s) {platform} connecte(s). "
                "Supprimez-en un dans Parametres avant d'en ajouter un nouveau, ou passez a une offre superieure."
            ),
        )

    await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE).insert(payload).execute()


async def _insert_publish_job(
    user_id: str,
    platform: str,
    external_id: str,
    status: str,
    error_message: Optional[str] = None,
    priority: int = DEFAULT_JOB_PRIORITY,
    scheduled_for: Optional[str] = None,
    timezone: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    client = await supabase_get_client()
    insert_payload: Dict[str, Any] = {
        "user_id": user_id,
        "platform": platform,
        "external_id": external_id,
        "status": status,
        "priority": _clamp_job_priority(priority),
    }
    if error_message:
        insert_payload["error_message"] = error_message
    if scheduled_for:
        insert_payload["scheduled_for"] = scheduled_for
    if timezone:
        insert_payload["timezone"] = timezone
    if payload is not None:
        insert_payload["payload"] = payload
    if status in {"done", "failed"}:
        insert_payload["completed_at"] = _utcnow_iso()
    response = await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).insert(insert_payload).execute()
    rows = response.data or []
    return str(rows[0].get("id")) if rows and rows[0].get("id") is not None else None


def _build_scheduled_publish_payload(user_id: str, task_payload: Dict[str, Any]) -> "PublishRequest":
    """Build the PublishRequest for a due scheduled publish job. Pulled out
    of _execute_scheduled_publish_job to keep its cognitive complexity down:
    a story publish (text only -- Facebook's native colored background,
    LinkedIn plain text, no media_url requirement) and a reel/caption
    publish (video_url required) need different shapes here."""
    description = str(task_payload.get("description") or "")
    title = str(task_payload.get("title") or "Vireel")

    if str(task_payload.get("source_type") or "") == "anonymous_story":
        background_id = task_payload.get("background_id")
        return PublishRequest(
            user_id=user_id, title=title, description=description, text=description,
            caption=description,
            facebook_text_format_preset_id=anonymous_stories.get_facebook_text_format_preset_id(background_id),
        )

    media_url = str(task_payload.get("media_url") or "").strip()
    if not media_url:
        raise HTTPException(status_code=400, detail="No media URL available for scheduled publish")

    return PublishRequest(
        user_id=user_id, title=title, description=description, text=description,
        caption=description, video_url=media_url,
    )


async def _execute_scheduled_publish_job(job_row: Dict[str, Any]) -> None:
    job_id = str(job_row.get("id") or "")
    user_id = str(job_row.get("user_id") or "")
    platform = str(job_row.get("platform") or "").lower()
    raw_payload = job_row.get("payload") or {}
    task_payload = raw_payload if isinstance(raw_payload, dict) else {}

    if not job_id or not user_id or not platform:
        return

    if str(task_payload.get("source_type") or "") == "social_post":
        await _execute_scheduled_social_post_job(job_id, user_id, platform, task_payload)
        return

    try:
        await _update_publish_job_status(job_id, "processing", error_message=None)

        # account_id is only present on jobs scheduled after multi-account
        # support was added -- fall back to "any account of this platform"
        # for older in-flight jobs that don't have it.
        account_id = task_payload.get("account_id")
        account = await _get_social_account_by_id(user_id, account_id) if account_id else None
        if not account:
            account = await _get_social_account(user_id, platform)
        if not account:
            raise HTTPException(status_code=404, detail=f"No connected {platform} account found")

        publish_payload = _build_scheduled_publish_payload(user_id, task_payload)

        platform_result = await publish_post(account, publish_payload)
        external_id = str(platform_result.get("publish_id") or platform_result.get("id") or platform_result.get("video_id") or "n/a")
        post_url = _build_social_post_url(platform, platform_result)
        await _update_publish_job_status(job_id, "done", external_id=external_id, post_url=post_url, error_message=None)
    except Exception as exc:
        await _update_publish_job_status(job_id, "failed", error_message=str(exc))


async def _process_due_annual_credit_refills() -> None:
    """One sweep: reset credit/storage for every annual subscription whose
    monthly anniversary is due, using each row's own snapshotted
    plan_credit/plan_stockage (see _allocate_plan_resources) -- never a
    live plan lookup, so a later change to the plan catalog never
    retroactively changes an already-in-progress annual subscription's
    monthly allowance. Resetting (not adding) to the snapshot value is
    exactly what already enforces the storage ceiling for a monthly plan
    (_reset_user_plan_balance), so no extra check is needed here."""
    due_rows = await supabase_list_souscriptions_due_for_monthly_credit_allocation()
    for row in due_rows:
        user_id = row.get("userid")
        souscription_id = str(row.get("id") or "")
        if not user_id or not souscription_id:
            continue

        plan_credit = float(row.get("plan_credit") or 0.0)
        plan_storage = float(row.get("plan_stockage") or 0.0)
        await _reset_user_plan_balance(user_id, plan_credit, plan_storage, souscription_id)

        previous_due_raw = row.get("next_credit_allocation_at")
        try:
            previous_due = datetime.fromisoformat(previous_due_raw) if previous_due_raw else datetime.now(timezone.utc)
        except ValueError:
            previous_due = datetime.now(timezone.utc)
        if previous_due.tzinfo is None:
            previous_due = previous_due.replace(tzinfo=timezone.utc)
        # Anchored to the previous due date (not "now") so the monthly
        # cadence stays tied to the original payment anniversary instead of
        # drifting later every time a sweep runs a bit behind schedule.
        next_due = supabase_add_one_month(previous_due)
        await supabase_update_souscription_row(souscription_id, {
            "next_credit_allocation_at": next_due.isoformat(),
            # The credit cycle (used by the upgrade-proration math in
            # _compute_annual_upgrade_proration) is this one-month
            # sub-window, not the whole paid year -- advance it in lockstep
            # with next_credit_allocation_at so a mid-sub-cycle upgrade
            # always prorates against the CURRENT window.
            "credit_cycle_start_at": previous_due.isoformat(),
            "credit_cycle_end_at": next_due.isoformat(),
        })


async def process_annual_credit_refill_jobs() -> None:
    while True:
        try:
            if is_supabase_configured():
                await _process_due_annual_credit_refills()
        except Exception as exc:
            logger.warning("Annual credit refill worker error: %s", exc, exc_info=True)

        await asyncio.sleep(max(300, ANNUAL_CREDIT_REFILL_INTERVAL_SECONDS))


async def _expire_one_media_asset(asset: Dict[str, Any]) -> None:
    """Deletes the physical S3 object, then marks the row EXPIRED -- in
    that order, and only on confirmed delete success, so an S3 failure
    (delete_s3_object returns False) leaves the row AVAILABLE for the next
    sweep to retry rather than ever marking EXPIRED for a file that's
    still actually there (or whose deletion we can't confirm)."""
    media_id = asset.get("id")
    if not media_id:
        return
    bucket = asset.get("s3_bucket")
    key = asset.get("s3_key")
    if bucket and key:
        deleted = delete_s3_object(bucket, key)
        if not deleted:
            logger.warning(
                "Failed to delete S3 object for media_asset %s (bucket=%s key=%s); leaving AVAILABLE for retry",
                media_id, bucket, key,
            )
            return
    # No bucket/key on this row (e.g. a legacy row created without one) --
    # nothing physical to delete, so there's nothing that can fail either.
    await supabase_mark_media_asset_expired(media_id)


async def _run_media_expiration_sweep() -> None:
    due = await supabase_list_media_assets_due_for_expiration(limit=100)
    for asset in due:
        try:
            await _expire_one_media_asset(asset)
        except Exception:
            logger.exception("Failed to expire media_asset %s", asset.get("id"))


async def process_media_expiration_jobs() -> None:
    """Required retention background process #1: physically deletes every
    AVAILABLE media past its retention_expires_at (see the media_assets
    migration and retention_config.py) -- the business row (reel/caption/
    film_summary/anonymous_story/project) is never touched, only this
    lifecycle row's own status/media_deleted_at."""
    while True:
        try:
            if is_supabase_configured():
                await _run_media_expiration_sweep()
        except Exception as exc:
            logger.warning("Media expiration worker error: %s", exc, exc_info=True)

        await asyncio.sleep(max(60, MEDIA_EXPIRATION_SWEEP_INTERVAL_SECONDS))


async def _notify_one_media_asset_expiring(asset: Dict[str, Any]) -> None:
    """Marks notified_before_expiry_at BEFORE sending the notification
    (not after): supabase_mark_media_asset_notified only succeeds while
    that column is still null, so this is the idempotency guard -- a
    second sweep (or a retry after a crash right after this one) that
    finds the column already set simply sends nothing, rather than racing
    on "did I already notify this?" after the fact."""
    media_id = asset.get("id")
    user_id = asset.get("user_id")
    if not media_id or not user_id:
        return
    newly_marked = await supabase_mark_media_asset_notified(media_id)
    if not newly_marked:
        return
    await supabase_insert_notification(
        user_id=user_id,
        type_="media_expiring_soon",
        title="Un media va etre supprime prochainement",
        body=(
            "Ce media sera supprime automatiquement le "
            f"{asset.get('retention_expires_at')}. Telechargez-le avant cette date pour le conserver."
        ),
        data={
            "media_asset_id": media_id,
            "content_kind": asset.get("content_kind"),
            "content_id": asset.get("content_id"),
            "retention_expires_at": asset.get("retention_expires_at"),
        },
    )


async def _run_media_expiry_notification_sweep() -> None:
    notify_before_time = datetime.now(timezone.utc) + timedelta(hours=RETENTION_NOTIFICATION_HOURS_BEFORE)
    due = await supabase_list_produced_media_due_for_notification(notify_before_time, limit=100)
    for asset in due:
        try:
            await _notify_one_media_asset_expiring(asset)
        except Exception:
            logger.exception("Failed to notify expiring media_asset %s", asset.get("id"))


async def process_media_expiry_notification_jobs() -> None:
    """Required retention background process #2: warns the user
    RETENTION_NOTIFICATION_HOURS_BEFORE ahead of a PRODUCED media's
    deletion (source media is never notified, per the spec's "avoid
    notification overload" rule -- see
    list_produced_media_due_for_notification's media_type filter)."""
    while True:
        try:
            if is_supabase_configured():
                await _run_media_expiry_notification_sweep()
        except Exception as exc:
            logger.warning("Media expiry notification worker error: %s", exc, exc_info=True)

        await asyncio.sleep(max(60, MEDIA_EXPIRY_NOTIFICATION_SWEEP_INTERVAL_SECONDS))


async def process_scheduled_social_publish_jobs() -> None:
    while True:
        try:
            if not is_supabase_configured():
                await asyncio.sleep(max(3, SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS))
                continue

            client = await supabase_get_client()
            now_iso = _utcnow_iso()
            response = (
                await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
                .select("*")
                .eq("status", "queued")
                .lte("scheduled_for", now_iso)
                .order("scheduled_for", desc=False)
                .limit(20)
                .execute()
            )

            for row in (response.data or []):
                await _execute_scheduled_publish_job(row)
        except Exception as exc:
            logger.warning("Scheduled publish worker error: %s", exc, exc_info=True)

        await asyncio.sleep(max(3, SOCIAL_PUBLISH_SCHEDULER_INTERVAL_SECONDS))


async def _update_publish_job_status(
    publish_job_id: Optional[str],
    status: str,
    error_message: Optional[str] = None,
    external_id: Optional[str] = None,
    post_url: Optional[str] = None,
    extra_payload: Optional[Dict[str, Any]] = None,
) -> None:
    if not publish_job_id:
        return
    client = await supabase_get_client()
    payload: Dict[str, Any] = {
        "status": status,
    }
    if error_message is not None:
        payload["error_message"] = error_message
    if external_id is not None:
        payload["external_id"] = external_id
    # Merges into the row's existing `payload` jsonb column rather than
    # replacing it, so the source_type/media_url/title/description recorded
    # at insert/schedule time survives past completion -- the publications
    # page needs it to show what was actually posted (see
    # SocialPublicationsPage.jsx).
    if post_url or extra_payload:
        existing = (
            await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
            .select("payload")
            .eq("id", publish_job_id)
            .limit(1)
            .execute()
        )
        existing_rows = existing.data or []
        existing_payload = (existing_rows[0].get("payload") or {}) if existing_rows else {}
        merged_payload: Dict[str, Any] = {**existing_payload, **(extra_payload or {})}
        if post_url:
            merged_payload["post_url"] = post_url
        payload["payload"] = merged_payload
    if status in {"done", "failed"}:
        payload["completed_at"] = _utcnow_iso()
    await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).update(payload).eq("id", publish_job_id).execute()


@app.get("/api/social/accounts", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def list_social_accounts(user_id: Annotated[str, Depends(get_user_id_header)]):
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .select("id, created_at, user_id, platform, platform_user_id, platform_account_name, scopes, expires_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    rows = response.data or []
    accounts = [
        {
            **row,
            "connected": True,
        }
        for row in rows
    ]
    # Included here (rather than a separate call) so the Settings page can
    # disable/annotate each network's "+ Connecter" button with how many
    # more accounts of that platform the current plan still allows.
    max_social_account = await _get_user_max_social_accounts(user_id)
    return {"accounts": accounts, "max_social_account": max_social_account}


@app.delete("/api/social/accounts/{account_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def disconnect_social_account(account_id: str, user_id: Annotated[str, Depends(get_user_id_header)]):
    """Disconnects one specific connected account (e.g. one Facebook Page
    among several) -- scoped by id rather than platform now that a user can
    have more than one account per platform (see _upsert_social_account)."""
    account = await _get_social_account_by_id(user_id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")
    client = await supabase_get_client()
    response = (
        await client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .delete()
        .eq("id", account_id)
        .eq("user_id", user_id)
        .execute()
    )
    return {"deleted": bool(response.data)}


def _apply_publish_jobs_date_filter(query, date_filter: Optional[str], date_from: Optional[str], date_to: Optional[str]):
    if not date_filter or date_filter == "all":
        return query

    now = datetime.now(timezone.utc)
    if date_filter == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        return query.gte("created_at", start_date)
    if date_filter == "week":
        week_ago = now - timedelta(days=7)
        return query.gte("created_at", week_ago.isoformat())
    if date_filter == "month":
        month_ago = now - timedelta(days=30)
        return query.gte("created_at", month_ago.isoformat())
    if date_filter != "custom":
        return query

    parsed_start_dt = None
    parsed_end_dt = None
    if date_from:
        try:
            parsed_start_dt = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            query = query.gte("created_at", parsed_start_dt.replace(hour=0, minute=0, second=0, microsecond=0).isoformat())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_from format. Expected YYYY-MM-DD")
    if date_to:
        try:
            parsed_end_dt = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
            query = query.lte("created_at", parsed_end_dt.replace(hour=23, minute=59, second=59, microsecond=999999).isoformat())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date_to format. Expected YYYY-MM-DD")
    if parsed_start_dt and parsed_end_dt and parsed_start_dt.date() > parsed_end_dt.date():
        raise HTTPException(status_code=400, detail="date_from must be before or equal to date_to")
    return query


def _filter_publish_jobs_by_search(items: List[Dict[str, Any]], total: int, search: Optional[str]):
    if not (search and search.strip()):
        return items, total
    search_lower = search.lower().strip()
    filtered = [
        item for item in items
        if (item.get("external_id", "").lower().find(search_lower) >= 0 or
            item.get("platform", "").lower().find(search_lower) >= 0)
    ]
    return filtered, len(filtered)


@app.get("/api/social/publish-jobs", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 500: {"description": "Internal Server Error"}})
async def list_publish_jobs(
    user_id: Annotated[str, Depends(get_user_id_header)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    platform: Annotated[Optional[str], Query()] = None,
    status: Annotated[Optional[str], Query()] = None,
    date_filter: Annotated[Optional[str], Query()] = None,  # all, today, week, month
    date_from: Annotated[Optional[str], Query()] = None,
    date_to: Annotated[Optional[str], Query()] = None,
    search: Annotated[Optional[str], Query()] = None,
):
    """
    Récupère les publications sociales de l'utilisateur avec filtres.

    Args:
        user_id: ID utilisateur
        page: Numéro de page (par défaut 1)
        page_size: Nombre d'items par page (par défaut 20, max 100)
        platform: Filtre par plateforme (facebook, instagram, tiktok, youtube, linkedin)
        status: Filtre par statut (pending, processing, done, failed)
        date_filter: Filtre par date (all, today, week, month, custom)
        date_from: Date de début (YYYY-MM-DD) si date_filter=custom
        date_to: Date de fin (YYYY-MM-DD) si date_filter=custom
        search: Recherche dans l'ID externe ou la plateforme
    """
    try:
        client = await supabase_get_client()

        # Construire la requête de base
        query = (
            client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
            .select("*", count="exact")
            .eq("user_id", user_id)
        )

        # Filtrer par plateforme
        if platform and platform not in ("all", ""):
            query = query.eq("platform", platform.lower())

        # Filtrer par statut
        if status and status not in ("all", ""):
            query = query.eq("status", status.lower())

        # Filtrer par date
        query = _apply_publish_jobs_date_filter(query, date_filter, date_from, date_to)

        # Ordonner par date de création (plus récent en premier)
        query = query.order("created_at", desc=True)

        # Exécuter la requête avec pagination
        offset = (page - 1) * page_size
        response = await query.range(offset, offset + page_size - 1).execute()

        items = response.data or []
        total = response.count or 0

        # Filtrer par recherche si fournie (filtre côté client pour simplifier)
        items, total = _filter_publish_jobs_by_search(items, total, search)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": max(1, (total + page_size - 1) // page_size),
        }
    except Exception as e:
        print(f"⚠️ Erreur lors de la récupération des publications: {e}")
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@app.delete("/api/social/publish-jobs/{publish_job_id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def delete_publish_job(
    publish_job_id: str,
    user_id: Annotated[str, Depends(get_user_id_header)],
):
    if not is_supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase social publishing is not configured")

    client = await supabase_get_client()
    existing = (
        await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE)
        .select("id, user_id, platform, status")
        .eq("id", publish_job_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Publish job not found")

    await client.table(SUPABASE_SOCIAL_PUBLISH_JOBS_TABLE).delete().eq("id", publish_job_id).eq("user_id", user_id).execute()
    return {"success": True, "deleted_id": publish_job_id}


class SelectFacebookPageRequest(BaseModel):
    selection_token: str
    page_id: str


@app.post("/api/auth/facebook/select-page", responses={400: {"description": "Bad Request"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}})
async def select_facebook_page(payload: SelectFacebookPageRequest):
    try:
        data = _page_selection_serializer.loads(payload.selection_token, max_age=_PAGE_SELECTION_TTL_SECONDS)
    except SignatureExpired:
        raise HTTPException(status_code=400, detail="Page selection expired, please reconnect Facebook")
    except BadSignature:
        raise HTTPException(status_code=400, detail="Invalid selection token")

    if data.get("platform") != "facebook":
        raise HTTPException(status_code=400, detail="Invalid selection token platform")

    user_id = data.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid selection token: missing user_id")

    page_token = (data.get("pages") or {}).get(payload.page_id)
    if not page_token:
        raise HTTPException(status_code=400, detail="This page was not part of the original selection")

    identity = await fetch_platform_identity("facebook", page_token)

    await _upsert_social_account(
        user_id=user_id,
        platform="facebook",
        access_token=page_token,
        refresh_token=None,  # les Page tokens n'ont pas de refresh_token classique
        expires_in=int(data.get("user_token_expires_in") or 5_184_000),
        platform_user_id=payload.page_id,
        platform_account_name=identity.get("name", "Facebook Page"),
        scopes=",".join(PLATFORM_CONFIG["facebook"]["scopes"]),
    )

    return {
        "success": True,
        "message": f"Connected Facebook page '{identity.get('name', 'Facebook Page')}'",
        "platform": "facebook",
        "page_id": payload.page_id,
    }


@app.get("/api/auth/{platform}/connect", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
def connect(platform: str, request: Request, user_id: Annotated[str, Depends(get_user_id_header)]):
    # Security: `user_id` MUST come from the verified session (get_user_id_header),
    # never from an unauthenticated query parameter -- otherwise an attacker
    # could craft a /connect link carrying their own user_id, get a victim to
    # complete the OAuth consent with the victim's real social account, and
    # have the resulting token linked to the attacker's Vireel account
    # (account-linking CSRF).
    key = (platform or "").strip().lower()
    config = _resolve_platform_config(key)
    redirect_uri = _oauth_redirect_uri(key, request)

    # Payload signé qui remplace le dict _oauth_states — plus besoin de stockage en mémoire
    state_payload = {
        "user_id": user_id,
        "platform": key,
        "redirect_uri": redirect_uri,
    }

    params = {
        "client_id": config["client_id"],
        "redirect_uri": redirect_uri,
        "scope": " ".join(config["scopes"]),
        "response_type": "code",
    }

    if key == "youtube":
        params["access_type"] = "offline"
        params["prompt"] = "consent"

    if key == "facebook":
        # Without this, Facebook silently skips the consent screen for a
        # user who already authorized the app and just reissues a token
        # with whatever permissions were granted the first time -- so
        # adding a new scope (e.g. pages_manage_engagement) to
        # PLATFORM_CONFIG never actually gets requested on a plain
        # "reconnect", even though the URL's `scope` param lists it.
        # auth_type=rerequest forces Facebook to show the full permission
        # dialog again, including newly added scopes.
        params["auth_type"] = "rerequest"

    if key == "tiktok":
        code_verifier, code_challenge = generate_pkce_pair()
        state_payload["code_verifier"] = code_verifier

        params["client_key"] = config["client_id"]
        params.pop("client_id", None)  # TikTok utilise client_key, pas client_id
        params["code_challenge"] = code_challenge
        params["code_challenge_method"] = "S256"
        params["scope"] = ",".join(config["scopes"])  # TikTok utilise scope séparé par des espaces

    # Signe le payload → devient le state envoyé à la plateforme
    state = _oauth_serializer.dumps(state_payload)
    params["state"] = state

    auth_url = f"{config['auth_url']}?{urlencode(params)}"
    return {"auth_url": auth_url}


def _build_oauth_token_payload(key: str, code: str, config: dict, state_data: dict) -> Dict[str, Any]:
    token_payload = {
        "code": code,
        "redirect_uri": state_data.get("redirect_uri") or _oauth_redirect_uri(key),
        "grant_type": "authorization_code",
    }

    if key == "tiktok":
        token_payload["client_key"] = config["client_id"]
        token_payload["client_secret"] = config["client_secret"]
        token_payload["code_verifier"] = state_data["code_verifier"]  # ← récupéré du connect
    else:
        token_payload["client_id"] = config["client_id"]
        token_payload["client_secret"] = config["client_secret"]

    return token_payload


async def _handle_facebook_oauth_callback(key: str, token_data: dict, state_data: dict):
    try:
        pages = await fetch_facebook_pages(token_data["access_token"])
        if pages:
            # Retourne le modal de sélection de pages
            return _oauth_popup_response(
                False, key, None,
                page_selection_data={
                    "pages": pages,
                    "user_token": token_data["access_token"],
                    "user_token_expires_in": token_data.get("expires_in", 5184000),
                    "user_id": state_data.get("user_id"),
                }
            )
        return _oauth_popup_response(
            False,
            key,
            "No manageable Facebook Pages found. Ensure you are Page admin/editor and grant pages_show_list, pages_manage_posts, pages_read_engagement.",
        )
    except Exception as e:
        return _oauth_popup_response(
            False,
            key,
            f"Facebook pages fetch failed: {e}",
        )


async def _finalize_oauth_callback_identity(key: str, state_data: dict, token_data: dict):
    identity = await fetch_platform_identity(key, token_data["access_token"])
    await _upsert_social_account(
        user_id=state_data["user_id"],
        platform=key,
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        expires_in=int(token_data.get("expires_in") or 3600),
        platform_user_id=identity.get("id", ""),
        platform_account_name=identity.get("name", key),
        scopes=str(token_data.get("scopes") or ""),
    )
    return _oauth_popup_response(True, key)


@app.get("/api/auth/{platform}/callback", responses={403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 502: {"description": "Bad Gateway"}, 503: {"description": "Service Unavailable"}})
async def callback(platform: str, code: Optional[str] = None, state: str = "", error: Optional[str] = None):
    key = (platform or "").strip().lower()

    try:
        state_data = _oauth_serializer.loads(state, max_age=_OAUTH_STATE_TTL_SECONDS)
    except SignatureExpired:
        return _oauth_popup_response(False, key, "OAuth state expired")
    except BadSignature:
        return _oauth_popup_response(False, key, "Invalid OAuth state")

    if state_data.get("platform") != key:
        return _oauth_popup_response(False, key, "Platform mismatch in OAuth state")
    if error:
        return _oauth_popup_response(False, key, error)
    if not code:
        return _oauth_popup_response(False, key, "Missing OAuth code")

    config = _resolve_platform_config(key)
    token_payload = _build_oauth_token_payload(key, code, config, state_data)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(config["token_url"], data=token_payload)
        response.raise_for_status()
        raw_token_data = response.json()

        # Instagram : échange immédiatement contre un long-lived token
        if key == "instagram":
            raw_token_data = await _exchange_instagram_long_lived_token(
                config, raw_token_data["access_token"]
            )

        token_data = await _extract_token_data(key, raw_token_data)

        # Facebook : récupère les pages et affiche la sélection
        if key == "facebook":
            return await _handle_facebook_oauth_callback(key, token_data, state_data)

        return await _finalize_oauth_callback_identity(key, state_data, token_data)
    except Exception as exc:
        return _oauth_popup_response(False, key, str(exc))


async def _exchange_instagram_long_lived_token(config: dict, short_lived_token: str) -> dict:
    """
    Instagram : le token initial expire en 1h.
    On l'échange immédiatement contre un token valide 60 jours.
    """
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            config["long_lived_token_url"],
            params={
                "grant_type": "ig_exchange_token",
                "client_secret": config["client_secret"],
                "access_token": short_lived_token,
            },
        )
    response.raise_for_status()
    data = response.json()
    return data

async def _fetch_linkedin_identity(client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, str]:
    response = await client.get("https://api.linkedin.com/v2/userinfo", headers=headers)
    response.raise_for_status()
    data = response.json()
    return {"id": str(data.get("sub") or ""), "name": data.get("name") or "LinkedIn"}


async def _fetch_facebook_identity(client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, str]:
    response = await client.get("https://graph.facebook.com/me", params={"fields": "id,name"}, headers=headers)
    response.raise_for_status()
    data = response.json()
    return {"id": str(data.get("id") or ""), "name": data.get("name") or "Facebook"}


async def _fetch_instagram_identity(access_token: str) -> Dict[str, str]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://graph.instagram.com/me",
            params={
                "fields": "id,username,account_type",
                "access_token": access_token,
            },
        )
    response.raise_for_status()
    data = response.json()
    return {"id": data["id"], "name": data.get("username", "instagram")}


async def _fetch_youtube_identity(client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, str]:
    response = await client.get("https://www.googleapis.com/youtube/v3/channels", params={"part": "snippet", "mine": "true"}, headers=headers)
    response.raise_for_status()
    items = response.json().get("items") or []
    first = items[0] if items else {}
    return {"id": str(first.get("id") or ""), "name": ((first.get("snippet") or {}).get("title") or "YouTube")}


async def _fetch_tiktok_identity(client: httpx.AsyncClient, headers: Dict[str, str]) -> Dict[str, str]:
    response = await client.get(
        "https://open.tiktokapis.com/v2/user/info/",
        params={"fields": "open_id,display_name"},
        headers=headers,
    )
    response.raise_for_status()
    user = ((response.json().get("data") or {}).get("user") or {})
    return {"id": str(user.get("open_id") or ""), "name": user.get("display_name") or "TikTok"}


async def fetch_platform_identity(platform: str, access_token: str):
    if platform == "instagram":
        return await _fetch_instagram_identity(access_token)

    headers = {"Authorization": f"Bearer {access_token}"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        if platform == "linkedin":
            return await _fetch_linkedin_identity(client, headers)
        if platform == "facebook":
            return await _fetch_facebook_identity(client, headers)
        if platform == "youtube":
            return await _fetch_youtube_identity(client, headers)
        if platform == "tiktok":
            return await _fetch_tiktok_identity(client, headers)

    raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)


def _is_token_expiring(account: Dict[str, Any], margin_seconds: int = 300) -> bool:
    expires_at = account.get("expires_at")
    if not expires_at:
        return True
    try:
        expires_dt = datetime.fromisoformat(str(expires_at).replace("Z", _ISO_UTC_OFFSET_SUFFIX))
        platform = str(account.get("platform") or "").lower()
        # Instagram tokens (via Meta) ont une fenêtre de 60 jours mais se dégradent silencieusement ;
        # forcer un refresh si l'expiration est dans moins de 5 jours.
        if platform == "instagram":
            margin_seconds = max(margin_seconds, 5 * 24 * 3600)  # 432 000 secondes
        return expires_dt <= datetime.now(timezone.utc) + timedelta(seconds=margin_seconds)
    except Exception:
        return True


# --------------------------------------------------------------------------
# Helpers génériques (social publishing)
# --------------------------------------------------------------------------

def _require_platform_user_id(account: Dict[str, Any], platform: str) -> str:
    user_id = str(account.get("platform_user_id") or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail=f"Connected {platform} account id is missing")
    return user_id


async def _raise_for_status_or_502(response: httpx.Response, platform: str) -> None:  # NOSONAR(S7503) kept async for uniformity across its ~18 `await`ed call sites (a mechanical de-asyncing of every one is not worth the churn/error risk for a function this trivially fast either way)
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as e:
        logger.exception("%s API error: %s - %s", platform, e.response.status_code, e.response.text)
        # Meta's Graph API (Facebook/Instagram) wraps its actual error text in
        # {"error": {"message": "..."}}; surfacing that message instead of the
        # raw JSON blob is what lets a specific, documented rejection (e.g.
        # the text-background length limit) read as a clear sentence rather
        # than an opaque payload. Other platforms' error shapes don't match,
        # so this just falls through to the original raw text for them.
        detail_message = e.response.text
        try:
            api_message = e.response.json().get("error", {}).get("message")
            if api_message:
                detail_message = api_message
        except (ValueError, AttributeError):
            pass
        raise HTTPException(
            status_code=502,
            detail=f"{platform} API error ({e.response.status_code}): {detail_message}",
        ) from e


def _resolve_and_validate_ips(hostname: str) -> List[str]:
    """Resolve hostname and reject it if any resolved address is
    private/loopback/link-local/multicast/reserved. Returns the resolved IPs."""
    try:
        resolved_ips = list({info[4][0] for info in socket.getaddrinfo(hostname, None)})
    except socket.gaierror as e:
        raise HTTPException(status_code=400, detail="video_url host could not be resolved") from e
    for ip_str in resolved_ips:
        ip = ipaddress.ip_address(ip_str)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved:
            raise HTTPException(status_code=400, detail="video_url points to a disallowed address")
    return resolved_ips


def _validate_download_url(url: str) -> None:
    """Anti-SSRF minimal avant un GET serveur vers une URL fournie par l'utilisateur."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(status_code=400, detail="video_url must be http(s)")
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="video_url is invalid")
    _resolve_and_validate_ips(hostname)


def _pin_url_to_validated_ip(url: str) -> tuple[str, Dict[str, Any]]:
    """Resolve+validate url's hostname, then rewrite the URL to connect
    directly to that validated IP, returning the rewritten URL plus httpx
    request extensions that keep TLS SNI / certificate hostname verification
    targeting the original hostname.

    Security: this closes the DNS-rebinding TOCTOU where _validate_download_url
    resolves and checks a hostname, but the actual HTTP client performs its
    own, independent DNS lookup at connect time -- an attacker controlling
    DNS for their domain (short TTL) could return a public IP for the check
    and a private/loopback IP for the real connection. Pinning the exact
    validated IP for the connection itself eliminates that window.
    """
    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise HTTPException(status_code=400, detail="video_url is invalid")
    validated_ips = _resolve_and_validate_ips(hostname)
    ip = validated_ips[0]
    netloc_host = f"[{ip}]" if ":" in ip else ip
    port = parsed.port
    netloc = f"{netloc_host}:{port}" if port else netloc_host
    pinned_url = parsed._replace(netloc=netloc).geturl()
    extensions = {"sni_hostname": hostname} if parsed.scheme == "https" else {}
    return pinned_url, extensions


async def _validated_stream_request(client: "httpx.AsyncClient", method: str, url: str, max_redirects: int = 5, **kwargs):
    """Issue a request without httpx's automatic redirect-following, so that
    every hop (including ones a malicious server returns after the initial
    validation) is re-checked by _validate_download_url before being
    followed. httpx's built-in follow_redirects=True would otherwise let a
    server bypass SSRF validation entirely by 302-redirecting to an
    internal/loopback/link-local address after the first request passed.
    Also pins each hop's connection to its validated IP (see
    _pin_url_to_validated_ip) to close the DNS-rebinding TOCTOU window.
    """
    current_url = url
    for _ in range(max_redirects + 1):
        original_hostname = urlparse(current_url).hostname
        pinned_url, extensions = _pin_url_to_validated_ip(current_url)
        headers = dict(kwargs.pop("headers", None) or {})
        headers.setdefault("Host", original_hostname)
        request = client.build_request(method, pinned_url, headers=headers, extensions=extensions, **kwargs)
        response = await client.send(request, stream=True)
        if response.is_redirect:
            location = response.headers.get("location")
            await response.aclose()
            if not location:
                response.raise_for_status()
                return response
            current_url = str(httpx.URL(current_url).join(location))
            continue
        return response
    raise HTTPException(status_code=400, detail="Too many redirects while fetching video_url")


async def _download_to_file(url: str, dest_path: str, timeout: float = 180.0) -> None:  # NOSONAR(S7483) this `timeout` configures httpx.AsyncClient's own connect/read/write/pool timeouts below, the idiomatic httpx pattern -- it isn't an asyncio.wait_for()-style overall deadline, so wrapping the call in asyncio.timeout() instead would change timeout semantics, not just syntax
    _validate_download_url(url)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        response = await _validated_stream_request(client, "GET", url)
        try:
            response.raise_for_status()
            async with aiofiles.open(dest_path, "wb") as handle:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    await handle.write(chunk)
        finally:
            await response.aclose()


# --------------------------------------------------------------------------
# Token refresh (get_valid_token)
# --------------------------------------------------------------------------

# Certains providers OAuth n'utilisent pas les noms de paramètres standards
# (client_id/client_secret). TikTok en particulier attend client_key.
_REFRESH_PARAM_OVERRIDES = {
    "tiktok": {"client_id_param": "client_key"},
}


async def _refresh_instagram_token(account: Dict[str, Any], access_token: Optional[str]) -> str:
    # --- Instagram : pas de refresh_token classique, on rafraîchit le
    # long-lived access_token directement via ig_refresh_token ---
    if not access_token:
        raise HTTPException(status_code=401, detail="Instagram account token missing, reconnection required")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://graph.instagram.com/refresh_access_token",
            params={"grant_type": "ig_refresh_token", "access_token": access_token},
        )

    if response.status_code in (400, 401):
        logger.warning("Instagram token refresh rejected: %s", response.text)
        raise HTTPException(status_code=401, detail="Instagram token expired, reconnection required")
    await _raise_for_status_or_502(response, "Instagram")

    new_data = response.json()
    refreshed_access_token = new_data.get("access_token")
    if not refreshed_access_token:
        raise HTTPException(status_code=502, detail="Instagram refresh response missing access_token")
    expires_in = int(new_data.get("expires_in") or 5_184_000)  # 60 jours par défaut

    await _persist_refreshed_token(account, refreshed_access_token, None, expires_in)
    return refreshed_access_token


async def _refresh_generic_oauth_token(account: Dict[str, Any], platform: str, access_token: Optional[str]) -> str:
    # --- Flow générique (OAuth refresh_token) pour les autres plateformes ---
    refresh_token = _decrypt_token(account.get("refresh_token_encrypted"))
    if not refresh_token:
        if access_token:
            logger.warning(
                "No refresh_token for account %s (%s); reusing possibly-expiring access_token",
                account.get("id"), platform,
            )
            return access_token
        raise HTTPException(status_code=401, detail="Account token expired and no refresh token available")

    config = _resolve_platform_config(platform)

    overrides = _REFRESH_PARAM_OVERRIDES.get(platform, {})
    client_id_param = overrides.get("client_id_param", "client_id")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            config["token_url"],
            data={
                client_id_param: config["client_id"],
                "client_secret": config["client_secret"],
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )

    if response.status_code in (400, 401):
        logger.warning("%s token refresh rejected: %s", platform, response.text)
        raise HTTPException(status_code=401, detail=f"{platform} refresh token invalid, reconnection required")
    await _raise_for_status_or_502(response, platform)

    new_tokens = await _extract_token_data(platform, response.json())
    refreshed_access_token = new_tokens.get("access_token")
    if not refreshed_access_token:
        raise HTTPException(status_code=502, detail=f"{platform} refresh response missing access_token")
    refreshed_refresh_token = new_tokens.get("refresh_token") or refresh_token
    expires_in = int(new_tokens.get("expires_in") or 3600)

    await _persist_refreshed_token(account, refreshed_access_token, refreshed_refresh_token, expires_in)
    return refreshed_access_token


async def get_valid_token(account: Dict[str, Any]) -> str:
    access_token = _decrypt_token(account.get("access_token_encrypted"))
    if access_token and not _is_token_expiring(account):
        return access_token

    platform = str(account.get("platform") or "").lower()

    if platform == "instagram":
        return await _refresh_instagram_token(account, access_token)

    return await _refresh_generic_oauth_token(account, platform, access_token)


async def _persist_refreshed_token(
    account: Dict[str, Any],
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
) -> None:
    update_payload: Dict[str, Any] = {
        "access_token_encrypted": _encrypt_token(access_token),
        "expires_at": datetime.fromtimestamp(time.time() + max(expires_in, 60), tz=timezone.utc).isoformat(),
        "updated_at": _utcnow_iso(),
    }
    if refresh_token is not None:
        update_payload["refresh_token_encrypted"] = _encrypt_token(refresh_token)

    client = await supabase_get_client()
    await (
        client.table(SUPABASE_SOCIAL_ACCOUNTS_TABLE)
        .update(update_payload)
        .eq("id", account.get("id"))
        .execute()
    )


class PublishRequest(BaseModel):
    user_id: str
    text: Optional[str] = None
    caption: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    video_url: Optional[str] = None
    video_file: Optional[str] = None
    image_url: Optional[str] = None
    facebook_text_format_preset_id: Optional[str] = None
    privacy_level: Optional[str] = "PUBLIC_TO_EVERYONE"


# --------------------------------------------------------------------------
# YouTube
# --------------------------------------------------------------------------

def _yt_validate_privacy(privacy: str) -> None:
    if privacy not in ALLOWED_YT_PRIVACY:
        raise HTTPException(status_code=400, detail=f"Invalid privacy '{privacy}', must be one of {sorted(ALLOWED_YT_PRIVACY)}")


async def _yt_initialize_upload(access_token: str, file_size: int, title: str, description: str, privacy: str) -> str:
    """Enregistre la session resumable et renvoie l'upload URL (header Location)."""
    metadata = {
        "snippet": {"title": title, "description": description, "categoryId": "22"},
        "status": {"privacyStatus": privacy},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        init_response = await client.post(
            "https://www.googleapis.com/upload/youtube/v3/videos",
            params={"uploadType": "resumable", "part": "snippet,status"},
            headers={
                "Authorization": f"Bearer {access_token}",
                "X-Upload-Content-Type": "video/*",
                "X-Upload-Content-Length": str(file_size),
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=metadata,
        )
    await _raise_for_status_or_502(init_response, "YouTube")

    upload_url = init_response.headers.get("Location")
    if not upload_url:
        raise HTTPException(status_code=502, detail="YouTube upload session URL is missing")
    return upload_url


async def _yt_put_chunk_with_retry(upload_url: str, chunk: bytes, chunk_start: int, chunk_end: int, file_size: int) -> httpx.Response:
    """PUT d'un chunk avec retry ; renvoie la réponse HTTP brute (200/201/308/erreur gérés par l'appelant)."""
    last_error: Optional[Exception] = None
    for attempt in range(YT_MAX_RETRIES_PER_CHUNK):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                return await client.put(
                    upload_url,
                    headers={
                        "Content-Length": str(len(chunk)),
                        "Content-Range": f"bytes {chunk_start}-{chunk_end}/{file_size}",
                    },
                    content=chunk,
                )
        except httpx.HTTPError as e:
            last_error = e
            logger.warning("YouTube chunk upload failed (attempt %s/%s): %s", attempt + 1, YT_MAX_RETRIES_PER_CHUNK, e)
            await asyncio.sleep(2 ** attempt)
    raise HTTPException(status_code=502, detail=f"YouTube chunk upload failed after retries: {last_error}")


def _yt_next_offset(range_header: Optional[str], uploaded: int, chunk_len: int) -> int:
    if range_header and "-" in range_header:
        return int(range_header.split("-")[-1]) + 1
    return uploaded + chunk_len


async def upload_youtube_video(
    access_token: str, video_path: str, title: str, description: str, privacy: str = "public",
) -> Dict[str, Any]:
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
    _yt_validate_privacy(privacy)

    file_size = os.path.getsize(video_path)
    upload_url = await _yt_initialize_upload(access_token, file_size, title, description, privacy)

    uploaded = 0
    async with aiofiles.open(video_path, "rb") as file_handle:
        while uploaded < file_size:
            await file_handle.seek(uploaded)
            chunk = await file_handle.read(YT_CHUNK_SIZE)
            response = await _yt_put_chunk_with_retry(upload_url, chunk, uploaded, uploaded + len(chunk) - 1, file_size)

            if response.status_code in (200, 201):
                result = response.json()
                return {"video_id": result.get("id"), "url": f"https://youtube.com/watch?v={result.get('id')}"}

            if response.status_code == 308:
                uploaded = _yt_next_offset(response.headers.get("Range"), uploaded, len(chunk))
                continue

            await _raise_for_status_or_502(response, "YouTube")

    raise HTTPException(status_code=502, detail="YouTube upload ended without a final response")


# --------------------------------------------------------------------------
# TikTok
# --------------------------------------------------------------------------

# Tant que l'app n'a pas passé l'audit TikTok, seul le scope video.upload est
# accordé -> on doit utiliser l'endpoint "inbox" (dépôt dans la boîte de
# réception du créateur, qui doit finaliser lui-même la publication dans
# l'app). video.publish (endpoint /video/init/, publication directe) ne sera
# disponible qu'une fois l'app passée en production/auditée par TikTok.
# Passe TIKTOK_DIRECT_POST_ENABLED=true dans l'environnement une fois
# l'audit validé et le scope video.publish accordé.
TIKTOK_DIRECT_POST_ENABLED = os.environ.get("TIKTOK_DIRECT_POST_ENABLED", "false").strip().lower() == "true"

# Statuts terminaux considérés comme un succès selon le flow utilisé.
_TIKTOK_DIRECT_SUCCESS_STATUSES = ("PUBLISH_COMPLETE",)
# En mode inbox, la vidéo est traitée puis déposée en boîte de réception ;
# PUBLISH_COMPLETE ne surviendra que si/quand le créateur termine dans l'app.
_TIKTOK_INBOX_SUCCESS_STATUSES = ("PUBLISH_COMPLETE", "SEND_TO_USER_INBOX")


async def publish_to_tiktok(access_token: str, video_url: str, caption: str, privacy_level: str = "PUBLIC_TO_EVERYONE"):
    """
    Point d'entrée unique utilisé par publish_post. Choisit automatiquement
    le flow direct post ou inbox selon TIKTOK_DIRECT_POST_ENABLED.
    """
    if TIKTOK_DIRECT_POST_ENABLED:
        return await _publish_to_tiktok_direct(access_token, video_url, caption, privacy_level)
    return await _publish_to_tiktok_inbox(access_token, video_url, caption)


async def _publish_to_tiktok_direct(access_token: str, video_url: str, caption: str, privacy_level: str) -> Dict[str, Any]:
    """
    Publication directe sur le profil — nécessite le scope video.publish
    (app auditée). Utilise FILE_UPLOAD (téléchargement local + envoi par
    chunks) plutôt que PULL_FROM_URL, pour ne jamais dépendre de la
    vérification de domaine TikTok (utile notamment pour des URLs S3 sur
    un domaine partagé qu'on ne peut pas prouver posséder).
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"tiktok_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(video_url, temp_path)

    try:
        file_size = os.path.getsize(temp_path)
        chunk_size, total_chunk_count = _tiktok_compute_chunks(file_size)

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": _CONTENT_TYPE_JSON}
        init_payload = {
            "post_info": {
                "title": caption, "privacy_level": privacy_level, "disable_duet": False,
                "disable_comment": False, "disable_stitch": False,
                "brand_content_toggle": False, "brand_organic_toggle": False,
            },
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            },
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            init_response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/video/init/", headers=headers, json=init_payload,
            )
        await _raise_for_status_or_502(init_response, "TikTok")

        init_data = init_response.json()
        if init_data.get("error", {}).get("code") != "ok":
            raise HTTPException(status_code=502, detail=f"TikTok publish init failed: {init_data}")

        data = init_data.get("data") or {}
        publish_id = (data.get("publish_id") or "").strip()
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise HTTPException(status_code=502, detail="TikTok direct post init response missing publish_id or upload_url")

        await _tiktok_upload_file_chunks(upload_url, temp_path, file_size, chunk_size, total_chunk_count)

        result = await poll_tiktok_status(access_token, publish_id, success_statuses=_TIKTOK_DIRECT_SUCCESS_STATUSES)
        result["mode"] = "direct_post"
        return result
    finally:
        _cleanup_temp_file(temp_path)


TIKTOK_CHUNK_SIZE = 10_000_000  # 10 Mo, dans la plage autorisée par TikTok (5-64 Mo par chunk)
TIKTOK_WHOLE_UPLOAD_THRESHOLD = 5_000_000  # en dessous, TikTok exige un upload en un seul morceau


def _tiktok_compute_chunks(file_size: int) -> "tuple[int, int]":
    """Renvoie (chunk_size, total_chunk_count) en respectant les règles TikTok."""
    if file_size <= TIKTOK_WHOLE_UPLOAD_THRESHOLD or file_size < TIKTOK_CHUNK_SIZE:
        return file_size, 1
    return TIKTOK_CHUNK_SIZE, file_size // TIKTOK_CHUNK_SIZE


async def _tiktok_upload_file_chunks(upload_url: str, video_path: str, file_size: int, chunk_size: int, total_chunk_count: int) -> None:
    """Envoie le fichier local par chunks séquentiels, avec retry par chunk."""
    async with aiofiles.open(video_path, "rb") as file_handle:
        for i in range(total_chunk_count):
            first_byte = i * chunk_size
            last_byte = file_size - 1 if i == total_chunk_count - 1 else first_byte + chunk_size - 1
            await file_handle.seek(first_byte)
            chunk = await file_handle.read(last_byte - first_byte + 1)

            last_error: Optional[Exception] = None
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.put(
                            upload_url,
                            headers={
                                "Content-Type": "video/mp4",
                                "Content-Length": str(len(chunk)),
                                "Content-Range": f"bytes {first_byte}-{last_byte}/{file_size}",
                            },
                            content=chunk,
                        )
                    if response.status_code in (200, 201, 206):
                        break
                    response.raise_for_status()
                except httpx.HTTPError as e:
                    last_error = e
                    logger.warning(
                        "TikTok chunk upload failed (bytes %s-%s, attempt %s/3): %s", first_byte, last_byte, attempt + 1, e,
                    )
                    await asyncio.sleep(2 ** attempt)
            else:
                raise HTTPException(status_code=502, detail=f"TikTok chunk upload failed after retries: {last_error}")


async def _publish_to_tiktok_inbox(access_token: str, video_url: str, caption: str) -> Dict[str, Any]:
    """
    Dépose la vidéo dans la boîte de réception TikTok du créateur — nécessite
    seulement video.upload. Le créateur doit ouvrir l'app pour finaliser la
    publication. NOTE: cet endpoint ne supporte pas de caption/titre via
    l'API ; le créateur devra la saisir manuellement dans l'app.

    Utilise FILE_UPLOAD (téléchargement local puis envoi par chunks) plutôt
    que PULL_FROM_URL : évite la vérification de domaine TikTok, nécessaire
    pour des URLs S3 sur un domaine partagé (*.amazonaws.com) qu'on ne peut
    pas prouver posséder.
    """
    if caption:
        logger.info("TikTok inbox upload: la légende ne peut pas être envoyée via l'API, le créateur devra la saisir dans l'app.")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"tiktok_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(video_url, temp_path)

    try:
        file_size = os.path.getsize(temp_path)
        chunk_size, total_chunk_count = _tiktok_compute_chunks(file_size)

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": _CONTENT_TYPE_JSON}
        init_payload = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunk_count,
            }
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            init_response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/", headers=headers, json=init_payload,
            )
        await _raise_for_status_or_502(init_response, "TikTok")

        init_data = init_response.json()
        if init_data.get("error", {}).get("code") != "ok":
            raise HTTPException(status_code=502, detail=f"TikTok inbox upload init failed: {init_data}")

        data = init_data.get("data") or {}
        publish_id = (data.get("publish_id") or "").strip()
        upload_url = data.get("upload_url")
        if not publish_id or not upload_url:
            raise HTTPException(status_code=502, detail="TikTok inbox init response missing publish_id or upload_url")

        await _tiktok_upload_file_chunks(upload_url, temp_path, file_size, chunk_size, total_chunk_count)

        result = await poll_tiktok_status(access_token, publish_id, success_statuses=_TIKTOK_INBOX_SUCCESS_STATUSES)
        result["mode"] = "inbox"
        if result.get("status") == "SEND_TO_USER_INBOX":
            result["note"] = "Video sent to the creator's TikTok inbox; they must open the app to finish posting."
        return result
    finally:
        _cleanup_temp_file(temp_path)


async def publish_to_tiktok_photo(token: str, image_urls: List[str], caption: str) -> Dict[str, Any]:
    """
    LIMITATION API TikTok : contrairement aux vidéos, l'endpoint photo
    (/v2/post/publish/content/init/) n'accepte QUE "source": "PULL_FROM_URL"
    — TikTok ne propose pas d'upload binaire pour les photos. Le domaine
    hébergeant image_urls doit donc être vérifié dans le TikTok Developer
    Portal (même prérequis que pour PULL_FROM_URL vidéo), il n'y a pas
    d'alternative FILE_UPLOAD possible ici.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": _CONTENT_TYPE_JSON}
    post_mode = "DIRECT_POST" if TIKTOK_DIRECT_POST_ENABLED else "MEDIA_UPLOAD"
    payload = {
        "post_info": {"title": caption, "description": caption},
        "source_info": {"source": "PULL_FROM_URL", "photo_images": image_urls, "photo_cover_index": 0},
        "post_mode": post_mode,
        "media_type": "PHOTO",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post("https://open.tiktokapis.com/v2/post/publish/content/init/", json=payload, headers=headers)
    await _raise_for_status_or_502(response, "TikTok")

    init_data = response.json()
    if init_data.get("error", {}).get("code") != "ok":
        raise HTTPException(status_code=502, detail=f"TikTok photo publish init failed: {init_data}")
    return init_data


async def poll_tiktok_status(
    access_token: str, publish_id: str, max_attempts: int = 20, success_statuses=("PUBLISH_COMPLETE",),
):
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": _CONTENT_TYPE_JSON}
    delay = 2.0
    for _ in range(max_attempts):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://open.tiktokapis.com/v2/post/publish/status/fetch/", headers=headers, json={"publish_id": publish_id},
            )
        await _raise_for_status_or_502(response, "TikTok")
        data = response.json().get("data") or {}
        status = data.get("status")
        if status in success_statuses:
            return {"success": True, "publish_id": publish_id, "status": status}
        if status == "FAILED":
            return {"success": False, "publish_id": publish_id, "status": status, "error": data.get("fail_reason") or "unknown"}
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 30.0)
    return {"success": False, "publish_id": publish_id, "status": "TIMEOUT", "error": "timeout"}



# --------------------------------------------------------------------------
# Facebook
# --------------------------------------------------------------------------

async def publish_to_facebook_video(access_token: str, target_id: str, video_url: str, message: str, title: str, description: str):
    if not target_id:
        raise HTTPException(status_code=400, detail=_FACEBOOK_TARGET_ID_MISSING)
    if not access_token:
        raise HTTPException(status_code=401, detail=_FACEBOOK_TOKEN_EXPIRED_OR_MISSING)

    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{target_id}/videos",
            data={"file_url": video_url, "description": message or description, "title": title, "access_token": access_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    return {"id": response.json().get("id")}


async def publish_to_facebook_photo(access_token: str, target_id: str, image_url: str, message: str) -> Dict[str, Any]:
    if not target_id:
        raise HTTPException(status_code=400, detail=_FACEBOOK_TARGET_ID_MISSING)
    if not access_token:
        raise HTTPException(status_code=401, detail=_FACEBOOK_TOKEN_EXPIRED_OR_MISSING)

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{target_id}/photos",
            data={"url": image_url, "caption": message, "access_token": access_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    return {"id": response.json().get("id")}


async def publish_to_facebook_text_with_background(
    access_token: str, page_id: str, message: str, meta_preset_id: str,
) -> Dict[str, Any]:
    """Facebook's native "text post with colored background"
    (text_format_preset_id on POST /{page-id}/feed) -- no third-party
    service involved. Must never be combined with a photo/video/link in
    the same call: Facebook silently drops the background style the
    moment any media is attached, so this only ever sends message +
    text_format_preset_id."""
    if not page_id:
        raise HTTPException(status_code=400, detail=_FACEBOOK_TARGET_ID_MISSING)
    if not access_token:
        raise HTTPException(status_code=401, detail=_FACEBOOK_TOKEN_EXPIRED_OR_MISSING)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed",
            data={"message": message, "text_format_preset_id": meta_preset_id, "access_token": access_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    return response.json()


async def publish_to_facebook_page(page_id: str, page_access_token: str, message: str):
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"https://graph.facebook.com/v19.0/{page_id}/feed", data={"message": message, "access_token": page_access_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    return response.json()


async def get_facebook_long_lived_token(short_lived_token: str) -> str:
    client_id = os.getenv("FACEBOOK_CLIENT_ID")
    client_secret = os.getenv("FACEBOOK_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="FACEBOOK_CLIENT_ID / FACEBOOK_CLIENT_SECRET not configured")

    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(
            "https://graph.facebook.com/v19.0/oauth/access_token",
            params={"grant_type": "fb_exchange_token", "client_id": client_id, "client_secret": client_secret, "access_token": short_lived_token},
        )
    await _raise_for_status_or_502(response, "Facebook")
    token = response.json().get("access_token")
    if not token:
        raise HTTPException(status_code=502, detail="Facebook did not return a long-lived access_token")
    return token

# --------------------------------------------------------------------------
# Instagram (Login direct -> graph.instagram.com)
# --------------------------------------------------------------------------

async def publish_to_instagram(token: str, ig_user_id: str, video_url: Optional[str], caption: str) -> Dict[str, Any]:
    if not video_url:
        raise HTTPException(status_code=400, detail="video_url is required for Instagram video publication")
    return await _publish_instagram_container(token, ig_user_id, caption, "REELS", "video_url", video_url)


async def publish_to_instagram_image(token: str, ig_user_id: str, image_url: str, caption: str) -> Dict[str, Any]:
    return await _publish_instagram_container(token, ig_user_id, caption, "IMAGE", "image_url", image_url)


async def _publish_instagram_container(
    token: str, ig_user_id: str, caption: str, media_type: str, media_field: str, media_value: str,
) -> Dict[str, Any]:
    base_url = f"https://graph.instagram.com/v19.0/{ig_user_id}"  # Instagram Login direct

    async with httpx.AsyncClient(timeout=60.0) as client:
        container_response = await client.post(
            f"{base_url}/media",
            data={media_field: media_value, "caption": caption, "media_type": media_type, "access_token": token},
        )
    await _raise_for_status_or_502(container_response, "Instagram")
    creation_id = container_response.json().get("id")
    if not creation_id:
        raise HTTPException(status_code=502, detail="Instagram did not return a creation id")

    status = await _poll_instagram_container_status(token, creation_id)
    if status != "FINISHED":
        raise HTTPException(status_code=502, detail=f"Instagram container not ready: {status}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        publish_response = await client.post(f"{base_url}/media_publish", data={"creation_id": creation_id, "access_token": token})
    await _raise_for_status_or_502(publish_response, "Instagram")
    result = publish_response.json()

    # The publish response only carries the internal media id -- the public
    # permalink (instagram.com/p/<shortcode> or /reel/<shortcode>) requires
    # a separate lookup. Best-effort: a failure here must not fail the
    # publish itself, since the post already went live.
    media_id = result.get("id")
    if media_id:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                permalink_response = await client.get(
                    f"https://graph.instagram.com/v19.0/{media_id}",
                    params={"fields": "permalink", "access_token": token},
                )
            if permalink_response.status_code == 200:
                result["permalink"] = permalink_response.json().get("permalink")
        except Exception as e:
            logger.warning("Instagram permalink lookup failed for media %s: %s", media_id, e)

    return result


async def _poll_instagram_container_status(token: str, creation_id: str, max_attempts: int = 20) -> str:
    delay = 2.0
    for _ in range(max_attempts):
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://graph.instagram.com/v19.0/{creation_id}",
                params={"fields": "status_code,status", "access_token": token},
            )
        await _raise_for_status_or_502(response, "Instagram")
        data = response.json()
        status = data.get("status_code")
        if status == "FINISHED":
            return status
        if status == "ERROR":
            logger.error("Instagram container error for %s: %s", creation_id, data.get("status"))
            return status
        await asyncio.sleep(delay)
        delay = min(delay * 1.5, 30.0)
    return "TIMEOUT"


# --------------------------------------------------------------------------
# LinkedIn (Videos API + Posts API — remplace Assets API + v2/ugcPosts)
# --------------------------------------------------------------------------

def _linkedin_headers(token: str, json_body: bool = True) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Restli-Protocol-Version": "2.0.0",
        "Linkedin-Version": LINKEDIN_API_VERSION,
    }
    if json_body:
        headers["Content-Type"] = _CONTENT_TYPE_JSON
    return headers


async def _create_linkedin_post(token: str, owner_urn: str, commentary: str, media: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "author": owner_urn,
        "commentary": commentary,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if media:
        payload["content"] = {"media": media}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post("https://api.linkedin.com/rest/posts", headers=_linkedin_headers(token), json=payload)
    await _raise_for_status_or_502(response, "LinkedIn")

    # LinkedIn renvoie l'id du post dans le header x-restli-id (pas dans le body).
    post_id = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
    return {"id": post_id}

def _cleanup_temp_file(path: str) -> None:
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            logger.warning("Could not remove temp file %s", path, exc_info=True)

async def _li_initialize_video_upload(access_token: str, owner_urn: str, file_size: int):
    """Renvoie (video_urn, upload_instructions, upload_token)."""
    init_payload = {
        "initializeUploadRequest": {
            "owner": owner_urn,
            "fileSizeBytes": file_size,
            "uploadCaptions": False,
            "uploadThumbnail": False,
        }
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        init_response = await client.post(
            "https://api.linkedin.com/rest/videos?action=initializeUpload",
            headers=_linkedin_headers(access_token),
            json=init_payload,
        )
    await _raise_for_status_or_502(init_response, "LinkedIn")

    init_data = (init_response.json() or {}).get("value") or {}
    video_urn = init_data.get("video")
    upload_instructions = init_data.get("uploadInstructions") or []
    upload_token = init_data.get("uploadToken", "")

    if not video_urn or not upload_instructions:
        raise HTTPException(status_code=502, detail="LinkedIn initializeUpload response missing video urn or upload instructions")
    return video_urn, upload_instructions, upload_token


async def _li_upload_part_with_retry(upload_url: str, chunk: bytes, first_byte: int, last_byte: int) -> str:
    """PUT d'une part avec retry ; renvoie l'ETag (sans guillemets) en cas de succès."""
    last_error: Optional[Exception] = None
    for attempt in range(LINKEDIN_MAX_RETRIES_PER_PART):
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                part_response = await client.put(
                    upload_url, headers={"Content-Type": "application/octet-stream"}, content=chunk,
                )
            part_response.raise_for_status()
            etag = (part_response.headers.get("etag") or part_response.headers.get("ETag") or "").strip('"')
            if not etag:
                raise ValueError("LinkedIn part upload response missing ETag header")
            return etag
        except (httpx.HTTPError, ValueError) as e:
            last_error = e
            logger.warning(
                "LinkedIn video part upload failed (bytes %s-%s, attempt %s/%s): %s",
                first_byte, last_byte, attempt + 1, LINKEDIN_MAX_RETRIES_PER_PART, e,
            )
            await asyncio.sleep(2 ** attempt)
    raise HTTPException(status_code=502, detail=f"LinkedIn video part upload failed after retries: {last_error}")


async def _li_upload_all_parts(temp_path: str, upload_instructions: List[Dict[str, Any]]) -> List[str]:
    uploaded_part_ids: List[str] = []
    async with aiofiles.open(temp_path, "rb") as file_handle:
        for part in upload_instructions:
            first_byte, last_byte = part["firstByte"], part["lastByte"]
            await file_handle.seek(first_byte)
            chunk = await file_handle.read(last_byte - first_byte + 1)
            etag = await _li_upload_part_with_retry(part["uploadUrl"], chunk, first_byte, last_byte)
            uploaded_part_ids.append(etag)
    return uploaded_part_ids


async def _li_finalize_upload(access_token: str, video_urn: str, upload_token: str, uploaded_part_ids: List[str]) -> None:
    finalize_payload = {
        "finalizeUploadRequest": {"video": video_urn, "uploadToken": upload_token, "uploadedPartIds": uploaded_part_ids}
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        finalize_response = await client.post(
            "https://api.linkedin.com/rest/videos?action=finalizeUpload",
            headers=_linkedin_headers(access_token),
            json=finalize_payload,
        )
    await _raise_for_status_or_502(finalize_response, "LinkedIn")


async def publish_to_linkedin_video(access_token: str, owner_urn: str, video_url: str, title: str, description: str) -> Dict[str, Any]:
    """
    Publie une vidéo sur LinkedIn via la Videos API actuelle :
    1. Téléchargement local de la vidéo (video_url) avec validation anti-SSRF.
    2. initializeUpload -> URN vidéo + plages de parts à uploader.
    3. Upload de chaque part avec retry, récupération de l'ETag.
    4. finalizeUpload avec la liste des ETags dans l'ordre des parts.
    5. Création du post via /rest/posts (Posts API) référençant l'URN vidéo.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"li_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(video_url, temp_path)

    try:
        file_size = os.path.getsize(temp_path)
        video_urn, upload_instructions, upload_token = await _li_initialize_video_upload(access_token, owner_urn, file_size)
        uploaded_part_ids = await _li_upload_all_parts(temp_path, upload_instructions)
        await _li_finalize_upload(access_token, video_urn, upload_token, uploaded_part_ids)

        post_result = await _create_linkedin_post(
            token=access_token, owner_urn=owner_urn, commentary=description, media={"title": title, "id": video_urn},
        )
        post_result["video_urn"] = video_urn
        return post_result
    finally:
        _cleanup_temp_file(temp_path)


async def _li_initialize_image_upload(access_token: str, owner_urn: str):
    """Renvoie (image_urn, upload_url) -- LinkedIn's Images API uses a
    single direct PUT rather than the video API's multi-part upload, since
    images don't need chunking."""
    init_payload = {"initializeUploadRequest": {"owner": owner_urn}}
    async with httpx.AsyncClient(timeout=30.0) as client:
        init_response = await client.post(
            "https://api.linkedin.com/rest/images?action=initializeUpload",
            headers=_linkedin_headers(access_token),
            json=init_payload,
        )
    await _raise_for_status_or_502(init_response, "LinkedIn")

    init_data = (init_response.json() or {}).get("value") or {}
    image_urn = init_data.get("image")
    upload_url = init_data.get("uploadUrl")
    if not image_urn or not upload_url:
        raise HTTPException(status_code=502, detail="LinkedIn initializeUpload response missing image urn or upload url")
    return image_urn, upload_url


async def publish_to_linkedin_image(access_token: str, owner_urn: str, image_url: str, commentary: str) -> Dict[str, Any]:
    """
    Publie une image sur LinkedIn via la Images API :
    1. Téléchargement local de l'image (image_url) avec validation anti-SSRF.
    2. initializeUpload -> URN image + URL d'upload.
    3. Upload direct du fichier (PUT, pas de decoupage en parts comme la video).
    4. Création du post via /rest/posts référençant l'URN image.
    """
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"li_publish_{uuid.uuid4().hex}.img")
    await _download_to_file(image_url, temp_path)

    try:
        image_urn, upload_url = await _li_initialize_image_upload(access_token, owner_urn)
        async with aiofiles.open(temp_path, "rb") as file_handle:
            image_bytes = await file_handle.read()
        async with httpx.AsyncClient(timeout=60.0) as client:
            upload_response = await client.put(
                upload_url, headers={"Content-Type": "application/octet-stream"}, content=image_bytes,
            )
        upload_response.raise_for_status()

        post_result = await _create_linkedin_post(
            token=access_token, owner_urn=owner_urn, commentary=commentary, media={"id": image_urn},
        )
        post_result["image_urn"] = image_urn
        return post_result
    finally:
        _cleanup_temp_file(temp_path)

# --------------------------------------------------------------------------
# Fonction principale
# --------------------------------------------------------------------------
async def _publish_media_then_text_fallback(has_media: bool, media_publisher, text_publisher, media_label: str = "video") -> Dict[str, Any]:
    """
    Tente media_publisher() si has_media est vrai ; en cas d'échec (ou s'il
    n'y a pas de média du tout), retombe sur text_publisher(). Les clés
    <media_label>_failed/<media_label>_error ne sont ajoutées que si un
    média a été tenté et a échoué. Shared by the video and photo paths
    (Facebook/LinkedIn) since both fall back to a plain-text post the same
    way on failure.
    """
    if not has_media:
        return await text_publisher()
    try:
        return await media_publisher()
    except Exception as e:
        logger.warning("%s publish failed, falling back to text: %s", media_label.capitalize(), e, exc_info=True)
        result = await text_publisher()
        result[f"{media_label}_failed"] = True
        result[f"{media_label}_error"] = str(e)
        return result


async def _publish_linkedin(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    # LinkedIn has no native colored-background text post and, per product
    # decision, must never substitute a rendered image for one for that
    # purpose either (same "stays text, no exceptions" principle as
    # Facebook's own background posts -- see _publish_facebook): an
    # anonymous story always publishes here as plain text, regardless of
    # which Facebook-only background the user picked, because it never
    # sets content.image_url. A real user-attached photo (from the "Faire
    # une publication" composer) does set it, and is genuinely posted as
    # an image below.
    _require_platform_user_id(account, "LinkedIn")
    owner_urn = f"urn:li:person:{account.get('platform_user_id')}"
    image_url = getattr(content, "image_url", None)

    async def video_publisher():
        return await publish_to_linkedin_video(
            access_token=token, owner_urn=owner_urn, video_url=content.video_url,
            title=content.title or "Vireel", description=text_value,
        )

    async def image_publisher():
        return await publish_to_linkedin_image(
            access_token=token, owner_urn=owner_urn, image_url=image_url, commentary=text_value,
        )

    async def text_publisher():
        return await _create_linkedin_post(token=token, owner_urn=owner_urn, commentary=text_value)

    if content.video_url:
        return await _publish_media_then_text_fallback(True, video_publisher, text_publisher, media_label="video")
    if image_url:
        return await _publish_media_then_text_fallback(True, image_publisher, text_publisher, media_label="image")
    return await text_publisher()


async def _publish_facebook(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    _require_platform_user_id(account, "Facebook")
    meta_preset_id = getattr(content, "facebook_text_format_preset_id", None)
    target_id = str(account.get("platform_user_id") or "")
    image_url = getattr(content, "image_url", None)

    async def video_publisher():
        return await publish_to_facebook_video(
            access_token=token, target_id=target_id,
            video_url=content.video_url, message=text_value,
            title=content.title or "Vireel", description=content.description or text_value,
        )

    async def image_publisher():
        return await publish_to_facebook_photo(
            access_token=token, target_id=target_id, image_url=image_url, message=text_value,
        )

    async def text_publisher():
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"https://graph.facebook.com/{target_id}/feed",
                data={"message": text_value, "access_token": token},
            )
        await _raise_for_status_or_502(response, "Facebook")
        return response.json()

    if not content.video_url and meta_preset_id:
        # Always native when the chosen background maps to one of Meta's
        # own text_format_preset_id values, regardless of text length --
        # confirmed against Publer (which uses this same mechanism):
        # Facebook truncates the post to ~130 chars inline with a "See
        # more" expander and keeps the colored background behind it, for
        # text of any length. Never falls back to an image: an anonymous
        # story's publication must stay text, per spec -- if Meta rejects
        # the call outright, that failure is surfaced to the user as-is.
        # (An anonymous story never sets content.image_url, so this branch
        # and the real photo-post one below never compete.)
        return await publish_to_facebook_text_with_background(
            access_token=token, page_id=target_id, message=text_value, meta_preset_id=meta_preset_id,
        )

    if content.video_url:
        return await _publish_media_then_text_fallback(True, video_publisher, text_publisher, media_label="video")
    if image_url:
        return await _publish_media_then_text_fallback(True, image_publisher, text_publisher, media_label="image")
    return await text_publisher()


async def _publish_instagram_platform(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    ig_user_id = _require_platform_user_id(account, "Instagram")
    image_url = getattr(content, "image_url", None)

    if content.video_url:
        return await publish_to_instagram(token, ig_user_id, content.video_url, text_value)
    if image_url:
        return await publish_to_instagram_image(token, ig_user_id, image_url, text_value)
    raise HTTPException(
        status_code=400,
        detail="Instagram requires either video_url or image_url (text-only posts are not supported by the platform)",
    )


async def _resolve_youtube_video_path(content) -> str:
    """Renvoie le chemin local du fichier vidéo à uploader (téléchargé si besoin)."""
    video_path = (content.video_file or "").strip()
    if video_path:
        return video_path
    if not content.video_url:
        raise HTTPException(status_code=400, detail="video_file or video_url is required for YouTube publication")

    os.makedirs(UPLOAD_DIR, exist_ok=True)
    temp_path = os.path.join(UPLOAD_DIR, f"yt_publish_{uuid.uuid4().hex}.mp4")
    await _download_to_file(content.video_url, temp_path)
    return temp_path


async def _publish_youtube_platform(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    video_path = await _resolve_youtube_video_path(content)
    downloaded = not (content.video_file or "").strip()  # temp file only if we downloaded it ourselves
    try:
        return await upload_youtube_video(token, video_path, content.title or "Vireel Short", content.description or text_value)
    finally:
        if downloaded:
            _cleanup_temp_file(video_path)


async def _publish_tiktok_platform(account: Dict[str, Any], token: str, content, text_value: str) -> Dict[str, Any]:
    image_url = getattr(content, "image_url", None)

    if content.video_url:
        return await publish_to_tiktok(token, content.video_url, text_value, content.privacy_level or "PUBLIC_TO_EVERYONE")
    if image_url:
        image_urls = image_url if isinstance(image_url, list) else [image_url]
        return await publish_to_tiktok_photo(token, image_urls, text_value)
    raise HTTPException(
        status_code=400,
        detail="TikTok requires either video_url or image_url (text-only posts are not supported by the platform)",
    )


_PLATFORM_HANDLERS = {
    "linkedin": _publish_linkedin,
    "facebook": _publish_facebook,
    "instagram": _publish_instagram_platform,
    "youtube": _publish_youtube_platform,
    "tiktok": _publish_tiktok_platform,
}


# --------------------------------------------------------------------------
# Social insights (analytics) -- Facebook / Instagram / YouTube only.
#
# LinkedIn and TikTok have no analytics scope requested (see PLATFORM_CONFIG)
# since their real analytics APIs require a separate platform partner
# approval process -- _get_social_insights_for_account reports them as
# unsupported rather than silently returning empty data.
# --------------------------------------------------------------------------

_SOCIAL_INSIGHTS_METRIC_KEYS = (
    "followers", "impressions", "reach", "engagement", "profile_views", "views",
    "follows_gained", "follows_lost",
    "watch_time_minutes", "subscribers_gained", "subscribers_lost", "likes", "comments",
)


def _empty_social_insights_metrics() -> Dict[str, Optional[int]]:
    return dict.fromkeys(_SOCIAL_INSIGHTS_METRIC_KEYS)


def _compute_metric_trend(current: int, previous: int) -> Dict[str, Any]:
    if current > previous:
        direction = "up"
    elif current < previous:
        direction = "down"
    else:
        direction = "flat"
    change_pct = round((current - previous) / previous * 100, 1) if previous else None
    return {"current": current, "previous": previous, "change_pct": change_pct, "direction": direction}


def _build_metric_trends(current_totals: Dict[str, int], previous_totals: Dict[str, int], keys: Tuple[str, ...]) -> Dict[str, Dict[str, Any]]:
    return {
        key: _compute_metric_trend(current_totals.get(key, 0), previous_totals.get(key, 0))
        for key in keys
    }


def _previous_period_bounds(since_unix: int, until_unix: int) -> Tuple[int, int]:
    period_length = until_unix - since_unix
    return since_unix - period_length, since_unix


# Meta has repeatedly retired individual Page Insights metrics (page_fans,
# page_impressions, ...) without warning, and each replacement name is a
# guess against third-party docs until proven against a live token -- so
# each metric is requested/parsed on its own, and a rejected one is logged
# by name and skipped rather than zeroing out every other metric too.
_FACEBOOK_METRIC_TO_BUCKET = {
    "page_media_view": "impressions",  # replaces the retired page_impressions
    "page_engaged_users": "engagement",
    "page_post_engagements": "engagement",
    "page_views_total": "profile_views",
    "page_video_views_unique": "views",
    "page_daily_follows": "follows_gained",  # replaces the retired page_fans/page_fan_adds
    "page_daily_unfollows": "follows_lost",  # replaces the retired page_fan_removes
}
_FACEBOOK_DAILY_METRICS = tuple(_FACEBOOK_METRIC_TO_BUCKET)
_FACEBOOK_TREND_KEYS = ("impressions", "engagement", "follows_gained", "follows_lost", "comments")


def _accumulate_facebook_daily_metric(daily_by_date: Dict[str, Dict[str, Any]], name: Optional[str], value_entry: Dict[str, Any]) -> None:
    bucket_key = _FACEBOOK_METRIC_TO_BUCKET.get(name)
    if bucket_key is None:
        return
    day = (value_entry.get("end_time") or "")[:10]
    if not day:
        return
    value = int(value_entry.get("value") or 0)
    bucket = daily_by_date.setdefault(day, {"date": day})
    bucket[bucket_key] = bucket.get(bucket_key, 0) + value


def _parse_facebook_insights_metrics(metric_entries: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    daily_by_date: Dict[str, Dict[str, Any]] = {}
    for metric_entry in metric_entries:
        name = metric_entry.get("name")
        for value_entry in (metric_entry.get("values") or []):
            _accumulate_facebook_daily_metric(daily_by_date, name, value_entry)

    totals: Dict[str, int] = {}
    for bucket in daily_by_date.values():
        for key, value in bucket.items():
            if key == "date":
                continue
            totals[key] = totals.get(key, 0) + value
    return daily_by_date, totals


def _merge_daily_buckets(daily_by_date: Dict[str, Dict[str, Any]], other_daily: Dict[str, Dict[str, Any]]) -> None:
    for day, other_bucket in other_daily.items():
        bucket = daily_by_date.setdefault(day, {"date": day})
        for key, value in other_bucket.items():
            if key == "date":
                continue
            bucket[key] = bucket.get(key, 0) + value


async def _request_facebook_insights_metrics(
    access_token: str, page_id: str, metrics: Tuple[str, ...], since_unix: int, until_unix: int,
) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://graph.facebook.com/v19.0/{page_id}/insights",
            params={
                "metric": ",".join(metrics),
                "period": "day",
                "since": since_unix,
                "until": until_unix,
                "access_token": access_token,
            },
        )
    if response.status_code in (401, 403):
        await _raise_for_status_or_502(response, "Facebook")
    response.raise_for_status()
    return response.json().get("data") or []


async def _fetch_one_facebook_metric(
    access_token: str, page_id: str, metric: str, since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    try:
        data = await _request_facebook_insights_metrics(access_token, page_id, (metric,), since_unix, until_unix)
        return _parse_facebook_insights_metrics(data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Facebook insights metric %r rejected for page %s: %s", metric, page_id, exc)
        return {}, {}


async def _fetch_facebook_metrics_individually(
    access_token: str, page_id: str, metrics: Tuple[str, ...], since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    daily_by_date: Dict[str, Dict[str, Any]] = {}
    totals: Dict[str, int] = {}
    for metric in metrics:
        metric_daily, metric_totals = await _fetch_one_facebook_metric(access_token, page_id, metric, since_unix, until_unix)
        _merge_daily_buckets(daily_by_date, metric_daily)
        for key, value in metric_totals.items():
            totals[key] = totals.get(key, 0) + value
    return daily_by_date, totals


async def _fetch_facebook_engagement_insights(
    access_token: str, page_id: str, since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    """Tries every known-useful metric in one batch call first (the common,
    cheap case); if Meta rejects any one of them, the whole batch fails, so
    this falls back to requesting each metric on its own and logs exactly
    which one(s) got rejected, rather than losing every metric to one bad
    name. An actual token/permission error (401/403) is re-raised so the
    caller can distinguish it from a partial-data failure (see
    _get_social_insights_for_account)."""
    try:
        data = await _request_facebook_insights_metrics(access_token, page_id, _FACEBOOK_DAILY_METRICS, since_unix, until_unix)
        return _parse_facebook_insights_metrics(data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "Facebook insights batch request rejected for page %s (%s); retrying metrics individually to isolate the invalid one(s)",
            page_id, exc,
        )
        return await _fetch_facebook_metrics_individually(access_token, page_id, _FACEBOOK_DAILY_METRICS, since_unix, until_unix)


async def _fetch_facebook_follower_count(access_token: str, page_id: str) -> Optional[int]:
    # A Page-node field, decoupled from Insights metric churn -- the stable
    # way to read follower count now that page_fans is retired.
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://graph.facebook.com/v19.0/{page_id}",
                params={"fields": "followers_count", "access_token": access_token},
            )
        if response.status_code in (401, 403):
            await _raise_for_status_or_502(response, "Facebook")
        response.raise_for_status()
        followers_count = response.json().get("followers_count")
        return int(followers_count) if followers_count is not None else None
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch Facebook follower count for page %s: %s", page_id, exc)
        return None


_FACEBOOK_COMMENTS_MAX_PAGES = 5


def _accumulate_facebook_post_comments(daily_by_date: Dict[str, Dict[str, Any]], post: Dict[str, Any]) -> int:
    day = str(post.get("created_time") or "")[:10]
    if not day:
        return 0
    count = int((post.get("comments") or {}).get("summary", {}).get("total_count") or 0)
    bucket = daily_by_date.setdefault(day, {"date": day})
    bucket["comments"] = bucket.get("comments", 0) + count
    return count


async def _fetch_facebook_comments_page(client: httpx.AsyncClient, url: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    response = await client.get(url, params=params)
    if response.status_code in (401, 403):
        await _raise_for_status_or_502(response, "Facebook")
    response.raise_for_status()
    return response.json()


async def _fetch_facebook_comments_daily(
    access_token: str, page_id: str, since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """Page Insights has no per-day "comments" metric -- Meta counts
    comments per post, not per Page -- so this sums each post's comment
    count, bucketed by the post's own publish day, over a bounded number of
    pages. Best-effort: returns ({}, 0) on any failure except an actual
    token/permission error, which is re-raised (see
    _get_social_insights_for_account)."""
    daily_by_date: Dict[str, Dict[str, Any]] = {}
    total_comments = 0
    url = f"https://graph.facebook.com/v19.0/{page_id}/posts"
    params: Optional[Dict[str, Any]] = {
        "fields": "created_time,comments.summary(true).limit(0)",
        "since": since_unix,
        "until": until_unix,
        "limit": 100,
        "access_token": access_token,
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for _ in range(_FACEBOOK_COMMENTS_MAX_PAGES):
                body = await _fetch_facebook_comments_page(client, url, params)
                for post in (body.get("data") or []):
                    total_comments += _accumulate_facebook_post_comments(daily_by_date, post)
                next_url = (body.get("paging") or {}).get("next")
                if not next_url:
                    break
                url, params = next_url, None
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch Facebook comments for page %s: %s", page_id, exc)
        return {}, 0
    return daily_by_date, total_comments


# Ad-breaks monetization insights are only populated for Pages actually
# enrolled in Meta's in-stream-ads program -- these metric names are
# unverified against a live account (see the module note above on Facebook
# insights metric churn), so each is requested on its own and a
# rejected/empty one just reads as "no monetization data", not an error.
_FACEBOOK_MONETIZATION_METRICS = (
    "page_daily_video_ad_break_ad_impressions",
    "page_daily_video_ad_break_ad_earnings",
    "page_daily_video_ad_break_ad_cpm",
)


async def _sum_facebook_metric_value(access_token: str, page_id: str, metric: str, since_unix: int, until_unix: int) -> Optional[int]:
    try:
        data = await _request_facebook_insights_metrics(access_token, page_id, (metric,), since_unix, until_unix)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Facebook monetization metric %r rejected for page %s: %s", metric, page_id, exc)
        return None
    return sum(int(value_entry.get("value") or 0) for entry in data for value_entry in (entry.get("values") or []))


async def _fetch_facebook_monetization(access_token: str, page_id: str, since_unix: int, until_unix: int) -> Dict[str, Any]:
    ad_impressions = await _sum_facebook_metric_value(access_token, page_id, "page_daily_video_ad_break_ad_impressions", since_unix, until_unix)
    ad_earnings_cents = await _sum_facebook_metric_value(access_token, page_id, "page_daily_video_ad_break_ad_earnings", since_unix, until_unix)
    ad_cpm_cents = await _sum_facebook_metric_value(access_token, page_id, "page_daily_video_ad_break_ad_cpm", since_unix, until_unix)

    available = bool(ad_impressions or ad_earnings_cents)
    return {
        "supported": True,
        "available": available,
        "reason": None if available else (
            "Aucune donnee de monetisation disponible (programme de monetisation video non actif "
            "ou aucune donnee sur cette periode)."
        ),
        "ad_impressions": ad_impressions if available else None,
        "ad_earnings_cents": ad_earnings_cents if available else None,
        "ad_cpm_cents": ad_cpm_cents if available else None,
    }


async def _fetch_facebook_page_insights(access_token: str, page_id: str, since_iso: str, until_iso: str) -> Dict[str, Any]:
    since_unix = int(datetime.fromisoformat(since_iso).timestamp())
    until_unix = int(datetime.fromisoformat(until_iso).timestamp())
    prev_since_unix, prev_until_unix = _previous_period_bounds(since_unix, until_unix)

    daily_by_date, totals = await _fetch_facebook_engagement_insights(access_token, page_id, since_unix, until_unix)
    _, previous_totals = await _fetch_facebook_engagement_insights(access_token, page_id, prev_since_unix, prev_until_unix)

    comments_daily, comments_total = await _fetch_facebook_comments_daily(access_token, page_id, since_unix, until_unix)
    _, previous_comments_total = await _fetch_facebook_comments_daily(access_token, page_id, prev_since_unix, prev_until_unix)
    _merge_daily_buckets(daily_by_date, comments_daily)
    totals["comments"] = comments_total
    previous_totals["comments"] = previous_comments_total

    followers = await _fetch_facebook_follower_count(access_token, page_id)
    monetization = await _fetch_facebook_monetization(access_token, page_id, since_unix, until_unix)

    metrics = _empty_social_insights_metrics()
    metrics["followers"] = followers
    for bucket_key in set(_FACEBOOK_METRIC_TO_BUCKET.values()) | {"comments"}:
        metrics[bucket_key] = totals.get(bucket_key, 0)

    trends = _build_metric_trends(totals, previous_totals, _FACEBOOK_TREND_KEYS)

    daily = [daily_by_date[day] for day in sorted(daily_by_date)]
    return {"metrics": metrics, "daily": daily, "trends": trends, "monetization": monetization}


# Instagram deprecated impressions/profile_views/website_clicks in Graph API
# v22.0 in favor of views/reach/follower_count -- same per-metric resilience
# pattern as Facebook's, since these replacement names are just as unverified
# against a live account.
_INSTAGRAM_METRIC_TO_BUCKET = {
    "views": "impressions",  # replaces the retired impressions metric
    "reach": "reach",
    "total_interactions": "engagement",  # replaces the retired website_clicks-as-engagement proxy
    "total_comments": "comments",
}
_INSTAGRAM_DAILY_METRICS = tuple(_INSTAGRAM_METRIC_TO_BUCKET)
_INSTAGRAM_TREND_KEYS = ("impressions", "engagement", "comments")


def _accumulate_instagram_daily_metric(daily_by_date: Dict[str, Dict[str, Any]], name: Optional[str], value_entry: Dict[str, Any]) -> None:
    bucket_key = _INSTAGRAM_METRIC_TO_BUCKET.get(name)
    if bucket_key is None:
        return
    day = (value_entry.get("end_time") or "")[:10]
    if not day:
        return
    value = int(value_entry.get("value") or 0)
    bucket = daily_by_date.setdefault(day, {"date": day})
    bucket[bucket_key] = bucket.get(bucket_key, 0) + value


def _parse_instagram_insights_metrics(metric_entries: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    daily_by_date: Dict[str, Dict[str, Any]] = {}
    for metric_entry in metric_entries:
        name = metric_entry.get("name")
        for value_entry in (metric_entry.get("values") or []):
            _accumulate_instagram_daily_metric(daily_by_date, name, value_entry)

    totals: Dict[str, int] = {}
    for bucket in daily_by_date.values():
        for key, value in bucket.items():
            if key == "date":
                continue
            totals[key] = totals.get(key, 0) + value
    return daily_by_date, totals


async def _request_instagram_insights_metrics(
    access_token: str, ig_user_id: str, metrics: Tuple[str, ...], since_unix: int, until_unix: int,
) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            f"https://graph.facebook.com/v19.0/{ig_user_id}/insights",
            params={
                "metric": ",".join(metrics),
                "period": "day",
                "since": since_unix,
                "until": until_unix,
                "access_token": access_token,
            },
        )
    if response.status_code in (401, 403):
        await _raise_for_status_or_502(response, "Instagram")
    response.raise_for_status()
    return response.json().get("data") or []


async def _fetch_one_instagram_metric(
    access_token: str, ig_user_id: str, metric: str, since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    try:
        data = await _request_instagram_insights_metrics(access_token, ig_user_id, (metric,), since_unix, until_unix)
        return _parse_instagram_insights_metrics(data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Instagram insights metric %r rejected for %s: %s", metric, ig_user_id, exc)
        return {}, {}


async def _fetch_instagram_metrics_individually(
    access_token: str, ig_user_id: str, metrics: Tuple[str, ...], since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    daily_by_date: Dict[str, Dict[str, Any]] = {}
    totals: Dict[str, int] = {}
    for metric in metrics:
        metric_daily, metric_totals = await _fetch_one_instagram_metric(access_token, ig_user_id, metric, since_unix, until_unix)
        _merge_daily_buckets(daily_by_date, metric_daily)
        for key, value in metric_totals.items():
            totals[key] = totals.get(key, 0) + value
    return daily_by_date, totals


async def _fetch_instagram_reach_insights(
    access_token: str, ig_user_id: str, since_unix: int, until_unix: int,
) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, int]]:
    """Tries every known-useful metric in one batch call first; if Meta
    rejects any one of them, falls back to requesting each metric on its
    own and logs exactly which one(s) got rejected (see the equivalent
    Facebook fetcher for why). An actual token/permission error (401/403)
    is re-raised so the caller can distinguish it from a partial-data
    failure (see _get_social_insights_for_account)."""
    try:
        data = await _request_instagram_insights_metrics(access_token, ig_user_id, _INSTAGRAM_DAILY_METRICS, since_unix, until_unix)
        return _parse_instagram_insights_metrics(data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning(
            "Instagram insights batch request rejected for %s (%s); retrying metrics individually to isolate the invalid one(s)",
            ig_user_id, exc,
        )
        return await _fetch_instagram_metrics_individually(access_token, ig_user_id, _INSTAGRAM_DAILY_METRICS, since_unix, until_unix)


async def _fetch_instagram_followers_count(access_token: str, ig_user_id: str) -> Optional[int]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"https://graph.facebook.com/v19.0/{ig_user_id}",
                params={"fields": "followers_count,media_count", "access_token": access_token},
            )
        if response.status_code in (401, 403):
            await _raise_for_status_or_502(response, "Instagram")
        response.raise_for_status()
        followers_count = response.json().get("followers_count")
        return int(followers_count) if followers_count is not None else None
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Failed to fetch Instagram profile for %s: %s", ig_user_id, exc)
        return None


_INSTAGRAM_MONETIZATION_UNSUPPORTED = (
    "Instagram ne propose pas d'API de monetisation publique pour les comptes "
    "createurs/business (Reels Play Bonus, Badges, etc. ne sont pas exposes via l'API Graph)."
)


async def _fetch_instagram_insights(access_token: str, ig_user_id: str, since_iso: str, until_iso: str) -> Dict[str, Any]:
    since_unix = int(datetime.fromisoformat(since_iso).timestamp())
    until_unix = int(datetime.fromisoformat(until_iso).timestamp())
    prev_since_unix, prev_until_unix = _previous_period_bounds(since_unix, until_unix)

    daily_by_date, totals = await _fetch_instagram_reach_insights(access_token, ig_user_id, since_unix, until_unix)
    _, previous_totals = await _fetch_instagram_reach_insights(access_token, ig_user_id, prev_since_unix, prev_until_unix)

    metrics = _empty_social_insights_metrics()
    for bucket_key in set(_INSTAGRAM_METRIC_TO_BUCKET.values()):
        metrics[bucket_key] = totals.get(bucket_key, 0)
    metrics["followers"] = await _fetch_instagram_followers_count(access_token, ig_user_id)

    trends = _build_metric_trends(totals, previous_totals, _INSTAGRAM_TREND_KEYS)
    monetization = {
        "supported": False,
        "available": False,
        "reason": _INSTAGRAM_MONETIZATION_UNSUPPORTED,
        "ad_impressions": None,
        "ad_earnings_cents": None,
        "ad_cpm_cents": None,
    }

    daily = [daily_by_date[day] for day in sorted(daily_by_date)]
    return {"metrics": metrics, "daily": daily, "trends": trends, "monetization": monetization}


_YOUTUBE_COLUMN_TO_METRIC_KEY = {
    "views": "views",
    "estimatedMinutesWatched": "watch_time_minutes",
    "subscribersGained": "subscribers_gained",
    "subscribersLost": "subscribers_lost",
    "likes": "likes",
    "comments": "comments",
}


def _parse_youtube_analytics_report(body: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    headers = [header.get("name") for header in (body.get("columnHeaders") or [])]
    column_index = {name: idx for idx, name in enumerate(headers)}

    daily: List[Dict[str, Any]] = []
    totals = dict.fromkeys(_YOUTUBE_COLUMN_TO_METRIC_KEY.values(), 0)

    for row in (body.get("rows") or []):
        day_idx = column_index.get("day")
        entry: Dict[str, Any] = {"date": row[day_idx] if day_idx is not None else None}
        for column_name, metric_key in _YOUTUBE_COLUMN_TO_METRIC_KEY.items():
            idx = column_index.get(column_name)
            if idx is None:
                continue
            value = int(row[idx] or 0)
            entry[metric_key] = value
            totals[metric_key] += value
        daily.append(entry)

    return daily, totals


async def _fetch_youtube_subscriber_count(access_token: str) -> Optional[int]:
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "statistics", "mine": "true", "access_token": access_token},
            )
        response.raise_for_status()
        items = response.json().get("items") or []
        if not items:
            return None
        subscriber_count = items[0].get("statistics", {}).get("subscriberCount")
        return int(subscriber_count) if subscriber_count is not None else None
    except Exception as exc:
        logger.warning("Failed to fetch YouTube subscriber count: %s", exc)
        return None


_YOUTUBE_MONETIZATION_METRICS = ("estimatedAdRevenue", "adImpressions", "cpm")
_YOUTUBE_MONETIZATION_UNAVAILABLE_REASON = (
    "Aucune donnee de monetisation disponible (chaine non inscrite au programme "
    "Partenaire YouTube, scope de monetisation non accorde -- reconnectez la chaine -- "
    "ou aucune donnee sur cette periode)."
)


async def _fetch_youtube_monetization(access_token: str, since_date: str, until_date: str) -> Dict[str, Any]:
    """Revenue metrics need the separate yt-analytics-monetary.readonly
    scope (accounts connected before it was added must reconnect) and
    channel membership in the YouTube Partner Program. Google returns a
    plain 403 for a missing scope, same as for a non-monetized channel --
    unlike the main analytics call, this must never raise: it's an add-on
    to already-working views/subscribers data, not a hard requirement."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://youtubeanalytics.googleapis.com/v2/reports",
                params={
                    "ids": "channel==MINE",
                    "startDate": since_date[:10],
                    "endDate": until_date[:10],
                    "metrics": ",".join(_YOUTUBE_MONETIZATION_METRICS),
                    "access_token": access_token,
                },
            )
        response.raise_for_status()
        rows = response.json().get("rows") or []
    except Exception as exc:
        logger.warning("Failed to fetch YouTube monetization: %s", exc)
        rows = []

    if not rows:
        return {
            "supported": True,
            "available": False,
            "reason": _YOUTUBE_MONETIZATION_UNAVAILABLE_REASON,
            "ad_impressions": None,
            "ad_earnings_cents": None,
            "ad_cpm_cents": None,
        }

    ad_earnings, ad_impressions, cpm = rows[0][:3]
    return {
        "supported": True,
        "available": True,
        "reason": None,
        "ad_impressions": int(ad_impressions or 0),
        "ad_earnings_cents": round(float(ad_earnings or 0) * 100),
        "ad_cpm_cents": round(float(cpm or 0) * 100),
    }


async def _fetch_youtube_analytics(access_token: str, since_date: str, until_date: str) -> Dict[str, Any]:
    since_date = since_date[:10]
    until_date = until_date[:10]

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            "https://youtubeanalytics.googleapis.com/v2/reports",
            params={
                "ids": "channel==MINE",
                "startDate": since_date,
                "endDate": until_date,
                "metrics": "views,estimatedMinutesWatched,subscribersGained,subscribersLost,likes,comments",
                "dimensions": "day",
                "sort": "day",
                "access_token": access_token,
            },
        )
    await _raise_for_status_or_502(response, "YouTube")

    daily, totals = _parse_youtube_analytics_report(response.json())

    metrics = _empty_social_insights_metrics()
    metrics.update(totals)
    metrics["followers"] = await _fetch_youtube_subscriber_count(access_token)
    monetization = await _fetch_youtube_monetization(access_token, since_date, until_date)

    return {"metrics": metrics, "daily": daily, "monetization": monetization}


async def _get_social_insights_for_account(account: Dict[str, Any], since_iso: str, until_iso: str) -> Dict[str, Any]:
    platform = str(account.get("platform") or "")
    if platform not in {"facebook", "instagram", "youtube"}:
        return {
            "supported": False,
            "reason": f"{platform.capitalize()} analytics require special platform partner access not yet available.",
            "metrics": None,
            "daily": [],
        }

    try:
        token = await get_valid_token(account)
        if platform == "facebook":
            target_id = str(account.get("platform_user_id") or "")
            result = await _fetch_facebook_page_insights(token, target_id, since_iso, until_iso)
        elif platform == "instagram":
            target_id = str(account.get("platform_user_id") or "")
            result = await _fetch_instagram_insights(token, target_id, since_iso, until_iso)
        else:  # youtube
            result = await _fetch_youtube_analytics(token, since_iso, until_iso)
        return {"supported": True, "error": None, **result}
    except Exception as exc:
        logger.warning("Failed to fetch %s insights for account %s: %s", platform, account.get("id"), exc)
        return {"supported": True, "error": str(exc), "metrics": None, "daily": []}


@app.get("/api/social/insights", responses={400: {"description": "Bad Request"}, 401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}, 404: {"description": "Not Found"}, 503: {"description": "Service Unavailable"}})
async def get_social_insights(
    account_id: Annotated[str, Query()],
    user_id: Annotated[str, Depends(get_user_id_header)],
    range: Annotated[str, Query()] = "30d",
):
    await _assert_user_can_access_analytics(user_id)
    if range not in {"7d", "30d", "90d"}:
        raise HTTPException(status_code=400, detail="range must be one of: 7d, 30d, 90d")
    account = await _get_social_account_by_id(user_id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Social account not found")

    days = {"7d": 7, "30d": 30, "90d": 90}[range]
    until = _utcnow()
    since = until - timedelta(days=days)
    result = await _get_social_insights_for_account(account, since.isoformat(), until.isoformat())

    return {
        "account_id": account_id,
        "platform": account.get("platform"),
        "platform_account_name": account.get("platform_account_name"),
        "range": range,
        **result,
    }


def _build_social_post_url(platform: str, platform_result: Dict[str, Any]) -> Optional[str]:
    """Best-effort real permalink for a post that was just published.

    Each platform's publish API returns a different kind of identifier (an
    internal video id, a share URN, a media container id, ...) -- none of
    which are the same thing as "https://<platform>.com/<id>", despite
    that being what the frontend used to assume (producing a 404 for the
    viewer even though the post genuinely published). Returns None when no
    reliable permalink can be derived, which the frontend treats as "no
    link available" rather than guessing wrong.
    """
    platform = (platform or "").lower()
    if platform == "youtube":
        # publish_to_youtube already returns the correct watch URL.
        url = platform_result.get("url")
        return str(url) if url else None
    if platform == "facebook":
        post_id = platform_result.get("id")
        if not post_id:
            return None
        # A feed/text post id already comes back as "<page_id>_<post_id>",
        # which facebook.com/<id> resolves directly. A video post id is a
        # bare numeric video id and needs the /watch path instead.
        if "_" in str(post_id):
            return f"https://www.facebook.com/{post_id}"
        return f"https://www.facebook.com/watch/?v={post_id}"
    if platform == "instagram":
        permalink = platform_result.get("permalink")
        return str(permalink) if permalink else None
    if platform == "linkedin":
        post_id = platform_result.get("id")
        return f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else None
    # TikTok's publish/status APIs don't reliably return a public video id
    # or the account's @handle (only its display name), so there's no safe
    # way to build a real tiktok.com/@handle/video/<id> link here.
    return None


async def publish_post(account: Dict[str, Any], content) -> Dict[str, Any]:
    token = await get_valid_token(account)
    platform = str(account.get("platform") or "").lower()
    text_value = content.text or content.caption or content.description or "Posted from Vireel"

    handler = _PLATFORM_HANDLERS.get(platform)
    if handler is None:
        raise HTTPException(status_code=404, detail=_UNSUPPORTED_PLATFORM)
    return await handler(account, token, content, text_value)


