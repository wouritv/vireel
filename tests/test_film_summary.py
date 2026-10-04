import asyncio
import json
import os
import subprocess
import sys
import types
from unittest.mock import MagicMock

import pytest

import film_summary as fs


# ---------------------------------------------------------------------------
# Credit history operation_type
# ---------------------------------------------------------------------------

def test_credit_operation_type_is_resume_film():
    assert fs.CREDIT_OPERATION_TYPE == "resume_film"
    # A second underscore would render badly in the credit history table
    # (Settings.jsx only replaces the first "_" before CSS-capitalizing).
    assert fs.CREDIT_OPERATION_TYPE.count("_") <= 1


# ---------------------------------------------------------------------------
# derive_target_duration_seconds / validate_target_duration_seconds
# ---------------------------------------------------------------------------

def test_derive_target_duration_uses_one_sixth_ratio_within_bounds():
    assert fs.derive_target_duration_seconds(3600, 180, 1200) == 600


def test_derive_target_duration_clamps_to_minimum():
    assert fs.derive_target_duration_seconds(300, 180, 1200) == 180


def test_derive_target_duration_clamps_to_maximum():
    assert fs.derive_target_duration_seconds(36000, 180, 1200) == 1200


def test_validate_target_duration_accepts_none():
    fs.validate_target_duration_seconds(None, 180, 1200)


def test_validate_target_duration_rejects_out_of_bounds():
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_target_duration_seconds(30, 180, 1200)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.INVALID_TARGET_DURATION


# ---------------------------------------------------------------------------
# validate_technical_constraints
# ---------------------------------------------------------------------------

def _valid_technical_kwargs(**overrides):
    kwargs = {
        "duration_seconds": 3600,
        "size_bytes": 1024 ** 3,
        "has_video_track": True,
        "has_audio_track": True,
        "max_upload_size_bytes": 20 * 1024 ** 3,
        "min_source_duration_seconds": 600,
        "max_source_duration_seconds": 4 * 3600,
    }
    kwargs.update(overrides)
    return kwargs


def test_validate_technical_constraints_passes_for_valid_media():
    fs.validate_technical_constraints(**_valid_technical_kwargs())


def test_validate_technical_constraints_rejects_oversized_file():
    kwargs = _valid_technical_kwargs(size_bytes=30 * 1024 ** 3)
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**kwargs)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.SOURCE_TOO_LARGE


def test_validate_technical_constraints_rejects_too_short():
    kwargs = _valid_technical_kwargs(duration_seconds=60)
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**kwargs)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.SOURCE_TOO_SHORT


def test_validate_technical_constraints_rejects_too_long():
    kwargs = _valid_technical_kwargs(duration_seconds=100000)
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**kwargs)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.SOURCE_TOO_LONG


def test_validate_technical_constraints_rejects_missing_video_track():
    kwargs = _valid_technical_kwargs(has_video_track=False)
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**kwargs)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.NO_VIDEO_TRACK


def test_validate_technical_constraints_rejects_missing_audio_track():
    kwargs = _valid_technical_kwargs(has_audio_track=False)
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**kwargs)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.NO_AUDIO_TRACK


# ---------------------------------------------------------------------------
# validate_media_type_verdict / decide_film_verdict
# ---------------------------------------------------------------------------

def test_validate_media_type_verdict_normalizes_valid_payload():
    raw = {
        "is_film": True, "confidence": 1.4, "estimated_category": "narrative_film",
        "positive_signals": ["recurring characters"], "negative_signals": [],
        "reason_code": "accepted", "user_message": "", "requires_secondary_review": False,
    }
    verdict = fs.validate_media_type_verdict(raw)
    assert verdict["is_film"] is True
    assert verdict["confidence"] == 1.0  # clamped
    assert verdict["positive_signals"] == ["recurring characters"]


def test_validate_media_type_verdict_rejects_missing_fields():
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_media_type_verdict({"is_film": True})


def test_validate_media_type_verdict_rejects_non_dict():
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_media_type_verdict("not a dict")


def test_decide_film_verdict_accepted():
    verdict = {"is_film": True, "confidence": 0.9, "requires_secondary_review": False}
    assert fs.decide_film_verdict(verdict, 0.75) == "ACCEPTED"


def test_decide_film_verdict_rejected():
    verdict = {"is_film": False, "confidence": 0.9, "requires_secondary_review": False}
    assert fs.decide_film_verdict(verdict, 0.75) == "REJECTED"


def test_decide_film_verdict_review_on_secondary_review_flag():
    verdict = {"is_film": True, "confidence": 0.99, "requires_secondary_review": True}
    assert fs.decide_film_verdict(verdict, 0.75) == "REVIEW"


def test_decide_film_verdict_review_when_confidence_too_low_either_way():
    verdict = {"is_film": True, "confidence": 0.5, "requires_secondary_review": False}
    assert fs.decide_film_verdict(verdict, 0.75) == "REVIEW"


# ---------------------------------------------------------------------------
# build_scene_index
# ---------------------------------------------------------------------------

def test_build_scene_index_joins_overlapping_transcript():
    scenes = [{"scene_id": "scene_001", "start_ms": 0, "end_ms": 5000}]
    transcript_segments = [
        {"start_ms": 0, "end_ms": 2000, "speaker": "A", "text": "Hello there."},
        {"start_ms": 4000, "end_ms": 6000, "speaker": "B", "text": "General Kenobi."},
        {"start_ms": 10000, "end_ms": 12000, "speaker": "A", "text": "Not overlapping."},
    ]
    index = fs.build_scene_index(scenes, transcript_segments)
    assert len(index) == 1
    assert index[0]["speakers"] == ["A", "B"]
    assert "Hello there." in index[0]["transcript_overlap"]
    assert "General Kenobi." in index[0]["transcript_overlap"]
    assert "Not overlapping." not in index[0]["transcript_overlap"]


def test_build_scene_index_empty_transcript_gives_empty_overlap():
    scenes = [{"scene_id": "scene_001", "start_ms": 0, "end_ms": 5000}]
    index = fs.build_scene_index(scenes, [])
    assert index[0]["transcript_overlap"] == ""
    assert index[0]["speakers"] == []


# ---------------------------------------------------------------------------
# build_transcript_sample
# ---------------------------------------------------------------------------

def test_build_transcript_sample_covers_start_middle_end():
    segments = [{"text": f"line {i}"} for i in range(30)]
    sample = fs.build_transcript_sample(segments, max_chars=1000)
    assert "line 0" in sample
    assert "line 15" in sample or "line 14" in sample or "line 16" in sample
    assert "line 29" in sample


def test_build_transcript_sample_empty_input():
    assert fs.build_transcript_sample([]) == ""


def test_build_transcript_sample_respects_max_chars():
    segments = [{"text": "x" * 100} for _ in range(50)]
    sample = fs.build_transcript_sample(segments, max_chars=300)
    assert len(sample) <= 300


# ---------------------------------------------------------------------------
# validate_edit_plan_schema / compute_total_estimated_duration_ms
# ---------------------------------------------------------------------------

def _valid_raw_plan():
    return {
        "characters": [{"id": "char_1", "canonical_name": "Alice", "aliases": [], "role": "protagonist"}],
        "segments": [
            {
                "id": "seg_001", "sequence": 1, "type": "voice_over", "narration": "Once upon a time.",
                "estimated_duration_ms": 26000, "clips": [
                    {"scene_id": "scene_001", "start_ms": 1000, "end_ms": 8000, "description": "opening", "match_score": 0.9},
                ],
                "source_event_ids": ["event_1"],
            },
            {
                "id": "seg_002", "sequence": 2, "type": "original_dialogue",
                "start_ms": 9000, "end_ms": 12000, "transcript_excerpt": "I know.", "speaker_ids": ["char_1"],
            },
        ],
        "unresolved_ambiguities": [],
    }


