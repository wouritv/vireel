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


def test_validate_edit_plan_content_never_flags_repeated_clip():
    # A clip reused across segments (same scene_id/start_ms/end_ms) is
    # deliberately never flagged at all -- not as an error, not even as a
    # warning. Discouraging reuse is the planning prompt's job alone
    # (VISUAL MATCHING RULE 6); validation never surfaces anything about it.
    plan = _built_plan(target_duration_ms=32000)
    plan["segments"][0]["clips"].append(dict(plan["segments"][0]["clips"][0]))
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["warnings"] == []


# ---------------------------------------------------------------------------
# FILM_SUMMARY_MAX_PLAN_DURATION_MS ideal ceiling (non-blocking -- "il ne
# dois pas y avoir de bloquant" -- both automatic and manual plans go
# through validate_edit_plan_content, which only ever warns about it)
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
    assert report["warnings"] == []


def test_validate_edit_plan_content_warns_but_accepts_plan_over_max_duration():
    plan = _plan_with_total_duration_ms(fs.FILM_SUMMARY_MAX_PLAN_DURATION_MS + 1000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    # Going over the ideal ceiling must never block the plan -- it's a
    # warning only, "valid" stays true and there's nothing in "errors".
    assert report["valid"] is True
    assert report["errors"] == []
    assert any("depasse la duree ideale" in w for w in report["warnings"])


def test_validate_edit_plan_content_max_duration_threshold_is_configurable(monkeypatch):
    # A plan comfortably under the default 5-minute ceiling must start
    # warning once the configurable threshold is lowered below its total --
    # proves the check reads FILM_SUMMARY_MAX_PLAN_DURATION_MS live rather
    # than a value captured once at import time -- but never blocks either way.
    plan = _plan_with_total_duration_ms(60000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    assert report["warnings"] == []

    monkeypatch.setattr(fs, "FILM_SUMMARY_MAX_PLAN_DURATION_MS", 30000)
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is True
    assert any("depasse la duree ideale" in w for w in report["warnings"])


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


def test_build_tts_instructions_maps_iso_code_to_full_name():
    # narration_language is persisted as the 2-letter code the app's own
    # language pickers use ("fr") -- dropping that raw code straight into
    # the instruction sentence ("Speak in fluent fr...") is meaningless to
    # the TTS engine and was silently steering it toward English regardless
    # of what the user actually chose.
    assert "fluent French" in fs.build_tts_instructions("fr")
    assert "fluent French" in fs.build_tts_instructions("FR")
    assert "fluent Spanish" in fs.build_tts_instructions("es")


def test_build_tts_instructions_falls_back_to_raw_value_for_unknown_code():
    assert "fluent Klingon" in fs.build_tts_instructions("Klingon")
    assert "the narration language" in fs.build_tts_instructions("")


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
    # An unknown-character warning never blocks validation, but is still
    # worth one corrective retry (see generate_edit_plan) -- the message
    # must mention it distinctly from any blocking error.
    report = {
        "errors": [],
        "warnings": ["Le segment seg_002 reference un personnage inconnu char_missing"],
    }
    plan = {"total_estimated_duration_ms": 29000}
    message = fs._build_planning_correction_message(report, plan, 29000, 0.15)
    assert "personnage inconnu" in message["content"]
    assert "did not block validation" in message["content"]
    assert "blocking errors" not in message["content"]


def test_build_planning_correction_message_includes_repeated_clips_too():
    # Clip reuse must never appear in validation_report (see
    # validate_edit_plan_content's docstring), but is still worth one
    # corrective retry via this separate repeated_clips argument.
    report = {"errors": [], "warnings": []}
    plan = {"total_estimated_duration_ms": 29000}
    repeated_clips = [("seg_003", ("scene_183", 1439291, 1461583))]
    message = fs._build_planning_correction_message(report, plan, 29000, 0.15, repeated_clips)
    assert "scene_183" in message["content"]
    assert "VISUAL MATCHING RULE 6" in message["content"]


# ---------------------------------------------------------------------------
# _find_repeated_voice_over_clips / _deduplicate_voice_over_clips
# ---------------------------------------------------------------------------

def _voice_over_segment(seg_id, sequence, clips):
    return {
        "id": seg_id, "sequence": sequence, "type": fs.SEGMENT_TYPE_VOICE_OVER,
        "narration": "Some narration.", "estimated_duration_ms": 5000, "clips": clips,
    }


def test_find_repeated_voice_over_clips_detects_reuse_across_segments():
    clip = {"scene_id": "scene_183", "start_ms": 1439291, "end_ms": 1461583}
    segments = [
        _voice_over_segment("seg_001", 1, [dict(clip)]),
        _voice_over_segment("seg_002", 2, [{"scene_id": "scene_270", "start_ms": 0, "end_ms": 5000}]),
        _voice_over_segment("seg_003", 3, [dict(clip)]),  # reuses seg_001's exact clip
    ]
    repeats = fs._find_repeated_voice_over_clips(segments)
    assert repeats == [("seg_003", ("scene_183", 1439291, 1461583))]


def test_find_repeated_voice_over_clips_ignores_non_voice_over_segments():
    segments = [
        {"id": "seg_001", "sequence": 1, "type": "original_dialogue", "start_ms": 0, "end_ms": 1000},
        {"id": "seg_002", "sequence": 2, "type": "breathing", "start_ms": 0, "end_ms": 1000},
    ]
    assert fs._find_repeated_voice_over_clips(segments) == []


def test_find_repeated_voice_over_clips_empty_when_all_distinct():
    segments = [
        _voice_over_segment("seg_001", 1, [{"scene_id": "scene_001", "start_ms": 0, "end_ms": 1000}]),
        _voice_over_segment("seg_002", 2, [{"scene_id": "scene_002", "start_ms": 0, "end_ms": 1000}]),
    ]
    assert fs._find_repeated_voice_over_clips(segments) == []


def test_deduplicate_voice_over_clips_drops_only_the_later_occurrence():
    clip = {"scene_id": "scene_183", "start_ms": 1439291, "end_ms": 1461583}
    other_clip = {"scene_id": "scene_270", "start_ms": 0, "end_ms": 5000}
    segments = [
        _voice_over_segment("seg_001", 1, [dict(clip)]),
        _voice_over_segment("seg_002", 2, [dict(other_clip), dict(clip)]),  # dict(clip) here is the repeat
    ]
    deduped = fs._deduplicate_voice_over_clips(segments)
    assert deduped[0]["clips"] == [clip]  # first occurrence untouched
    assert deduped[1]["clips"] == [other_clip]  # only the repeat was dropped, other_clip kept
    assert fs._find_repeated_voice_over_clips(deduped) == []


def test_deduplicate_voice_over_clips_leaves_segment_with_no_clips_when_all_are_repeats():
    clip = {"scene_id": "scene_183", "start_ms": 1439291, "end_ms": 1461583}
    segments = [
        _voice_over_segment("seg_001", 1, [dict(clip)]),
        _voice_over_segment("seg_002", 2, [dict(clip)]),  # entirely a repeat of seg_001's only clip
    ]
    deduped = fs._deduplicate_voice_over_clips(segments)
    assert deduped[1]["clips"] == []  # falls back to render's blank-segment path, never a duplicate


def test_deduplicate_voice_over_clips_passes_through_segments_without_clips_or_type():
    segments = [
        {"id": "seg_001", "sequence": 1, "type": "original_dialogue", "start_ms": 0, "end_ms": 1000},
        _voice_over_segment("seg_002", 2, []),
    ]
    assert fs._deduplicate_voice_over_clips(segments) == segments


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
    # An unknown-character warning never makes validation fail, so this
    # plan is "valid": True on the first attempt. The retry must still fire
    # to give the model a chance to fix it, and must not block the final
    # result either way.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    unknown_character_plan = _valid_raw_plan()
    unknown_character_plan["segments"][1]["speaker_ids"] = ["char_missing"]

    corrected_plan = _valid_raw_plan()  # seg_002.speaker_ids back to the known ["char_1"]

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(json.dumps(unknown_character_plan)),
        _fake_openai_response(json.dumps(corrected_plan)),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=29000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert "personnage inconnu" in sent_messages[-1]["content"]
    assert "did not block validation" in sent_messages[-1]["content"]
    # The corrected plan no longer references the unknown character.
    assert result["plan"]["segments"][1]["speaker_ids"] == ["char_1"]


def test_generate_edit_plan_does_not_retry_forever_on_persistent_warning(monkeypatch):
    # The warning-driven retry must still respect max_attempts and return
    # the last plan rather than looping -- the warning is never blocking.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    unknown_character_plan = _valid_raw_plan()
    unknown_character_plan["segments"][1]["speaker_ids"] = ["char_missing"]
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(unknown_character_plan))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=29000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    assert result["plan"]["segments"][1]["speaker_ids"] == ["char_missing"]


def _raw_plan_with_repeated_clip():
    repeated_clip = {"scene_id": "scene_183", "start_ms": 1439291, "end_ms": 1461583, "description": "x", "match_score": 0.9}
    return {
        "characters": [],
        "segments": [
            {
                "id": "seg_001", "sequence": 1, "type": "voice_over", "narration": "First beat.",
                "estimated_duration_ms": 13000, "clips": [dict(repeated_clip)], "source_event_ids": ["event_1"],
            },
            {
                "id": "seg_002", "sequence": 2, "type": "voice_over", "narration": "Second beat.",
                "estimated_duration_ms": 13000, "clips": [dict(repeated_clip)], "source_event_ids": ["event_1"],
            },
        ],
        "unresolved_ambiguities": [],
    }


def test_generate_edit_plan_retries_on_repeated_clip_even_when_already_valid(monkeypatch):
    # No duration/warning issue here (total 26000ms matches the target
    # exactly) -- the repeat alone must still trigger one corrective retry,
    # the same silent mechanism used for warnings (see generate_edit_plan).
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    repeated_clip_plan = _raw_plan_with_repeated_clip()
    corrected_plan = _raw_plan_with_repeated_clip()
    corrected_plan["segments"][1]["clips"] = [{"scene_id": "scene_270", "start_ms": 0, "end_ms": 5000, "description": "y", "match_score": 0.8}]

    fake_client = MagicMock()
    fake_client.chat.completions.create.side_effect = [
        _fake_openai_response(json.dumps(repeated_clip_plan)),
        _fake_openai_response(json.dumps(corrected_plan)),
    ]
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=26000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2
    sent_messages = fake_client.chat.completions.create.call_args_list[1].kwargs["messages"]
    assert "scene_183" in sent_messages[-1]["content"]
    assert "VISUAL MATCHING RULE 6" in sent_messages[-1]["content"]
    assert result["plan"]["segments"][1]["clips"][0]["scene_id"] == "scene_270"


def test_generate_edit_plan_deduplicates_repeated_clip_when_model_never_fixes_it(monkeypatch):
    # "ne jamais utiliser la meme scene 2 fois ... l'utilisateur ne dois pas
    # intervenir" -- even if the model keeps reusing the same clip across
    # every attempt, the plan generate_edit_plan actually returns must
    # never contain the duplicate, with no error/warning raised about it.
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    repeated_clip_plan = _raw_plan_with_repeated_clip()
    fake_client = MagicMock()
    fake_client.chat.completions.create.return_value = _fake_openai_response(json.dumps(repeated_clip_plan))
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)

    movie_metadata = {"title": "M", "source_duration_ms": 3600000, "source_language": "en", "narration_language": "en"}
    result = asyncio.run(fs.generate_edit_plan(
        movie_metadata=movie_metadata, target_duration_ms=26000, narration_language="en", narration_style="cinematic",
        transcript_segments=[], scene_index=[], generation_constraints={},
    ))

    assert fake_client.chat.completions.create.call_count == 2  # respects max_attempts, no infinite loop
    assert result["plan"]["segments"][0]["clips"][0]["scene_id"] == "scene_183"  # first use kept
    assert result["plan"]["segments"][1]["clips"] == []  # later duplicate dropped, never shipped
    assert fs._find_repeated_voice_over_clips(result["plan"]["segments"]) == []


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


