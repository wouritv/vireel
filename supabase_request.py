import os
import secrets
import string
from datetime import datetime, timedelta, timezone
import calendar
import math
from typing import Any, Dict, List, Optional, Tuple

from supabase import acreate_client, AsyncClient
from supabase.lib.client_options import AsyncClientOptions
from postgrest.exceptions import APIError

import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
SUPABASE_REELS_TABLE = os.environ.get("SUPABASE_REELS_TABLE", "reels")
SUPABASE_CAPTIONS_TABLE = os.environ.get("SUPABASE_CAPTIONS_TABLE", "captions")
SUPABASE_PROJECTS_TABLE = os.environ.get("SUPABASE_PROJECTS_TABLE", "projects")
SUPABASE_ABONNEMENTS_TABLE = os.environ.get("SUPABASE_ABONNEMENTS_TABLE", "abonnement")
SUPABASE_SOUSCRIPTION_TABLE = os.environ.get("SUPABASE_SOUSCRIPTION_TABLE", "souscription")
SUPABASE_JOBS_TABLE = os.environ.get("SUPABASE_JOBS_TABLE", "jobs")
SUPABASE_JOB_LOGS_TABLE = os.environ.get("SUPABASE_JOB_LOGS_TABLE", "job_logs")
SUPABASE_USER_DATA_TABLE = os.environ.get("SUPABASE_USER_DATA_TABLE", "user_data")
SUPABASE_USER_DATA_HISTORY_TABLE = os.environ.get("SUPABASE_USER_DATA_HISTORY_TABLE", "user_data_history")
SUPABASE_USER_CREDIT_BANK_TABLE = os.environ.get("SUPABASE_USER_CREDIT_BANK_TABLE", "user_credit_bank")
SUPABASE_TRANSCRIPTIONS_TABLE = os.environ.get("SUPABASE_TRANSCRIPTIONS_TABLE", "transcriptions")
SUPABASE_STYLE_EDIT_VERSIONS_TABLE = os.environ.get("SUPABASE_STYLE_EDIT_VERSIONS_TABLE", "style_edit_versions")
SUPABASE_ANONYMOUS_STORIES_TABLE = os.environ.get("SUPABASE_ANONYMOUS_STORIES_TABLE", "anonymous_stories")
SUPABASE_FILM_SUMMARIES_TABLE = os.environ.get("SUPABASE_FILM_SUMMARIES_TABLE", "film_summaries")
SUPABASE_CAPTION_STYLE_THEMES_TABLE = os.environ.get("SUPABASE_CAPTION_STYLE_THEMES_TABLE", "caption_style_themes")
SUPABASE_REFERRAL_CODES_TABLE = os.environ.get("SUPABASE_REFERRAL_CODES_TABLE", "referral_codes")
SUPABASE_REFERRALS_TABLE = os.environ.get("SUPABASE_REFERRALS_TABLE", "referrals")
SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE = os.environ.get("SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE", "promotional_credit_batches")
SUPABASE_NOTIFICATIONS_TABLE = os.environ.get("SUPABASE_NOTIFICATIONS_TABLE", "notifications")
SUPABASE_MEDIA_ASSETS_TABLE = os.environ.get("SUPABASE_MEDIA_ASSETS_TABLE", "media_assets")


class SupabaseNotConfiguredError(RuntimeError):
	pass


def is_supabase_configured() -> bool:
	return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _build_ilike_or_filter(query: str, columns: List[str]) -> str:
	"""Build a safe PostgREST `or=(...)` filter string for a free-text search.

	Security: `query` is untrusted user input. PostgREST's `or` filter syntax
	treats `,`, `(` and `)` as structural separators, so embedding a raw
	search term directly (as `column.ilike.*<term>*`) let an attacker append
	extra filter clauses (e.g. `foo,other_column.eq.secret`) or break out of
	the grouping (audit finding P2-7). Per PostgREST's own escaping rules,
	wrapping the value in double quotes makes those characters literal; only
	backslashes and double quotes inside the value then need escaping.
	"""
	stripped = query.replace("*", "")
	escaped = stripped.replace("\\", "\\\\").replace('"', '\\"')
	return ",".join(f'{column}.ilike."*{escaped}*"' for column in columns)


# --------------------------------------------------------------------------
# Client singleton (à réutiliser plutôt que d'en recréer un à chaque appel)
# --------------------------------------------------------------------------
_client: Optional[AsyncClient] = None


def _ceil_credit(value: float) -> int:
	return int(max(0, math.ceil(float(value or 0.0))))


async def get_client() -> AsyncClient:
	"""Retourne un client Supabase async partagé (créé une seule fois)."""
	global _client

	if not is_supabase_configured():
		raise SupabaseNotConfiguredError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

	if _client is None:
		_client = await acreate_client(
			SUPABASE_URL,
			SUPABASE_SERVICE_ROLE_KEY,
			options=AsyncClientOptions(postgrest_client_timeout=20),
		)
	return _client


