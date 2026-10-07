"""Film Summary ("Resume de film"): turn a full movie (upload or YouTube
link) into a condensed, narrated cinematic summary -- transcript -> scene
detection -> AI narrative planning -> user review -> TTS voice-over ->
FFmpeg assembly.

Like anonymous_stories.py, this module holds only the feature's pure/
validation logic, its prompts, and its external-API/subprocess calls behind
small functions; request handling, credits, S3 and Supabase persistence
stay in app.py.

Engineering note on scope: the cahier des charges describes the narrative
pipeline as up to 10 separate persisted stages (chaptering, per-chapter
analysis, character/chronology reconstruction, spine selection, script
writing, clip matching, dialogue selection, each with their own JSON
artifact). This implementation consolidates chaptering through dialogue
selection into a single planning call (see PLANNING_SYSTEM_PROMPT /
generate_edit_plan) that is given the full transcript and scene index at
once and asked to produce the same final edit-plan contract (section 10 of
the spec) end-to-end. The data contracts, job/credits/storage integration,
review/validation surface and acceptance criteria are otherwise unchanged;
splitting the planning call back into separate persisted stages later (for
very long films whose evidence no longer fits one context window) is a
natural follow-up that doesn't require changing this module's public
surface.
"""

import asyncio
import base64
import hashlib
import json
import os
import subprocess
import uuid
from typing import Any, Dict, List, Optional, Tuple


class FilmSummarySourceType:
    UPLOAD = "upload"
    YOUTUBE = "youtube"


class FilmSummaryStatus:
    DRAFT = "draft"
    QUEUED = "queued"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


# Fine-grained pipeline stage, persisted on the film_summaries row and used
# as the job's `current_step` (spec section 8 "Cycle de statuts"). See the
# module docstring for why ANALYZING_CHAPTERS/BUILDING_STORY/GENERATING_
# SCRIPT/MATCHING_CLIPS from the original spec are folded into PLANNING here.
class FilmSummaryStage:
    UPLOADING = "uploading"
    VALIDATING_MEDIA = "validating_media"
    VALIDATING_FILM = "validating_film"
    TRANSCRIBING = "transcribing"
    DETECTING_SCENES = "detecting_scenes"
    PLANNING = "planning"
    VALIDATING_PLAN = "validating_plan"
    AWAITING_USER_REVIEW = "awaiting_user_review"
    GENERATING_VOICE = "generating_voice"
    RENDERING_PREVIEW = "rendering_preview"
    RENDERING_FINAL = "rendering_final"
    ADDING_SUBTITLES = "adding_subtitles"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"
    CANCELLED = "cancelled"


# User-safe error codes (only the code is ever persisted; the frontend maps
# it to a translated message -- same convention as AnonymousStoryErrorCode).
class FilmSummaryErrorCode:
    INVALID_FORMAT = "INVALID_FORMAT"
    SOURCE_TOO_LARGE = "SOURCE_TOO_LARGE"
    SOURCE_TOO_LONG = "SOURCE_TOO_LONG"
    SOURCE_TOO_SHORT = "SOURCE_TOO_SHORT"
    NO_VIDEO_TRACK = "NO_VIDEO_TRACK"
    NO_AUDIO_TRACK = "NO_AUDIO_TRACK"
    INVALID_TARGET_DURATION = "INVALID_TARGET_DURATION"
    YOUTUBE_UNAVAILABLE = "YOUTUBE_UNAVAILABLE"
    NOT_A_FILM = "NOT_A_FILM"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    TRANSCRIPTION_FAILED = "TRANSCRIPTION_FAILED"
    SCENE_DETECTION_FAILED = "SCENE_DETECTION_FAILED"
    PLANNING_FAILED = "PLANNING_FAILED"
    PLAN_INVALID = "PLAN_INVALID"
    TTS_FAILED = "TTS_FAILED"
    RENDER_FAILED = "RENDER_FAILED"
    GENERATION_INVALID = "GENERATION_INVALID"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    JOB_CANCELLED = "JOB_CANCELLED"


# Single source of truth for the credit/storage history `operation_type`
# (see supabase_request.insert_user_data_history), same convention as
# anonymous_stories.CREDIT_OPERATION_TYPE -- must contain at most one
# underscore (see test_credit_operation_type_is_resume_film).
CREDIT_OPERATION_TYPE = "resume_film"

SEGMENT_TYPE_VOICE_OVER = "voice_over"
# "il ne dois y avoir aucune parole du film originale, uniquement les
# sequences videos + voix off de narration" -- voice_over is the only
# segment type a plan may ever contain; every clip's own audio is always
# fully replaced by the narration (see film_summary_render.duck_and_mix_
# narration), so no original film dialogue or audio is ever heard.
SEGMENT_TYPES = (SEGMENT_TYPE_VOICE_OVER,)

# Ideal ceiling on a film summary's total runtime: "dans l'ideal le resume
# dois etre de moins de 5mn, mais jamais cela deborde il ne dois pas y
# avoir de bloquant" -- kept as a changeable env-configurable constant,
# same convention as FILM_SUMMARY_PLANNING_MODEL below, but deliberately
# non-blocking: going over it only ever adds a warning in
# validate_edit_plan_content (every caller -- generate_edit_plan, and the
# /validate and /render endpoints that re-run that same validator -- still
# accepts the plan).
FILM_SUMMARY_MAX_PLAN_DURATION_MS = int(os.environ.get("FILM_SUMMARY_MAX_PLAN_DURATION_MS", str(5 * 60 * 1000)))

EDIT_PLAN_SCHEMA_VERSION = "1.0"


class FilmSummaryValidationError(ValueError):
    """Raised whenever validated content (media verdict, edit plan, user
    edit) fails validation. Carries the FilmSummaryErrorCode to persist, so
    callers never have to re-derive an error code from a free-form
    exception message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# Pure validation / normalization (spec sections 4-6, 13)
# ---------------------------------------------------------------------------

def derive_target_duration_seconds(
    source_duration_seconds: float, min_target_duration_seconds: float, max_target_duration_seconds: float,
) -> int:
    """Auto-compute a target summary duration from the source's length when
    the user didn't provide one (spec section 4 table: "Calcul automatique
    selon la duree du film si absent"). Uses a ~1/6 compression ratio,
    clamped to the configured bounds."""
    source = max(0.0, float(source_duration_seconds or 0.0))
    computed = source / 6.0
    return int(round(min(max(computed, min_target_duration_seconds), max_target_duration_seconds)))


def validate_target_duration_seconds(
    target_duration_seconds: Optional[float], min_target_duration_seconds: float, max_target_duration_seconds: float,
) -> None:
    if target_duration_seconds is None:
        return
    value = float(target_duration_seconds)
    if value < min_target_duration_seconds or value > max_target_duration_seconds:
        raise FilmSummaryValidationError(
            FilmSummaryErrorCode.INVALID_TARGET_DURATION,
            f"Target duration must be between {min_target_duration_seconds:.0f}s and "
            f"{max_target_duration_seconds:.0f}s (got {value:.0f}s).",
        )


def validate_technical_constraints(
    *,
    duration_seconds: float,
    size_bytes: float,
    has_video_track: bool,
    has_audio_track: bool,
    max_upload_size_bytes: float,
    min_source_duration_seconds: float,
    max_source_duration_seconds: float,
) -> None:
    """Niveau 1 technical validation (spec section 5). Raises
    FilmSummaryValidationError with a user-safe code/message on the first
    rule violated; never lets an unusable media reach the (costly)
    classification/transcription stages."""
    if max_upload_size_bytes > 0 and size_bytes > max_upload_size_bytes:
        raise FilmSummaryValidationError(
            FilmSummaryErrorCode.SOURCE_TOO_LARGE,
            f"File is too large ({size_bytes / (1024 ** 3):.2f} GB); "
            f"maximum allowed is {max_upload_size_bytes / (1024 ** 3):.2f} GB.",
        )
    if min_source_duration_seconds > 0 and duration_seconds < min_source_duration_seconds:
        raise FilmSummaryValidationError(
            FilmSummaryErrorCode.SOURCE_TOO_SHORT,
            f"Video is too short ({duration_seconds:.0f}s); minimum is {min_source_duration_seconds:.0f}s.",
        )
    if max_source_duration_seconds > 0 and duration_seconds > max_source_duration_seconds:
        raise FilmSummaryValidationError(
            FilmSummaryErrorCode.SOURCE_TOO_LONG,
            f"Video is too long ({duration_seconds / 60.0:.1f} min); "
            f"maximum is {max_source_duration_seconds / 60.0:.1f} min.",
        )
    if not has_video_track:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.NO_VIDEO_TRACK, "No decodable video track found.")
    if not has_audio_track:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.NO_AUDIO_TRACK, "No usable audio track found.")


REQUIRED_VERDICT_FIELDS = ("is_film", "confidence", "reason_code")


def validate_media_type_verdict(raw: Any) -> Dict[str, Any]:
    """Validate and normalize the classifier's JSON output against the
    schema from spec section 12. Raises FilmSummaryValidationError on a
    malformed payload -- a malformed classification is always a technical
    error, never silently treated as an accept/reject decision."""
    if not isinstance(raw, dict):
        raise FilmSummaryValidationError(FilmSummaryErrorCode.GENERATION_INVALID, "Classifier output is not a JSON object")
    for field in REQUIRED_VERDICT_FIELDS:
        if field not in raw:
            raise FilmSummaryValidationError(FilmSummaryErrorCode.GENERATION_INVALID, f"Missing field: {field}")

    try:
        confidence = float(raw.get("confidence"))
    except (TypeError, ValueError) as exc:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.GENERATION_INVALID, "confidence must be a number") from exc
    confidence = min(max(confidence, 0.0), 1.0)

    return {
        "is_film": bool(raw.get("is_film")),
        "confidence": confidence,
        "estimated_category": str(raw.get("estimated_category") or "").strip(),
        "positive_signals": [str(s) for s in (raw.get("positive_signals") or []) if str(s).strip()],
        "negative_signals": [str(s) for s in (raw.get("negative_signals") or []) if str(s).strip()],
        "reason_code": str(raw.get("reason_code") or "").strip() or "unknown",
        "user_message": str(raw.get("user_message") or "").strip(),
        "requires_secondary_review": bool(raw.get("requires_secondary_review")),
    }


def decide_film_verdict(verdict: Dict[str, Any], validation_threshold: float) -> str:
    """ACCEPTED / REVIEW / REJECTED decision from spec section 5 Niveau 2."""
    if verdict.get("requires_secondary_review"):
        return "REVIEW"
    is_film = bool(verdict.get("is_film"))
    confidence = float(verdict.get("confidence") or 0.0)
    if is_film and confidence >= validation_threshold:
        return "ACCEPTED"
    if not is_film and confidence >= validation_threshold:
        return "REJECTED"
    return "REVIEW"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def build_scene_index(scenes: List[Dict[str, Any]], transcript_segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Join detected scenes with overlapping transcript segments into the
    queryable index the planning prompt expects as `scene_index` (spec
    section 7 "Construire un index interrogeable"). Pure/deterministic --
    no AI call."""
    index = []
    for scene in scenes:
        start_ms = _safe_int(scene.get("start_ms"))
        end_ms = _safe_int(scene.get("end_ms"))
        overlapping = [
            seg for seg in transcript_segments
            if _safe_int(seg.get("end_ms")) > start_ms and _safe_int(seg.get("start_ms")) < end_ms
        ]
        speakers = sorted({str(seg.get("speaker")) for seg in overlapping if seg.get("speaker")})
        transcript_overlap = " ".join(str(seg.get("text") or "").strip() for seg in overlapping).strip()
        index.append({
            "scene_id": scene.get("scene_id"),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "duration_ms": max(0, end_ms - start_ms),
            "speakers": speakers,
            "transcript_overlap": transcript_overlap,
            "quality_flags": scene.get("quality_flags") or [],
        })
    return index