def test_validate_edit_plan_schema_normalizes_valid_plan():
    movie_metadata = {"title": "My Movie", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    plan = fs.validate_edit_plan_schema(_valid_raw_plan(), movie_metadata=movie_metadata, target_duration_ms=600000)
    assert plan["schema_version"] == "1.0"
    assert plan["movie"] == movie_metadata
    assert len(plan["segments"]) == 2
    assert plan["total_estimated_duration_ms"] == 26000 + 3000


def test_validate_edit_plan_schema_never_trusts_model_movie_metadata():
    raw = _valid_raw_plan()
    raw["movie"] = {"title": "Hallucinated Title", "source_duration_ms": 1}
    movie_metadata = {"title": "Real Title", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    plan = fs.validate_edit_plan_schema(raw, movie_metadata=movie_metadata, target_duration_ms=600000)
    assert plan["movie"]["title"] == "Real Title"


def test_validate_edit_plan_schema_rejects_insufficient_evidence():
    raw = {"status": "insufficient_evidence", "explanation": "Not enough scenes"}
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_edit_plan_schema(raw, movie_metadata={}, target_duration_ms=600000)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLANNING_FAILED


def test_validate_edit_plan_schema_rejects_empty_segments():
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_edit_plan_schema({"segments": []}, movie_metadata={}, target_duration_ms=600000)


def test_validate_edit_plan_schema_rejects_unknown_segment_type():
    raw = _valid_raw_plan()
    raw["segments"][0]["type"] = "not_a_real_type"
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_edit_plan_schema(raw, movie_metadata={}, target_duration_ms=600000)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


# ---------------------------------------------------------------------------
# estimate_narration_duration_ms / validate_edited_plan_patch
# ---------------------------------------------------------------------------

def test_estimate_narration_duration_ms_uses_135_wpm():
    text = " ".join(["word"] * 135)
    assert fs.estimate_narration_duration_ms(text) == 60000


def test_estimate_narration_duration_ms_empty_text_is_zero():
    assert fs.estimate_narration_duration_ms("") == 0


def test_validate_edited_plan_patch_recomputes_estimate_from_edited_narration():
    # The AI-provided estimated_duration_ms (26000) would normally be
    # trusted as-is, but a user editing narration in the review UI has no
    # way to update that field themselves -- validate_edited_plan_patch
    # must recompute it from the new text so the total actually moves.
    raw = _valid_raw_plan()
    raw["segments"][0]["narration"] = " ".join(["word"] * 270)  # -> 120000ms at 135 wpm
    plan = fs.validate_edited_plan_patch(raw, movie_metadata={}, target_duration_ms=600000)
    voice_over = next(s for s in plan["segments"] if s["type"] == "voice_over")
    assert voice_over["estimated_duration_ms"] == 120000
    assert plan["total_estimated_duration_ms"] == 120000 + 3000


# ---------------------------------------------------------------------------
# validate_edit_plan_content
# ---------------------------------------------------------------------------

def _built_plan(target_duration_ms=29000):
    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    return fs.validate_edit_plan_schema(_valid_raw_plan(), movie_metadata=movie_metadata, target_duration_ms=target_duration_ms)


def test_validate_edit_plan_content_valid_plan_passes():
    plan = _built_plan()
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    assert report["errors"] == []


def test_validate_edit_plan_content_flags_unknown_scene_id():
    plan = _built_plan()
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_999"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("scene_id inconnu" in e for e in report["errors"])


def test_validate_edit_plan_content_flags_out_of_bounds_clip():
    plan = _built_plan()
    plan["segments"][0]["clips"][0]["end_ms"] = 10_000_000  # beyond source duration
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("hors limites" in e for e in report["errors"])


def test_validate_edit_plan_content_flags_overlapping_dialogue_segments():
    plan = _built_plan()
    plan["segments"].append({
        "id": "seg_003", "sequence": 3, "type": "breathing",
        "start_ms": 10000, "end_ms": 11000, "transcript_excerpt": "", "speaker_ids": [],
    })
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    # Names both segment ids and their exact timecodes -- fed back verbatim
    # to the planning model as corrective context on a retry, a bare
    # generic message gives it nothing to act on.
    assert any("seg_002" in e and "seg_003" in e and "9000-12000ms" in e and "10000-11000ms" in e for e in report["errors"])


def test_validate_edit_plan_content_flags_duration_outside_tolerance():
    plan = _built_plan(target_duration_ms=1)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.1,
    )
    assert report["valid"] is False
    assert any("tolerance" in e for e in report["errors"])


def test_validate_edit_plan_content_flags_bad_sequence_numbers():
    plan = _built_plan()
    plan["segments"][1]["sequence"] = 5
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("sequence" in e for e in report["errors"])


def test_validate_edit_plan_content_warns_on_repeated_clip():
    # A clip reused across segments (same scene_id/start_ms/end_ms) is only
    # a warning -- the planning prompt asks the model to avoid it, but the
    # user must never be blocked from generating their video over it.
    plan = _built_plan(target_duration_ms=32000)
    plan["segments"][0]["clips"].append(dict(plan["segments"][0]["clips"][0]))
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    # Names the exact repeated clip instead of a bare count, in case this
    # is ever surfaced as corrective context the way the dialogue-overlap
    # error already is.
    assert any(
        "utilises plus d'une fois" in w and "scene_001" in w and "1000-8000ms" in w
        for w in report["warnings"]
    )
    assert report["errors"] == []


# ---------------------------------------------------------------------------
# FILM_SUMMARY_MAX_PLAN_DURATION_MS hard cap (blocking, both automatic and
# manual plans go through validate_edit_plan_content)
# ---------------------------------------------------------------------------

def _plan_with_total_duration_ms(total_ms):
    raw = _valid_raw_plan()
    # Fold the whole total into the single voice_over segment's estimated
    # duration and drop the original_dialogue segment, so total_estimated_
    # duration_ms is exactly total_ms with nothing else to account for.
    raw["segments"] = [raw["segments"][0]]
    raw["segments"][0]["sequence"] = 1
    raw["segments"][0]["estimated_duration_ms"] = total_ms
    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    return fs.validate_edit_plan_schema(raw, movie_metadata=movie_metadata, target_duration_ms=total_ms)


def test_validate_edit_plan_content_passes_under_max_plan_duration():
    plan = _plan_with_total_duration_ms(fs.FILM_SUMMARY_MAX_PLAN_DURATION_MS - 1000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    assert report["errors"] == []


def test_validate_edit_plan_content_rejects_plan_over_max_duration():
    plan = _plan_with_total_duration_ms(fs.FILM_SUMMARY_MAX_PLAN_DURATION_MS + 1000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("depasse la limite maximale" in e for e in report["errors"])


def test_validate_edit_plan_content_max_duration_threshold_is_configurable(monkeypatch):
    # A plan comfortably under the default 5-minute cap must start failing
    # once the configurable threshold is lowered below its total -- proves
    # the check reads FILM_SUMMARY_MAX_PLAN_DURATION_MS live rather than a
    # value captured once at import time.
    plan = _plan_with_total_duration_ms(60000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True

    monkeypatch.setattr(fs, "FILM_SUMMARY_MAX_PLAN_DURATION_MS", 30000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("depasse la limite maximale" in e for e in report["errors"])


# ---------------------------------------------------------------------------
# realign_plan_target_duration
# ---------------------------------------------------------------------------

def test_realign_plan_target_duration_snaps_target_to_actual_total_when_outside_tolerance():
    # total is 29000 (26000 + 3000); a target of 1ms is hopelessly outside
    # any tolerance -- the user has no direct way to hit it, so the target
    # itself should move to match what was actually produced instead of
    # leaving the plan permanently invalid.
    plan = _built_plan(target_duration_ms=1)
    realigned, report = fs.realign_plan_target_duration(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.15,
    )
    assert realigned["target_duration_ms"] == 29000
    assert report["valid"] is True
    assert report["errors"] == []


def test_realign_plan_target_duration_leaves_plan_untouched_within_tolerance():
    plan = _built_plan(target_duration_ms=29000)
    realigned, report = fs.realign_plan_target_duration(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.15,
    )
    assert realigned is plan
    assert realigned["target_duration_ms"] == 29000
    assert report["valid"] is True


def test_realign_plan_target_duration_does_not_mask_other_errors():
    plan = _built_plan(target_duration_ms=1)
    plan["segments"][1]["sequence"] = 5  # unrelated, still-blocking error
    _, report = fs.realign_plan_target_duration(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.15,
    )
    assert report["valid"] is False
    assert any("sequence" in e for e in report["errors"])
    assert not any("tolerance" in e for e in report["errors"])


# ---------------------------------------------------------------------------
# _clamp_legacy_duration_truncation_overage (source_duration_seconds used to
# be stored truncated to a whole second, see _persist_film_summary_row in
# app.py) and its use inside realign_plan_target_duration
# ---------------------------------------------------------------------------

def test_clamp_legacy_duration_truncation_overage_clamps_voice_over_clip_within_bound():
    plan = _built_plan()
    plan["segments"][0]["clips"][0]["end_ms"] = 3_600_500  # 500ms over -- the known truncation window
    fixed, changed = fs._clamp_legacy_duration_truncation_overage(plan["segments"], 3_600_000)
    assert changed is True
    assert fixed[0]["clips"][0]["end_ms"] == 3_600_000
    assert plan["segments"][0]["clips"][0]["end_ms"] == 3_600_500  # input left untouched


def test_clamp_legacy_duration_truncation_overage_clamps_timed_segment_within_bound():
    plan = _built_plan()
    plan["segments"][1]["end_ms"] = 3_600_800  # 800ms over
    fixed, changed = fs._clamp_legacy_duration_truncation_overage(plan["segments"], 3_600_000)
    assert changed is True
    assert fixed[1]["end_ms"] == 3_600_000


def test_clamp_legacy_duration_truncation_overage_leaves_larger_overage_alone():
    # 1500ms is beyond the max 999ms a whole-second truncation could ever
    # lose -- this is a real out-of-bounds plan and must still fail.
    plan = _built_plan()
    plan["segments"][0]["clips"][0]["end_ms"] = 3_601_500
    fixed, changed = fs._clamp_legacy_duration_truncation_overage(plan["segments"], 3_600_000)
    assert changed is False
    assert fixed[0]["clips"][0]["end_ms"] == 3_601_500


def test_realign_plan_target_duration_self_heals_legacy_truncation_overage():
    plan = _built_plan()
    plan["segments"][0]["clips"][0]["end_ms"] = 3_600_500
    realigned, report = fs.realign_plan_target_duration(
        plan, source_duration_ms=3_600_000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    assert report["errors"] == []
    assert realigned["segments"][0]["clips"][0]["end_ms"] == 3_600_000


def test_realign_plan_target_duration_still_rejects_real_out_of_bounds_clip():
    plan = _built_plan()
    plan["segments"][0]["clips"][0]["end_ms"] = 10_000_000
    _, report = fs.realign_plan_target_duration(
        plan, source_duration_ms=3_600_000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("hors limites" in e for e in report["errors"])


# ---------------------------------------------------------------------------
# apply_actual_tts_durations / compute_total_estimated_duration_ms
# ---------------------------------------------------------------------------

def test_apply_actual_tts_durations_updates_voice_over_and_recomputes_total():
    plan = _built_plan()
    updated = fs.apply_actual_tts_durations(plan, {"seg_001": 30000})
    voice_over = next(s for s in updated["segments"] if s["id"] == "seg_001")
    assert voice_over["actual_duration_ms"] == 30000
    assert updated["total_estimated_duration_ms"] == 30000 + 3000


def test_apply_actual_tts_durations_does_not_mutate_input_plan():
    plan = _built_plan()
    original_total = plan["total_estimated_duration_ms"]
    fs.apply_actual_tts_durations(plan, {"seg_001": 99999})
    assert plan["total_estimated_duration_ms"] == original_total


# ---------------------------------------------------------------------------
# tts_cache_key / resolve_tts_voice
# ---------------------------------------------------------------------------

def test_tts_cache_key_is_stable_and_sensitive_to_inputs():
    key1 = fs.tts_cache_key("Hello world", "gpt-4o-mini-tts", "cedar", "narrate calmly")
    key2 = fs.tts_cache_key("Hello world", "gpt-4o-mini-tts", "cedar", "narrate calmly")
    key3 = fs.tts_cache_key("Hello world!", "gpt-4o-mini-tts", "cedar", "narrate calmly")
    assert key1 == key2
    assert key1 != key3


def test_resolve_tts_voice_falls_back_to_default_for_unknown_voice():
    assert fs.resolve_tts_voice("not-a-real-voice", "cedar") == "cedar"


def test_resolve_tts_voice_accepts_allowed_voice_case_insensitively():
    assert fs.resolve_tts_voice("ONYX", "cedar") == "onyx"


# ---------------------------------------------------------------------------
# build_tts_instructions
# ---------------------------------------------------------------------------

def test_build_tts_instructions_substitutes_language():
    instructions = fs.build_tts_instructions("French")
    assert "fluent French" in instructions
    assert "{{LANGUAGE}}" not in instructions


# ---------------------------------------------------------------------------
# classify_media_type (network call mocked)
# ---------------------------------------------------------------------------

def _fake_openai_response(content, prompt_tokens=10, completion_tokens=5):
    fake_message = types.SimpleNamespace(content=content)
    fake_choice = types.SimpleNamespace(message=fake_message)
    fake_usage = types.SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens)
    return types.SimpleNamespace(choices=[fake_choice], usage=fake_usage)


def test_classify_media_type_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    coro = fs.classify_media_type(metadata={}, transcript_sample="", scene_stats={})
    with pytest.raises(RuntimeError):
        asyncio.run(coro)


def test_classify_media_type_returns_verdict_with_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = _fake_openai_response(
        '{"is_film": true, "confidence": 0.9, "estimated_category": "narrative_film", '
        '"positive_signals": [], "negative_signals": [], "reason_code": "accepted", '
        '"user_message": "", "requires_secondary_review": false}'
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = response
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    verdict = asyncio.run(fs.classify_media_type(metadata={"duration_seconds": 3600}, transcript_sample="hello", scene_stats={}))

    assert verdict["is_film"] is True
    assert verdict["usage"]["prompt_tokens"] == 10


def test_classify_media_type_sends_keyframes_as_image_content(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    response = _fake_openai_response(
        '{"is_film": false, "confidence": 0.9, "estimated_category": "interview", '
        '"positive_signals": [], "negative_signals": [], "reason_code": "not_narrative", '
        '"user_message": "", "requires_secondary_review": false}'
    )
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = response
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    asyncio.run(fs.classify_media_type(
        metadata={}, transcript_sample="", scene_stats={}, keyframe_data_urls=["data:image/jpeg;base64,AA=="],
    ))

    sent_messages = fake_client.chat.completions.create.call_args.kwargs["messages"]
    user_content = sent_messages[-1]["content"]
    assert isinstance(user_content, list)
    assert any(part.get("type") == "image_url" for part in user_content)


def test_classify_media_type_raises_on_bad_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response("not json")
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    coro = fs.classify_media_type(metadata={}, transcript_sample="", scene_stats={})
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.GENERATION_INVALID


def test_build_generation_constraints_includes_segment_count_hint():
    constraints = fs.build_generation_constraints(401000)
    # 401000 / 27500 (the documented average voice-over segment length) rounds to 15.
    assert constraints["approximate_total_segment_count_hint"] == 15


def test_describe_duration_gap_suggests_adding_segments_when_short():
    message = fs._describe_duration_gap({"total_estimated_duration_ms": 240679}, 401000)
    assert "160321ms short" in message
    assert "add approximately 6 more" in message


def test_describe_duration_gap_suggests_removing_segments_when_over():
    message = fs._describe_duration_gap({"total_estimated_duration_ms": 511022}, 401000)
    assert "110022ms over" in message
    assert "remove or shorten approximately 4" in message


def test_build_planning_correction_message_includes_duration_hint_only_when_out_of_tolerance():
    # duration_hint is now recomputed from plan/target/ratio directly rather
    # than sniffed from the (translated, French) error text -- see
    # _build_planning_correction_message.
    duration_report = {"errors": ["La duree totale estimee de 240679ms est en dehors de la tolerance de 15% autour de la cible de 401000ms"]}
    out_of_tolerance_plan = {"total_estimated_duration_ms": 240679}
    message = fs._build_planning_correction_message(duration_report, out_of_tolerance_plan, 401000, 0.15)
    assert "short of the target" in message["content"]

    other_report = {"errors": ["Les numeros de sequence des segments doivent etre continus, en commencant a 1, dans l'ordre de lecture"]}
    within_tolerance_plan = {"total_estimated_duration_ms": 401000}
    other_message = fs._build_planning_correction_message(other_report, within_tolerance_plan, 401000, 0.15)
    assert "short of the target" not in other_message["content"]


def test_build_planning_correction_message_includes_warnings_too():
    # A repeated-clip warning never blocks validation, but is still worth
    # one corrective retry (see generate_edit_plan) -- the message must
    # mention it distinctly from any blocking error.
    report = {
        "errors": [],
        "warnings": ["Le(s) clip(s) suivant(s) sont utilises plus d'une fois : scene_001 (1000-8000ms)"],
    }
    plan = {"total_estimated_duration_ms": 29000}
    message = fs._build_planning_correction_message(report, plan, 29000, 0.15)
    assert "utilises plus d'une fois" in message["content"]
    assert "did not block validation" in message["content"]
    assert "blocking errors" not in message["content"]


# ---------------------------------------------------------------------------
# generate_edit_plan (network call mocked)
# ---------------------------------------------------------------------------

def test_generate_edit_plan_returns_validated_plan_and_usage(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    plan_json = json.dumps(_valid_raw_plan())
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(plan_json)
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    # target_duration_ms matches _valid_raw_plan()'s own total (26000 + 3000)
    # so this plan passes content validation on the first attempt -- this
    # test is about the schema/usage plumbing, not the retry-on-failure
    # path (see the dedicated tests below for that).
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=29000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert result["plan"]["movie"] == movie_metadata
    assert result["usage"]["prompt_tokens"] == 10
    fake_client.chat.completions.create.assert_called_once()


def test_generate_edit_plan_raises_on_bad_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response("not json")
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    coro = fs.generate_edit_plan(
        movie_metadata={}, target_duration_ms=600000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    )
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


def test_generate_edit_plan_retries_once_and_converges_on_correction(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    invalid_plan = _valid_raw_plan()  # total duration (29000ms) far below the 600000ms target below
    corrected_plan = _valid_raw_plan()
    corrected_plan["segments"][0]["estimated_duration_ms"] = 597000  # brings the total within tolerance

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(json.dumps(invalid_plan), prompt_tokens=10, completion_tokens=5),
        _fake_openai_response(json.dumps(corrected_plan), prompt_tokens=20, completion_tokens=8),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=600000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    assert result["plan"]["total_estimated_duration_ms"] == 597000 + 3000
    assert result["usage"] == {"prompt_tokens": 30, "completion_tokens": 13}
    # The corrective follow-up must reference the earlier response so the
    # model can patch it rather than starting from a blank slate.
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert sent_messages[-2]["role"] == "assistant"
    assert "blocking errors" in sent_messages[-1]["content"]


def test_generate_edit_plan_retries_on_warning_only_even_when_already_valid(monkeypatch):
    # A repeated-clip warning never makes validation fail (see
    # _validate_repeated_clips), so this plan is "valid": True on the first
    # attempt. The retry must still fire to give the model a chance to drop
    # the duplicate, and must not block the final result either way.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    repeated_clip_plan = _valid_raw_plan()
    repeated_clip_plan["segments"] = [
        {
            "id": "seg_001", "sequence": 1, "type": "voice_over", "narration": "Once upon a time.",
            "estimated_duration_ms": 26000, "clips": [
                {"scene_id": "scene_001", "start_ms": 1000, "end_ms": 8000, "description": "opening", "match_score": 0.9},
            ],
            "source_event_ids": ["event_1"],
        },
        {
            "id": "seg_002", "sequence": 2, "type": "voice_over", "narration": "Later that day.",
            "estimated_duration_ms": 26000, "clips": [
                {"scene_id": "scene_001", "start_ms": 1000, "end_ms": 8000, "description": "reused", "match_score": 0.9},
            ],
            "source_event_ids": ["event_2"],
        },
    ]

    corrected_plan = _valid_raw_plan()
    corrected_plan["segments"] = [
        repeated_clip_plan["segments"][0],
        {
            "id": "seg_002", "sequence": 2, "type": "voice_over", "narration": "Later that day.",
            "estimated_duration_ms": 26000, "clips": [
                {"scene_id": "scene_002", "start_ms": 2000, "end_ms": 9000, "description": "different", "match_score": 0.9},
            ],
            "source_event_ids": ["event_2"],
        },
    ]

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(json.dumps(repeated_clip_plan)),
        _fake_openai_response(json.dumps(corrected_plan)),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=52000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert "utilises plus d'une fois" in sent_messages[-1]["content"]
    assert "did not block validation" in sent_messages[-1]["content"]
    # The corrected plan no longer reuses the clip.
    clips_by_segment = [seg["clips"][0]["scene_id"] for seg in result["plan"]["segments"]]
    assert clips_by_segment == ["scene_001", "scene_002"]


def test_generate_edit_plan_does_not_retry_forever_on_persistent_warning(monkeypatch):
    # The warning-driven retry must still respect max_attempts and return
    # the last plan rather than looping -- the warning is never blocking.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    repeated_clip_plan = _valid_raw_plan()
    repeated_clip_plan["segments"] = [
        {
            "id": "seg_001", "sequence": 1, "type": "voice_over", "narration": "Once upon a time.",
            "estimated_duration_ms": 26000, "clips": [
                {"scene_id": "scene_001", "start_ms": 1000, "end_ms": 8000, "description": "opening", "match_score": 0.9},
            ],
            "source_event_ids": ["event_1"],
        },
        {
            "id": "seg_002", "sequence": 2, "type": "voice_over", "narration": "Later that day.",
            "estimated_duration_ms": 26000, "clips": [
                {"scene_id": "scene_001", "start_ms": 1000, "end_ms": 8000, "description": "reused", "match_score": 0.9},
            ],
            "source_event_ids": ["event_2"],
        },
    ]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(repeated_clip_plan))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=52000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    assert result["plan"]["segments"][1]["clips"][0]["scene_id"] == "scene_001"


def test_generate_edit_plan_retries_on_truncated_json_and_converges(monkeypatch):
    # A long plan can get cut off mid-string by max_tokens -- json.loads
    # then raises, which used to abort the whole request outright instead
    # of giving the model (now with much more max_tokens headroom, see
    # _call_planning_model) another try.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    truncated_json = '{"segments": [{"id": "seg_001", "sequence": 1, "type": "voice_over"'
    valid_plan = _valid_raw_plan()

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(truncated_json, prompt_tokens=10, completion_tokens=16000),
        _fake_openai_response(json.dumps(valid_plan), prompt_tokens=20, completion_tokens=8),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=29000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    assert result["plan"]["total_estimated_duration_ms"] == 29000
    # Usage from the truncated attempt is still billed -- those tokens
    # were genuinely consumed even though the response was unusable.
    assert result["usage"] == {"prompt_tokens": 30, "completion_tokens": 16008}
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert sent_messages[-2]["role"] == "assistant"
    assert sent_messages[-2]["content"] == truncated_json
    assert "not valid, complete JSON" in sent_messages[-1]["content"]


def test_generate_edit_plan_raises_after_exhausting_attempts_on_malformed_json(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    truncated_json = '{"segments": ['
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(truncated_json)
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    coro = fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=600000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    )
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID
    assert fake_client.chat.completions.create.call_count == 2


def test_generate_edit_plan_gives_up_after_max_attempts(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    still_invalid_plan = _valid_raw_plan()
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(still_invalid_plan))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=600000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    # Default max attempts is 2 -- gives up and returns the last (still
    # invalid) plan rather than looping or raising, matching the existing
    # "surface the validation report to the user" behavior.
    assert fake_client.chat.completions.create.call_count == 2
    assert result["plan"]["total_estimated_duration_ms"] == 29000


# ---------------------------------------------------------------------------
# validate_manual_selection_partition
# ---------------------------------------------------------------------------

def _manual_selection_fixture():
    return [
        {"scene_id": "scene_001", "start_ms": 0, "end_ms": 5000},
        {"scene_id": "scene_002", "start_ms": 1000, "end_ms": 6000},
    ]


def _manual_plan_with_clips(clip_groups, extra_segment=None):
    """Builds a normalized-shaped plan whose voice_over segments' clips are
    exactly `clip_groups` (a list of lists of {scene_id,start_ms,end_ms})."""
    segments = []
    for i, clips in enumerate(clip_groups, start=1):
        segments.append({
            "id": f"seg_{i:02d}", "sequence": i, "type": fs.SEGMENT_TYPE_VOICE_OVER,
            "narration": "Some narration.", "estimated_duration_ms": 5000,
            "actual_duration_ms": None,
            "clips": [dict(c) for c in clips],
            "source_event_ids": [],
        })
    if extra_segment:
        extra_segment = dict(extra_segment)
        extra_segment["sequence"] = len(segments) + 1
        segments.append(extra_segment)
    return {"segments": segments}


def test_validate_manual_selection_partition_accepts_exact_grouped_partition():
    manual_selection = _manual_selection_fixture()
    plan = _manual_plan_with_clips([manual_selection])  # both clips grouped into one segment
    fs.validate_manual_selection_partition(plan, manual_selection)  # must not raise

    plan_split = _manual_plan_with_clips([[manual_selection[0]], [manual_selection[1]]])  # one clip per segment
    fs.validate_manual_selection_partition(plan_split, manual_selection)  # must not raise


def test_validate_manual_selection_partition_rejects_reordered_clips():
    manual_selection = _manual_selection_fixture()
    reordered_plan = _manual_plan_with_clips([[manual_selection[1], manual_selection[0]]])
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_manual_selection_partition(reordered_plan, manual_selection)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


def test_validate_manual_selection_partition_rejects_dropped_clip():
    manual_selection = _manual_selection_fixture()
    missing_plan = _manual_plan_with_clips([[manual_selection[0]]])  # second clip silently dropped
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_manual_selection_partition(missing_plan, manual_selection)


def test_validate_manual_selection_partition_rejects_invented_clip():
    manual_selection = _manual_selection_fixture()
    invented_clip = {"scene_id": "scene_999", "start_ms": 0, "end_ms": 1000}
    invented_plan = _manual_plan_with_clips([manual_selection + [invented_clip]])
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_manual_selection_partition(invented_plan, manual_selection)


def test_validate_manual_selection_partition_rejects_altered_timecode():
    manual_selection = _manual_selection_fixture()
    altered = [dict(manual_selection[0], end_ms=4999), manual_selection[1]]
    altered_plan = _manual_plan_with_clips([altered])
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_manual_selection_partition(altered_plan, manual_selection)


def test_validate_manual_selection_partition_rejects_non_voice_over_segment():
    manual_selection = _manual_selection_fixture()
    plan = _manual_plan_with_clips([manual_selection[:1]], extra_segment={
        "id": "seg_breath", "type": fs.SEGMENT_TYPE_BREATHING, "start_ms": 1000, "end_ms": 6000,
        "transcript_excerpt": "", "speaker_ids": [],
    })
    # The second manual clip was never placed in any voice_over segment's
    # clips -- a breathing segment can't carry it -- so this must still be
    # rejected as a broken partition.
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_manual_selection_partition(plan, manual_selection)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


# ---------------------------------------------------------------------------
# generate_narration_for_selected_clips (network call mocked)
# ---------------------------------------------------------------------------

def _manual_scene_index():
    return [
        {"scene_id": "scene_001", "start_ms": 0, "end_ms": 5000, "duration_ms": 5000, "speakers": ["char_1"], "transcript_overlap": "Hello there.", "quality_flags": []},
        {"scene_id": "scene_002", "start_ms": 1000, "end_ms": 6000, "duration_ms": 5000, "speakers": ["char_1"], "transcript_overlap": "Goodbye now.", "quality_flags": []},
    ]


def _valid_manual_narration_raw_plan(manual_selection):
    return {
        "characters": [],
        "segments": [
            {
                "id": "seg_01", "sequence": 1, "type": "voice_over", "narration": "A grouped narration line.",
                "estimated_duration_ms": 10000,
                "clips": [
                    {"scene_id": c["scene_id"], "start_ms": c["start_ms"], "end_ms": c["end_ms"], "description": "", "match_score": 0.9}
                    for c in manual_selection
                ],
                "source_event_ids": [],
            },
        ],
        "unresolved_ambiguities": [],
    }


def test_generate_narration_for_selected_clips_raises_when_manual_selection_empty(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    coro = fs.generate_narration_for_selected_clips(
        movie_metadata={"source_duration_ms": 3600000}, narration_language="en", narration_style="cinematic",
        scene_index=[], manual_selection=[],
    )
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


def test_generate_narration_for_selected_clips_returns_validated_plan_and_usage(monkeypatch):
    # Happy path: the model groups the user's exact clips (in order) into
    # voice_over segment(s) and narrates them -- the partition invariant
    # holds, so the plan comes back without raising.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    manual_selection = _manual_selection_fixture()
    raw_plan = _valid_manual_narration_raw_plan(manual_selection)
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(raw_plan))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_narration_for_selected_clips(
        movie_metadata=movie_metadata, narration_language="en", narration_style="cinematic",
        scene_index=_manual_scene_index(), manual_selection=manual_selection,
    ))

    fake_client.chat.completions.create.assert_called_once()
    produced_clips = [
        (clip["scene_id"], clip["start_ms"], clip["end_ms"])
        for seg in result["plan"]["segments"] for clip in seg["clips"]
    ]
    assert produced_clips == [("scene_001", 0, 5000), ("scene_002", 1000, 6000)]
    assert result["validation_report"]["valid"] is True
    assert result["usage"]["prompt_tokens"] == 10


def test_generate_narration_for_selected_clips_rejects_response_that_reorders_clips(monkeypatch):
    # Rejection path: a fabricated LLM response that reorders the user's
    # clips must never be allowed to silently diverge from manual_selection
    # (see validate_manual_selection_partition) -- it must raise even after
    # exhausting the corrective retry.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    manual_selection = _manual_selection_fixture()
    reordered_raw_plan = _valid_manual_narration_raw_plan(list(reversed(manual_selection)))
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(reordered_raw_plan))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    coro = fs.generate_narration_for_selected_clips(
        movie_metadata=movie_metadata, narration_language="en", narration_style="cinematic",
        scene_index=_manual_scene_index(), manual_selection=manual_selection,
    )
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID
    # Exhausted the corrective retry (default max attempts is 2) instead of
    # raising immediately on the first bad response.
    assert fake_client.chat.completions.create.call_count == 2


def test_generate_narration_for_selected_clips_rejects_response_that_omits_a_clip(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    manual_selection = _manual_selection_fixture()
    raw_plan_missing_clip = _valid_manual_narration_raw_plan(manual_selection[:1])
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(raw_plan_missing_clip))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    coro = fs.generate_narration_for_selected_clips(
        movie_metadata=movie_metadata, narration_language="en", narration_style="cinematic",
        scene_index=_manual_scene_index(), manual_selection=manual_selection,
    )
    with pytest.raises(fs.FilmSummaryValidationError):
        asyncio.run(coro)


def test_generate_narration_for_selected_clips_converges_after_one_correction(monkeypatch):
    # The model's first response invents an extra clip; its second response
    # (after the corrective follow-up) is a clean partition and must be
    # accepted.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    manual_selection = _manual_selection_fixture()
    invented_clip_plan = _valid_manual_narration_raw_plan(manual_selection)
    invented_clip_plan["segments"][0]["clips"].append(
        {"scene_id": "scene_999", "start_ms": 0, "end_ms": 1000, "description": "", "match_score": 0.9}
    )
    corrected_plan = _valid_manual_narration_raw_plan(manual_selection)

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(json.dumps(invented_clip_plan)),
        _fake_openai_response(json.dumps(corrected_plan)),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_narration_for_selected_clips(
        movie_metadata=movie_metadata, narration_language="en", narration_style="cinematic",
        scene_index=_manual_scene_index(), manual_selection=manual_selection,
    ))

    assert fake_client.chat.completions.create.call_count == 2
    produced_clips = [
        (clip["scene_id"], clip["start_ms"], clip["end_ms"])
        for seg in result["plan"]["segments"] for clip in seg["clips"]
    ]
    assert produced_clips == [("scene_001", 0, 5000), ("scene_002", 1000, 6000)]
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert "clip partition rule" in sent_messages[-1]["content"]


# ---------------------------------------------------------------------------
# validate_narration_translation_structure
# ---------------------------------------------------------------------------

def test_validate_narration_translation_structure_allows_narration_only_change():
    original_plan = _built_plan()
    translated_plan = json.loads(json.dumps(original_plan))
    translated_plan["segments"][0]["narration"] = "Traduction."
    fs.validate_narration_translation_structure(original_plan, translated_plan)  # must not raise


def test_validate_narration_translation_structure_rejects_altered_clip():
    original_plan = _built_plan()
    translated_plan = json.loads(json.dumps(original_plan))
    translated_plan["segments"][0]["clips"][0]["end_ms"] = 1
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_narration_translation_structure(original_plan, translated_plan)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


def test_validate_narration_translation_structure_rejects_segment_count_mismatch():
    original_plan = _built_plan()
    translated_plan = json.loads(json.dumps(original_plan))
    translated_plan["segments"].pop()
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_narration_translation_structure(original_plan, translated_plan)


def test_validate_narration_translation_structure_rejects_reordered_segments():
    original_plan = _built_plan()
    translated_plan = json.loads(json.dumps(original_plan))
    translated_plan["segments"] = list(reversed(translated_plan["segments"]))
    with pytest.raises(fs.FilmSummaryValidationError):
        fs.validate_narration_translation_structure(original_plan, translated_plan)


# ---------------------------------------------------------------------------
# translate_edit_plan_narration (network call mocked)
# ---------------------------------------------------------------------------

def _translated_raw_plan(original_plan, narration_text="Il etait une fois."):
    segments = []
    for seg in original_plan["segments"]:
        seg_copy = dict(seg)
        if seg_copy.get("type") == fs.SEGMENT_TYPE_VOICE_OVER:
            seg_copy["narration"] = narration_text
            seg_copy["clips"] = [dict(c) for c in seg_copy.get("clips") or []]
        segments.append(seg_copy)
    return {
        "status": "ok",
        "characters": original_plan.get("characters") or [],
        "segments": segments,
        "total_estimated_duration_ms": original_plan.get("total_estimated_duration_ms"),
        "unresolved_ambiguities": [],
    }


def test_translate_edit_plan_narration_translates_and_preserves_structure(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    original_plan = _built_plan()
    translated_raw = _translated_raw_plan(original_plan, "Il etait une fois.")
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(translated_raw))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000}
    result = asyncio.run(fs.translate_edit_plan_narration(
        plan=original_plan, target_language="fr", movie_metadata=movie_metadata,
    ))

    fake_client.chat.completions.create.assert_called_once()
    translated_plan = result["plan"]
    voice_over = next(s for s in translated_plan["segments"] if s["type"] == "voice_over")
    dialogue = next(s for s in translated_plan["segments"] if s["type"] == "original_dialogue")
    assert voice_over["narration"] == "Il etait une fois."
    # Everything else -- clips, timing, the original (untranslated) quoted
    # dialogue -- must come through unchanged.
    assert voice_over["clips"] == original_plan["segments"][0]["clips"]
    assert dialogue["transcript_excerpt"] == "I know."
    assert dialogue["start_ms"] == 9000 and dialogue["end_ms"] == 12000
    assert result["validation_report"]["valid"] is True
    assert result["usage"]["prompt_tokens"] == 10


def test_translate_edit_plan_narration_rejects_fabricated_clip_alteration(monkeypatch):
    # Rejection path: a fabricated response that alters a clip (not just
    # the narration) must never be allowed to silently diverge from the
    # already-approved plan (see validate_narration_translation_structure)
    # -- it must raise even after exhausting the corrective retry.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    original_plan = _built_plan()
    altered_raw = _translated_raw_plan(original_plan, "Traduction.")
    altered_raw["segments"][0]["clips"][0]["end_ms"] = 999
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(altered_raw))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000}
    coro = fs.translate_edit_plan_narration(plan=original_plan, target_language="fr", movie_metadata=movie_metadata)
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)

    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID
    # Exhausted the corrective retry (default max attempts is 2) instead of
    # raising immediately on the first bad response.
    assert fake_client.chat.completions.create.call_count == 2


def test_translate_edit_plan_narration_rejects_dropped_segment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    original_plan = _built_plan()
    raw = _translated_raw_plan(original_plan, "Traduction.")
    raw["segments"] = raw["segments"][:1]  # the original_dialogue segment silently dropped
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(raw))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000}
    coro = fs.translate_edit_plan_narration(plan=original_plan, target_language="fr", movie_metadata=movie_metadata)
    with pytest.raises(fs.FilmSummaryValidationError):
        asyncio.run(coro)


