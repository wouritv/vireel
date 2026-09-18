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
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**_valid_technical_kwargs(size_bytes=30 * 1024 ** 3))
    assert exc_info.value.code == fs.FilmSummaryErrorCode.SOURCE_TOO_LARGE


def test_validate_technical_constraints_rejects_too_short():
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**_valid_technical_kwargs(duration_seconds=60))
    assert exc_info.value.code == fs.FilmSummaryErrorCode.SOURCE_TOO_SHORT


def test_validate_technical_constraints_rejects_too_long():
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**_valid_technical_kwargs(duration_seconds=100000))
    assert exc_info.value.code == fs.FilmSummaryErrorCode.SOURCE_TOO_LONG


def test_validate_technical_constraints_rejects_missing_video_track():
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**_valid_technical_kwargs(has_video_track=False))
    assert exc_info.value.code == fs.FilmSummaryErrorCode.NO_VIDEO_TRACK


def test_validate_technical_constraints_rejects_missing_audio_track():
    with pytest.raises(fs.FilmSummaryValidationError) as exc_info:
        fs.validate_technical_constraints(**_valid_technical_kwargs(has_audio_track=False))
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
    assert any("unknown scene_id" in e for e in report["errors"])


def test_validate_edit_plan_content_flags_out_of_bounds_clip():
    plan = _built_plan()
    plan["segments"][0]["clips"][0]["end_ms"] = 10_000_000  # beyond source duration
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert report["valid"] is False
    assert any("out-of-bounds" in e for e in report["errors"])


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
    assert any("overlap" in e for e in report["errors"])


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
    plan = _built_plan(target_duration_ms=32000)
    plan["segments"][0]["clips"].append(dict(plan["segments"][0]["clips"][0]))
    report = fs.validate_edit_plan_content(
        plan, source_duration_ms=3600000, valid_scene_ids=["scene_001"], duration_tolerance_ratio=0.5,
    )
    assert any("reused" in w for w in report["warnings"])


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
