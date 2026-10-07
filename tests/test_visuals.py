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

    # Base video is SAR-normalized once, up front, before anything else reads it.
    assert "[0:v]setsar=1[vsar]" in result
    # 35% of 1920 = 672 (even already), video half = 1920-672=1248.
    assert "[vsar]split=2[vfull0][vsrc0]" in result
    assert "scale=1080:1248:force_original_aspect_ratio=increase" in result
    assert "crop=1080:1248[vcrop0]" in result
    # TOP: image at y=0, video padded down to y=image_height=672.
    assert "pad=1080:1920:0:672:black[vpad0]" in result
    # Image is split into a blurred, stretch-filled (always-opaque) backdrop
    # and a cover-fit (possibly still-alpha) foreground, composited together
    # before ever reaching the video's black pad -- so a transparent source
    # image can never let that black show through.
    assert "[1:v]split=2[vimgbgsrc0][vimgsrc0]" in result
    assert "boxblur=" in result and "format=yuv420p[vimgbg0]" in result
    assert "crop=1080:672[vimgfg0]" in result
    assert "[vimgbg0][vimgfg0]overlay=0:0[vimg0]" in result
    assert "[vpad0][vimg0]overlay=0:0[vsplit0]" in result
    assert "[vfull0][vsplit0]overlay=0:0:enable='between(t,12.500,17.500)'[out]" in result


def test_build_visuals_filter_complex_single_bottom_visual():
    visuals_mod = importlib.import_module("visuals")
    visuals = [{"position": "BOTTOM", "start_time": 0.0, "duration": 3.0}]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1080, 1920)

    # BOTTOM: video at y=0 (top), image at y=video_half_height=1248.
    assert "pad=1080:1920:0:0:black[vpad0]" in result
    assert "[vpad0][vimg0]overlay=0:1248[vsplit0]" in result
    assert "between(t,0.000,3.000)" in result


def test_build_visuals_filter_complex_chains_multiple_visuals():
    visuals_mod = importlib.import_module("visuals")
    visuals = [
        {"position": "TOP", "start_time": 2.0, "duration": 3.0},
        {"position": "BOTTOM", "start_time": 10.0, "duration": 4.0},
    ]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1080, 1920)

    # First stage reads from the SAR-normalized input, feeds into a named intermediate stage...
    assert "[vsar]split=2[vfull0][vsrc0]" in result
    assert "[vfull0][vsplit0]overlay=0:0:enable='between(t,2.000,5.000)'[vstage0]" in result
    # ...the second visual reads from that intermediate stage and produces [out].
    assert "[vstage0]split=2[vfull1][vsrc1]" in result
    assert "[1:v]" in result and "[2:v]" in result  # two distinct image inputs
    assert "[vfull1][vsplit1]overlay=0:0:enable='between(t,10.000,14.000)'[out]" in result


def test_build_visuals_filter_complex_dimensions_stay_even():
    import re

    visuals_mod = importlib.import_module("visuals")
    visuals = [{"position": "TOP", "start_time": 0.0, "duration": 1.0}]

    # An odd height (1921) must still produce even scale/crop/pad targets
    # (libx264/yuv420p requires even dimensions).
    result = visuals_mod.build_visuals_filter_complex(visuals, 1081, 1921)
    for match in re.finditer(r"(?:scale|crop|pad)=(\d+):(\d+)", result):
        assert int(match.group(1)) % 2 == 0
        assert int(match.group(2)) % 2 == 0


def test_build_visuals_filter_complex_image_backdrop_is_forced_opaque():
    """The image's blurred backdrop must drop any alpha channel
    (format=yuv420p) -- otherwise a transparent source image would still
    let the video's black pad show through after compositing."""
    visuals_mod = importlib.import_module("visuals")
    visuals = [{"position": "BOTTOM", "start_time": 0.0, "duration": 2.0}]

    result = visuals_mod.build_visuals_filter_complex(visuals, 1080, 1920)

    bg_stage = next(part for part in result.split(";") if part.endswith("[vimgbg0]"))
    assert "format=yuv420p" in bg_stage
    assert "scale=1080:672" in bg_stage


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
    assert "-map" in cmd
    map_values = [cmd[i + 1] for i, token in enumerate(cmd) if token == "-map"]
    assert map_values == ["[out]", "0:a?"]
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy"
    assert "out.mp4" == cmd[-1]


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