def build_transcript_sample(transcript_segments: List[Dict[str, Any]], max_chars: int = 4000) -> str:
    """Cheap, representative sample of the transcript for the Niveau 2
    classifier (spec section 5: "une transcription partielle repartie dans
    le temps") -- takes the start, middle and end thirds rather than just
    the head, so a film that only turns narrative midway isn't misjudged
    from its cold open alone."""
    texts = [str(seg.get("text") or "").strip() for seg in transcript_segments if seg.get("text")]
    if not texts:
        return ""
    budget = max(1, max_chars // 3)

    def _take(chunk: List[str], char_budget: int) -> str:
        out, total = [], 0
        for text in chunk:
            if total >= char_budget:
                break
            out.append(text)
            total += len(text) + 1
        return " ".join(out)

    n = len(texts)
    start_part = _take(texts[: max(1, n // 3)], budget)
    middle_part = _take(texts[n // 3: max(n // 3 + 1, 2 * n // 3)], budget)
    end_part = _take(texts[max(0, 2 * n // 3):], budget)
    return "\n...\n".join(p for p in (start_part, middle_part, end_part) if p)[:max_chars]


_AVERAGE_VOICE_OVER_SEGMENT_MS = 27500  # ~27s average voice-over block length (NARRATIVE RULE 8 lets individual blocks run shorter or longer)


def build_generation_constraints(
    target_duration_ms: int, duration_tolerance_ratio: float = 0.15,
) -> Dict[str, Any]:
    return {
        "target_duration_ms": target_duration_ms,
        "duration_tolerance_ratio": duration_tolerance_ratio,
        "min_voice_over_segment_seconds": 12,
        "max_voice_over_segment_seconds": 40,
        "hook_min_seconds": 20,
        "hook_max_seconds": 35,
        "conclusion_min_seconds": 25,
        "conclusion_max_seconds": 45,
        "words_per_minute_low": 125,
        "words_per_minute_high": 150,
        # A concrete sizing anchor for the model: tracking a running total
        # against a target across many segments is a self-consistency task
        # LLMs are prone to under- or overshoot on (observed misses as large
        # as -48% and +27% of target even when the prompt states the
        # tolerance in words) -- naming an approximate segment *count* up
        # front, not just a duration target, gives it a concrete plan to
        # build against instead of estimating durations in a vacuum.
        "approximate_total_segment_count_hint": max(1, round(target_duration_ms / _AVERAGE_VOICE_OVER_SEGMENT_MS)),
    }


def _normalize_clip(raw_clip: Any) -> Dict[str, Any]:
    if not isinstance(raw_clip, dict):
        return {}
    return {
        "scene_id": raw_clip.get("scene_id"),
        "start_ms": _safe_int(raw_clip.get("start_ms")),
        "end_ms": _safe_int(raw_clip.get("end_ms")),
        "description": str(raw_clip.get("description") or "").strip(),
        "match_score": float(raw_clip.get("match_score") or 0.0),
    }


_NARRATION_WORDS_PER_MINUTE = 135  # matches TTS_INSTRUCTIONS_TEMPLATE's stated narration pace


def estimate_narration_duration_ms(narration: str) -> int:
    """Formulaic duration estimate from a voice_over segment's narration text,
    at the same ~135 wpm pace given to the TTS model. Used to keep a user's
    edited plan (validate_edited_plan_patch) honest: the planning model's own
    estimated_duration_ms guess would otherwise stay frozen the moment the
    review UI lets someone shorten/lengthen the narration text, so the
    duration-tolerance check would never reflect their edit."""
    word_count = len(narration.split())
    if word_count == 0:
        return 0
    return max(1000, round(word_count / _NARRATION_WORDS_PER_MINUTE * 60000))


def _resolve_voice_over_estimated_duration_ms(
    raw: Any, narration: str, recompute_narration_estimates: bool,
) -> int:
    if recompute_narration_estimates:
        return estimate_narration_duration_ms(narration)
    return _safe_int(raw.get("estimated_duration_ms"))


def _normalize_segment(raw: Any, *, recompute_narration_estimates: bool = False) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise FilmSummaryValidationError(FilmSummaryErrorCode.PLAN_INVALID, "Segment must be a JSON object")
    seg_type = str(raw.get("type") or "").strip()
    if seg_type not in SEGMENT_TYPES:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.PLAN_INVALID, f"Unknown segment type: {seg_type}")

    narration = str(raw.get("narration") or "").strip()
    return {
        "id": str(raw.get("id") or f"seg_{uuid.uuid4().hex[:8]}"),
        "sequence": _safe_int(raw.get("sequence")),
        "type": seg_type,
        "approval_status": str(raw.get("approval_status") or "pending"),
        "narration": narration,
        "estimated_duration_ms": _resolve_voice_over_estimated_duration_ms(raw, narration, recompute_narration_estimates),
        "actual_duration_ms": _safe_int(raw.get("actual_duration_ms")) or None,
        "clips": [_normalize_clip(c) for c in (raw.get("clips") or []) if isinstance(c, dict)],
        "source_event_ids": [str(e) for e in (raw.get("source_event_ids") or [])],
    }


def validate_edit_plan_schema(
    raw: Any, *, movie_metadata: Dict[str, Any], target_duration_ms: int, recompute_narration_estimates: bool = False,
) -> Dict[str, Any]:
    """Validate and normalize the planning model's JSON output against the
    contract in spec section 10. Never trusts the model's own copy of
    `movie`/`target_duration_ms` -- those are always rebuilt backend-side
    from the authoritative values passed in, same principle as
    anonymous_stories.build_final_text.

    recompute_narration_estimates replaces each voice_over segment's
    estimated_duration_ms with a word-count-based estimate instead of
    trusting the caller's copy -- set by validate_edited_plan_patch so a
    user's narration edits actually move the validated total (see
    estimate_narration_duration_ms)."""
    if not isinstance(raw, dict):
        raise FilmSummaryValidationError(FilmSummaryErrorCode.PLAN_INVALID, "Plan output is not a JSON object")

    if raw.get("status") == "insufficient_evidence":
        raise FilmSummaryValidationError(
            FilmSummaryErrorCode.PLANNING_FAILED,
            str(raw.get("explanation") or "Insufficient evidence to build a coherent summary"),
        )

    segments_raw = raw.get("segments")
    if not isinstance(segments_raw, list) or not segments_raw:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.PLAN_INVALID, "Plan has no segments")
    segments = [_normalize_segment(s, recompute_narration_estimates=recompute_narration_estimates) for s in segments_raw]

    characters = [c for c in (raw.get("characters") or []) if isinstance(c, dict)]
    normalized_characters = [{
        "id": str(c.get("id") or f"char_{i + 1}"),
        "canonical_name": str(c.get("canonical_name") or "").strip(),
        "aliases": [str(a) for a in (c.get("aliases") or [])],
        "role": str(c.get("role") or "").strip(),
    } for i, c in enumerate(characters)]

    plan = {
        "schema_version": EDIT_PLAN_SCHEMA_VERSION,
        "movie": dict(movie_metadata),
        "target_duration_ms": target_duration_ms,
        "characters": normalized_characters,
        "segments": segments,
        "total_estimated_duration_ms": compute_total_estimated_duration_ms(segments),
        "unresolved_ambiguities": [str(a) for a in (raw.get("unresolved_ambiguities") or [])],
    }
    return plan


def compute_total_estimated_duration_ms(segments: List[Dict[str, Any]]) -> int:
    return sum(_safe_int(seg.get("actual_duration_ms") or seg.get("estimated_duration_ms")) for seg in segments)


def _validate_segment_sequence_numbers(segments: List[Dict[str, Any]]) -> List[str]:
    sequences = [seg.get("sequence") for seg in segments]
    if sequences == sorted(sequences) and sequences == list(range(1, len(segments) + 1)):
        return []
    return ["Les numeros de sequence des segments doivent etre continus, en commencant a 1, dans l'ordre de lecture"]


def _validate_voice_over_segment(
    seg: Dict[str, Any], source_duration_ms: int, known_scene_ids: set,
) -> List[str]:
    errors = []
    if not str(seg.get("narration") or "").strip():
        # app.py's render pipeline skips the TTS call outright for blank
        # text (nothing to synthesize), so an empty narration never
        # becomes an audio file -- the segment's clip then keeps the
        # source video's own raw audio instead of the narrator's voice,
        # a stretch of the final video where "le son de narration ne
        # s'ecoute plus". Blocking (not a warning): every voice_over
        # segment must carry real narration before it can reach render.
        errors.append(f"Le segment {seg.get('id')} n'a aucune narration -- la voix off ne serait pas audible a cet endroit de la video")
    for clip in seg.get("clips") or []:
        start_ms, end_ms = clip.get("start_ms"), clip.get("end_ms")
        if start_ms is None or end_ms is None or start_ms < 0 or end_ms <= start_ms or end_ms > source_duration_ms:
            errors.append(f"Le segment {seg.get('id')} a un timecode de clip hors limites")
            continue
        if known_scene_ids and clip.get("scene_id") not in known_scene_ids:
            errors.append(f"Le segment {seg.get('id')} reference un scene_id inconnu {clip.get('scene_id')}")
    return errors


def _validate_segments(
    segments: List[Dict[str, Any]], source_duration_ms: int, known_scene_ids: set,
) -> List[str]:
    """Per-segment checks (type, narration presence, clip/timecode bounds,
    scene references). Split out of validate_edit_plan_content to keep
    that function's own cognitive complexity low. A segment whose type
    isn't voice_over (e.g. a pre-existing plan's original_dialogue/
    breathing segment, from before those types were retired -- "il ne
    dois y avoir aucune parole du film originale") is flagged as an
    unknown type rather than silently accepted."""
    errors: List[str] = []
    for seg in segments:
        seg_type = seg.get("type")
        if seg_type not in SEGMENT_TYPES:
            errors.append(f"Le segment {seg.get('id')} a un type inconnu {seg_type}")
        else:
            errors.extend(_validate_voice_over_segment(seg, source_duration_ms, known_scene_ids))
    return errors


def _validate_duration_tolerance(total_ms: int, target_ms: int, duration_tolerance_ratio: float) -> List[str]:
    if target_ms <= 0:
        return []
    tolerance_ms = target_ms * duration_tolerance_ratio
    if abs(total_ms - target_ms) <= tolerance_ms:
        return []
    return [
        f"La duree totale estimee de {total_ms}ms est en dehors de la tolerance de {duration_tolerance_ratio:.0%} "
        f"autour de la cible de {target_ms}ms"
    ]


def _validate_max_plan_duration(total_ms: int) -> List[str]:
    """Non-blocking: FILM_SUMMARY_MAX_PLAN_DURATION_MS is the ideal ceiling
    for a film summary's total runtime (automatic or manual), independent
    of -- and checked in addition to -- the target-duration tolerance
    above, but going over it must never block generation/validation ("il
    ne dois pas y avoir de bloquant") -- it's surfaced as a warning only,
    never added to `errors`."""
    if total_ms <= FILM_SUMMARY_MAX_PLAN_DURATION_MS:
        return []
    return [
        f"La duree totale estimee de {total_ms}ms depasse la duree ideale de "
        f"{FILM_SUMMARY_MAX_PLAN_DURATION_MS}ms pour un resume de film"
    ]


def validate_edit_plan_content(
    plan: Dict[str, Any], *, source_duration_ms: int, valid_scene_ids: Optional[List[str]] = None,
    duration_tolerance_ratio: float = 0.15,
) -> Dict[str, Any]:
    """Deterministic plan validation (spec section 13 / the "Controle |
    Echec si" table): bounds, references, duration tolerance, overlap,
    chronology and repetition. Pure and side-effect free -- returns a
    report instead of raising, so callers (both the automatic pipeline
    stage and the manual /validate endpoint) can decide what to do with
    non-fatal warnings. Each check lives in its own _validate_* helper
    above; this function only orchestrates and merges their results, to
    keep its own cognitive complexity low."""
    known_scene_ids = set(valid_scene_ids or [])
    segments = plan.get("segments") or []

    errors: List[str] = [] if segments else ["Le plan ne contient aucun segment"]
    errors.extend(_validate_segment_sequence_numbers(segments))
    errors.extend(_validate_segments(segments, source_duration_ms, known_scene_ids))

    total_ms = compute_total_estimated_duration_ms(segments)
    target_ms = int(plan.get("target_duration_ms") or 0)
    errors.extend(_validate_duration_tolerance(total_ms, target_ms, duration_tolerance_ratio))
    warnings: List[str] = list(_validate_max_plan_duration(total_ms))

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "total_estimated_duration_ms": total_ms,
    }


def _clamped_legacy_end_ms(end_ms: Any, source_duration_ms: int, max_overage_ms: int) -> Optional[int]:
    """source_duration_ms if end_ms overshoots it by no more than
    max_overage_ms (the known truncation window -- see
    _clamp_legacy_duration_truncation_overage), else None when end_ms
    needs no clamping."""
    if isinstance(end_ms, int) and source_duration_ms < end_ms <= source_duration_ms + max_overage_ms:
        return source_duration_ms
    return None


def _clamp_voice_over_clips_overage(
    clips: List[Dict[str, Any]], source_duration_ms: int, max_overage_ms: int,
) -> Tuple[List[Dict[str, Any]], bool]:
    changed = False
    fixed_clips = []
    for clip in clips:
        clip = dict(clip)
        clamped = _clamped_legacy_end_ms(clip.get("end_ms"), source_duration_ms, max_overage_ms)
        if clamped is not None:
            clip["end_ms"] = clamped
            changed = True
        fixed_clips.append(clip)
    return fixed_clips, changed


def _clamp_legacy_duration_truncation_overage(
    segments: List[Dict[str, Any]], source_duration_ms: int, max_overage_ms: int = 999,
) -> Tuple[List[Dict[str, Any]], bool]:
    """Repairs a pre-existing precision-loss bug: source_duration_seconds
    used to be stored truncated to a whole second (losing up to 999ms of
    precision), so a segment/clip whose end_ms was valid against the
    full-precision duration used when the plan was first generated can
    overshoot the now-reconstituted (truncated) source_duration_ms by
    exactly that much. Clamping only an overage within that known bound --
    never a bigger one, which would be a real out-of-bounds plan -- lets
    an already-affected film summary render instead of staying
    permanently stuck on "timecode hors limites", without weakening the
    bounds check for anything else."""
    changed = False
    fixed_segments = []
    for seg in segments:
        seg = dict(seg)
        seg["clips"], clips_changed = _clamp_voice_over_clips_overage(
            seg.get("clips") or [], source_duration_ms, max_overage_ms,
        )
        changed = changed or clips_changed
        fixed_segments.append(seg)
    return fixed_segments, changed


def realign_plan_target_duration(
    plan: Dict[str, Any], *, source_duration_ms: int, valid_scene_ids: Optional[List[str]] = None,
    duration_tolerance_ratio: float = 0.15,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The target duration is a goal handed to the planning model for the
    cut, not a contract the end user must personally satisfy afterwards --
    they have no direct way to hit an exact millisecond total, and
    generate_edit_plan's own corrective retry already gave the model its
    best shot at converging during planning. So once segmentation is done
    (fresh out of generate_edit_plan, after a user's narration edit in
    validate_edited_plan_patch, or on a plan generated before this existed),
    if the actual total still lands outside the tolerance band, the target
    is snapped to that total instead of leaving the plan permanently stuck
    on a duration mismatch. Returns (plan, validation_report); the plan is
    the same object, unchanged, when already within tolerance.

    Also repairs the legacy duration-truncation bug described in
    _clamp_legacy_duration_truncation_overage before validating."""
    clamped_segments, clamped = _clamp_legacy_duration_truncation_overage(plan.get("segments") or [], source_duration_ms)
    if clamped:
        plan = dict(plan)
        plan["segments"] = clamped_segments

    total_ms = compute_total_estimated_duration_ms(plan.get("segments") or [])
    target_ms = int(plan.get("target_duration_ms") or 0)
    if target_ms > 0 and abs(total_ms - target_ms) > target_ms * duration_tolerance_ratio:
        plan = dict(plan)
        plan["target_duration_ms"] = total_ms
    validation_report = validate_edit_plan_content(
        plan, source_duration_ms=source_duration_ms, valid_scene_ids=valid_scene_ids,
        duration_tolerance_ratio=duration_tolerance_ratio,
    )
    return plan, validation_report


def validate_edited_plan_patch(raw: Any, *, movie_metadata: Dict[str, Any], target_duration_ms: int) -> Dict[str, Any]:
    """Validate a user-submitted plan edit (PATCH body) before persisting --
    reuses the same schema validator the AI output goes through, so an
    edited plan can never drift out of the contract shape. Recomputes
    voice_over estimated_duration_ms from the (possibly just-edited)
    narration text so shortening/lengthening a segment in the review UI
    actually changes the validated total instead of being silently ignored."""
    return validate_edit_plan_schema(
        raw, movie_metadata=movie_metadata, target_duration_ms=target_duration_ms, recompute_narration_estimates=True,
    )


def _clip_signature(clip: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (clip.get("scene_id"), clip.get("start_ms"), clip.get("end_ms"))


_NARRATION_TRANSLATION_INVARIANT_SEGMENT_FIELDS = ("id", "type", "sequence", "estimated_duration_ms", "source_event_ids")


def _narration_translation_segment_signature(seg: Dict[str, Any]) -> Dict[str, Any]:
    """The subset of a segment's fields a narration translation must never
    touch (see validate_narration_translation_structure) -- everything
    except `narration` itself (`actual_duration_ms`, which the translation
    call never sets, is excluded too)."""
    signature = {field: seg.get(field) for field in _NARRATION_TRANSLATION_INVARIANT_SEGMENT_FIELDS}
    signature["clips"] = [_clip_signature(c) for c in (seg.get("clips") or [])]
    return signature


def validate_narration_translation_structure(original_plan: Dict[str, Any], translated_plan: Dict[str, Any]) -> None:
    """The one invariant translate_edit_plan_narration's model must never
    violate: the translated plan has exactly the same segments, in the
    same order -- same id/type/sequence/clips/estimated_duration_ms/
    source_event_ids as the original plan -- only each segment's
    `narration` text may differ (total_estimated_duration_ms/unresolved_
    ambiguities may be recomputed from it).

    Raises FilmSummaryValidationError(PLAN_INVALID, ...) on any violation;
    returns None when the invariant holds."""
    original_segments = original_plan.get("segments") or []
    translated_segments = translated_plan.get("segments") or []
    if len(original_segments) != len(translated_segments):
        raise FilmSummaryValidationError(
            FilmSummaryErrorCode.PLAN_INVALID,
            f"Translated plan has {len(translated_segments)} segments, expected exactly "
            f"{len(original_segments)} (same count, same order, as the original plan)",
        )

    for original_seg, translated_seg in zip(original_segments, translated_segments):
        original_signature = _narration_translation_segment_signature(original_seg)
        translated_signature = _narration_translation_segment_signature(translated_seg)
        if original_signature != translated_signature:
            raise FilmSummaryValidationError(
                FilmSummaryErrorCode.PLAN_INVALID,
                f"Translated segment {translated_seg.get('id')} must keep every field unchanged except "
                f"narration -- expected {original_signature}, got {translated_signature}",
            )


def tts_cache_key(text: str, model: str, voice: str, instructions: str) -> str:
    """Idempotency cache key for TTS generation (spec section 14: "Cache
    par hash texte + modele + voix + instructions") -- lets a retry skip
    segments whose audio was already generated."""
    payload = json.dumps({"text": text, "model": model, "voice": voice, "instructions": instructions}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def apply_actual_tts_durations(plan: Dict[str, Any], actual_durations_ms: Dict[str, int]) -> Dict[str, Any]:
    """Re-inject real TTS durations into voice_over segments and recompute
    the plan total (spec section 7.9: "les durees reelles sont reinjectees
    dans le plan"). Returns a new plan dict; never mutates the input."""
    segments = []
    for seg in plan.get("segments") or []:
        seg = dict(seg)
        if seg.get("type") == SEGMENT_TYPE_VOICE_OVER and seg.get("id") in actual_durations_ms:
            seg["actual_duration_ms"] = int(actual_durations_ms[seg["id"]])
        segments.append(seg)
    new_plan = dict(plan)
    new_plan["segments"] = segments
    new_plan["total_estimated_duration_ms"] = compute_total_estimated_duration_ms(segments)
    return new_plan


# ---------------------------------------------------------------------------
# Prompts (spec sections 11, 12, 14) -- kept as plain strings and combined
# with a separate JSON user message rather than str.format()/f-string
# interpolation, since the master prompt's own OUTPUT CONTRACT example
# contains literal `{`/`}` braces (same defensive pattern as
# anonymous_stories.build_story_prompt).
# ---------------------------------------------------------------------------

MEDIA_VALIDATOR_SYSTEM_PROMPT = """You are Vireel's Media Type Validator. Determine whether the supplied evidence represents a narrative movie suitable for the Film Summary feature.

Use only the supplied metadata, distributed transcript samples, scene statistics and keyframe descriptions. Do not infer a movie merely because the title contains words such as “film” or “movie”. Consider the overall audiovisual structure.

A suitable movie normally contains recurring characters, acted or staged scenes, narrative progression, character goals, conflict, consequences and multiple connected sequences. It may be short or feature-length and may belong to drama, romance, comedy, family, action or another narrative genre.

Reject podcasts, interviews, tutorials, lectures, news, factual presentations, music performances, compilations, gameplay, screen recordings, static-image videos, corrupted media and other content without a sustained cinematic narrative. Documentary acceptance is disabled unless the input policy explicitly enables it.

Return JSON only:
{
  "is_film": true,
  "confidence": 0.0,
  "estimated_category": "narrative_film",
  "positive_signals": [],
  "negative_signals": [],
  "reason_code": "accepted",
  "user_message": "",
  "requires_secondary_review": false
}

confidence must be between 0 and 1. Use requires_secondary_review when evidence is contradictory or confidence is close to the configured threshold. Never claim certainty unsupported by the evidence."""


PLANNING_SYSTEM_PROMPT = """You are Vireel's Film Summary Planning Engine. You combine the judgment of a film editor, screenwriter, script doctor, narrative analyst, and high-retention video storyteller. Your task is to transform verified movie evidence into a cinematic summary and a machine-executable edit plan.

You do not have permission to invent facts. Treat the supplied transcript, chapter analyses, scene index, keyframe descriptions, character bible, and chronology as the only source of truth. If evidence is ambiguous, preserve the ambiguity or use neutral wording. Never invent a character, relationship, event, marriage, death, pregnancy, betrayal, motive, location, revelation, dialogue, image, or timecode.

INPUTS
- movie_metadata: title, source duration, source language and technical metadata
- target_duration_ms: requested final duration
- narration_language: language of the generated voice-over
- narration_style: requested storytelling style
- scene_index: every usable scene with scene_id, start_ms, end_ms, keyframe descriptions, visible characters, actions, locations, emotions, transcript overlap and quality flags
- transcript_segments: exact transcript text with start_ms, end_ms and speaker identifiers where available
- generation_constraints: segment, clip, duration and safety limits

PRIMARY GOAL
Create a condensed version of the movie that plays like a real editor's recap cut, not a flat synopsis or a plot-point checklist. The audience must understand the plot, relationships, motivations, conflicts, major reversals, climax, resolution and meaningful character evolution -- through specific, named, evidence-backed particulars (who, where, what exact stakes), never through generic or interchangeable phrasing that could describe almost any movie. If a sentence you drafted could be pasted into a summary of a completely different film without anyone noticing, rewrite it with the actual confirmed detail that makes it true of THIS movie and no other. Respect the original movie and never mock its characters.

NARRATIVE RULES
1. Always open with a brief narrative introduction (roughly 10-to-20 seconds) that orients the viewer before any plot action is narrated: state the film's setting (time period, place, world or milieu) and introduce its central character(s) by canonical name and role, in plain scene-setting narration -- the way a storyteller frames "this is the story of NAME, a ROLE in PLACE" before diving in. Only after this orientation, continue into a compelling 20-to-35-second hook based on a confirmed paradox, conflict, transformation, impossible relationship, betrayal, dramatic consequence or extraordinary situation, intriguing the viewer without needlessly exposing the ending. The introduction and the hook may be written as one combined opening voice-over block or as two consecutive blocks, whichever reads more naturally -- but the setting/character orientation must always come first, never the hook or plot action alone.
2. Be concrete, never generic. Anchor every segment in specific, evidence-backed particulars: characters by their canonical name (never "the man," "someone," "a woman"), specific places, specific objects, specific numbers (ages, amounts of money, elapsed time, counts) and the specific stakes of that moment. A line that only asserts a generic escalation ("things get complicated," "the situation gets worse," "everything changes") is incomplete on its own -- it must be paired, in the same or the very next sentence, with the specific confirmed fact that makes it true. Write like an editor who actually watched this movie and is telling a friend exactly what happens in it, not like someone paraphrasing a synopsis they skimmed.
3. Select only events required to understand the story, preserve its main emotional progression and reach the resolution naturally.
4. Remove repetition, inconsequential conversations, unnecessary travel, redundant explanations and secondary plots that do not affect the main story.
5. Never remove an event required to understand a later event.
6. Write natural, cinematic, emotionally precise narration suitable for AI speech. Never say “in this scene,” “we can see,” “the transcript says,” or similar analytical phrases.
7. Map the summary onto a real story structure, not a flat chronological list of things that happen: the opening setting/character introduction and hook (NARRATIVE RULE 1), an opening status quo, the inciting incident that sets the real story in motion, two to four rising complications that escalate in stakes (not just in number), a midpoint turn where the situation changes in kind rather than merely in degree, the climax, and the resolution. Every segment should serve one identifiable beat in this structure -- if you cannot say which beat a segment serves, cut it or fold it into an adjacent one.
8. Voice-over blocks average around 27 seconds, but do not force every block to the same length -- vary it with the story's own rhythm the way an editor would: a fast run of escalating complications can use a few shorter ~12-to-20-second blocks back to back, while a pivotal emotional beat can justify a longer ~30-to-40-second block. Contain enough words for the declared duration; estimate speech at 125 to 150 words per minute, while recognizing that the backend will replace estimates with actual TTS durations.
9. Each voice-over block must advance the story and should end with a useful transition, question, tension point or new information when this arises naturally.
10. End with a 25-to-45-second reflection grounded in the movie's confirmed character evolution and theme. Do not impose an unsupported moral.

VISUAL MATCHING RULES
1. Use only scene IDs and timecodes present in scene_index or transcript_segments.
2. Every start_ms must be greater than or equal to zero, every end_ms must be greater than start_ms, and no end_ms may exceed the source duration.
3. Match images to the narrated action, reaction, relationship, location or consequence. A generic shot of a mentioned character is not sufficient when a more specific confirmed scene exists.
4. Prefer several short, relevant clips over one excessively long range. Avoid black frames, credits, slates, blurred frames and transition frames when quality flags identify them.
5. Preserve source chronology unless a clearly justified hook briefly previews a later confirmed event. After the hook, return to the natural beginning.
6. Never reuse the same exact clip (same scene_id and start_ms/end_ms) in more than one segment, except in a genuine case of absolute necessity where no other confirmed footage exists to illustrate that moment -- in every other situation, pick a different confirmed moment from the same scene, or a different scene entirely, instead.
7. The cumulative clip duration for a voice-over block must be compatible with that block's estimated narration duration. Small backend-adjustable differences are acceptable.
8. Never fabricate visual information based only on transcript dialogue. Use keyframe and scene evidence to confirm visual claims.

NO ORIGINAL AUDIO RULE
The final video must never play any of the original film's own dialogue, speech or audio -- only the narrated footage (video + voice-over). There is no "original dialogue" or "breathing" segment type: every segment is "voice_over", and its clips' own audio is always fully replaced by the narration. Never write narration that merely describes a line of dialogue happening off-screen as a substitute for quoting it -- paraphrase the confirmed content and meaning of the moment instead, in your own narration.

DURATION RULES
The total duration is the sum of every voice-over block's estimated_duration_ms. Keep total_estimated_duration_ms within the tolerance supplied in generation_constraints. Do not pretend that a short sentence lasts 30 seconds. Never solve a duration deficit by selecting irrelevant footage or repeating information. Before writing segments, use generation_constraints.approximate_total_segment_count_hint as your sizing anchor: it is roughly target_duration_ms divided by a typical ~27-second voice-over block, so plan for approximately that many segments. Individual blocks may run shorter or longer than that average per NARRATIVE RULE 8, but producing far fewer segments than the hint, or making most voice-over blocks much shorter than average to compensate, is the most common way plans miss the duration tolerance -- if your draft segment count is well below the hint, add more voice-over blocks covering additional confirmed plot points rather than inflating estimated_duration_ms on existing ones.

EVIDENCE AND UNCERTAINTY
Every narrated segment must include source_event_ids. Every clip must reference a valid scene_id. When names are uncertain, use the canonical identity from character_bible or neutral wording. Add unresolved issues to unresolved_ambiguities. If the evidence cannot support a coherent summary, return status="insufficient_evidence" and explain the blocking evidence gaps without generating fake content.

OUTPUT SCHEMA
Return exactly this JSON shape -- every field below is required unless marked optional, and no other top-level or segment field names are read:
{
  "status": "ok" | "insufficient_evidence"   (optional, default "ok"),
  "explanation": string   (required only when status is "insufficient_evidence"),
  "characters": [ { "id": string, "canonical_name": string, "aliases": [string], "role": string } ],
  "segments": [ <segment, see below> ],
  "total_estimated_duration_ms": integer   (your own best-effort sum, backend recomputes the authoritative value),
  "unresolved_ambiguities": [string]
}
Every segment is a JSON object with these fields:
- "id": a stable unique string you invent (e.g. "seg_01").
- "sequence": REQUIRED integer. Segments MUST be numbered 1, 2, 3, ... with no gaps and no repeats, strictly in playback order -- segment N's sequence is always exactly N. This is validated mechanically; a missing, duplicated, non-integer or out-of-order sequence value fails the plan outright.
- "type": always "voice_over" -- this is the only segment type (see NO ORIGINAL AUDIO RULE).
- "narration": string, the spoken voice-over text.
- "estimated_duration_ms": integer, your best estimate of this block's spoken duration.
- "source_event_ids": [string], the story events/evidence this narration is based on.
- "clips": [ { "scene_id": string (must exist in scene_index), "start_ms": integer, "end_ms": integer, "description": string, "match_score": number 0-1 } ].

OUTPUT CONTRACT
Return JSON only. Do not use Markdown. Do not include commentary before or after the JSON. The output must validate against the OUTPUT SCHEMA above exactly -- do not add, rename or omit fields. Use integer milliseconds for all durations and timecodes. Every segment's type is exactly "voice_over". Keep segments in playback order with contiguous 1-based sequence numbers and stable unique IDs.

Before returning the JSON, silently verify:
- every segment has an integer "sequence" field, and the full list is exactly 1, 2, 3, ... with no gaps, duplicates or reordering;
- every segment's "type" is "voice_over" -- the final video must never play any of the original film's own dialogue or audio, only narrated footage;
- all important story claims are supported;
- every scene_id and timecode exists and remains within bounds;
- chronology is coherent;
- no clips overlap incompatibly;
- narration length agrees with estimated duration;
- no clip (same scene_id and start_ms/end_ms) is used in more than one segment unless genuinely unavoidable, and repeated facts are minimized;
- the target duration tolerance is respected;
- every voice_over segment's "narration" is non-empty -- an empty one never reaches the audience as speech, leaving that stretch of the video with no narration audible at all;
- the opening introduces the film's setting and principal characters by name before any hook or plot action is narrated (NARRATIVE RULE 1);
- the hook, main progression, climax, resolution and conclusion are present when supported by the movie;
- the setup, inciting incident, rising complications, midpoint turn, climax and resolution are each identifiable in at least one segment;
- every segment names its characters, places and objects specifically rather than generically, and no segment is a generic sentence that could describe almost any movie;
- the result can be executed by an automated FFmpeg pipeline."""


# Appended as a separate system message (never merged into the verbatim
# prompt above) explaining that this deployment consolidates the
# chapter/story-bible/spine pre-computation stages the master prompt was
# originally designed to receive as separate inputs -- see module docstring.
PLANNING_CONSOLIDATION_NOTE = (
    "OPERATIONAL NOTE: chapter_analyses, character_bible, chronology and story_spine were not "
    "pre-computed separately in this deployment. Derive them internally from transcript_segments "
    "and scene_index as part of this single pass, then produce the same OUTPUT CONTRACT JSON "
    "(schema_version, movie, target_duration_ms, characters, segments, total_estimated_duration_ms, "
    "unresolved_ambiguities)."
)


# Narrower than PLANNING_SYSTEM_PROMPT (see translate_edit_plan_narration):
# the plan -- footage, timing, segment structure -- is already final and
# approved; the only thing wrong with it is the narration's language ("il
# arrive qu'on ait fait une mauvaise selection au debut"). The model's only
# job is to translate text, never to re-edit.
NARRATION_TRANSLATION_SYSTEM_PROMPT = """You are Vireel's Film Summary Narration Translation Engine. An edit plan for a film summary already exists -- its footage, timing and segment structure are final and approved. The only problem is that its narration was written in the wrong language. Your ONLY job is to translate the spoken narration text of each voice_over segment into the requested target_language. You do not edit, re-cut, re-order, re-group, add, remove or re-time anything else.

You have no permission to change any field other than a voice_over segment's "narration". Every other field -- "id", "type", "sequence", "clips" (and every clip's "scene_id", "start_ms", "end_ms"), "estimated_duration_ms", "source_event_ids" and "characters" -- must be copied byte-for-byte identical to the input, in the same order, same count.

INPUTS
- movie_metadata: title, source duration, source language and technical metadata
- target_language: the language to translate every voice_over segment's narration into
- characters, segments: the existing plan's own fields, to copy through (segments' narration aside) exactly as given

TRANSLATION RULES
1. Translate only the "narration" string of each voice_over segment into target_language. Preserve its meaning, tone and register -- a natural, cinematic, emotionally precise translation suitable for AI speech, not a literal word-for-word rendering.
2. Never shorten, lengthen, embellish, summarize or otherwise rewrite the narration's content beyond what translation requires. Keep roughly the same information density and pacing.
3. Leave "estimated_duration_ms" exactly as given, even though the translated text's natural spoken length may differ slightly -- the backend recomputes real durations from actual TTS output, not from this estimate.

OUTPUT SCHEMA
Return exactly this JSON shape -- every field required unless marked optional:
{
  "status": "ok"   (optional, default "ok"),
  "characters": [ <copied through unchanged> ],
  "segments": [ <segment, see below -- same count and order as the input> ],
  "total_estimated_duration_ms": integer   (your own best-effort sum, backend recomputes the authoritative value),
  "unresolved_ambiguities": [string]   (may be empty)
}
Each segment object must have exactly the same shape and field values as the corresponding input segment, with this single exception: "narration" holds the translated text instead of the original. "id", "sequence", "type", "estimated_duration_ms", "source_event_ids" and "clips" are all copied through unchanged.

OUTPUT CONTRACT
Return JSON only. Do not use Markdown. Do not include commentary before or after the JSON.
Before returning the JSON, silently verify: the segment count, order, types, sequence numbers, clips, timecodes, estimated_duration_ms, source_event_ids and characters are all byte-for-byte identical to the input; only each voice_over segment's narration text has changed, and it is a faithful translation into target_language."""


TTS_INSTRUCTIONS_TEMPLATE = (
    "Speak in fluent {{LANGUAGE}} as a cinematic film narrator. Use a natural, controlled and "
    "emotionally responsive delivery. Maintain clarity at approximately 135 words per minute. "
    "Respect punctuation and character names. Build tension subtly without exaggeration. Do not "
    "add, omit or paraphrase any words. Do not read stage directions, identifiers or timecodes."
)

# The ISO 639-1 codes this app's own language pickers use (dashboard's
# NARRATION_LANGUAGE_OPTIONS / FilmSummaryCreatePage's source-language
# select), mapped to the full English name a natural-language instruction
# sentence actually needs. A raw code dropped straight into the template
# ("Speak in fluent fr as a cinematic film narrator...") is meaningless to
# the TTS engine and was silently steering it toward English regardless of
# the narration_language the user chose.
_TTS_LANGUAGE_CODE_TO_NAME = {
    "fr": "French", "en": "English", "es": "Spanish",
    "de": "German", "it": "Italian", "pt": "Portuguese",
}


def _resolve_tts_language_name(language: str) -> str:
    return _TTS_LANGUAGE_CODE_TO_NAME.get((language or "").strip().lower(), language or "the narration language")


def build_tts_instructions(language: str) -> str:
    return TTS_INSTRUCTIONS_TEMPLATE.replace("{{LANGUAGE}}", _resolve_tts_language_name(language))


# ---------------------------------------------------------------------------
# External calls (OpenAI classification/planning/TTS, AssemblyAI
# transcription, PySceneDetect scene detection, ffmpeg/ffprobe assembly).
# ---------------------------------------------------------------------------

def _get_openai_client():
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key or api_key == "your_openai_key":
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _usage_dict(response, model_name: str) -> Dict[str, Any]:
    usage = getattr(response, "usage", None)
    return {
        "prompt_tokens": int(getattr(usage, "prompt_tokens", 0) or 0),
        "completion_tokens": int(getattr(usage, "completion_tokens", 0) or 0),
        "model": model_name,
    }


async def classify_media_type(
    *, metadata: Dict[str, Any], transcript_sample: str, scene_stats: Dict[str, Any],
    keyframe_data_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Niveau 2 classification (spec section 12): cheap sampling-based
    verdict on whether the source is a narrative film, before the full
    (costly) pipeline runs. Raises FilmSummaryValidationError on a
    malformed model response, RuntimeError for transport/config failures."""
    client = _get_openai_client()
    model_name = os.environ.get("FILM_SUMMARY_CLASSIFIER_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))

    evidence = {"metadata": metadata, "transcript_sample": transcript_sample, "scene_stats": scene_stats}
    user_content: Any
    if keyframe_data_urls:
        user_content = [{"type": "text", "text": json.dumps(evidence)}]
        for data_url in keyframe_data_urls[:6]:
            user_content.append({"type": "image_url", "image_url": {"url": data_url}})
    else:
        user_content = json.dumps(evidence)

    def _call():
        return client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": MEDIA_VALIDATOR_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=800,
            response_format={"type": "json_object"},
        )

    response = await asyncio.to_thread(_call)
    raw_text = response.choices[0].message.content
    try:
        raw = json.loads(raw_text)
    except (TypeError, ValueError) as exc:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.GENERATION_INVALID, f"Invalid JSON from classifier: {exc}") from exc

    verdict = validate_media_type_verdict(raw)
    verdict["usage"] = _usage_dict(response, model_name)
    return verdict


def _call_planning_model(client, model_name: str, messages: List[Dict[str, Any]]):
    # A long source (many confirmed plot points -> many segments) can
    # produce an edit-plan JSON object that no longer fits in 8000 output
    # tokens, silently truncating mid-string -- json.loads then fails with
    # "Unterminated string ..." and, before generate_edit_plan's retry-on-
    # malformed-JSON handling, used to abort the whole request outright.
    # 16000 is gpt-4o's effective ceiling for this parameter; raising it
    # leaves much more headroom before that happens again.
    return client.chat.completions.create(
        model=model_name, messages=messages, temperature=0.6, max_tokens=16000,
        response_format={"type": "json_object"},
    )


def _describe_duration_gap(plan: Dict[str, Any], target_duration_ms: int) -> str:
    """Turns 'you missed the target' into a concrete number of segments to
    add or remove -- the bare validator message alone ("total X outside
    tolerance around Y") gave the model nothing to act on beyond re-guessing,
    which is exactly the failure mode this corrective retry exists to fix."""
    total_ms = int(plan.get("total_estimated_duration_ms") or 0)
    gap_ms = target_duration_ms - total_ms
    if gap_ms == 0:
        return ""
    segment_count = max(1, round(abs(gap_ms) / _AVERAGE_VOICE_OVER_SEGMENT_MS))
    if gap_ms > 0:
        return (
            f" Your plan is {gap_ms}ms short of the target: add approximately {segment_count} more "
            "voice-over segment(s) (~27s on average) covering additional confirmed plot points -- do not "
            "just inflate estimated_duration_ms on existing segments."
        )
    return (
        f" Your plan is {abs(gap_ms)}ms over the target: remove or shorten approximately {segment_count} "
        "segment(s), prioritizing the least essential voice-over blocks or dialogue moments, rather than "
        "shrinking every segment slightly."
    )


def _voice_over_clip_signature(clip: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    return (clip.get("scene_id"), clip.get("start_ms"), clip.get("end_ms"))


def _find_repeated_voice_over_clips(segments: List[Dict[str, Any]]) -> List[Tuple[str, Tuple[Any, Any, Any]]]:
    """Internal-only signal used exclusively by generate_edit_plan's own
    corrective retry below -- deliberately NOT part of
    validate_edit_plan_content/the user-facing validation report (clip
    reuse must never surface as an error or warning the user has to act
    on, see that function's docstring). Returns one (segment_id,
    signature) pair per voice_over clip whose exact (scene_id, start_ms,
    end_ms) signature already appeared earlier in plan order, so the
    corrective message can name exactly which repeats to fix."""
    seen: set = set()
    repeats: List[Tuple[str, Tuple[Any, Any, Any]]] = []
    for seg in segments:
        if seg.get("type") != SEGMENT_TYPE_VOICE_OVER:
            continue
        for clip in seg.get("clips") or []:
            signature = _voice_over_clip_signature(clip)
            if signature in seen:
                repeats.append((seg.get("id"), signature))
            else:
                seen.add(signature)
    return repeats


def _describe_repeated_voice_over_clips(repeats: List[Tuple[str, Tuple[Any, Any, Any]]]) -> str:
    return "; ".join(
        f"segment {seg_id} reuses the exact same clip (scene_id={scene_id}, start_ms={start_ms}, end_ms={end_ms}) "
        "already used earlier in the plan"
        for seg_id, (scene_id, start_ms, end_ms) in repeats
    )


def _deduplicate_voice_over_clips(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Final, unconditional guarantee that no exact clip (scene_id,
    start_ms, end_ms) ever reaches more than one segment in the plan
    generate_edit_plan returns -- "ne jamais utiliser la meme scene 2
    fois ... l'utilisateur ne dois pas intervenir": this must hold by
    construction, not merely by prompt instruction (VISUAL MATCHING RULE
    6) or by the best-effort corrective retry above, and it must never
    surface as an error/warning. Drops only the later duplicate
    occurrence's clip entry, keeping the first use and every other
    distinct clip in that segment untouched. A voice_over segment left
    with no clips at all falls back to render's existing blank-segment
    behavior (film_summary_render._build_voice_over_segment_clip) -- the
    same graceful path already used whenever a segment has no usable
    footage, instead of ever shipping a duplicate."""
    seen: set = set()
    deduped_segments = []
    for seg in segments:
        if seg.get("type") != SEGMENT_TYPE_VOICE_OVER or not seg.get("clips"):
            deduped_segments.append(seg)
            continue
        kept_clips = []
        for clip in seg["clips"]:
            signature = _voice_over_clip_signature(clip)
            if signature in seen:
                continue
            seen.add(signature)
            kept_clips.append(clip)
        deduped_segments.append({**seg, "clips": kept_clips})
    return deduped_segments


def _build_planning_correction_message(
    validation_report: Dict[str, Any], plan: Dict[str, Any], target_duration_ms: int, duration_tolerance_ratio: float,
    repeated_clips: Optional[List[Tuple[str, Tuple[Any, Any, Any]]]] = None,
) -> Dict[str, str]:
    errors = "; ".join(validation_report.get("errors") or [])
    warnings = "; ".join(validation_report.get("warnings") or [])
    # Recomputed directly instead of sniffing the (now user-facing, French)
    # error text for the word "duration" -- that substring match broke the
    # moment _validate_duration_tolerance's message got translated.
    total_ms = int(plan.get("total_estimated_duration_ms") or 0)
    duration_out_of_tolerance = (
        target_duration_ms > 0 and abs(total_ms - target_duration_ms) > target_duration_ms * duration_tolerance_ratio
    )
    duration_hint = _describe_duration_gap(plan, target_duration_ms) if duration_out_of_tolerance else ""
    repeated_clips_text = _describe_repeated_voice_over_clips(repeated_clips or [])

    sentences = []
    if errors:
        sentences.append(f"Your previous plan failed automated validation with these blocking errors: {errors}.")
    if warnings:
        # Non-blocking issues (e.g. an unknown character reference) are
        # still worth one corrective shot here, the same mechanism already
        # used for blocking errors, instead of relying only on the planning
        # prompt's own best-effort instructions.
        sentences.append(f"It also has these quality issues you should fix even though they did not block validation: {warnings}.")
    if repeated_clips_text:
        sentences.append(
            f"It also violates VISUAL MATCHING RULE 6 (never reuse the same exact clip unless genuinely "
            f"unavoidable): {repeated_clips_text}. Replace each of these with a different confirmed moment."
        )

    return {
        "role": "user",
        "content": (
            f"{' '.join(sentences)}{duration_hint} Return a corrected full plan (same OUTPUT SCHEMA, JSON only) "
            "that fixes every one of these issues while preserving everything else that was already correct."
        ),
    }


def _parse_planning_json_with_retry(
    raw_text: str, *, attempt: int, max_attempts: int, messages: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Shared JSON-parse-with-one-retry-on-truncation step used by every
    planning loop (generate_edit_plan, generate_narration_for_selected_
    clips): a long response can get cut off mid-string by max_tokens (see
    _call_planning_model), and json.loads then raises "Unterminated
    string ..." -- worth one corrective retry instead of failing the whole
    request outright, same mechanism as a validation-error retry.

    Returns the parsed dict on success. On a parse failure before the last
    attempt, appends the model's raw response plus a corrective follow-up
    onto `messages` (in place) and returns None -- the caller should
    `continue` its loop. Raises FilmSummaryValidationError once attempts
    are exhausted."""
    try:
        return json.loads(raw_text)
    except (TypeError, ValueError) as exc:
        if attempt == max_attempts - 1:
            raise FilmSummaryValidationError(FilmSummaryErrorCode.PLAN_INVALID, f"Invalid JSON from planning model: {exc}") from exc
        messages.append({"role": "assistant", "content": raw_text})
        messages.append({
            "role": "user",
            "content": (
                f"Your previous response was not valid, complete JSON ({exc}). Return the complete "
                "corrected plan as a single valid JSON object (same OUTPUT SCHEMA, JSON only), nothing else."
            ),
        })
        return None


async def generate_edit_plan(
    *, movie_metadata: Dict[str, Any], target_duration_ms: int, narration_language: str, narration_style: str,
    transcript_segments: List[Dict[str, Any]], scene_index: List[Dict[str, Any]],
    generation_constraints: Dict[str, Any],
) -> Dict[str, Any]:
    """Single consolidated planning call producing the edit-plan JSON
    contract (see module docstring). Raises FilmSummaryValidationError on a
    still-malformed response after exhausting every attempt, or an
    insufficient-evidence one (see validate_edit_plan_schema).

    Also self-corrects once on a truncated/malformed JSON response (most
    often max_tokens cut the response short on a long plan) -- same retry
    mechanism as below, just triggered by a json.loads failure instead of
    a validation one.

    Self-corrects once on a blocking validation failure (duration outside
    tolerance, non-contiguous sequence numbers, overlapping dialogue, ...)
    or a non-blocking warning (an unknown character reference, ...):
    LLM-produced plans occasionally violate a numeric/structural
    constraint, since keeping a running total consistent across many
    segments is a self-consistency task models don't reliably get right in
    one pass. Feeding the exact validation errors/warnings back as a
    corrective follow-up turn (keeping the model's own prior answer in
    context, rather than starting over) converges far more often than a
    fresh independent attempt would, at the cost of a second call only
    when the first one actually had something to fix. A warning that
    still isn't resolved after the retry is never blocking -- the user
    must always be able to render.

    Clip reuse (the same exact scene_id/start_ms/end_ms used in more than
    one voice_over segment) is never surfaced as an error or warning
    ("ne plus mettre d'avertissement pour cela") -- VISUAL MATCHING RULE 6
    in PLANNING_SYSTEM_PROMPT discourages it in the first place, and a
    repeat still present after a model response is also fed back as a
    silent corrective nudge (see _find_repeated_voice_over_clips/
    _build_planning_correction_message) the same way a validation warning
    is. But unlike every other check here, this one must never ship
    unresolved either ("ne jamais utiliser la meme scene 2 fois ...
    l'utilisateur ne dois pas intervenir") -- so after the loop below,
    _deduplicate_voice_over_clips deterministically strips any repeat
    still present in the returned plan, by construction, with no further
    model call and nothing for the user to notice or act on."""
    client = _get_openai_client()
    model_name = os.environ.get("FILM_SUMMARY_PLANNING_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o"))
    max_attempts = int(os.environ.get("FILM_SUMMARY_PLANNING_MAX_ATTEMPTS", "2"))

    payload = {
        "movie_metadata": movie_metadata,
        "target_duration_ms": target_duration_ms,
        "narration_language": narration_language,
        "narration_style": narration_style,
        "transcript_segments": transcript_segments,
        "scene_index": scene_index,
        "generation_constraints": generation_constraints,
    }
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
        {"role": "system", "content": PLANNING_CONSOLIDATION_NOTE},
        {"role": "user", "content": json.dumps(payload)},
    ]
    valid_scene_ids = [s.get("scene_id") for s in scene_index]
    source_duration_ms = int(movie_metadata.get("source_duration_ms") or 0)
    duration_tolerance_ratio = float(generation_constraints.get("duration_tolerance_ratio", 0.15))

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    plan: Dict[str, Any] = {}

    for attempt in range(max(1, max_attempts)):
        response = await asyncio.to_thread(_call_planning_model, client, model_name, messages)
        raw_text = response.choices[0].message.content
        usage = _usage_dict(response, model_name)
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

        raw = _parse_planning_json_with_retry(raw_text, attempt=attempt, max_attempts=max_attempts, messages=messages)
        if raw is None:
            continue

        plan = validate_edit_plan_schema(raw, movie_metadata=movie_metadata, target_duration_ms=target_duration_ms)

        validation_report = validate_edit_plan_content(
            plan, source_duration_ms=source_duration_ms, valid_scene_ids=valid_scene_ids,
            duration_tolerance_ratio=duration_tolerance_ratio,
        )
        repeated_clips = _find_repeated_voice_over_clips(plan.get("segments") or [])
        has_fixable_issue = not validation_report["valid"] or bool(validation_report["warnings"]) or bool(repeated_clips)
        if not has_fixable_issue or attempt == max_attempts - 1:
            break
        messages.append({"role": "assistant", "content": raw_text})
        messages.append(_build_planning_correction_message(
            validation_report, plan, target_duration_ms, duration_tolerance_ratio, repeated_clips,
        ))

    if plan.get("segments"):
        plan["segments"] = _deduplicate_voice_over_clips(plan["segments"])

    return {"plan": plan, "usage": total_usage}


# ---------------------------------------------------------------------------
# Narration (re)translation (see NARRATION_TRANSLATION_SYSTEM_PROMPT /
# translate_edit_plan_narration): lets the user fix a wrong narration
# language choice on an already-approved plan -- footage, timing and
# segment structure are untouched, only the voice_over text is rewritten in
# the newly chosen language.
# ---------------------------------------------------------------------------

def _build_narration_translation_payload(
    *, plan: Dict[str, Any], target_language: str, movie_metadata: Dict[str, Any],
) -> Dict[str, Any]:
    """Only the fields the translation model actually needs: the existing
    plan's own characters/segments (to copy through verbatim, translating
    only each voice_over segment's narration) plus the requested
    target_language and movie_metadata for context."""
    return {
        "movie_metadata": movie_metadata,
        "target_language": target_language,
        "characters": plan.get("characters") or [],
        "segments": plan.get("segments") or [],
    }


def _build_narration_translation_correction_message(
    validation_report: Dict[str, Any], structure_error: Optional["FilmSummaryValidationError"],
) -> Dict[str, str]:
    """Same spirit as _build_planning_correction_message, plus the one
    extra failure mode specific to this mode: the model altered, reordered,
    dropped or added a segment/clip instead of merely translating
    narration text (see validate_narration_translation_structure)."""
    errors = "; ".join(validation_report.get("errors") or [])
    warnings = "; ".join(validation_report.get("warnings") or [])

    sentences = []
    if structure_error is not None:
        sentences.append(f"Your previous response violated the translation invariant: {structure_error}.")
    if errors:
        sentences.append(f"Your previous plan failed automated validation with these blocking errors: {errors}.")
    if warnings:
        sentences.append(f"It also has these quality issues you should fix even though they did not block validation: {warnings}.")

    return {
        "role": "user",
        "content": (
            f"{' '.join(sentences)} Return a corrected full plan (same OUTPUT SCHEMA, JSON only) that keeps "
            "every field byte-for-byte identical to your previous response except each voice_over segment's "
            "narration, translated into the requested target_language, while fixing every issue above."
        ),
    }


async def translate_edit_plan_narration(
    *, plan: Dict[str, Any], target_language: str, movie_metadata: Dict[str, Any],
    duration_tolerance_ratio: float = 0.15,
) -> Dict[str, Any]:
    """AI-driven retranslation of an already-approved edit plan's narration
    into a newly chosen target_language, keeping every clip, timecode and
    segment exactly as-is (see validate_narration_translation_structure) --
    lets the user correct a wrong narration-language choice after the fact
    without regenerating or re-matching any footage ("l'IA va retraduire
    dans la langue qu'on va choisir car il arrive qu'on ait fait une
    mauvaise selection au debut").

    Returns {"plan", "validation_report", "usage"}. Raises
    FilmSummaryValidationError when plan has no segments, when every
    attempt still produces malformed JSON (see
    _parse_planning_json_with_retry), or when the model's response still
    violates validate_narration_translation_structure after exhausting
    every retry -- a translation must never be allowed to silently alter
    the approved footage or timing."""
    segments = plan.get("segments") or []
    if not segments:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.PLAN_INVALID, "plan has no segments to translate")

    client = _get_openai_client()
    model_name = os.environ.get("FILM_SUMMARY_PLANNING_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o"))
    max_attempts = int(os.environ.get("FILM_SUMMARY_PLANNING_MAX_ATTEMPTS", "2"))

    target_duration_ms = int(plan.get("target_duration_ms") or compute_total_estimated_duration_ms(segments))
    payload = _build_narration_translation_payload(plan=plan, target_language=target_language, movie_metadata=movie_metadata)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": NARRATION_TRANSLATION_SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(payload)},
    ]
    source_duration_ms = int(movie_metadata.get("source_duration_ms") or 0)

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}
    translated_plan: Dict[str, Any] = {}
    validation_report: Dict[str, Any] = {"valid": False, "errors": [], "warnings": []}
    structure_error: Optional[FilmSummaryValidationError] = None

    for attempt in range(max(1, max_attempts)):
        response = await asyncio.to_thread(_call_planning_model, client, model_name, messages)
        raw_text = response.choices[0].message.content
        usage = _usage_dict(response, model_name)
        total_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
        total_usage["completion_tokens"] += usage.get("completion_tokens", 0)

        raw = _parse_planning_json_with_retry(raw_text, attempt=attempt, max_attempts=max_attempts, messages=messages)
        if raw is None:
            continue

        translated_plan = validate_edit_plan_schema(raw, movie_metadata=movie_metadata, target_duration_ms=target_duration_ms)

        structure_error = None
        try:
            validate_narration_translation_structure(plan, translated_plan)
        except FilmSummaryValidationError as exc:
            structure_error = exc

        validation_report = validate_edit_plan_content(
            translated_plan, source_duration_ms=source_duration_ms, duration_tolerance_ratio=duration_tolerance_ratio,
        )
        has_fixable_issue = structure_error is not None or not validation_report["valid"] or bool(validation_report["warnings"])
        if not has_fixable_issue or attempt == max_attempts - 1:
            break
        messages.append({"role": "assistant", "content": raw_text})
        messages.append(_build_narration_translation_correction_message(validation_report, structure_error))

    if structure_error is not None:
        raise structure_error

    return {"plan": translated_plan, "validation_report": validation_report, "usage": total_usage}


def _build_utterance_segments(transcript: Any) -> List[Dict[str, Any]]:
    segments = [
        {
            "start_ms": int(utterance.start or 0),
            "end_ms": int(utterance.end or 0),
            "speaker": str(utterance.speaker or ""),
            "text": (utterance.text or "").strip(),
        }
        for utterance in (transcript.utterances or [])
    ]
    if segments:
        return segments

    # Fall back to a single segment spanning the whole transcript when the
    # source has no distinguishable speakers/utterances.
    text = (transcript.text or "").strip()
    if not text:
        return []
    audio_ms = int((transcript.audio_duration or 0) * 1000)
    return [{"start_ms": 0, "end_ms": audio_ms, "speaker": "", "text": text}]


def _transcribe_with_assemblyai(video_path: str, api_key: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
    import assemblyai as aai

    aai.settings.api_key = api_key
    config_kwargs = {"punctuate": True, "format_text": True, "speaker_labels": True}
    normalized_hint = (language_hint or "").strip().lower()
    if normalized_hint:
        # The user already told us the language (or a prior pass on this
        # same film already resolved it) -- transcribe directly in it
        # instead of guessing, which is both faster and more accurate.
        config_kwargs["language_code"] = normalized_hint
    else:
        # Without language_detection, AssemblyAI's TranscriptionConfig
        # silently assumes English rather than actually detecting anything
        # -- a French film with no language override would come back
        # language_code="en" every time, not because detection got it
        # wrong, but because no detection ever ran.
        config_kwargs["language_detection"] = True
    config = aai.TranscriptionConfig(**config_kwargs)
    transcript = aai.Transcriber(config=config).transcribe(video_path)
    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(transcript.error or "AssemblyAI transcription failed")

    return {
        "text": transcript.text or "",
        "language": transcript.language_code or normalized_hint or "unknown",
        "segments": _build_utterance_segments(transcript),
    }


async def transcribe_video_with_timecodes(video_path: str, language_hint: Optional[str] = None) -> Dict[str, Any]:
    """Transcribe a local video with AssemblyAI, keeping per-utterance
    timecodes (ms) and speaker labels -- unlike anonymous_stories.
    transcribe_video, this feature needs timecodes to cite transcript
    evidence and quote original dialogue verbatim with real bounds. The
    actual call runs in _transcribe_with_assemblyai (a plain, non-nested
    function) rather than a closure here, since a nested function's body
    counts against *this* function's cognitive complexity.

    `language_hint`, when given (the user's own source_language choice,
    see app.py's callers), is passed straight through as AssemblyAI's
    language_code rather than relying on auto-detection -- see
    _transcribe_with_assemblyai for why detection alone isn't reliable."""
    api_key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not configured")
    return await asyncio.to_thread(_transcribe_with_assemblyai, video_path, api_key, language_hint)


def download_youtube_source(url: str, output_dir: str) -> Dict[str, str]:
    """Download a YouTube video to `output_dir`. Delegates to
    youtube_download.download_youtube_video (same shared proxy/cookies/
    PO-Token strategy reels and anonymous stories use)."""
    import youtube_download

    os.makedirs(output_dir, exist_ok=True)
    path, sanitized_title = youtube_download.download_youtube_video(url, output_dir)
    return {"path": path, "title": sanitized_title.replace("_", " ").strip()}


def _probe_technical_metadata_json(video_path: str, timeout_seconds: int) -> Optional[Dict[str, Any]]:
    try:
        cmd = [
            "ffprobe", "-v", "error", "-print_format", "json",
            "-show_format", "-show_streams", video_path,
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout_seconds).decode()
        return json.loads(out)
    except Exception:
        return None


def _parse_video_stream_fps(stream: Dict[str, Any]) -> float:
    rate = str(stream.get("avg_frame_rate") or "0/1")
    try:
        num, den = rate.split("/")
        return (float(num) / float(den)) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        return 0.0


def _apply_stream_metadata(result: Dict[str, Any], streams: List[Dict[str, Any]]) -> None:
    for stream in streams:
        codec_type = stream.get("codec_type")
        if codec_type == "video" and not result["has_video"]:
            result["has_video"] = True
            result["video_codec"] = str(stream.get("codec_name") or "")
            result["width"] = _safe_int(stream.get("width"))
            result["height"] = _safe_int(stream.get("height"))
            result["fps"] = _parse_video_stream_fps(stream)
        elif codec_type == "audio" and not result["has_audio"]:
            result["has_audio"] = True
            result["audio_codec"] = str(stream.get("codec_name") or "")


def probe_technical_metadata(video_path: str, timeout_seconds: int = 60) -> Dict[str, Any]:
    """ffprobe-based technical probe used for Niveau 1 validation: real
    container/codec introspection rather than trusting the file extension
    (spec section 5: "l'extension seule n'est jamais suffisante"). Stream
    parsing lives in the _parse_video_stream_fps/_apply_stream_metadata
    helpers above to keep this function's own cognitive complexity low."""
    result = {
        "has_video": False, "has_audio": False, "width": 0, "height": 0, "fps": 0.0,
        "video_codec": "", "audio_codec": "", "duration_seconds": 0.0, "container_format_name": "",
    }
    data = _probe_technical_metadata_json(video_path, timeout_seconds)
    if data is None:
        return result

    fmt = data.get("format") or {}
    result["container_format_name"] = str(fmt.get("format_name") or "")
    try:
        result["duration_seconds"] = float(fmt.get("duration") or 0.0)
    except (TypeError, ValueError):
        pass

    _apply_stream_metadata(result, data.get("streams") or [])
    return result


def probe_media_duration_seconds(audio_path: str, timeout_seconds: int = 30) -> float:
    try:
        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", audio_path]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout_seconds).decode().strip()
        return max(0.0, float(out or 0))
    except Exception:
        return 0.0


def detect_scenes(video_path: str, threshold: float = 27.0, min_scene_len_frames: int = 15) -> List[Dict[str, Any]]:
    """Scene-change detection with PySceneDetect (already a dependency,
    same detector main.py's reel pipeline uses -- see main.py:detect_
    scenes), returning millisecond boundaries. Synchronous: call via
    asyncio.to_thread from the async pipeline."""
    from scenedetect import open_video, SceneManager
    from scenedetect.detectors import ContentDetector

    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector(threshold=threshold, min_scene_len=min_scene_len_frames))
    scene_manager.detect_scenes(video=video)
    scene_list = scene_manager.get_scene_list()

    scenes = []
    if not scene_list:
        duration_ms = int(video.duration.get_seconds() * 1000) if video.duration else 0
        scenes.append({"scene_id": "scene_001", "start_ms": 0, "end_ms": duration_ms, "quality_flags": []})
        return scenes

    for i, (start_tc, end_tc) in enumerate(scene_list):
        scenes.append({
            "scene_id": f"scene_{i + 1:03d}",
            "start_ms": int(start_tc.get_seconds() * 1000),
            "end_ms": int(end_tc.get_seconds() * 1000),
            "quality_flags": [],
        })
    return scenes


def extract_keyframe(video_path: str, timestamp_ms: int, output_path: str, timeout_seconds: int = 30) -> bool:
    timestamp_seconds = max(0.0, timestamp_ms / 1000.0)
    cmd = [
        "ffmpeg", "-y", "-ss", f"{timestamp_seconds:.3f}", "-i", video_path,
        "-frames:v", "1", "-q:v", "3", output_path,
    ]
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout_seconds)
        return result.returncode == 0 and os.path.exists(output_path)
    except Exception:
        return False


def encode_image_data_url(image_path: str) -> Optional[str]:
    """Base64 data: URL for a locally extracted keyframe, so it can be sent
    inline as an OpenAI vision `image_url` content part (spec section 5/12:
    the Niveau 2 classifier is meant to look at "images representatives",
    not text signals alone)."""
    try:
        with open(image_path, "rb") as handle:
            encoded = base64.b64encode(handle.read()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except OSError:
        return None


def extract_classification_keyframes(video_path: str, scene_index: List[Dict[str, Any]], max_frames: int = 3) -> List[str]:
    """Pull a handful of representative keyframes (start/middle/end scenes)
    as base64 data URLs for the classifier. Best-effort: a frame that fails
    to extract or encode is silently skipped rather than failing
    classification, since these images are a supporting signal, not the
    only one (transcript_sample and scene_stats are always present)."""
    if not scene_index:
        return []
    n = len(scene_index)
    candidate_indices = sorted({0, n // 2, n - 1})[:max_frames]
    work_dir = os.path.dirname(video_path) or "."

    data_urls = []
    for index in candidate_indices:
        scene = scene_index[index]
        midpoint_ms = (int(scene.get("start_ms", 0)) + int(scene.get("end_ms", 0))) // 2
        frame_path = os.path.join(work_dir, f"_film_summary_classify_frame_{index}.jpg")
        try:
            if extract_keyframe(video_path, midpoint_ms, frame_path):
                data_url = encode_image_data_url(frame_path)
                if data_url:
                    data_urls.append(data_url)
        finally:
            if os.path.exists(frame_path):
                try:
                    os.remove(frame_path)
                except OSError:
                    pass
    return data_urls


async def synthesize_tts_segment(
    *, text: str, voice: str, model: str, instructions: str, output_path: str,
) -> float:
    """Generate one voice-over segment's audio with OpenAI TTS (spec
    section 14: "genere chaque bloc separement"). Returns the real audio
    duration in seconds (probed with ffprobe) so the caller can re-inject
    it into the plan (see apply_actual_tts_durations).

    Writes to a temporary path first and only moves it to output_path on
    full success. get_film_summary_voice_preview_endpoint caches its output
    by checking whether output_path already exists -- writing directly to
    it meant a request that failed partway through streaming (a dropped
    connection, a timeout, a missing API key) could still leave a partial
    or empty file there, which the cache check would then treat as a valid
    preview forever, breaking that voice's preview permanently until
    someone deleted the file by hand on the server."""
    tmp_path = f"{output_path}.tmp-{uuid.uuid4().hex[:8]}"
    try:
        client = _get_openai_client()

        def _call():
            with client.audio.speech.with_streaming_response.create(
                model=model, voice=voice, input=text, instructions=instructions,
            ) as response:
                response.stream_to_file(tmp_path)

        await asyncio.to_thread(_call)
    except Exception as exc:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise FilmSummaryValidationError(FilmSummaryErrorCode.TTS_FAILED, str(exc)) from exc

    os.replace(tmp_path, output_path)
    return probe_media_duration_seconds(output_path)


ALLOWED_TTS_VOICES = ("alloy", "ash", "ballad", "cedar", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer", "verse")


def resolve_tts_voice(requested_voice: Optional[str], default_voice: str) -> str:
    voice = str(requested_voice or "").strip().lower()
    return voice if voice in ALLOWED_TTS_VOICES else default_voice
