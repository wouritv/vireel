import types

import pytest

import film_summary
import film_summary_render as render


CANVAS = {"width": 1280, "height": 720, "fps": 30.0}


def _fake_completed_process(returncode=0, stderr=b""):
    return types.SimpleNamespace(returncode=returncode, stderr=stderr)


def _capture_ffmpeg_calls(monkeypatch, returncode=0, stderr=b""):
    calls = []

    def _fake_run(cmd, **kwargs):
        calls.append(cmd)
        return _fake_completed_process(returncode=returncode, stderr=stderr)

    monkeypatch.setattr(render.subprocess, "run", _fake_run)
    return calls


# ---------------------------------------------------------------------------
# _run_ffmpeg
# ---------------------------------------------------------------------------

def test_run_ffmpeg_succeeds_on_zero_returncode(monkeypatch):
    _capture_ffmpeg_calls(monkeypatch, returncode=0)
    render._run_ffmpeg(["ffmpeg", "-y"])  # should not raise


def test_run_ffmpeg_raises_render_failed_on_nonzero_returncode(monkeypatch):
    _capture_ffmpeg_calls(monkeypatch, returncode=1, stderr=b"boom")
    with pytest.raises(film_summary.FilmSummaryValidationError) as exc_info:
        render._run_ffmpeg(["ffmpeg", "-y"])
    assert exc_info.value.code == film_summary.FilmSummaryErrorCode.RENDER_FAILED
    assert "boom" in str(exc_info.value)


def test_run_ffmpeg_raises_render_failed_on_timeout(monkeypatch):
    def _fake_run(cmd, **kwargs):
        raise render.subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

    monkeypatch.setattr(render.subprocess, "run", _fake_run)
    with pytest.raises(film_summary.FilmSummaryValidationError) as exc_info:
        render._run_ffmpeg(["ffmpeg", "-y"], timeout_seconds=5)
    assert exc_info.value.code == film_summary.FilmSummaryErrorCode.RENDER_FAILED


# ---------------------------------------------------------------------------
# _target_canvas
# ---------------------------------------------------------------------------

def test_target_canvas_rounds_odd_dimensions_up(monkeypatch):
    monkeypatch.setattr(render, "probe_technical_metadata", lambda path: {"width": 1281, "height": 721, "fps": 24.0})
    canvas = render._target_canvas("/tmp/video.mp4")
    assert canvas == {"width": 1282, "height": 722, "fps": 24.0}


def test_target_canvas_clamps_invalid_fps_to_30(monkeypatch):
    monkeypatch.setattr(render, "probe_technical_metadata", lambda path: {"width": 1280, "height": 720, "fps": 0.0})
    canvas = render._target_canvas("/tmp/video.mp4")
    assert canvas["fps"] == 30.0


def test_target_canvas_clamps_excessive_fps_to_30(monkeypatch):
    monkeypatch.setattr(render, "probe_technical_metadata", lambda path: {"width": 1280, "height": 720, "fps": 240.0})
    canvas = render._target_canvas("/tmp/video.mp4")
    assert canvas["fps"] == 30.0


def test_target_canvas_falls_back_to_defaults_when_metadata_missing(monkeypatch):
    monkeypatch.setattr(render, "probe_technical_metadata", lambda path: {"width": 0, "height": 0, "fps": 0.0})
    canvas = render._target_canvas("/tmp/video.mp4")
    assert canvas == {"width": 1280, "height": 720, "fps": 30.0}


# ---------------------------------------------------------------------------
# extract_source_subclip / build_blank_segment / concat_video_clips
# ---------------------------------------------------------------------------

def test_extract_source_subclip_builds_scale_and_pad_filter(monkeypatch):
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.extract_source_subclip("/tmp/source.mp4", 1000, 4000, "/tmp/out.mp4", canvas=CANVAS)
    cmd = calls[0]
    assert "scale=1280:720:force_original_aspect_ratio=decrease" in cmd[cmd.index("-vf") + 1]
    assert "-ss" in cmd
    assert "1.000" in cmd


def test_build_blank_segment_uses_lavfi_color_source(monkeypatch):
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.build_blank_segment(5.0, "/tmp/out.mp4", canvas=CANVAS)
    cmd = calls[0]
    assert any("color=c=black" in part for part in cmd)