def test_transcribe_video_with_timecodes_enables_language_detection_without_hint(monkeypatch):
    # Without language_detection, AssemblyAI's TranscriptionConfig silently
    # assumes English rather than actually detecting anything -- this is
    # the config every transcription must request when the caller doesn't
    # already know the language.
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    _install_fake_assemblyai(monkeypatch, utterances=[])
    captured_config = {}
    real_transcriber_init = sys.modules["assemblyai"].Transcriber.__init__

    def _capturing_init(self, config=None):
        captured_config.update(config or {})
        real_transcriber_init(self, config)

    sys.modules["assemblyai"].Transcriber.__init__ = _capturing_init

    asyncio.run(fs.transcribe_video_with_timecodes("/tmp/video.mp4"))

    assert captured_config.get("language_detection") is True
    assert "language_code" not in captured_config


def test_transcribe_video_with_timecodes_uses_language_hint_instead_of_detection(monkeypatch):
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    _install_fake_assemblyai(monkeypatch, utterances=[])
    captured_config = {}
    real_transcriber_init = sys.modules["assemblyai"].Transcriber.__init__

    def _capturing_init(self, config=None):
        captured_config.update(config or {})
        real_transcriber_init(self, config)

    sys.modules["assemblyai"].Transcriber.__init__ = _capturing_init

    asyncio.run(fs.transcribe_video_with_timecodes("/tmp/video.mp4", language_hint="FR"))

    # The user's own choice is passed straight through as language_code
    # (normalized to lowercase) instead of asking AssemblyAI to guess.
    assert captured_config.get("language_code") == "fr"
    assert "language_detection" not in captured_config


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