def test_translate_edit_plan_narration_converges_after_one_correction(monkeypatch):
    # The model's first response alters a clip; its second response (after
    # the corrective follow-up) keeps every field but narration unchanged
    # and must be accepted.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    original_plan = _built_plan()
    broken_raw = _translated_raw_plan(original_plan, "Traduction cassee.")
    broken_raw["segments"][0]["clips"][0]["end_ms"] = 999
    fixed_raw = _translated_raw_plan(original_plan, "Traduction correcte.")

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(json.dumps(broken_raw)),
        _fake_openai_response(json.dumps(fixed_raw)),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000}
    result = asyncio.run(fs.translate_edit_plan_narration(
        plan=original_plan, target_language="fr", movie_metadata=movie_metadata,
    ))

    assert fake_client.chat.completions.create.call_count == 2
    voice_over = next(s for s in result["plan"]["segments"] if s["type"] == "voice_over")
    assert voice_over["narration"] == "Traduction correcte."
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert "translation invariant" in sent_messages[-1]["content"]


def test_translate_edit_plan_narration_raises_when_plan_has_no_segments(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    coro = fs.translate_edit_plan_narration(plan={"segments": []}, target_language="fr", movie_metadata={})
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.PLAN_INVALID


# ---------------------------------------------------------------------------
# synthesize_tts_segment (network call mocked)
# ---------------------------------------------------------------------------

def test_synthesize_tts_segment_returns_probed_duration(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    output_path = str(tmp_path / "segment.mp3")

    # The real stream_to_file writes bytes to whatever path it's given --
    # mimic that so the temp-file-then-rename dance under test actually has
    # a file to rename.
    def _fake_stream_to_file(path):
        with open(path, "wb") as handle:
            handle.write(b"fake-audio-bytes")

    fake_response = MagicMock()
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)
    fake_response.stream_to_file = MagicMock(side_effect=_fake_stream_to_file)
    fake_client = MagicMock()
    fake_client.audio.speech.with_streaming_response.create.return_value = fake_response
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)
    monkeypatch.setattr(fs, "probe_media_duration_seconds", lambda path: 12.5)

    duration = asyncio.run(fs.synthesize_tts_segment(
        text="Hello", voice="cedar", model="gpt-4o-mini-tts", instructions="narrate", output_path=output_path,
    ))

    assert duration == 12.5
    fake_response.stream_to_file.assert_called_once()
    written_path = fake_response.stream_to_file.call_args.args[0]
    # Written to a temp path, not output_path directly, then moved into
    # place -- see synthesize_tts_segment's docstring for why.
    assert written_path != output_path
    assert not os.path.exists(written_path)
    assert os.path.exists(output_path)
    with open(output_path, "rb") as handle:
        assert handle.read() == b"fake-audio-bytes"