def test_concat_video_clips_writes_filelist_and_invokes_ffmpeg(monkeypatch, tmp_path):
    calls = _capture_ffmpeg_calls(monkeypatch)
    clip_paths = [str(tmp_path / "a.mp4"), str(tmp_path / "b.mp4")]
    output_path = str(tmp_path / "out.mp4")

    render.concat_video_clips(clip_paths, output_path, str(tmp_path))

    filelist_path = tmp_path / "concat_out.mp4.txt"
    assert filelist_path.exists()
    content = filelist_path.read_text()
    assert f"file '{clip_paths[0]}'" in content
    assert f"file '{clip_paths[1]}'" in content
    assert calls[0][:2] == ["ffmpeg", "-y"]


# ---------------------------------------------------------------------------
# pad_or_trim_to_duration
# ---------------------------------------------------------------------------

def test_pad_or_trim_renames_when_duration_already_matches(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "probe_media_duration_seconds", lambda path: 10.0)
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake")
    output_path = tmp_path / "output.mp4"

    render.pad_or_trim_to_duration(str(input_path), 10.05, str(output_path))

    assert output_path.exists()
    assert not input_path.exists()


def test_pad_or_trim_renames_when_probe_returns_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "probe_media_duration_seconds", lambda path: 0.0)
    input_path = tmp_path / "input.mp4"
    input_path.write_bytes(b"fake")
    output_path = tmp_path / "output.mp4"

    render.pad_or_trim_to_duration(str(input_path), 10.0, str(output_path))

    assert output_path.exists()


def test_pad_or_trim_trims_when_too_long(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "probe_media_duration_seconds", lambda path: 30.0)
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.pad_or_trim_to_duration(str(tmp_path / "input.mp4"), 10.0, str(tmp_path / "output.mp4"))
    cmd = calls[0]
    assert "-t" in cmd
    assert "10.000" in cmd
    assert "copy" in cmd


def test_pad_or_trim_pads_when_too_short(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "probe_media_duration_seconds", lambda path: 5.0)
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.pad_or_trim_to_duration(str(tmp_path / "input.mp4"), 10.0, str(tmp_path / "output.mp4"))
    cmd = calls[0]
    assert any("tpad=stop_mode=clone" in part for part in cmd)
    assert any("apad=pad_dur" in part for part in cmd)


# ---------------------------------------------------------------------------
# duck_and_mix_narration / normalize_audio_loudness / encode_preview
# ---------------------------------------------------------------------------

def test_duck_and_mix_narration_builds_amix_filter(monkeypatch):
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.duck_and_mix_narration("/tmp/visual.mp4", "/tmp/narration.mp3", "/tmp/out.mp4")
    cmd = calls[0]
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "amix=inputs=2" in filter_complex
    assert f"volume={render.ORIGINAL_AUDIO_DUCK_VOLUME}" in filter_complex


def test_normalize_audio_loudness_uses_loudnorm_filter(monkeypatch):
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.normalize_audio_loudness("/tmp/in.mp4", "/tmp/out.mp4")
    cmd = calls[0]
    assert "loudnorm=I=-16:TP=-1.5:LRA=11" in cmd[cmd.index("-af") + 1]


def test_encode_preview_rounds_odd_height_up(monkeypatch):
    calls = _capture_ffmpeg_calls(monkeypatch)
    render.encode_preview("/tmp/in.mp4", "/tmp/out.mp4", height=481)
    cmd = calls[0]
    assert "scale=-2:482" in cmd[cmd.index("-vf") + 1]


# ---------------------------------------------------------------------------
# _build_voice_over_segment_clip / _build_original_segment_clip
# ---------------------------------------------------------------------------

def test_build_voice_over_segment_clip_uses_blank_segment_when_no_clips(monkeypatch, tmp_path):
    _capture_ffmpeg_calls(monkeypatch)
    monkeypatch.setattr(render, "probe_media_duration_seconds", lambda path: 20.0)
    segment = {"id": "seg_1", "estimated_duration_ms": 20000, "clips": []}

    result = render._build_voice_over_segment_clip(segment, "/tmp/source.mp4", None, str(tmp_path), CANVAS)

    assert result.endswith("seg_1_visual.mp4")


def test_build_voice_over_segment_clip_concatenates_multiple_clips(monkeypatch, tmp_path):
    concat_calls = []
    monkeypatch.setattr(render, "concat_video_clips", lambda paths, out, work_dir: concat_calls.append(paths))
    monkeypatch.setattr(render, "extract_source_subclip", lambda *a, **k: None)
    monkeypatch.setattr(render, "pad_or_trim_to_duration", lambda inp, dur, out: None)
    segment = {
        "id": "seg_2", "estimated_duration_ms": 15000,
        "clips": [{"start_ms": 0, "end_ms": 1000}, {"start_ms": 2000, "end_ms": 3000}],
    }

    result = render._build_voice_over_segment_clip(segment, "/tmp/source.mp4", None, str(tmp_path), CANVAS)

    assert len(concat_calls[0]) == 2
    assert result.endswith("seg_2_visual.mp4")