# --------------------------------------------------------------------------
# Reels
# --------------------------------------------------------------------------
async def insert_reels(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	if not rows:
		return []

	client = await get_client()
	response = await client.table(SUPABASE_REELS_TABLE).insert(rows).execute()
	return response.data


async def list_reels(
	user_id: str,
	page: int,
	page_size: int,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_REELS_TABLE)
		.select("*", count="exact")
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
		.order("reel_created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if status:
		q = q.eq("reel_status", status)

	if query:
		q = q.or_(_build_ilike_or_filter(query, ["reel_title", "reel_description"]))

	response = await q.execute()
	return response.data, response.count or 0


async def list_reel_dates_since(user_id: str, since_iso: Optional[str]) -> List[str]:
	client = await get_client()
	q = (
		client.table(SUPABASE_REELS_TABLE)
		.select("reel_created_at")
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
	)
	if since_iso:
		q = q.gte("reel_created_at", since_iso)
	response = await q.execute()
	return [row["reel_created_at"] for row in (response.data or []) if row.get("reel_created_at")]


async def get_reel(reel_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("id", reel_id)
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


async def get_reel_by_job_clip(
	job_id: str,
	clip_index: int,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Look up a reel by (job_id, clip_index). Pass ``user_id`` whenever the
	caller has an authenticated identity available -- it adds a second,
	defense-in-depth ownership filter so this lookup can never return
	another user's reel even if an upstream authorization check were ever
	missing or buggy."""
	client = await get_client()
	q = (
		client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("reel_job_id", job_id)
		.eq("reel_clip_index", clip_index)
		.is_("deleted_at", "null")
	)
	if user_id:
		q = q.eq("reel_user_id", user_id)
	response = (
		await q
		.order("reel_updated_at", desc=True)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


async def update_reel_media_by_job_clip(
	job_id: str,
	clip_index: int,
	reel_url: str,
	reel_s3_key: Optional[str] = None,
	reel_thumbnail_url: Optional[str] = None,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update a reel's media URL by (job_id, clip_index). Pass ``user_id``
	whenever available for a defense-in-depth ownership filter (see
	get_reel_by_job_clip)."""
	if not job_id or clip_index is None or not reel_url:
		return None

	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload: Dict[str, Any] = {
		"reel_url": reel_url,
		"reel_updated_at": now_iso,
	}
	if reel_s3_key:
		payload["reel_s3_key"] = reel_s3_key
	if reel_thumbnail_url is not None:
		payload["reel_thumbnail_url"] = reel_thumbnail_url

	q = (
		client.table(SUPABASE_REELS_TABLE)
		.update(payload)
		.eq("reel_job_id", job_id)
		.eq("reel_clip_index", int(clip_index))
		.is_("deleted_at", "null")
	)
	if user_id:
		q = q.eq("reel_user_id", user_id)
	response = await q.execute()
	rows = response.data or []
	if not rows:
		return None
	return rows[0]


async def update_reel_base_media_by_job_clip(
	job_id: str,
	clip_index: int,
	reel_base_url: str,
	reel_base_s3_key: Optional[str] = None,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Persist a reel baseline media reference by (job_id, clip_index)."""
	if not job_id or clip_index is None or not reel_base_url:
		return None

	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload: Dict[str, Any] = {
		"reel_base_url": reel_base_url,
		"reel_base_s3_key": reel_base_s3_key,
		"reel_updated_at": now_iso,
	}

	q = (
		client.table(SUPABASE_REELS_TABLE)
		.update(payload)
		.eq("reel_job_id", job_id)
		.eq("reel_clip_index", int(clip_index))
		.is_("deleted_at", "null")
	)
	if user_id:
		q = q.eq("reel_user_id", user_id)
	response = await q.execute()
	rows = response.data or []
	if not rows:
		return None
	return rows[0]


async def soft_delete_reel(reel_id: str, user_id: str) -> bool:
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()

	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.update({"deleted_at": now_iso, "reel_updated_at": now_iso})
		.eq("id", reel_id)
		.eq("reel_user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)

	return bool(response.data)


# --------------------------------------------------------------------------
# Reel visuals (manual image split-screen overlays -- see
# supabase/migrations/20261008_create_reel_visuals.sql)
# --------------------------------------------------------------------------
SUPABASE_REEL_VISUALS_TABLE = os.environ.get("SUPABASE_REEL_VISUALS_TABLE", "reel_visuals")


async def insert_reel_visual(
	reel_id: str,
	user_id: str,
	position: str,
	start_time: float,
	duration: float,
	image_s3_key: str,
) -> Dict[str, Any]:
	client = await get_client()
	payload = {
		"reel_id": reel_id,
		"user_id": user_id,
		"position": position,
		"start_time": float(start_time),
		"duration": float(duration),
		"image_s3_key": image_s3_key,
	}
	response = await client.table(SUPABASE_REEL_VISUALS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def list_reel_visuals(reel_id: str) -> List[Dict[str, Any]]:
	if not reel_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_REEL_VISUALS_TABLE)
		.select("*")
		.eq("reel_id", reel_id)
		.order("start_time", desc=False)
		.execute()
	)
	return response.data or []


async def get_reel_visual(visual_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	if not visual_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_REEL_VISUALS_TABLE)
		.select("*")
		.eq("id", visual_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_reel_visual(visual_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not visual_id or not updates:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_REEL_VISUALS_TABLE)
		.update(dict(updates))
		.eq("id", visual_id)
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def delete_reel_visual(visual_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	"""Deletes the row and returns it (so the caller can clean up its
	S3 image) -- or None if it didn't exist / wasn't owned by user_id."""
	if not visual_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_REEL_VISUALS_TABLE)
		.delete()
		.eq("id", visual_id)
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


# --------------------------------------------------------------------------
# Projects
# --------------------------------------------------------------------------
async def create_project(
	user_id: str,
	name: str,
	project_type: str,
	source_type: str,
	source_s3_key: str,
	source_size: int,
	description: Optional[str] = None,
	source_url: Optional[str] = None,
	source_duration: Optional[int] = None,
	thumbnail_url: Optional[str] = None,
	status: str = "processing",
) -> Dict[str, Any]:
	"""Create a new project."""
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload = {
		"user_id": user_id,
		"name": name,
		"project_type": project_type,
		"source_type": source_type,
		"source_s3_key": source_s3_key,
		"source_size": int(source_size),
		"description": description,
		"source_url": source_url,
		"source_duration": source_duration,
		"thumbnail_url": thumbnail_url,
		"output_count": 0,
		"status": status,
		"created_at": now_iso,
		"updated_at": now_iso,
	}
	response = await client.table(SUPABASE_PROJECTS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def list_projects(
	user_id: str,
	page: int = 1,
	page_size: int = 20,
	project_type: Optional[str] = None,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	"""List projects for a user with optional filtering."""
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_PROJECTS_TABLE)
		.select("*", count="exact")
		.eq("user_id", user_id)
		.order("created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if project_type:
		q = q.eq("project_type", project_type)

	if status:
		q = q.eq("status", status)

	if query:
		q = q.or_(_build_ilike_or_filter(query, ["name", "description"]))

	response = await q.execute()
	return response.data or [], response.count or 0


async def get_project(project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	"""Get a project by ID (user must own it)."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.select("*")
		.eq("id", project_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_project(
	project_id: str,
	user_id: str,
	updates: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
	"""Update a project (user must own it)."""
	if not project_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	await (
		client.table(SUPABASE_PROJECTS_TABLE)
		.update(payload)
		.eq("id", project_id)
		.eq("user_id", user_id)
		.execute()
	)
	response = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.select("*")
		.eq("id", project_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_project_status(
	project_id: str,
	status: str,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update project status (completed, failed, or cancelled) and set completed_at if applicable.
	Pass ``user_id`` whenever available for a defense-in-depth ownership filter."""
	if not project_id or status not in ("completed", "failed", "cancelled"):
		return None
	client = await get_client()

	payload = {
		"status": status,
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}

	# Set completed_at when transitioning from processing to terminal state
	if status in ("completed", "failed", "cancelled"):
		payload["completed_at"] = datetime.now(timezone.utc).isoformat()

	q = (
		client.table(SUPABASE_PROJECTS_TABLE)
		.update(payload)
		.eq("id", project_id)
	)
	if user_id:
		q = q.eq("user_id", user_id)
	response = await q.execute()
	rows = response.data or []
	return rows[0] if rows else None


async def soft_delete_project(project_id: str, user_id: str) -> bool:
	"""Hard delete a project and all its contents (reels, captions, files on S3)."""
	client = await get_client()

	# Security: verify ownership BEFORE cascading any deletes. The reels/
	# captions deletes below filter only by project_id (they have no
	# user_id column of their own to check against project ownership), so
	# if we deleted them first and only verified ownership on the final
	# project delete, a caller supplying another user's project_id could
	# have that user's reels/captions deleted even though the project row
	# itself would survive (0 rows affected on the ownership-filtered
	# delete). Verifying first makes the whole operation a no-op for a
	# project the caller doesn't own.
	owned = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.select("id")
		.eq("id", project_id)
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	if not owned.data:
		return False

	# Delete all reels associated with this project
	await (
		client.table(SUPABASE_REELS_TABLE)
		.delete()
		.eq("project_id", project_id)
		.execute()
	)

	# Delete all captions associated with this project
	await (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.delete()
		.eq("project_id", project_id)
		.execute()
	)

	# Delete all anonymous stories associated with this project
	await (
		client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.delete()
		.eq("project_id", project_id)
		.execute()
	)

	# Delete the project itself
	response = (
		await client.table(SUPABASE_PROJECTS_TABLE)
		.delete()
		.eq("id", project_id)
		.eq("user_id", user_id)
		.execute()
	)

	return bool(response.data)


async def get_reels_by_project(project_id: str) -> List[Dict[str, Any]]:
	"""Get all reels associated with a project."""
	if not project_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_REELS_TABLE)
		.select("*")
		.eq("project_id", project_id)
		.execute()
	)
	return response.data or []


async def get_captions_by_project(project_id: str) -> List[Dict[str, Any]]:
	"""Get all captions associated with a project."""
	if not project_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select("*")
		.eq("project_id", project_id)
		.execute()
	)
	return response.data or []


async def get_anonymous_stories_by_project(project_id: str) -> List[Dict[str, Any]]:
	"""Get all anonymous stories associated with a project."""
	if not project_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.select("*")
		.eq("project_id", project_id)
		.execute()
	)
	return response.data or []


async def get_film_summaries_by_project(project_id: str) -> List[Dict[str, Any]]:
	"""Get all film summaries associated with a project."""
	if not project_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_FILM_SUMMARIES_TABLE)
		.select("*")
		.eq("project_id", project_id)
		.execute()
	)
	return response.data or []


# --------------------------------------------------------------------------
# IA Captions
# --------------------------------------------------------------------------
CAPTION_COLUMNS = (
	"id, caption_url, caption_thumbnail_url, caption_title, caption_description, "
	"caption_duration, caption_created_at, caption_updated_at, caption_user_id, "
	"caption_status, caption_job_id, caption_clip_index, caption_s3_key, generation_inputs, "
	"input_source_type, input_source_value, billing_details, total_cost_usd, deleted_at, project_id"
)


def caption_status_value(status: Optional[str]) -> str:
	if status in {"en_cours", "termine", "echec"}:
		return status
	return "termine"


async def increment_project_output_count(
	project_id: str,
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Increment the output_count of a project. Pass ``user_id`` whenever
	available for a defense-in-depth ownership filter."""
	if not project_id:
		return None
	client = await get_client()
	q = client.table(SUPABASE_PROJECTS_TABLE).select("*").eq("id", project_id)
	if user_id:
		q = q.eq("user_id", user_id)
	response = await q.limit(1).execute()
	rows = response.data or []
	current = rows[0] if rows else None
	if not current:
		return None
	new_count = (current.get("output_count") or 0) + 1
	update_q = (
		client.table(SUPABASE_PROJECTS_TABLE)
		.update({"output_count": new_count})
		.eq("id", project_id)
	)
	if user_id:
		update_q = update_q.eq("user_id", user_id)
	response = await update_q.execute()
	rows = response.data or []
	return rows[0] if rows else None


async def insert_captions(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
	if not rows:
		return []
	client = await get_client()
	response = await client.table(SUPABASE_CAPTIONS_TABLE).insert(rows).execute()
	return response.data or []


async def list_captions(
	user_id: str,
	page: int,
	page_size: int,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS, count="exact")
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.order("caption_created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if status:
		q = q.eq("caption_status", status)

	if query:
		q = q.or_(_build_ilike_or_filter(query, ["caption_title", "caption_description"]))

	response = await q.execute()
	return response.data or [], response.count or 0


async def list_caption_dates_since(user_id: str, since_iso: Optional[str]) -> List[str]:
	client = await get_client()
	q = (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.select("caption_created_at")
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
	)
	if since_iso:
		q = q.gte("caption_created_at", since_iso)
	response = await q.execute()
	return [row["caption_created_at"] for row in (response.data or []) if row.get("caption_created_at")]


async def get_caption(caption_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)
	rows = response.data or []
	if not rows:
		return None
	return rows[0]


async def get_caption_by_job_clip(job_id: str, clip_index: int, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("caption_job_id", job_id)
		.eq("caption_clip_index", int(clip_index))
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.order("caption_updated_at", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	if not rows:
		return None
	return rows[0]


async def get_caption_by_job_clip_any(job_id: str, clip_index: int) -> Optional[Dict[str, Any]]:
	"""Internal helper: fetch latest caption row by job/clip regardless of owner."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("caption_job_id", job_id)
		.eq("caption_clip_index", int(clip_index))
		.is_("deleted_at", "null")
		.order("caption_updated_at", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_caption(caption_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not caption_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["caption_updated_at"] = datetime.now(timezone.utc).isoformat()
	await (
		client.table(SUPABASE_CAPTIONS_TABLE)
		.update(payload)
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.select(CAPTION_COLUMNS)
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def soft_delete_caption(caption_id: str, user_id: str) -> bool:
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_CAPTIONS_TABLE)
		.update({"deleted_at": now_iso, "caption_updated_at": now_iso})
		.eq("id", caption_id)
		.eq("caption_user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	return bool(response.data)


# --------------------------------------------------------------------------
# Transcriptions cache (transcript + translation cache)
# --------------------------------------------------------------------------
async def get_transcription_by_job_clip(job_id: str, clip_index: int, user_id: str) -> Optional[Dict[str, Any]]:
	if not job_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_TRANSCRIPTIONS_TABLE)
		.select("*")
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.order("updated_at", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def upsert_transcription(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	client = await get_client()
	response = await client.table(SUPABASE_TRANSCRIPTIONS_TABLE).upsert(
		row,
		on_conflict="user_id,job_id,clip_index",
	).execute()
	rows = response.data or []
	return rows[0] if rows else row


async def update_transcription_translations_cache(
	job_id: str,
	clip_index: int,
	user_id: str,
	translations_cache: Dict[str, Any],
	billing_details: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
	if not job_id or not user_id:
		return None
	client = await get_client()
	payload: Dict[str, Any] = {
		"translations_cache": translations_cache or {},
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	if billing_details is not None:
		payload["billing_details"] = billing_details
	await (
		client.table(SUPABASE_TRANSCRIPTIONS_TABLE)
		.update(payload)
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.execute()
	)
	return await get_transcription_by_job_clip(job_id, clip_index, user_id)


# --------------------------------------------------------------------------
# Style edit versions
# --------------------------------------------------------------------------
async def insert_style_edit_version(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	client = await get_client()
	response = await client.table(SUPABASE_STYLE_EDIT_VERSIONS_TABLE).insert(row).execute()
	rows = response.data or []
	return rows[0] if rows else row


async def list_style_edit_versions(job_id: str, clip_index: int, user_id: str) -> List[Dict[str, Any]]:
	if not job_id or not user_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_STYLE_EDIT_VERSIONS_TABLE)
		.select("*")
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.order("version_number", desc=False)
		.execute()
	)
	return response.data or []


async def delete_style_edit_versions(job_id: str, clip_index: int, user_id: str) -> int:
	if not job_id or not user_id:
		return 0
	client = await get_client()
	response = (
		await client.table(SUPABASE_STYLE_EDIT_VERSIONS_TABLE)
		.delete()
		.eq("job_id", job_id)
		.eq("clip_index", int(clip_index))
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	return len(rows)


# --------------------------------------------------------------------------
# Abonnements
# --------------------------------------------------------------------------
ABONNEMENT_COLUMNS = "*"
SOUSCRIPTION_COLUMNS = (
	"id, created_at, userid, abonnement, payment_mode, payment_amount, payment_reference, "
	"payment_start_date, payment_end_date, payment_status, payment_comment, "
	"auto_renew, canceled_at, reactivated_at, paused_at, resumed_at, "
	"retention_deadline_at, account_disabled_at, stripe_subscription_id, stripe_customer_id, "
	"billing_interval, plan_credit, plan_stockage, next_credit_allocation_at, "
	"credit_cycle_start_at, credit_cycle_end_at, scheduled_abonnement_id, "
	"scheduled_billing_interval, scheduled_effective_at, scheduled_created_at, "
	"stripe_schedule_id"
)

async def list_abonnements() -> List[Dict[str, Any]]:
	"""Récupère tous les abonnements disponibles, dans leur ordre
	d'affichage explicite (colonne "ordre", croissant) plutôt que par
	created_at, qui ne correspondait a rien de voulu pour l'affichage.
	Renvoie aussi les lignes sans ordre (ex. un plan retire de la vente) --
	c'est a l'appelant public-facing (app.py's list_abonnements endpoint)
	de les filtrer, puisque cette fonction est aussi utilisee pour
	resoudre le nom d'un plan dans l'historique d'un abonnement existant."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_ABONNEMENTS_TABLE)
		.select(ABONNEMENT_COLUMNS)
		.order("ordre", desc=False)
		.execute()
	)
	return response.data


async def get_abonnement(abonnement_uuid: str) -> Optional[Dict[str, Any]]:
	"""Récupère un abonnement précis par son uuid."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_ABONNEMENTS_TABLE)
		.select(ABONNEMENT_COLUMNS)
		.eq("id", abonnement_uuid)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]


def add_one_month(dt: datetime) -> datetime:
	"""Add one calendar month while keeping day within target month bounds."""
	year = dt.year + (1 if dt.month == 12 else 0)
	month = 1 if dt.month == 12 else dt.month + 1
	day = min(dt.day, calendar.monthrange(year, month)[1])
	return dt.replace(year=year, month=month, day=day)


def add_one_year(dt: datetime) -> datetime:
	"""Add one calendar year while keeping day within target month bounds
	(handles Feb 29 on a leap-year start date)."""
	year = dt.year + 1
	day = min(dt.day, calendar.monthrange(year, dt.month)[1])
	return dt.replace(year=year, day=day)


async def insert_souscription(
	user_id: str,
	abonnement: Optional[str],
	payment_mode: str,
	payment_amount: float,
	payment_reference: str,
	payment_status: str = "confirmed",
	payment_comment: str = "",
	payment_date: Optional[datetime] = None,
	period_end_date: Optional[datetime] = None,
	stripe_subscription_id: Optional[str] = None,
	stripe_customer_id: Optional[str] = None,
	billing_interval: str = "month",
	plan_credit: Optional[float] = None,
	plan_stockage: Optional[float] = None,
	next_credit_allocation_at: Optional[datetime] = None,
	credit_cycle_start_at: Optional[datetime] = None,
	credit_cycle_end_at: Optional[datetime] = None,
) -> Dict[str, Any]:
	"""Create a subscription row after a confirmed payment.

	period_end_date overrides the default end date (+1 calendar month, or
	+1 calendar year when billing_interval == "year") -- a Stripe
	subscription renewal invoice carries its own authoritative billing
	period (see _handle_subscription_renewal_invoice in app.py), which
	must be used as-is instead of recomputed, so the stored period stays
	exactly in sync with what Stripe actually billed.

	plan_credit/plan_stockage snapshot the plan's allowance at the moment
	of this payment -- see the annual-billing migration's comment on
	souscription for why this must never be a live lookup.

	credit_cycle_start_at/credit_cycle_end_at default to this row's own
	billing period (start_date/end_date) when omitted -- correct for a
	monthly subscription, where the credit cycle and the billing period
	are the same thing. A caller allocating resources for an annual
	subscription's one-month sub-cycle (not the whole paid year) passes
	these explicitly -- see _allocate_plan_resources in app.py."""
	client = await get_client()
	start_date = payment_date or datetime.now(timezone.utc)
	if start_date.tzinfo is None:
		start_date = start_date.replace(tzinfo=timezone.utc)
	if period_end_date is not None:
		end_date = period_end_date
	elif billing_interval == "year":
		end_date = add_one_year(start_date)
	else:
		end_date = add_one_month(start_date)
	if end_date.tzinfo is None:
		end_date = end_date.replace(tzinfo=timezone.utc)

	cycle_start = credit_cycle_start_at if credit_cycle_start_at is not None else start_date
	# An annual row's credit cycle is a one-month sub-window, not the
	# whole paid year -- default it to +1 month from the cycle start
	# rather than to end_date (the annual payment_end_date) when the
	# caller hasn't already resolved it explicitly.
	if credit_cycle_end_at is not None:
		cycle_end = credit_cycle_end_at
	elif billing_interval == "year":
		cycle_end = add_one_month(cycle_start)
	else:
		cycle_end = end_date
	if cycle_start.tzinfo is None:
		cycle_start = cycle_start.replace(tzinfo=timezone.utc)
	if cycle_end.tzinfo is None:
		cycle_end = cycle_end.replace(tzinfo=timezone.utc)

	payload = {
		"userid": user_id,
		"abonnement": abonnement,
		"payment_mode": payment_mode,
		"payment_amount": float(payment_amount),
		"payment_reference": payment_reference,
		"payment_start_date": start_date.isoformat(),
		"payment_end_date": end_date.isoformat(),
		"payment_status": payment_status,
		"payment_comment": payment_comment,
		"billing_interval": billing_interval,
		"credit_cycle_start_at": cycle_start.isoformat(),
		"credit_cycle_end_at": cycle_end.isoformat(),
	}
	if stripe_subscription_id:
		payload["stripe_subscription_id"] = stripe_subscription_id
	if stripe_customer_id:
		payload["stripe_customer_id"] = stripe_customer_id
	if plan_credit is not None:
		payload["plan_credit"] = float(plan_credit)
	if plan_stockage is not None:
		payload["plan_stockage"] = float(plan_stockage)
	if next_credit_allocation_at is not None:
		if next_credit_allocation_at.tzinfo is None:
			next_credit_allocation_at = next_credit_allocation_at.replace(tzinfo=timezone.utc)
		payload["next_credit_allocation_at"] = next_credit_allocation_at.isoformat()

	response = await client.table(SUPABASE_SOUSCRIPTION_TABLE).insert(payload).execute()
	rows = response.data or []
	if not rows:
		return payload
	return rows[0]


async def get_souscription_by_reference(payment_reference: str) -> Optional[Dict[str, Any]]:
	"""Fetch a subscription row by payment reference for webhook idempotency."""
	if not payment_reference:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("payment_reference", payment_reference)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	return rows[0]

async def get_user_abonnement(user_id: str) -> Optional[Dict[str, Any]]:
	"""Récupère l'abonnement actif d'un utilisateur."""
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.eq("payment_status", "completed")
		.neq("payment_mode", "stripe_credits")
		.not_.is_("abonnement", "null")
		.is_("account_disabled_at", "null")
		.gte("payment_end_date", now_iso)
		# Without an explicit order, which row postgrest returns is
		# unordered/arbitrary once more than one row matches (e.g. a legacy
		# one-off "payment" row with no stripe_subscription_id, alongside a
		# real Stripe-subscription row created later) -- see the change-plan
		# handler in app.py, which already has to work around this by
		# expiring the old row. Ordering by payment_end_date picks the
		# currently governing row deterministically.
		.order("payment_end_date", desc=True)
		.limit(1)
		.execute()
	)

	rows = response.data
	if not rows:
		return None
	row = dict(rows[0])

	# Resolve plan priority from the abonnement table; default to 1 when unknown.
	priority = 1
	try:
		abonnement_id = row.get("abonnement")
		if abonnement_id:
			abonnement = await get_abonnement(str(abonnement_id))
			raw_priority = (abonnement or {}).get("priorite")
			if raw_priority is not None:
				priority = int(raw_priority)
	except Exception:
		priority = 1

	row["priorite"] = max(1, min(3, int(priority or 1)))
	return row


async def get_latest_user_souscription(user_id: str) -> Optional[Dict[str, Any]]:
	"""Get latest subscription row for a user (active or expired)."""
	if not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.order("payment_end_date", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def get_latest_user_paid_subscription(user_id: str) -> Optional[Dict[str, Any]]:
	"""Get latest confirmed plan subscription (excluding direct credit purchases)."""
	if not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.eq("payment_status", "completed")
		.neq("payment_mode", "stripe_credits")
		.not_.is_("abonnement", "null")
		.order("payment_end_date", desc=True)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def list_user_souscriptions(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
	"""List latest subscriptions/payments for a user."""
	if not user_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("userid", user_id)
		.order("payment_start_date", desc=True)
		.limit(min(max(limit, 1), 500))
		.execute()
	)
	return response.data or []


async def list_souscriptions_due_for_monthly_credit_allocation(
	now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
	"""Annual subscriptions whose next monthly credit/storage refill is due
	-- Stripe raises an annual subscription's renewal invoice only once a
	year, so this is what drives the monthly-anniversary reset in between
	(see process_annual_credit_refill_jobs in app.py). Only rows with
	billing_interval == "year" ever carry a non-null
	next_credit_allocation_at (see insert_souscription), so filtering on
	it being due is enough -- no need to also filter billing_interval."""
	client = await get_client()
	now_iso = (now or datetime.now(timezone.utc)).isoformat()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("payment_status", "completed")
		.is_("account_disabled_at", "null")
		.not_.is_("next_credit_allocation_at", "null")
		.lte("next_credit_allocation_at", now_iso)
		.gte("payment_end_date", now_iso)
		.order("next_credit_allocation_at", desc=False)
		.limit(100)
		.execute()
	)
	return response.data or []


async def update_souscription_row(
	subscription_id: str,
	updates: Dict[str, Any],
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update one subscription row and return it. Pass ``user_id`` whenever
	available for a defense-in-depth ownership filter (column: ``userid``)."""
	if not subscription_id:
		return None
	client = await get_client()
	q = (
		client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.update(dict(updates or {}))
		.eq("id", subscription_id)
	)
	if user_id:
		q = q.eq("userid", user_id)
	await q.execute()
	response = (
		await client.table(SUPABASE_SOUSCRIPTION_TABLE)
		.select(SOUSCRIPTION_COLUMNS)
		.eq("id", subscription_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


# --------------------------------------------------------------------------
# Jobs
# --------------------------------------------------------------------------
JOB_COLUMNS = (
	"id, created_at, updated_at, user_id, job_type, status, attempts, max_attempts, "
	"progress, current_step, error_code, error_message, queue_name, pipeline_name, "
	"reserved_quota, consumed_quota, estimated_cost_usd, estimated_credit, actual_cost_usd, actual_credit, "
	"actual_storage_gb, cost_breakdown, priority, job_data, result_data"
)


async def create_job_record(
	job_id: str,
	user_id: str,
	job_type: str,
	status: str,
	job_data: Dict[str, Any],
	queue_name: str,
	pipeline_name: str,
	max_attempts: int = 2,
	reserved_quota: float = 0.0,
	estimated_cost_usd: float = 0.0,
	priority: int = 1,
) -> Dict[str, Any]:
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload = {
		"id": job_id,
		"user_id": user_id,
		"job_type": job_type,
		"status": status,
		"attempts": 0,
		"max_attempts": max(1, int(max_attempts)),
		"progress": 0,
		"current_step": "created",
		"queue_name": queue_name,
		"pipeline_name": pipeline_name,
		"reserved_quota": float(reserved_quota),
		"consumed_quota": 0.0,
		"estimated_cost_usd": float(estimated_cost_usd),
		"estimated_credit": 0.0,
		"actual_cost_usd": 0.0,
		"actual_credit": 0.0,
		"actual_storage_gb": 0.0,
		"cost_breakdown": {},
		"priority": max(1, min(3, int(priority or 1))),
		"job_data": job_data or {},
		"result_data": {},
		"created_at": now_iso,
		"updated_at": now_iso,
	}
	response = await client.table(SUPABASE_JOBS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def update_job_record(
	job_id: str,
	updates: Dict[str, Any],
	user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
	"""Update a job row. Pass ``user_id`` whenever available for a
	defense-in-depth ownership filter -- without it, any caller with only a
	job_id can rewrite any user's job status/results/cost fields."""
	if not job_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	q = client.table(SUPABASE_JOBS_TABLE).update(payload).eq("id", job_id)
	if user_id:
		q = q.eq("user_id", user_id)
	await q.execute()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("id", job_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def get_job_record(job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
	if not job_id:
		return None
	client = await get_client()
	q = (
		client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("id", job_id)
		.limit(1)
	)
	if user_id:
		q = q.eq("user_id", user_id)
	response = await q.execute()
	rows = response.data or []
	return rows[0] if rows else None


ACTIVE_JOB_STATUSES = ("created", "queued", "processing", "retry_wait")


async def count_active_jobs_for_user(user_id: str) -> int:
	"""Count a user's jobs currently in a non-terminal state (created, queued,
	processing, or waiting to retry). Used to cap per-user concurrent job
	submissions so a single account can't flood the queue/disk/S3 storage
	(see security audit finding H7)."""
	if not user_id:
		return 0
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select("id", count="exact")
		.eq("user_id", user_id)
		.in_("status", list(ACTIVE_JOB_STATUSES))
		.execute()
	)
	return int(response.count or 0)


async def list_active_jobs(limit: int = 1000) -> List[Dict[str, Any]]:
	"""Return jobs (any user) currently in a non-terminal state.

	Unlike count_active_jobs_for_user, this is not scoped to one user --
	it's used at process startup to find jobs orphaned by a previous
	process's restart/crash (runtime execution state lives only in
	in-memory JobManager.runtime_jobs, which a restart wipes, while these
	Supabase rows persist and would otherwise count against
	MAX_ACTIVE_JOBS_PER_USER forever with nothing left to ever complete
	or retry them)."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.in_("status", list(ACTIVE_JOB_STATUSES))
		.limit(max(1, limit))
		.execute()
	)
	return response.data or []


async def get_latest_job_record_by_project(project_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	"""Return the latest job row linked to a project for a specific user."""
	if not project_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("user_id", user_id)
		.order("created_at", desc=True)
		.limit(300)
		.execute()
	)
	rows = response.data or []
	for row in rows:
		job_data = row.get("job_data") or {}
		if str(job_data.get("project_id") or "") == str(project_id):
			return row
	return None


async def append_job_log(job_id: str, level: str, message: str, metadata: Optional[Dict[str, Any]] = None) -> None:
	if not job_id:
		return
	client = await get_client()
	payload = {
		"job_id": job_id,
		"level": (level or "INFO").upper(),
		"message": message or "",
		"metadata": metadata or {},
		"created_at": datetime.now(timezone.utc).isoformat(),
	}
	await client.table(SUPABASE_JOB_LOGS_TABLE).insert(payload).execute()


async def list_job_logs(job_id: str, limit: int = 300) -> List[Dict[str, Any]]:
	if not job_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_JOB_LOGS_TABLE)
		.select("id, job_id, level, message, metadata, created_at")
		.eq("job_id", job_id)
		.order("created_at", desc=False)
		.limit(min(max(limit, 1), 1000))
		.execute()
	)
	return response.data or []


async def list_recoverable_jobs(queue_name: str, statuses: Optional[List[str]] = None, limit: int = 200) -> List[Dict[str, Any]]:
	client = await get_client()
	status_values = statuses or ["queued", "processing", "retry_wait"]
	q = (
		client.table(SUPABASE_JOBS_TABLE)
		.select(JOB_COLUMNS)
		.eq("queue_name", queue_name)
		.in_("status", status_values)
		.order("created_at", desc=False)
		.limit(min(max(limit, 1), 1000))
	)
	response = await q.execute()
	return response.data or []


# --------------------------------------------------------------------------
# User Data (credits & storage)
# --------------------------------------------------------------------------

async def get_user_data(user_id: str) -> Optional[Dict[str, Any]]:
	"""Get the credit/storage balance for a user."""
	if not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_USER_DATA_TABLE)
		.select("*")
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


def _extract_user_data_state(existing: Dict[str, Any]) -> Dict[str, float]:
	current_credit = float(existing.get("credit", 0) or 0.0)
	current_storage = float(existing.get("stockage", 0) or 0.0)
	current_credit_max = float(existing.get("credit_max", current_credit) or 0.0)
	current_stockage_max = float(existing.get("stockage_max", max(current_storage, 0.0)) or 0.0)
	current_debt = float(existing.get("credit_debt", 0) or 0.0)
	return {
		"current_credit": current_credit,
		"current_storage": current_storage,
		"current_credit_max": current_credit_max,
		"current_stockage_max": current_stockage_max,
		"current_debt": current_debt,
	}


def _apply_credit_delta_on_debt(credit_delta: float, current_debt: float) -> Dict[str, float]:
	delta_credit = float(credit_delta)
	debt_paid = 0.0
	remaining_debt = float(current_debt)
	if delta_credit > 0 and remaining_debt > 0:
		debt_paid = min(remaining_debt, delta_credit)
		delta_credit -= debt_paid
		remaining_debt = max(0.0, remaining_debt - debt_paid)
	return {
		"delta_credit": delta_credit,
		"debt_paid": debt_paid,
		"remaining_debt": remaining_debt,
	}


def _build_upsert_existing_payload(
	existing_state: Dict[str, float],
	credit_delta: float,
	storage_delta: float,
	update_credit_max: bool,
	update_stockage_max: bool,
) -> Dict[str, float]:
	debt_state = _apply_credit_delta_on_debt(credit_delta, existing_state["current_debt"])
	new_credit = float(_ceil_credit(existing_state["current_credit"] + debt_state["delta_credit"]))
	new_storage = float(existing_state["current_storage"] + float(storage_delta))

	new_credit_max = max(0.0, existing_state["current_credit_max"])
	new_stockage_max = max(0.0, existing_state["current_stockage_max"])
	if update_credit_max:
		# Credit top-ups and subscription allocations can redefine the user's ceiling.
		new_credit_max = float(_ceil_credit(existing_state["current_credit_max"] + float(credit_delta)))
	if update_stockage_max:
		new_stockage_max = float(existing_state["current_stockage_max"] + float(storage_delta))

	if new_credit > new_credit_max:
		new_credit_max = float(new_credit)

	return {
		"credit": new_credit,
		"credit_debt": debt_state["remaining_debt"],
		"stockage": new_storage,
		"credit_max": new_credit_max,
		"stockage_max": new_stockage_max,
		"debt_paid": debt_state["debt_paid"],
	}


async def _record_debt_payment_if_needed(
	user_id: str,
	debt_paid: float,
	debt_balance_after: float,
	operation_type: str,
	operation_id: str,
	source: str,
) -> None:
	if debt_paid <= 0:
		return

	await insert_user_credit_bank_entry(
		user_id=user_id,
		direction="debt_payment",
		amount=debt_paid,
		debt_balance_after=debt_balance_after,
		operation_type=operation_type,
		operation_id=operation_id,
		metadata={"source": source},
	)


def _build_new_user_data_payload(user_id: str, credit_delta: float, storage_delta: float) -> Dict[str, Any]:
	initial_credit = _ceil_credit(credit_delta)
	initial_storage = max(0.0, float(storage_delta))
	return {
		"user_id": user_id,
		"credit": initial_credit,
		"credit_debt": 0.0,
		"stockage": initial_storage,
		"credit_max": float(initial_credit),
		"stockage_max": float(initial_storage),
	}


async def upsert_user_data_credits(
	user_id: str,
	credit_delta: float,
	storage_delta: float = 0.0,
	update_credit_max: bool = False,
	update_stockage_max: bool = False,
	operation_type: str = "credit_recharge",
	operation_id: str = "",
) -> Dict[str, Any]:
	client = await get_client()
	existing = await get_user_data(user_id)

	if not existing:
		payload = _build_new_user_data_payload(user_id, credit_delta, storage_delta)
		response = await client.table(SUPABASE_USER_DATA_TABLE).insert(payload).execute()
		rows = response.data or []
		return rows[0] if rows else payload

	existing_state = _extract_user_data_state(existing)
	logger.info(
		f"Current user data for {user_id}: credit={existing_state['current_credit']}, "
		f"stockage={existing_state['current_storage']}, credit_max={existing_state['current_credit_max']}, "
		f"stockage_max={existing_state['current_stockage_max']}"
	)

	update_values = _build_upsert_existing_payload(
		existing_state,
		credit_delta,
		storage_delta,
		update_credit_max,
		update_stockage_max,
	)
	logger.info(
		f"Updating user data for {user_id}: credit={update_values['credit']}, stockage={update_values['stockage']}, "
		f"credit_max={update_values['credit_max']}, stockage_max={update_values['stockage_max']}"
	)

	response = (
		await client.table(SUPABASE_USER_DATA_TABLE)
		.update({
			"credit": update_values["credit"],
			"credit_debt": update_values["credit_debt"],
			"stockage": update_values["stockage"],
			"credit_max": update_values["credit_max"],
			"stockage_max": update_values["stockage_max"],
			"updated_at": datetime.now(timezone.utc).isoformat(),
		})
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	await _record_debt_payment_if_needed(
		user_id=user_id,
		debt_paid=update_values["debt_paid"],
		debt_balance_after=update_values["credit_debt"],
		operation_type=operation_type,
		operation_id=operation_id,
		source="upsert_user_data_credits",
	)
	return rows[0] if rows else existing


def _build_set_balance_payload(
	user_id: str,
	credit: float,
	storage: float,
	credit_max: Optional[float],
	storage_max: Optional[float],
	now_iso: str,
) -> Dict[str, Any]:
	clamped_credit = _ceil_credit(credit)
	clamped_storage = float(storage or 0.0)
	return {
		"user_id": user_id,
		"credit": clamped_credit,
		"credit_debt": 0.0,
		"stockage": clamped_storage,
		"credit_max": _ceil_credit(credit_max if credit_max is not None else clamped_credit),
		"stockage_max": max(0.0, float(storage_max if storage_max is not None else max(clamped_storage, 0.0))),
		"updated_at": now_iso,
	}


def _build_existing_set_balance_update(
	existing: Dict[str, Any],
	payload: Dict[str, Any],
	credit_max: Optional[float],
	storage_max: Optional[float],
) -> Dict[str, float]:
	clamped_credit = float(payload["credit"])
	existing_debt = float(existing.get("credit_debt", 0) or 0.0)
	debt_paid = min(existing_debt, clamped_credit)
	net_credit = max(0.0, clamped_credit - debt_paid)
	remaining_debt = max(0.0, existing_debt - debt_paid)

	next_credit_max = float(payload["credit_max"])
	if credit_max is None:
		next_credit_max = float(_ceil_credit(existing.get("credit_max", existing.get("credit", 0.0)) or 0.0))

	next_storage_max = float(payload["stockage_max"])
	if storage_max is None:
		next_storage_max = max(
			0.0,
			float(existing.get("stockage_max", max(existing.get("stockage", 0.0), 0.0)) or 0.0),
		)

	if clamped_credit > next_credit_max:
		next_credit_max = float(_ceil_credit(net_credit))

	return {
		"credit": net_credit,
		"credit_debt": remaining_debt,
		"stockage": float(payload["stockage"]),
		"credit_max": next_credit_max,
		"stockage_max": next_storage_max,
		"debt_paid": debt_paid,
	}


async def set_user_data_balance(
	user_id: str,
	credit: float,
	storage: float,
	credit_max: Optional[float] = None,
	storage_max: Optional[float] = None,
	operation_type: str = "subscription",
	operation_id: str = "",
) -> Dict[str, Any]:
	"""Set absolute credit/storage values for a user balance row."""
	if not user_id:
		return {"user_id": "", "credit": 0.0, "stockage": 0.0, "credit_max": 0.0, "stockage_max": 0.0}
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	payload = _build_set_balance_payload(user_id, credit, storage, credit_max, storage_max, now_iso)
	existing = await get_user_data(user_id)
	if not existing:
		response = await client.table(SUPABASE_USER_DATA_TABLE).insert(payload).execute()
		rows = response.data or []
		return rows[0] if rows else payload

	update_values = _build_existing_set_balance_update(existing, payload, credit_max, storage_max)
	response = (
		await client.table(SUPABASE_USER_DATA_TABLE)
		.update({
			"credit": update_values["credit"],
			"credit_debt": update_values["credit_debt"],
			"stockage": update_values["stockage"],
			"credit_max": update_values["credit_max"],
			"stockage_max": update_values["stockage_max"],
			"updated_at": now_iso,
		})
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	await _record_debt_payment_if_needed(
		user_id=user_id,
		debt_paid=update_values["debt_paid"],
		debt_balance_after=update_values["credit_debt"],
		operation_type=operation_type,
		operation_id=operation_id,
		source="set_user_data_balance",
	)
	return rows[0] if rows else payload


async def zero_subscription_credit(user_id: str, operation_id: str = "") -> None:
	"""Zeroes out ONLY the pure-subscription credit balance (credit/
	credit_max) -- used when Stripe definitively gives up retrying a
	subscription's renewal charge (see _handle_subscription_payment_failed
	in app.py). Storage, and the promotional/purchased credit batches
	(a separate table -- see promotional_credit_batches), are never
	touched: this account may still have usable bonus credit left even
	though its subscription itself is now unpaid. A subsequent successful
	renewal resets this back to the plan's full allowance as usual (see
	_reset_user_plan_balance), same as every other renewal."""
	if not user_id:
		return
	existing = await get_user_data(user_id)
	if not existing:
		return
	credit_removed = max(0.0, float(existing.get("credit", 0) or 0.0))
	current_storage = float(existing.get("stockage", 0) or 0.0)
	storage_max = float(existing.get("stockage_max", max(current_storage, 0.0)) or 0.0)
	await set_user_data_balance(
		user_id=user_id, credit=0.0, storage=current_storage,
		credit_max=0.0, storage_max=storage_max,
		operation_type="subscription_payment_failed", operation_id=operation_id,
	)
	await insert_user_data_history(
		user_id=user_id, credit=credit_removed, storage=0.0, operation="output",
		operation_type="subscription_payment_failed", operation_id=operation_id,
	)


async def set_user_max_daily_publications(user_id: str, max_daily_publications: float) -> None:
	"""Snapshots the active plan's daily-publication cap (0 = unlimited)
	onto user_data at the moment it's allocated (purchase, renewal, plan
	change -- see _allocate_plan_resources/_finalize_immediate_upgrade in
	app.py), so the quota check (consume_publish_quota) always reads it
	off the user's own row rather than re-deriving it live from
	abonnement -- it depends on the user, not a fresh plan lookup, exactly
	as asked. A harmless 0-delta credit "touch" first (see
	upsert_user_data_credits) makes sure the row exists at all for a
	brand-new user_id with no prior credit grant."""
	if not user_id:
		return
	await upsert_user_data_credits(user_id, credit_delta=0.0, operation_type="max_daily_publications_touch")
	client = await get_client()
	await (
		client.table(SUPABASE_USER_DATA_TABLE)
		.update({"max_daily_publications": int(max(0, max_daily_publications))})
		.eq("user_id", user_id)
		.execute()
	)


async def consume_publish_quota(user_id: str, count: int = 1) -> Dict[str, Any]:
	"""Checks this user's own snapshotted daily-publication cap
	(user_data.max_daily_publications, 0 = unlimited) against today's
	count (user_data.publications_today), and if there's room, consumes
	``count`` of it. The daily reset is lazy, not a scheduled job: if the
	stored publications_count_date isn't today (UTC), today's count is
	simply treated as starting from 0 -- correct without a cron sweep.

	This is a plain read-then-write, not the optimistic-CAS retry loop
	deduct_user_credits uses for money -- a rate limit tolerates the rare
	benign race (two simultaneous requests both reading the same stale
	count) that a credit ledger never could; losing a request's increment
	here only ever means one extra publication slips through, not a
	financial loss.

	Returns {"allowed": True, "max_daily", "used_today"} when it fits
	(max_daily/used_today are the post-consumption state), or
	{"allowed": False, "max_daily", "used_today", "resets_at"} when it
	doesn't -- resets_at is the next UTC midnight, exactly when the daily
	counter lazily starts over, so the caller can tell the user precisely
	when they'll be able to publish again."""
	if count <= 0:
		return {"allowed": True, "max_daily": 0, "used_today": 0}
	existing = await get_user_data(user_id)
	if not existing:
		return {"allowed": True, "max_daily": 0, "used_today": 0}

	max_daily = int(existing.get("max_daily_publications") or 0)
	today = datetime.now(timezone.utc).date()
	stored_date = existing.get("publications_count_date")
	current_count = int(existing.get("publications_today") or 0) if stored_date == today.isoformat() else 0

	if max_daily > 0 and current_count + count > max_daily:
		resets_at = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
		return {
			"allowed": False, "max_daily": max_daily, "used_today": current_count,
			"resets_at": resets_at.isoformat(),
		}

	new_count = current_count + count
	client = await get_client()
	await (
		client.table(SUPABASE_USER_DATA_TABLE)
		.update({"publications_today": new_count, "publications_count_date": today.isoformat()})
		.eq("user_id", user_id)
		.execute()
	)
	return {"allowed": True, "max_daily": max_daily, "used_today": new_count}


MAX_CREDIT_DEBT = max(0.0, float(os.environ.get("MAX_CREDIT_DEBT", "0") or "0"))


def _calculate_credit_debit(existing: Dict[str, Any], credits: float) -> Dict[str, float]:
	current_credits = float(existing.get("credit", 0) or 0.0)
	current_debt = float(existing.get("credit_debt", 0) or 0.0)
	debit_credits = max(0.0, float(credits or 0.0))

	new_credit = current_credits - debit_credits
	debt_delta = 0.0
	if new_credit < 0:
		debt_delta = abs(new_credit)
		new_credit = 0.0

	new_debt = current_debt + debt_delta
	return {
		"current_credits": current_credits,
		"current_debt": current_debt,
		"debit_credits": debit_credits,
		"new_credit": new_credit,
		"debt_delta": debt_delta,
		"new_debt": new_debt,
	}


def _calculate_storage_after_deduction(existing: Dict[str, Any], storage_delta: float) -> Dict[str, float]:
	# Storage is no longer a quota that can block an operation (see
	# retention_config.py / Vireel's credit-only billing model) -- this
	# still tracks current_storage/new_storage for bookkeeping on the
	# user_data row, but never rejects a deduction for it.
	current_storage = float(existing.get("stockage", 0) or 0.0)
	new_storage = current_storage + float(storage_delta)
	return {
		"current_storage": current_storage,
		"new_storage": new_storage,
	}


def _build_deduction_update(existing: Dict[str, Any], credits: float, storage_delta: float) -> Optional[Dict[str, float]]:
	credit_state = _calculate_credit_debit(existing, credits)
	if credit_state["new_debt"] > MAX_CREDIT_DEBT:
		return None

	storage_state = _calculate_storage_after_deduction(existing, storage_delta)

	return {
		**credit_state,
		**storage_state,
	}


async def _try_apply_deduction_update(client: AsyncClient, user_id: str, update_state: Dict[str, float]) -> bool:
	response = await (
		client.table(SUPABASE_USER_DATA_TABLE)
		.update({
			"credit": update_state["new_credit"],
			"credit_debt": update_state["new_debt"],
			"stockage": update_state["new_storage"],
			"updated_at": datetime.now(timezone.utc).isoformat(),
		})
		.eq("user_id", user_id)
		.eq("credit", update_state["current_credits"])
		.eq("stockage", update_state["current_storage"])
		.execute()
	)
	return bool(response.data)


async def _record_debt_increase_if_needed(user_id: str, update_state: Dict[str, float]) -> None:
	if update_state["debt_delta"] <= 0:
		return

	await insert_user_credit_bank_entry(
		user_id=user_id,
		direction="debt_increase",
		amount=update_state["debt_delta"],
		debt_balance_after=update_state["new_debt"],
		operation_type="operation",
		operation_id="",
		metadata={"requested_credit_debit": update_state["debit_credits"]},
	)


async def _consume_promotional_credits(client: AsyncClient, user_id: str, amount: float) -> Dict[str, Any]:
	"""Atomically drain up to ``amount`` from this user's promotional
	credit batches, oldest-expiry-first (see the consume_promotional_credits
	Postgres function -- it row-locks each batch it touches, so this alone
	is safe under concurrency). A no-op for amount <= 0 (e.g. the
	storage-only deductions some callers make)."""
	if not amount or amount <= 0:
		return {"consumed": 0.0, "batches": []}
	response = await client.rpc(
		"consume_promotional_credits", {"p_user_id": user_id, "p_amount": float(amount)}
	).execute()
	data = response.data
	if isinstance(data, list):
		data = data[0] if data else None
	return data or {"consumed": 0.0, "batches": []}


async def _restore_promotional_credits(client: AsyncClient, batches: Optional[List[Dict[str, Any]]]) -> None:
	"""Reverses a prior _consume_promotional_credits draw -- used when the
	rest of a deduction (the standard-credit side) ultimately fails, so a
	user's promotional credits are never silently spent for an operation
	that didn't go through. Best-effort: a failure here must never mask
	the original deduction failure the caller is already returning."""
	if not batches:
		return
	try:
		await client.rpc("restore_promotional_credits", {"p_batches": batches}).execute()
	except Exception:
		logger.warning("Failed to restore promotional credit batches: %s", batches, exc_info=True)


async def deduct_user_credits(
	user_id: str,
	credits: float,
	storage_delta: float = 0.0,
	max_attempts: int = 5,
) -> bool:
	"""Deduct ``credits`` from the user balance -- promotional credits
	first (oldest-expiry-first), the standard balance for whatever's left.

	Returns ``False`` if the user does not have sufficient credits/storage
	headroom, or if the account's debt would exceed MAX_CREDIT_DEBT. On
	that path, any promotional credits already drawn for this call are
	restored first, so a rejected deduction never costs the user anything
	(see _restore_promotional_credits).

	Security: this uses optimistic concurrency (a conditional UPDATE that
	only applies if credit/stockage still match what we just read, retried
	on conflict) so two concurrent operations can never both silently debit
	against the same stale balance -- one of them detects the conflict and
	recomputes against the fresh row instead of the update being lost. It
	also enforces a hard ceiling on ``credit_debt`` instead of allowing it to
	grow without bound while the account keeps consuming paid processing
	(see security audit finding C7).
	"""
	client = await get_client()

	promo_result = await _consume_promotional_credits(client, user_id, credits)
	promo_consumed = float(promo_result.get("consumed") or 0.0)
	promo_batches = promo_result.get("batches") or []
	remaining_credits = max(0.0, float(credits or 0.0) - promo_consumed)

	for _ in range(max_attempts):
		existing = await get_user_data(user_id)
		if not existing:
			await _restore_promotional_credits(client, promo_batches)
			return False

		update_state = _build_deduction_update(existing, remaining_credits, storage_delta)
		if not update_state:
			await _restore_promotional_credits(client, promo_batches)
			return False

		updated = await _try_apply_deduction_update(client, user_id, update_state)
		if not updated:
			# Another concurrent request changed the balance between our read
			# and this write -- retry against the fresh balance rather than
			# silently dropping this deduction (classic TOCTOU double-spend).
			continue

		await _record_debt_increase_if_needed(user_id, update_state)
		return True

	await _restore_promotional_credits(client, promo_batches)
	return False


async def refund_user_credits(
	user_id: str,
	credits: float,
	storage_delta: float = 0.0,
	max_attempts: int = 5,
) -> bool:
	"""Add ``credits`` back to a user's balance (releasing a reservation made
	via deduct_user_credits, e.g. on job failure/cancellation, or settling a
	completed job whose actual cost was lower than its reservation).

	Existing debt is paid down first, same as set_user_data_balance's
	top-up logic, before any surplus is added to the spendable balance.
	Uses the same optimistic-concurrency retry as deduct_user_credits so a
	concurrent refund/debit can never be silently lost.
	"""
	if credits <= 0 and storage_delta == 0:
		return True
	client = await get_client()

	for _ in range(max_attempts):
		existing = await get_user_data(user_id)
		if not existing:
			return False

		current_credits = float(existing.get("credit", 0) or 0.0)
		current_debt = float(existing.get("credit_debt", 0) or 0.0)
		credit_amount = max(0.0, float(credits or 0.0))

		debt_paid = min(current_debt, credit_amount)
		new_debt = current_debt - debt_paid
		new_credit = current_credits + (credit_amount - debt_paid)

		current_storage = float(existing.get("stockage", 0) or 0.0)
		new_storage = current_storage + float(storage_delta)

		response = await (
			client.table(SUPABASE_USER_DATA_TABLE)
			.update({
				"credit":     new_credit,
				"credit_debt": new_debt,
				"stockage":   new_storage,
				"updated_at": datetime.now(timezone.utc).isoformat(),
			})
			.eq("user_id", user_id)
			.eq("credit", current_credits)
			.eq("stockage", current_storage)
			.execute()
		)

		if not response.data:
			continue

		if debt_paid > 0:
			await insert_user_credit_bank_entry(
				user_id=user_id,
				direction="debt_payment",
				amount=debt_paid,
				debt_balance_after=new_debt,
				operation_type="refund",
				operation_id="",
				metadata={"refunded_credit": credit_amount},
			)
		return True

	return False


async def insert_user_credit_bank_entry(
	user_id: str,
	direction: str,
	amount: float,
	debt_balance_after: float,
	operation_type: str,
	operation_id: str = "",
	metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
	"""Track credit debt creation/repayment events."""
	client = await get_client()
	payload = {
		"user_id": user_id,
		"direction": (direction or "").strip().lower(),
		"amount": float(max(0.0, amount or 0.0)),
		"debt_balance_after": float(max(0.0, debt_balance_after or 0.0)),
		"operation_type": operation_type,
		"operation_id": operation_id or "",
		"metadata": metadata or {},
	}
	response = await client.table(SUPABASE_USER_CREDIT_BANK_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def insert_user_data_history(
	user_id: str,
	credit: float,
	storage: float,
	operation: str,        # 'input' or 'output'
	operation_type: str,   # 'subscription' | 'reels' | 'captions' | 'publications' | 'credit_purchase'
	operation_id: str = "",
) -> Dict[str, Any]:
	"""Append an entry to the user credit/storage history table."""
	client = await get_client()
	rounded_credit = _ceil_credit(credit)
	payload = {
		"user_id":        user_id,
		"credit":         rounded_credit,
		"storage":        float(storage),   # reste float/numeric
		"operation":      operation,
		"operation_type": operation_type,
		"operation_id":   operation_id or "",
	}
	response = await client.table(SUPABASE_USER_DATA_HISTORY_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def upsert_user_data_history_entry(
	user_id: str,
	credit: float,
	storage: float,
	operation: str,        # 'input' | 'output' | 'refund'
	operation_type: str,   # 'subscription' | 'reels' | 'captions' | 'publications' | 'credit_purchase'
	operation_id: str = "",
) -> Dict[str, Any]:
	"""Same ledger as insert_user_data_history, but merges into an existing
	row for this (user_id, operation_id, operation) instead of always
	appending a new one -- for when one job's completion bills several
	sub-charges that belong to the same logical operation as its primary
	charge (e.g. a reel generation job's auto-caption cost, or its
	preserved-source-video storage cost): those should show up as one
	user-facing history line with the amounts summed, not several.

	The merged row's credit/storage are summed; its operation_type is left
	exactly as it was when the row was first created -- "la nature de
	l'operation reste l'operation principale" -- the operation_type passed
	here is only used when there's no existing row yet to merge into, so
	callers must insert/merge the primary charge before any sub-charge for
	a job for this to land the type they expect (every current caller
	already does: see job_manager.debit_credits_for_job, which always bills
	a job's own primary charge before app.py's per-job sub-charges run).

	Falls back to a plain insert when operation_id is empty (nothing to
	key a merge on, same as insert_user_data_history's default)."""
	if not operation_id:
		return await insert_user_data_history(user_id, credit, storage, operation, operation_type, operation_id)

	client = await get_client()
	existing_response = (
		await client.table(SUPABASE_USER_DATA_HISTORY_TABLE)
		.select("*")
		.eq("user_id", user_id)
		.eq("operation_id", operation_id)
		.eq("operation", operation)
		.limit(1)
		.execute()
	)
	existing_rows = existing_response.data or []
	if not existing_rows:
		return await insert_user_data_history(user_id, credit, storage, operation, operation_type, operation_id)

	existing = existing_rows[0]
	merged_credit = _ceil_credit(float(existing.get("credit") or 0.0) + float(credit or 0.0))
	merged_storage = float(existing.get("storage") or 0.0) + float(storage or 0.0)
	update_response = (
		await client.table(SUPABASE_USER_DATA_HISTORY_TABLE)
		.update({"credit": merged_credit, "storage": merged_storage})
		.eq("id", existing["id"])
		.execute()
	)
	rows = update_response.data or []
	return rows[0] if rows else {**existing, "credit": merged_credit, "storage": merged_storage}


async def get_user_data_history(
	user_id: str,
	page: int = 1,
	page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
	"""Return paginated credit/storage history for a user."""
	if not user_id:
		return [], 0
	client = await get_client()
	page      = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset    = (page - 1) * page_size

	response = (
		await client.table(SUPABASE_USER_DATA_HISTORY_TABLE)
		.select("*", count="exact")
		.eq("user_id", user_id)
		.order("created_at", desc=True)
		.range(offset, offset + page_size - 1)
		.execute()
	)
	return response.data or [], response.count or 0


# --------------------------------------------------------------------------
# Referral program
# --------------------------------------------------------------------------
# No ambiguous-looking characters (0/O, 1/I/L) so a code stays easy to
# read aloud or retype from a screenshot.
_REFERRAL_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_REFERRAL_CODE_LENGTH = 7


def _generate_referral_code() -> str:
	return "".join(secrets.choice(_REFERRAL_CODE_ALPHABET) for _ in range(_REFERRAL_CODE_LENGTH))


async def get_referral_code(user_id: str) -> Optional[str]:
	"""The user's existing referral code, if one has already been generated."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_REFERRAL_CODES_TABLE)
		.select("code")
		.eq("user_id", user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0]["code"] if rows else None


async def get_or_create_referral_code(user_id: str, max_attempts: int = 5) -> str:
	"""Returns the user's referral code, generating one on first use --
	codes are never pre-created for every user up front (there is no
	signup trigger in this codebase to do that; see user_data's own
	lazy-creation pattern for the established precedent)."""
	existing = await get_referral_code(user_id)
	if existing:
		return existing

	client = await get_client()
	for _ in range(max_attempts):
		code = _generate_referral_code()
		try:
			response = (
				await client.table(SUPABASE_REFERRAL_CODES_TABLE)
				.insert({"user_id": user_id, "code": code})
				.execute()
			)
			rows = response.data or []
			if rows:
				return rows[0]["code"]
			return code
		except APIError:
			# Either the random code collided with someone else's (retry a
			# fresh one) or a concurrent request already created this exact
			# user's code (re-read and use that instead).
			existing = await get_referral_code(user_id)
			if existing:
				return existing
			continue

	raise RuntimeError(f"Could not generate a unique referral code for user {user_id}")


async def get_referral_code_owner(code: str) -> Optional[str]:
	"""Resolve a referral code back to its owner's user_id, or None if the
	code doesn't exist. Lookup is case-insensitive since a user might
	retype a shared link/code by hand."""
	if not code:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_REFERRAL_CODES_TABLE)
		.select("user_id")
		.ilike("code", code.strip())
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0]["user_id"] if rows else None


REFERRAL_COLUMNS = (
	"id, created_at, referrer_user_id, referred_user_id, referral_code, status, "
	"signup_reward_granted_at, signup_reward_batch_id, first_subscription_type, "
	"first_subscription_souscription_id, subscription_reward_granted_at, "
	"subscription_reward_batch_id, invalidated_at, invalidated_reason"
)


async def get_referral_by_referred_user(referred_user_id: str) -> Optional[Dict[str, Any]]:
	"""The (at most one) referral relationship where this user is the
	referee -- used both to check "does this user already have a
	referrer" and, on a first-subscription webhook, "was this user
	referred at all"."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_REFERRALS_TABLE)
		.select(REFERRAL_COLUMNS)
		.eq("referred_user_id", referred_user_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def insert_referral(
	referrer_user_id: str, referred_user_id: str, referral_code: str,
) -> Tuple[Optional[Dict[str, Any]], bool]:
	"""Create the referral row associating referred_user_id with
	referrer_user_id. Returns (row, created) -- created is False when the
	row already existed (the referred_user_id UNIQUE constraint is what
	actually enforces "a user can never have more than one referrer",
	this is just the application-level surface over it: a second attempt
	returns the EXISTING row rather than erroring, so the caller can
	treat it as an idempotent no-op instead of a failure)."""
	client = await get_client()
	try:
		response = (
			await client.table(SUPABASE_REFERRALS_TABLE)
			.insert({
				"referrer_user_id": referrer_user_id,
				"referred_user_id": referred_user_id,
				"referral_code": referral_code,
			})
			.execute()
		)
		rows = response.data or []
		return (rows[0] if rows else None), True
	except APIError:
		existing = await get_referral_by_referred_user(referred_user_id)
		return existing, False


async def update_referral_row(referral_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_REFERRALS_TABLE)
		.update(dict(updates or {}))
		.eq("id", referral_id)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def claim_referral_subscription_reward(
	referral_id: str, subscription_type: str, souscription_id: str,
) -> Optional[Dict[str, Any]]:
	"""Atomically claims the (at most once ever) subscription-reward slot
	for this referral: the conditional UPDATE's WHERE clause is the
	compare-and-swap that guarantees a webhook delivered twice (or
	retried) can only ever win this race once. Returns the updated row,
	or None if it was already claimed (nothing to do -- the caller must
	not grant a second reward)."""
	client = await get_client()
	response = (
		await client.table(SUPABASE_REFERRALS_TABLE)
		.update({
			"subscription_reward_granted_at": datetime.now(timezone.utc).isoformat(),
			"first_subscription_type": subscription_type,
			"first_subscription_souscription_id": souscription_id,
			"status": "rewarded",
		})
		.eq("id", referral_id)
		.is_("subscription_reward_granted_at", "null")
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def list_referrals_by_referrer(referrer_user_id: str, limit: int = 200) -> List[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_REFERRALS_TABLE)
		.select(REFERRAL_COLUMNS)
		.eq("referrer_user_id", referrer_user_id)
		.order("created_at", desc=True)
		.limit(min(max(limit, 1), 500))
		.execute()
	)
	return response.data or []


async def invalidate_referral(referral_id: str, reason: str) -> Optional[Dict[str, Any]]:
	"""Administrative kill switch for a fraudulent/abusive referral (see
	REVIEW section 12) -- marks it invalid so no further reward can ever
	be granted from it. Does not claw back credits already spent; use
	revoke_promotional_credit_batches_by_source_reference for that."""
	return await update_referral_row(referral_id, {
		"status": "invalid",
		"invalidated_at": datetime.now(timezone.utc).isoformat(),
		"invalidated_reason": reason,
	})


async def get_auth_user_created_at(user_id: str) -> Optional[datetime]:
	"""The Supabase Auth account's own creation timestamp, via the Admin
	Auth API (requires the service-role client this module already uses
	everywhere else). This codebase has no signup webhook/trigger on
	auth.users, so this is how the referral-association endpoint verifies
	-- server-side, never trusting the frontend's word for it -- that the
	calling account is genuinely brand new rather than an existing user
	retroactively attaching a referrer. Returns None on any failure
	(unknown user, Admin API error, ...) so the caller can fail closed."""
	try:
		client = await get_client()
		response = await client.auth.admin.get_user_by_id(user_id)
		user = getattr(response, "user", None)
		created_at = getattr(user, "created_at", None)
		if created_at is None:
			return None
		if isinstance(created_at, str):
			return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
		return created_at
	except Exception:
		logger.warning("Failed to fetch auth user created_at for %s", user_id, exc_info=True)
		return None


# --------------------------------------------------------------------------
# Promotional credits (generic ledger -- referrals are the first source,
# not the only one; see the migration's comment on promotional_credit_batches)
# --------------------------------------------------------------------------
PROMOTIONAL_CREDIT_BATCH_COLUMNS = (
	"id, created_at, user_id, amount_initial, amount_remaining, source, "
	"source_reference, expires_at, revoked_at, revoked_reason, tier"
)

# tier 1 (promotional) is always drained before tier 2 (purchased) --
# see consume_promotional_credits in the credit-tiers migration.
CREDIT_BATCH_TIER_PROMOTIONAL = 1
CREDIT_BATCH_TIER_PURCHASED = 2


async def insert_promotional_credit_batch(
	user_id: str, amount: float, source: str, expiration_days: int, source_reference: Optional[str] = None,
	tier: int = CREDIT_BATCH_TIER_PROMOTIONAL,
) -> Dict[str, Any]:
	"""Grants one independent credit batch, expiring ``expiration_days``
	from now (fixed at grant time -- a later change to the expiration env
	var never touches this batch's own expires_at). ``tier`` distinguishes
	promotional credit (default, consumed first) from a standalone
	purchased top-up (consumed second, before subscription credit -- see
	_handle_credit_purchase in app.py). Also makes sure a user_data row
	exists for this user (harmless 0-delta "touch" -- see
	upsert_user_data_credits): without this, a brand-new referred user who
	has ONLY promotional credits and no plan yet would have no user_data
	row at all, and deduct_user_credits would reject spending their promo
	credits purely because that row doesn't exist yet."""
	await upsert_user_data_credits(user_id, credit_delta=0.0, operation_type="promotional_credit_touch")

	client = await get_client()
	amount = max(0.0, float(amount or 0))
	expires_at = datetime.now(timezone.utc) + timedelta(days=max(0, int(expiration_days)))
	payload = {
		"user_id": user_id,
		"amount_initial": amount,
		"amount_remaining": amount,
		"source": source,
		"source_reference": source_reference,
		"expires_at": expires_at.isoformat(),
		"tier": int(tier),
	}
	response = await client.table(SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def list_active_promotional_credit_batches(user_id: str) -> List[Dict[str, Any]]:
	"""Non-expired, non-revoked batches with credits left, soonest-expiry
	first -- what the wallet UI needs for its "X credits expire in Y days"
	breakdown (see section 15)."""
	if not user_id:
		return []
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE)
		.select(PROMOTIONAL_CREDIT_BATCH_COLUMNS)
		.eq("user_id", user_id)
		.is_("revoked_at", "null")
		.gt("expires_at", now_iso)
		.gt("amount_remaining", 0)
		.order("expires_at", desc=False)
		.execute()
	)
	return response.data or []


async def revoke_promotional_credit_batches_by_source_reference(
	source_reference: str, reason: str,
) -> int:
	"""Cancels whatever's still available in every promotional batch
	created from this source_reference (e.g. the souscription a chargeback
	or refund landed on) -- never creates a negative balance, since this
	only ever zeroes amount_remaining rather than subtracting from
	anything already spent."""
	if not source_reference:
		return 0
	client = await get_client()
	response = (
		await client.table(SUPABASE_PROMOTIONAL_CREDIT_BATCHES_TABLE)
		.update({
			"revoked_at": datetime.now(timezone.utc).isoformat(),
			"revoked_reason": reason,
			"amount_remaining": 0,
		})
		.eq("source_reference", source_reference)
		.is_("revoked_at", "null")
		.execute()
	)
	return len(response.data or [])


# --------------------------------------------------------------------------
# Notifications (generic in-app notifications, not email)
# --------------------------------------------------------------------------
async def insert_notification(
	user_id: str, type_: str, title: str, body: str = "", data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
	client = await get_client()
	payload = {
		"user_id": user_id,
		"type": type_,
		"title": title,
		"body": body or "",
		"data": data or {},
	}
	response = await client.table(SUPABASE_NOTIFICATIONS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def list_notifications(
	user_id: str, limit: int = 20, unread_only: bool = False,
) -> Tuple[List[Dict[str, Any]], int]:
	"""Returns (items, unread_count) -- unread_count always reflects the
	true total regardless of ``unread_only``, so a notification bell badge
	stays correct even while the panel is showing every notification."""
	if not user_id:
		return [], 0
	client = await get_client()

	query = client.table(SUPABASE_NOTIFICATIONS_TABLE).select("*").eq("user_id", user_id)
	if unread_only:
		query = query.is_("read_at", "null")
	response = await query.order("created_at", desc=True).limit(min(max(limit, 1), 100)).execute()

	unread_response = (
		await client.table(SUPABASE_NOTIFICATIONS_TABLE)
		.select("id", count="exact")
		.eq("user_id", user_id)
		.is_("read_at", "null")
		.limit(1)
		.execute()
	)
	return response.data or [], unread_response.count or 0


async def mark_notification_read(notification_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	client = await get_client()
	response = (
		await client.table(SUPABASE_NOTIFICATIONS_TABLE)
		.update({"read_at": datetime.now(timezone.utc).isoformat()})
		.eq("id", notification_id)
		.eq("user_id", user_id)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def mark_all_notifications_read(user_id: str) -> int:
	client = await get_client()
	response = (
		await client.table(SUPABASE_NOTIFICATIONS_TABLE)
		.update({"read_at": datetime.now(timezone.utc).isoformat()})
		.eq("user_id", user_id)
		.is_("read_at", "null")
		.execute()
	)
	return len(response.data or [])


# --------------------------------------------------------------------------
# Anonymous stories ("Temoignages")
# --------------------------------------------------------------------------
async def insert_anonymous_story(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	client = await get_client()
	response = await client.table(SUPABASE_ANONYMOUS_STORIES_TABLE).insert(row).execute()
	rows = response.data or []
	return rows[0] if rows else None


async def list_anonymous_stories(
	user_id: str,
	page: int,
	page_size: int,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.select("*", count="exact")
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.order("created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if status:
		q = q.eq("status", status)
	if query:
		q = q.or_(_build_ilike_or_filter(query, ["title"]))

	response = await q.execute()
	return response.data or [], response.count or 0


async def list_anonymous_story_dates_since(user_id: str, since_iso: Optional[str]) -> List[str]:
	client = await get_client()
	q = (
		client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.select("created_at")
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
	)
	if since_iso:
		q = q.gte("created_at", since_iso)
	response = await q.execute()
	return [row["created_at"] for row in (response.data or []) if row.get("created_at")]


async def get_anonymous_story(story_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	if not story_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.select("*")
		.eq("id", story_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def get_anonymous_story_by_job(job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	if not job_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.select("*")
		.eq("job_id", job_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_anonymous_story(story_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not story_id or not user_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	await (
		client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.update(payload)
		.eq("id", story_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	return await get_anonymous_story(story_id, user_id)


async def soft_delete_anonymous_story(story_id: str, user_id: str) -> bool:
	if not story_id or not user_id:
		return False
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_ANONYMOUS_STORIES_TABLE)
		.update({"deleted_at": now_iso, "updated_at": now_iso})
		.eq("id", story_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	return bool(response.data)


# ---------------------------------------------------------------------------
# Film Summary ("Resume de film") CRUD -- mirrors the anonymous_stories
# block above.
# ---------------------------------------------------------------------------

async def insert_film_summary(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not row:
		return None
	client = await get_client()
	response = await client.table(SUPABASE_FILM_SUMMARIES_TABLE).insert(row).execute()
	rows = response.data or []
	return rows[0] if rows else None


async def list_film_summaries(
	user_id: str,
	page: int,
	page_size: int,
	status: Optional[str] = None,
	query: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
	page = max(page, 1)
	page_size = min(max(page_size, 1), 100)
	offset = (page - 1) * page_size

	client = await get_client()
	q = (
		client.table(SUPABASE_FILM_SUMMARIES_TABLE)
		.select("*", count="exact")
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.order("created_at", desc=True)
		.range(offset, offset + page_size - 1)
	)

	if status:
		q = q.eq("status", status)
	if query:
		q = q.or_(_build_ilike_or_filter(query, ["title"]))

	response = await q.execute()
	return response.data or [], response.count or 0


async def list_film_summary_dates_since(user_id: str, since_iso: Optional[str]) -> List[str]:
	client = await get_client()
	q = (
		client.table(SUPABASE_FILM_SUMMARIES_TABLE)
		.select("created_at")
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
	)
	if since_iso:
		q = q.gte("created_at", since_iso)
	response = await q.execute()
	return [row["created_at"] for row in (response.data or []) if row.get("created_at")]


async def get_film_summary(film_summary_id: str, user_id: str) -> Optional[Dict[str, Any]]:
	if not film_summary_id or not user_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_FILM_SUMMARIES_TABLE)
		.select("*")
		.eq("id", film_summary_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def update_film_summary(film_summary_id: str, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	if not film_summary_id or not user_id:
		return None
	client = await get_client()
	payload = dict(updates or {})
	payload["updated_at"] = datetime.now(timezone.utc).isoformat()
	await (
		client.table(SUPABASE_FILM_SUMMARIES_TABLE)
		.update(payload)
		.eq("id", film_summary_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	return await get_film_summary(film_summary_id, user_id)


async def soft_delete_film_summary(film_summary_id: str, user_id: str) -> bool:
	if not film_summary_id or not user_id:
		return False
	client = await get_client()
	now_iso = datetime.now(timezone.utc).isoformat()
	response = (
		await client.table(SUPABASE_FILM_SUMMARIES_TABLE)
		.update({"deleted_at": now_iso, "updated_at": now_iso})
		.eq("id", film_summary_id)
		.eq("user_id", user_id)
		.is_("deleted_at", "null")
		.execute()
	)
	return bool(response.data)


# --------------------------------------------------------------------------
# Caption style themes (user-saved subtitle style presets)
# --------------------------------------------------------------------------
async def list_caption_style_themes(user_id: str) -> List[Dict[str, Any]]:
	if not user_id:
		return []
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTION_STYLE_THEMES_TABLE)
		.select("*")
		.eq("user_id", user_id)
		.order("updated_at", desc=True)
		.execute()
	)
	return response.data or []


async def upsert_caption_style_theme(user_id: str, name: str, style: Dict[str, Any]) -> Optional[Dict[str, Any]]:
	"""Create a custom theme, or overwrite the caller's own theme of the same
	name (unique on (user_id, name)) -- saving under a name the user already
	used updates that theme in place instead of erroring on a conflict."""
	if not user_id or not name:
		return None
	client = await get_client()
	payload = {
		"user_id": user_id,
		"name": name,
		"style": style or {},
		"updated_at": datetime.now(timezone.utc).isoformat(),
	}
	response = await client.table(SUPABASE_CAPTION_STYLE_THEMES_TABLE).upsert(
		payload,
		on_conflict="user_id,name",
	).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def delete_caption_style_theme(theme_id: str, user_id: str) -> bool:
	if not theme_id or not user_id:
		return False
	client = await get_client()
	response = (
		await client.table(SUPABASE_CAPTION_STYLE_THEMES_TABLE)
		.delete()
		.eq("id", theme_id)
		.eq("user_id", user_id)
		.execute()
	)
	return bool(response.data)


# --------------------------------------------------------------------------
# Media assets (physical-lifecycle registry -- one row per source upload or
# produced deliverable; see the 20261012 migration's module comment and
# retention_config.py / billing.add_retention_cost_to_breakdown for the
# policy and cost this table's rows are snapshotted from at creation time)
# --------------------------------------------------------------------------
MEDIA_ASSET_COLUMNS = (
	"id, created_at, user_id, content_kind, content_id, job_id, media_type, "
	"s3_bucket, s3_key, size_bytes, subscription_status_at_creation, "
	"retention_days, retention_started_at, retention_expires_at, "
	"s3_storage_cost_per_gb_day, retention_storage_cost_usd, "
	"retention_storage_credit_cost, billing_created_at, media_status, "
	"media_deleted_at, notified_before_expiry_at"
)

CONTENT_KIND_PROJECT_SOURCE = "project_source"
CONTENT_KIND_REEL = "reel"
CONTENT_KIND_CAPTION = "caption"
CONTENT_KIND_FILM_SUMMARY = "film_summary"
CONTENT_KIND_ANONYMOUS_STORY = "anonymous_story"

MEDIA_STATUS_AVAILABLE = "AVAILABLE"
MEDIA_STATUS_EXPIRED = "EXPIRED"
MEDIA_STATUS_DELETED = "DELETED"
MEDIA_STATUS_MISSING = "MISSING"


async def insert_media_asset(
	user_id: str,
	content_kind: str,
	content_id: str,
	media_type: str,
	subscription_status_at_creation: str,
	retention_days: int,
	retention_started_at: datetime,
	retention_expires_at: datetime,
	job_id: Optional[str] = None,
	s3_bucket: Optional[str] = None,
	s3_key: Optional[str] = None,
	size_bytes: Optional[int] = None,
	s3_storage_cost_per_gb_day: Optional[float] = None,
	retention_storage_cost_usd: Optional[float] = None,
	retention_storage_credit_cost: Optional[float] = None,
	billing_created_at: Optional[datetime] = None,
) -> Dict[str, Any]:
	"""Creates this media's lifecycle row, fixing its retention policy and
	billing snapshot forever (see _finalize_media_retention_billing in
	app.py -- this is called exactly once, at the moment the media's
	definitive size is known, and never updated afterward to reflect a
	later env var or subscription change)."""
	client = await get_client()
	payload = {
		"user_id": user_id,
		"content_kind": content_kind,
		"content_id": content_id,
		"job_id": job_id,
		"media_type": media_type,
		"s3_bucket": s3_bucket,
		"s3_key": s3_key,
		"size_bytes": int(size_bytes) if size_bytes is not None else None,
		"subscription_status_at_creation": subscription_status_at_creation,
		"retention_days": int(retention_days),
		"retention_started_at": retention_started_at.isoformat(),
		"retention_expires_at": retention_expires_at.isoformat(),
		"s3_storage_cost_per_gb_day": s3_storage_cost_per_gb_day,
		"retention_storage_cost_usd": retention_storage_cost_usd,
		"retention_storage_credit_cost": retention_storage_credit_cost,
		"billing_created_at": billing_created_at.isoformat() if billing_created_at else datetime.now(timezone.utc).isoformat(),
	}
	response = await client.table(SUPABASE_MEDIA_ASSETS_TABLE).insert(payload).execute()
	rows = response.data or []
	return rows[0] if rows else payload


async def get_media_asset_by_content(content_kind: str, content_id: str) -> Optional[Dict[str, Any]]:
	if not content_kind or not content_id:
		return None
	client = await get_client()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.select(MEDIA_ASSET_COLUMNS)
		.eq("content_kind", content_kind)
		.eq("content_id", content_id)
		.limit(1)
		.execute()
	)
	rows = response.data or []
	return rows[0] if rows else None


async def list_media_assets_by_content_ids(content_kind: str, content_ids: List[str]) -> Dict[str, Dict[str, Any]]:
	"""Batch lookup for list/detail endpoints that need to show expiration
	UI (see app.py's _attach_media_asset_fields) without an N+1 query per
	row -- returns a {content_id: row} map, one query for the whole page
	instead of one per item."""
	unique_ids = [cid for cid in dict.fromkeys(content_ids or []) if cid]
	if not content_kind or not unique_ids:
		return {}
	client = await get_client()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.select(MEDIA_ASSET_COLUMNS)
		.eq("content_kind", content_kind)
		.in_("content_id", unique_ids)
		.execute()
	)
	return {row["content_id"]: row for row in (response.data or []) if row.get("content_id")}


async def list_media_assets_due_for_expiration(now: Optional[datetime] = None, limit: int = 100) -> List[Dict[str, Any]]:
	"""AVAILABLE media whose retention_expires_at has passed, soonest-expired
	first -- the expiration sweep's own query shape (see
	process_media_expiration_jobs in app.py)."""
	client = await get_client()
	now_iso = (now or datetime.now(timezone.utc)).isoformat()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.select(MEDIA_ASSET_COLUMNS)
		.eq("media_status", MEDIA_STATUS_AVAILABLE)
		.lte("retention_expires_at", now_iso)
		.order("retention_expires_at", desc=False)
		.limit(min(max(limit, 1), 500))
		.execute()
	)
	return response.data or []


async def mark_media_asset_expired(media_id: str) -> bool:
	"""Only ever called after a confirmed successful S3 delete (see
	process_media_expiration_jobs) -- a failed/unconfirmed delete must never
	reach this, so an AVAILABLE row always means the file really is still
	there (or needs a MISSING flag instead, see mark_media_asset_missing)."""
	if not media_id:
		return False
	client = await get_client()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.update({
			"media_status": MEDIA_STATUS_EXPIRED,
			"media_deleted_at": datetime.now(timezone.utc).isoformat(),
		})
		.eq("id", media_id)
		.eq("media_status", MEDIA_STATUS_AVAILABLE)
		.execute()
	)
	return bool(response.data)


async def mark_media_asset_missing(media_id: str) -> bool:
	"""The object should be there but S3 can't find/reach it -- distinct
	from EXPIRED (deleted by our own retention sweep) and DELETED (deleted
	by the user), so an operator can tell these cases apart."""
	if not media_id:
		return False
	client = await get_client()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.update({"media_status": MEDIA_STATUS_MISSING})
		.eq("id", media_id)
		.execute()
	)
	return bool(response.data)


async def mark_media_asset_deleted(media_id: str) -> bool:
	"""For the user-initiated delete flow (see _delete_s3_and_get_freed_bytes
	and friends in app.py) -- not yet wired into that flow, but kept
	symmetrical with mark_media_asset_expired/missing for when it is."""
	if not media_id:
		return False
	client = await get_client()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.update({
			"media_status": MEDIA_STATUS_DELETED,
			"media_deleted_at": datetime.now(timezone.utc).isoformat(),
		})
		.eq("id", media_id)
		.execute()
	)
	return bool(response.data)


async def list_produced_media_due_for_notification(notify_before_time: Optional[datetime] = None, limit: int = 100) -> List[Dict[str, Any]]:
	"""PRODUCED, still-AVAILABLE, not-yet-notified media expiring at or
	before ``notify_before_time`` (the caller passes now + the configured
	RETENTION_NOTIFICATION_HOURS_BEFORE lead time) -- source media is never
	returned here, per the spec's "don't notify for source media" rule."""
	client = await get_client()
	before_iso = (notify_before_time or datetime.now(timezone.utc)).isoformat()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.select(MEDIA_ASSET_COLUMNS)
		.eq("media_status", MEDIA_STATUS_AVAILABLE)
		.eq("media_type", "produced")
		.is_("notified_before_expiry_at", "null")
		.lte("retention_expires_at", before_iso)
		.order("retention_expires_at", desc=False)
		.limit(min(max(limit, 1), 500))
		.execute()
	)
	return response.data or []


async def mark_media_asset_notified(media_id: str, when: Optional[datetime] = None) -> bool:
	"""Idempotency guard for the expiry-notification sweep -- once set, this
	media's notified_before_expiry_at is never cleared, so a given expiry
	can only ever produce one notification."""
	if not media_id:
		return False
	client = await get_client()
	response = (
		await client.table(SUPABASE_MEDIA_ASSETS_TABLE)
		.update({"notified_before_expiry_at": (when or datetime.now(timezone.utc)).isoformat()})
		.eq("id", media_id)
		.is_("notified_before_expiry_at", "null")
		.execute()
	)
	return bool(response.data)