def test_synthesize_tts_segment_wraps_failures_as_tts_failed(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    fake_client = MagicMock()
    fake_client.audio.speech.with_streaming_response.create.side_effect = RuntimeError("boom")
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    coro = fs.synthesize_tts_segment(
        text="Hello", voice="cedar", model="gpt-4o-mini-tts", instructions="narrate",
        output_path=str(tmp_path / "segment.mp3"),
    )
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.TTS_FAILED


def test_synthesize_tts_segment_leaves_no_partial_file_on_mid_stream_failure(monkeypatch, tmp_path):
    # Regression test: a request that fails partway through streaming (a
    # dropped connection, a timeout) used to leave a partial/broken file at
    # output_path, which the voice-preview endpoint's cache check then
    # treated as valid forever -- permanently breaking that voice's preview.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    output_path = str(tmp_path / "segment.mp3")
    captured = {}

    def _fake_stream_to_file(path):
        captured["tmp_path"] = path
        with open(path, "wb") as handle:
            handle.write(b"partial-bytes")
        raise RuntimeError("connection dropped mid-stream")

    fake_response = MagicMock()
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)
    fake_response.stream_to_file = MagicMock(side_effect=_fake_stream_to_file)
    fake_client = MagicMock()
    fake_client.audio.speech.with_streaming_response.create.return_value = fake_response
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    coro = fs.synthesize_tts_segment(
        text="Hello", voice="cedar", model="gpt-4o-mini-tts", instructions="narrate", output_path=output_path,
    )
    with pytest.raises(fs.FilmSummaryValidationError):
        asyncio.run(coro)

    assert not os.path.exists(output_path)
    assert not os.path.exists(captured["tmp_path"])


