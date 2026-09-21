import asyncio
import json
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


def test_build_planning_correction_message_includes_duration_hint_only_for_duration_errors():
    duration_report = {"errors": ["Total estimated duration 240679ms is outside the 15% tolerance around the 401000ms target"]}
    plan = {"total_estimated_duration_ms": 240679}
    message = fs._build_planning_correction_message(duration_report, plan, 401000)
    assert "short of the target" in message["content"]

    other_report = {"errors": ["Segment sequence numbers must be contiguous, starting at 1, in playback order"]}
    other_message = fs._build_planning_correction_message(other_report, plan, 401000)
    assert "short of the target" not in other_message["content"]


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
# synthesize_tts_segment (network call mocked)
# ---------------------------------------------------------------------------

def test_synthesize_tts_segment_returns_probed_duration(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    output_path = str(tmp_path / "segment.mp3")

    fake_response = MagicMock()
    fake_response.__enter__ = MagicMock(return_value=fake_response)
    fake_response.__exit__ = MagicMock(return_value=False)
    fake_client = MagicMock()
    fake_client.audio.speech.with_streaming_response.create.return_value = fake_response
    monkeypatch.setattr(fs, "_get_openai_client", lambda: fake_client)
    monkeypatch.setattr(fs, "probe_media_duration_seconds", lambda path: 12.5)

    duration = asyncio.run(fs.synthesize_tts_segment(
        text="Hello", voice="cedar", model="gpt-4o-mini-tts", instructions="narrate", output_path=output_path,
    ))

    assert duration == 12.5
    fake_response.stream_to_file.assert_called_once_with(output_path)


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