def test_build_voice_over_segment_clip_mixes_narration_when_present(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "extract_source_subclip", lambda *a, **k: None)
    monkeypatch.setattr(render, "pad_or_trim_to_duration", lambda inp, dur, out: None)
    duck_calls = []
    monkeypatch.setattr(render, "duck_and_mix_narration", lambda *a, **k: duck_calls.append(a))

    narration_path = tmp_path / "narration.mp3"
    narration_path.write_bytes(b"fake")
    segment = {"id": "seg_3", "estimated_duration_ms": 10000, "clips": [{"start_ms": 0, "end_ms": 1000}]}

    result = render._build_voice_over_segment_clip(segment, "/tmp/source.mp4", str(narration_path), str(tmp_path), CANVAS)

    assert len(duck_calls) == 1
    assert result.endswith("seg_3_final.mp4")


def test_build_voice_over_segment_clip_ignores_missing_narration_file(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "extract_source_subclip", lambda *a, **k: None)
    monkeypatch.setattr(render, "pad_or_trim_to_duration", lambda inp, dur, out: None)
    segment = {"id": "seg_4", "estimated_duration_ms": 10000, "clips": [{"start_ms": 0, "end_ms": 1000}]}

    result = render._build_voice_over_segment_clip(
        segment, "/tmp/source.mp4", str(tmp_path / "does_not_exist.mp3"), str(tmp_path), CANVAS,
    )

    assert result.endswith("seg_4_visual.mp4")


def test_build_original_segment_clip_extracts_subclip(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(render, "extract_source_subclip", lambda *a, **k: calls.append((a, k)))
    segment = {"id": "seg_5", "start_ms": 1000, "end_ms": 3000}

    result = render._build_original_segment_clip(segment, "/tmp/source.mp4", str(tmp_path), CANVAS)

    assert result.endswith("seg_5_final.mp4")
    assert len(calls) == 1


# ---------------------------------------------------------------------------
# render_edit_plan (full orchestration)
# ---------------------------------------------------------------------------

def _sample_plan():
    return {
        "segments": [
            {"id": "seg_1", "sequence": 1, "type": "voice_over", "estimated_duration_ms": 5000, "clips": [{"start_ms": 0, "end_ms": 5000}]},
            {"id": "seg_2", "sequence": 2, "type": "original_dialogue", "start_ms": 6000, "end_ms": 8000},
        ],
    }


def test_render_edit_plan_raises_when_no_segments(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "_target_canvas", lambda path: CANVAS)
    with pytest.raises(film_summary.FilmSummaryValidationError) as exc_info:
        render.render_edit_plan(
            plan={"segments": []}, source_video_path="/tmp/source.mp4", voiceover_paths_by_segment_id={},
            work_dir=str(tmp_path), final_output_path=str(tmp_path / "final.mp4"), preview_output_path=str(tmp_path / "preview.mp4"),
        )
    assert exc_info.value.code == film_summary.FilmSummaryErrorCode.RENDER_FAILED


def test_render_edit_plan_orchestrates_all_segments(monkeypatch, tmp_path):
    monkeypatch.setattr(render, "_target_canvas", lambda path: CANVAS)
    monkeypatch.setattr(render, "_build_voice_over_segment_clip", lambda *a, **k: str(tmp_path / "seg_1_final.mp4"))
    monkeypatch.setattr(render, "_build_original_segment_clip", lambda *a, **k: str(tmp_path / "seg_2_final.mp4"))
    concat_calls = []
    monkeypatch.setattr(render, "concat_video_clips", lambda paths, out, work_dir: concat_calls.append(paths))
    monkeypatch.setattr(render, "normalize_audio_loudness", lambda inp, out: None)
    monkeypatch.setattr(render, "encode_preview", lambda inp, out, **k: None)
    monkeypatch.setattr(render, "probe_media_duration_seconds", lambda path: 13.0)

    result = render.render_edit_plan(
        plan=_sample_plan(), source_video_path="/tmp/source.mp4", voiceover_paths_by_segment_id={"seg_1": "/tmp/narration.mp3"},
        work_dir=str(tmp_path), final_output_path=str(tmp_path / "final.mp4"), preview_output_path=str(tmp_path / "preview.mp4"),
    )

    assert result == {"segment_count": 2, "final_duration_seconds": 13.0}
    assert concat_calls[0] == [str(tmp_path / "seg_1_final.mp4"), str(tmp_path / "seg_2_final.mp4")]