def test_synthesize_tts_segment_raises_tts_failed_when_api_key_missing(monkeypatch, tmp_path):
    # _get_openai_client() used to be called outside the try/except, so a
    # missing API key raised a bare RuntimeError instead of the
    # FilmSummaryValidationError callers (and the voice-preview endpoint)
    # expect -- surfacing as an unhandled 500 instead of a clean 502.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    coro = fs.synthesize_tts_segment(
        text="Hello", voice="cedar", model="gpt-4o-mini-tts", instructions="narrate",
        output_path=str(tmp_path / "segment.mp3"),
    )
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        asyncio.run(coro)
    assert exc_info.value.code == fs.FilmSummaryErrorCode.TTS_FAILED


# ---------------------------------------------------------------------------
# transcribe_video_with_timecodes (AssemblyAI mocked out at module level)
# ---------------------------------------------------------------------------

def test_transcribe_video_with_timecodes_raises_when_api_key_missing(monkeypatch):
    monkeypatch.delenv("ASSEMBLYAI_API_KEY", raising=False)
    coro = fs.transcribe_video_with_timecodes("/tmp/does-not-matter.mp4")
    with pytest.raises(RuntimeError):
        asyncio.run(coro)


def _install_fake_assemblyai(monkeypatch, *, utterances=None, status_error=False, fallback_text=""):
    # Note: the fake transcript is built as a SimpleNamespace (not a class
    # body) because a class body can't close over an enclosing function's
    # locals the way a nested function can -- `attr = utterances` inside a
    # class statement here would raise NameError.
    fake_module = types.ModuleType("assemblyai")

    class _TranscriptStatus:
        error = "error"
        completed = "completed"

    fake_transcript = types.SimpleNamespace(
        status=_TranscriptStatus.error if status_error else _TranscriptStatus.completed,
        error="boom" if status_error else None,
        utterances=utterances,
        text=fallback_text,
        language_code="en",
        audio_duration=42.0,
    )

    class _Transcriber:
        def __init__(self, config=None):
            self.config = config

        def transcribe(self, video_path):
            return fake_transcript

    fake_module.settings = types.SimpleNamespace(api_key=None)
    fake_module.TranscriptStatus = _TranscriptStatus
    fake_module.TranscriptionConfig = lambda **kwargs: kwargs
    fake_module.Transcriber = _Transcriber
    monkeypatch.setitem(sys.modules, "assemblyai", fake_module)


