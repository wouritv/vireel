import importlib
import os
import subprocess
import sys

import pytest


def _import_visuals(monkeypatch):
    if "visuals" in sys.modules:
        return importlib.reload(sys.modules["visuals"])
    return importlib.import_module("visuals")


def test_build_visuals_filter_complex_single_top_visual():
    visuals_mod = importlib.import_module("visuals")
    visuals = [{"position": "TOP", "start_time": 12.5, "duration": 5.0}]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1080, 1920)

    # 50% of 1920 = 960 for both halves.
    assert "[0:v]split=2[vfull0][vsrc0]" in result
    assert "crop=1080:960:(iw-ow)/2:(ih-oh)/2[vcrop0]" in result
    # TOP: image at y=0, video padded down to y=image_height=960.
    assert "pad=1080:1920:0:960:black[vpad0]" in result
    assert "[1:v]scale=1080:960:force_original_aspect_ratio=increase,crop=1080:960:(iw-ow)/2:(ih-oh)/2[vimg0]" in result
    assert "[vpad0][vimg0]overlay=0:0[vsplit0]" in result
    assert "[vfull0][vsplit0]overlay=0:0:enable='between(t,12.500,17.500)'[out]" in result


def test_build_visuals_filter_complex_single_bottom_visual():
    visuals_mod = importlib.import_module("visuals")
    visuals = [{"position": "BOTTOM", "start_time": 0.0, "duration": 3.0}]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1080, 1920)

    # BOTTOM: video at y=0 (top), image at y=video_half_height=960.
    assert "pad=1080:1920:0:0:black[vpad0]" in result
    assert "[vpad0][vimg0]overlay=0:960[vsplit0]" in result
    assert "between(t,0.000,3.000)" in result


def test_build_visuals_filter_complex_chains_multiple_visuals():
    visuals_mod = importlib.import_module("visuals")
    visuals = [
        {"position": "TOP", "start_time": 2.0, "duration": 3.0},
        {"position": "BOTTOM", "start_time": 10.0, "duration": 4.0},
    ]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1080, 1920)

    assert "[0:v]split=2[vfull0][vsrc0]" in result
    assert "[vfull0][vsplit0]overlay=0:0:enable='between(t,2.000,5.000)'[vstage0]" in result
    assert "[vstage0]split=2[vfull1][vsrc1]" in result
    assert "[1:v]" in result
    assert "[2:v]" in result
    assert "[vfull1][vsplit1]overlay=0:0:enable='between(t,10.000,14.000)'[out]" in result


def test_build_visuals_filter_complex_dimensions_stay_even():
    import re

    visuals_mod = importlib.import_module("visuals")
    visuals = [{"position": "TOP", "start_time": 0.0, "duration": 1.0}]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1081, 1921)
    for match in re.finditer(r"(?:scale|crop|pad)=(\d+):(\d+)", result):
        assert not int(match.group(1)) % 2
        assert not int(match.group(2)) % 2


def test_probe_video_dimensions_falls_back_on_failure(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no ffprobe")))
    assert visuals_mod._probe_video_dimensions("missing.mp4") == (1080, 1920)


def test_probe_video_dimensions_parses_ffprobe_output(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: b"720x1280")
    assert visuals_mod._probe_video_dimensions("video.mp4") == (720, 1280)


def test_apply_visuals_to_video_raises_when_video_missing(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    with pytest.raises(FileNotFoundError):
        visuals_mod.apply_visuals_to_video("missing.mp4", [{"position": "TOP", "start_time": 0, "duration": 1, "image_path": "img.jpg"}], "out.mp4")


def test_apply_visuals_to_video_raises_when_no_visuals(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    with pytest.raises(ValueError):
        visuals_mod.apply_visuals_to_video("video.mp4", [], "out.mp4")


def test_apply_visuals_to_video_builds_correct_ffmpeg_command(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    monkeypatch.setattr(visuals_mod, "_probe_video_dimensions", lambda path: (1080, 1920))

    captured = {}

    def fake_run(cmd, check, stdout, stderr, timeout):
        captured["cmd"] = cmd
        return None

    monkeypatch.setattr(visuals_mod.subprocess, "run", fake_run)

    visuals = [
        {"position": "TOP", "start_time": 1.0, "duration": 2.0, "image_path": "img1.jpg"},
        {"position": "BOTTOM", "start_time": 5.0, "duration": 2.0, "image_path": "img2.jpg"},
    ]
    ok = visuals_mod.apply_visuals_to_video("video.mp4", visuals, "out.mp4")

    assert ok is True
    cmd = captured["cmd"]
    assert cmd[:3] == ["ffmpeg", "-y", "-i"]
    assert "video.mp4" in cmd
    assert "img1.jpg" in cmd
    assert "img2.jpg" in cmd
    assert "-filter_complex" in cmd
    filter_complex = cmd[cmd.index("-filter_complex") + 1]
    assert "boxblur" not in filter_complex
    assert "force_original_aspect_ratio=decrease" not in filter_complex
    assert "crop=1080:960:(iw-ow)/2:(ih-oh)/2[vimg0]" in filter_complex
    assert "crop=1080:960:(iw-ow)/2:(ih-oh)/2[vcrop0]" in filter_complex
    assert "-map" in cmd
    map_values = [cmd[i + 1] for i, token in enumerate(cmd) if token == "-map"]
    assert map_values == ["[out]", "0:a?"]
    assert "-c:a" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "copy"
    assert cmd[-1] == "out.mp4"


def test_apply_visuals_to_video_raises_runtime_error_on_ffmpeg_failure(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    monkeypatch.setattr(visuals_mod, "_probe_video_dimensions", lambda path: (1080, 1920))

    def fake_run(cmd, check, stdout, stderr, timeout):
        raise subprocess.CalledProcessError(1, cmd, stderr=b"ffmpeg exploded")

    monkeypatch.setattr(visuals_mod.subprocess, "run", fake_run)

    visuals = [{"position": "TOP", "start_time": 0.0, "duration": 1.0, "image_path": "img1.jpg"}]
    with pytest.raises(RuntimeError, match="ffmpeg exploded"):
        visuals_mod.apply_visuals_to_video("video.mp4", visuals, "out.mp4")


def test_apply_visuals_to_video_raises_runtime_error_on_timeout(monkeypatch):
    visuals_mod = _import_visuals(monkeypatch)
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    monkeypatch.setattr(visuals_mod, "_probe_video_dimensions", lambda path: (1080, 1920))

    def fake_run(cmd, check, stdout, stderr, timeout):
        raise subprocess.TimeoutExpired(cmd, timeout)

    monkeypatch.setattr(visuals_mod.subprocess, "run", fake_run)

    visuals = [{"position": "TOP", "start_time": 0.0, "duration": 1.0, "image_path": "img1.jpg"}]
    with pytest.raises(RuntimeError, match="timed out"):
        visuals_mod.apply_visuals_to_video("video.mp4", visuals, "out.mp4")