def test_transcribe_video_with_timecodes_returns_segments(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    utterance = types.SimpleNamespace(start=1000, end=4000, speaker="A", text="Hello there")
    _install_fake_assemblyai(monkeypatch, utterances=[utterance])

    result = asyncio.run(fs.transcribe_video_with_timecodes("/tmp/video.mp4"))

    assert result["segments"] == [{"start_ms": 1000, "end_ms": 4000, "speaker": "A", "text": "Hello there"}]
    assert result["language"] == "en"


def test_transcribe_video_with_timecodes_falls_back_to_single_segment(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    _install_fake_assemblyai(monkeypatch, utterances=[], fallback_text="Full transcript text")

    result = asyncio.run(fs.transcribe_video_with_timecodes("/tmp/video.mp4"))

    assert len(result["segments"]) == 1
    assert result["segments"][0]["text"] == "Full transcript text"
    assert result["segments"][0]["end_ms"] == 42000


def test_transcribe_video_with_timecodes_raises_on_transcript_error(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    _install_fake_assemblyai(monkeypatch, utterances=[], status_error=True)

    coro = fs.transcribe_video_with_timecodes("/tmp/video.mp4")
    with pytest.raises(RuntimeError):
        asyncio.run(coro)


# ---------------------------------------------------------------------------
# download_youtube_source (delegates to the shared youtube_download module)
# ---------------------------------------------------------------------------

def test_download_youtube_source_delegates_to_shared_youtube_download(monkeypatch, tmp_path):
    fake_module = types.ModuleType("youtube_download")
    calls = []

    def fake_download_youtube_video(url, output_dir):
        calls.append((url, output_dir))
        return (f"{output_dir}/My_Movie.mp4", "My_Movie")

    fake_module.download_youtube_video = fake_download_youtube_video
    monkeypatch.setitem(sys.modules, "youtube_download", fake_module)

    result = fs.download_youtube_source("https://youtu.be/xyz", str(tmp_path))

    assert calls == [("https://youtu.be/xyz", str(tmp_path))]
    assert result["path"] == f"{tmp_path}/My_Movie.mp4"
    assert result["title"] == "My Movie"


# ---------------------------------------------------------------------------
# detect_scenes (PySceneDetect mocked out at module level)
# ---------------------------------------------------------------------------

def _install_fake_scenedetect(monkeypatch, *, scene_list, duration_seconds=0.0):
    scenedetect_mod = types.ModuleType("scenedetect")
    detectors_mod = types.ModuleType("scenedetect.detectors")

    class _FakeVideo:
        duration = types.SimpleNamespace(get_seconds=lambda: duration_seconds)

    class _FakeSceneManager:
        def __init__(self):
            self.detectors = []

        def add_detector(self, detector):
            self.detectors.append(detector)

        def detect_scenes(self, video):
            pass

        def get_scene_list(self):
            return scene_list

    scenedetect_mod.open_video = lambda path: _FakeVideo()
    scenedetect_mod.SceneManager = _FakeSceneManager
    detectors_mod.ContentDetector = lambda threshold=27.0, min_scene_len=15: MagicMock()
    monkeypatch.setitem(sys.modules, "scenedetect", scenedetect_mod)
    monkeypatch.setitem(sys.modules, "scenedetect.detectors", detectors_mod)


def _fake_timecode(seconds):
    return types.SimpleNamespace(get_seconds=lambda: seconds)


def test_detect_scenes_converts_scene_list_to_milliseconds(monkeypatch):
    scene_list = [(_fake_timecode(0.0), _fake_timecode(2.5)), (_fake_timecode(2.5), _fake_timecode(5.0))]
    _install_fake_scenedetect(monkeypatch, scene_list=scene_list)

    scenes = fs.detect_scenes("/tmp/video.mp4")

    assert scenes == [
        {"scene_id": "scene_001", "start_ms": 0, "end_ms": 2500, "quality_flags": []},
        {"scene_id": "scene_002", "start_ms": 2500, "end_ms": 5000, "quality_flags": []},
    ]


def test_detect_scenes_falls_back_to_single_scene_when_no_boundaries_found(monkeypatch):
    _install_fake_scenedetect(monkeypatch, scene_list=[], duration_seconds=10.0)

    scenes = fs.detect_scenes("/tmp/video.mp4")

    assert scenes == [{"scene_id": "scene_001", "start_ms": 0, "end_ms": 10000, "quality_flags": []}]


# ---------------------------------------------------------------------------
# probe_technical_metadata / probe_media_duration_seconds / extract_keyframe
# ---------------------------------------------------------------------------

_FFPROBE_JSON = json.dumps({
    "format": {"format_name": "mov,mp4", "duration": "120.5"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080, "avg_frame_rate": "30/1"},
        {"codec_type": "audio", "codec_name": "aac"},
    ],
})


def test_probe_technical_metadata_parses_ffprobe_output(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: _FFPROBE_JSON.encode())

    meta = fs.probe_technical_metadata("/tmp/video.mp4")

    assert meta["has_video"] is True
    assert meta["has_audio"] is True
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["fps"] == 30.0
    assert meta["duration_seconds"] == 120.5


def test_probe_technical_metadata_returns_defaults_on_ffprobe_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "ffprobe")

    monkeypatch.setattr(subprocess, "check_output", _raise)

    meta = fs.probe_technical_metadata("/tmp/video.mp4")

    assert meta["has_video"] is False
    assert meta["has_audio"] is False
    assert meta["duration_seconds"] == 0.0


def test_parse_video_stream_fps_handles_zero_denominator():
    assert fs._parse_video_stream_fps({"avg_frame_rate": "30/0"}) == 0.0


def test_parse_video_stream_fps_handles_malformed_rate():
    assert fs._parse_video_stream_fps({"avg_frame_rate": "not-a-rate"}) == 0.0


def test_probe_media_duration_seconds_parses_output(monkeypatch):
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: b"5.5\n")
    assert fs.probe_media_duration_seconds("/tmp/audio.mp3") == 5.5


def test_probe_media_duration_seconds_returns_zero_on_failure(monkeypatch):
    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "ffprobe")

    monkeypatch.setattr(subprocess, "check_output", _raise)
    assert fs.probe_media_duration_seconds("/tmp/audio.mp3") == 0.0


def test_extract_keyframe_returns_true_on_success(monkeypatch, tmp_path):
    output_path = tmp_path / "frame.jpg"

    def _fake_run(cmd, **kwargs):
        output_path.write_bytes(b"fake")
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", _fake_run)
    assert fs.extract_keyframe("/tmp/video.mp4", 1000, str(output_path)) is True


def test_extract_keyframe_returns_false_on_nonzero_exit(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=1))
    assert fs.extract_keyframe("/tmp/video.mp4", 1000, str(tmp_path / "frame.jpg")) is False


def test_extract_classification_keyframes_skips_frames_that_fail_to_extract(monkeypatch):
    scene_index = [{"scene_id": f"scene_{i:03d}", "start_ms": i * 1000, "end_ms": (i + 1) * 1000} for i in range(5)]
    monkeypatch.setattr(fs, "extract_keyframe", lambda *a, **k: False)

    assert fs.extract_classification_keyframes("/tmp/video.mp4", scene_index) == []


# ---------------------------------------------------------------------------
# encode_image_data_url / extract_classification_keyframes
# ---------------------------------------------------------------------------

def test_encode_image_data_url_reads_and_encodes_file(tmp_path):
    image_path = tmp_path / "frame.jpg"
    image_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    data_url = fs.encode_image_data_url(str(image_path))
    assert data_url.startswith("data:image/jpeg;base64,")


def test_encode_image_data_url_returns_none_for_missing_file():
    assert fs.encode_image_data_url("/nonexistent/path/frame.jpg") is None


def test_extract_classification_keyframes_returns_empty_for_no_scenes():
    assert fs.extract_classification_keyframes("/some/video.mp4", []) == []
