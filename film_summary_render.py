"""FFmpeg assembly for Film Summary (spec section 7.10 "Montage FFmpeg").

Kept as its own module (same split as subtitles.py's burn_subtitles vs.
anonymous_stories.py) since it is pure ffmpeg/ffprobe subprocess
orchestration with no AI call and no Supabase/S3 coupling -- film_summary.py
stays focused on validation, prompts and the OpenAI/AssemblyAI/PySceneDetect
calls.

Every segment is re-encoded to one common resolution/framerate up front so
the final concat demuxer pass can safely stream-copy (`-c copy`) instead of
re-encoding twice.
"""

import logging
import os
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional

from film_summary import FilmSummaryErrorCode, FilmSummaryValidationError, SEGMENT_TYPE_VOICE_OVER, probe_media_duration_seconds, probe_technical_metadata

logger = logging.getLogger(__name__)

FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "veryfast")
EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
ORIGINAL_AUDIO_DUCK_VOLUME = float(os.environ.get("FILM_SUMMARY_ORIGINAL_AUDIO_DUCK_VOLUME", "0.15"))
PREVIEW_HEIGHT = int(os.environ.get("FILM_SUMMARY_PREVIEW_HEIGHT", "480"))


def _run_ffmpeg(cmd: List[str], timeout_seconds: int = FFMPEG_STEP_TIMEOUT_SECONDS) -> None:
    # This module previously had no logging at all: a stalled render gave
    # no indication of which ffmpeg command was running or how long it had
    # been running for, making "stuck with no error" reports (a slow-but-
    # healthy render and a genuinely hung one look identical from outside)
    # impossible to tell apart from the logs.
    logger.info("Running ffmpeg: %s", " ".join(cmd))
    started_at = time.monotonic()
    try:
        result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        logger.error("ffmpeg timed out after %ss: %s", timeout_seconds, " ".join(cmd))
        raise FilmSummaryValidationError(FilmSummaryErrorCode.RENDER_FAILED, f"FFmpeg timed out after {timeout_seconds}s") from exc
    elapsed = time.monotonic() - started_at
    if result.returncode != 0:
        stderr_text = result.stderr.decode(errors="replace")[-2000:]
        logger.error("ffmpeg failed after %.1fs (exit %s): %s\nstderr: %s", elapsed, result.returncode, " ".join(cmd), stderr_text)
        raise FilmSummaryValidationError(FilmSummaryErrorCode.RENDER_FAILED, f"FFmpeg failed: {stderr_text}")
    logger.info("ffmpeg finished in %.1fs", elapsed)


def _probe_duration_seconds(path: str) -> float:
    return probe_media_duration_seconds(path)


def _target_canvas(source_path: str) -> Dict[str, Any]:
    meta = probe_technical_metadata(source_path)
    width = meta.get("width") or 1280
    height = meta.get("height") or 720
    fps = meta.get("fps") or 30.0
    if fps <= 0 or fps > 60:
        fps = 30.0
    # Even dimensions are required by libx264's yuv420p pixel format.
    width = width if width % 2 == 0 else width + 1
    height = height if height % 2 == 0 else height + 1
    return {"width": int(width), "height": int(height), "fps": round(float(fps), 3)}


def extract_source_subclip(
    source_path: str, start_ms: int, end_ms: int, output_path: str, *, canvas: Dict[str, Any],
) -> None:
    start_seconds = max(0.0, start_ms / 1000.0)
    duration_seconds = max(0.05, (end_ms - start_ms) / 1000.0)
    vf = (
        f"scale={canvas['width']}:{canvas['height']}:force_original_aspect_ratio=decrease,"
        f"pad={canvas['width']}:{canvas['height']}:(ow-iw)/2:(oh-ih)/2,"
        f"fps={canvas['fps']},setsar=1"
    )
    cmd = [
        "ffmpeg", "-y", "-ss", f"{start_seconds:.3f}", "-i", source_path, "-t", f"{duration_seconds:.3f}",
        "-vf", vf, "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", output_path,
    ]
    _run_ffmpeg(cmd)


def build_blank_segment(duration_seconds: float, output_path: str, *, canvas: Dict[str, Any]) -> None:
    """Neutral black-frame filler for a voice_over segment the plan
    provided no usable clips for -- keeps the assembly resilient instead of
    failing the whole render over one under-specified segment."""
    duration_seconds = max(0.05, duration_seconds)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=black:s={canvas['width']}x{canvas['height']}:r={canvas['fps']}",
        "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
        "-t", f"{duration_seconds:.3f}", "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
        "-pix_fmt", "yuv420p", "-c:a", "aac", output_path,
    ]
    _run_ffmpeg(cmd)


def concat_video_clips(clip_paths: List[str], output_path: str, work_dir: str) -> None:
    # The concat demuxer resolves a relative path written into the file
    # list against the *file list's own directory*, not the ffmpeg
    # process's working directory -- since every clip path passed in here
    # (built via os.path.join(work_dir, ...) upstream) is already relative
    # to the app's own CWD, and the file list itself also lives inside
    # work_dir, ffmpeg was concatenating work_dir onto an already-relative
    # path, doubling it (e.g. "work/output/.../work/seg_01_clip_0.mp4") and
    # failing with "No such file or directory". Writing absolute paths
    # sidesteps the ambiguity entirely regardless of either directory.
    filelist_path = os.path.join(work_dir, f"concat_{os.path.basename(output_path)}.txt")
    with open(filelist_path, "w", encoding="utf-8") as handle:
        for path in clip_paths:
            escaped = os.path.abspath(path).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", filelist_path, "-c", "copy", output_path]
    _run_ffmpeg(cmd)


def pad_or_trim_to_duration(input_path: str, target_seconds: float, output_path: str) -> None:
    current_seconds = _probe_duration_seconds(input_path)
    target_seconds = max(0.05, target_seconds)

    if current_seconds <= 0:
        if input_path != output_path:
            os.replace(input_path, output_path)
        return

    if abs(current_seconds - target_seconds) < 0.15:
        if input_path != output_path:
            os.replace(input_path, output_path)
        return

    if current_seconds > target_seconds:
        cmd = ["ffmpeg", "-y", "-i", input_path, "-t", f"{target_seconds:.3f}", "-c", "copy", output_path]
    else:
        pad_seconds = target_seconds - current_seconds
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", f"tpad=stop_mode=clone:stop_duration={pad_seconds:.3f}",
            "-af", f"apad=pad_dur={pad_seconds:.3f}",
            "-c:v", "libx264", "-preset", EXPORT_VIDEO_PRESET, "-crf", EXPORT_VIDEO_CRF,
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-t", f"{target_seconds:.3f}", output_path,
        ]
    _run_ffmpeg(cmd)


def duck_and_mix_narration(
    visual_with_audio_path: str, narration_audio_path: str, output_path: str,
    original_volume: float = ORIGINAL_AUDIO_DUCK_VOLUME,
) -> None:
    """Mix the segment's own (ducked) original audio with the narration
    track (spec 7.10: "reduit automatiquement l'audio source sous la voix
    off"). `duration=first` keeps the mix locked to the visual track's
    length, which pad_or_trim_to_duration already matched to the narration."""
    filter_complex = (
        f"[0:a]volume={original_volume}[a0];[1:a]volume=1.0[a1];"
        f"[a0][a1]amix=inputs=2:duration=first:dropout_transition=0[aout]"
    )
    cmd = [
        "ffmpeg", "-y", "-i", visual_with_audio_path, "-i", narration_audio_path,
        "-filter_complex", filter_complex, "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", output_path,
    ]
    _run_ffmpeg(cmd)


def normalize_audio_loudness(input_path: str, output_path: str) -> None:
    cmd = ["ffmpeg", "-y", "-i", input_path, "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-c:v", "copy", output_path]
    _run_ffmpeg(cmd)


def encode_preview(input_path: str, output_path: str, height: int = PREVIEW_HEIGHT) -> None:
    even_height = height if height % 2 == 0 else height + 1
    cmd = [
        "ffmpeg", "-y", "-i", input_path, "-vf", f"scale=-2:{even_height}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-c:a", "aac", "-b:a", "96k", output_path,
    ]
    _run_ffmpeg(cmd)


def _build_voice_over_segment_clip(
    segment: Dict[str, Any], source_video_path: str, narration_path: Optional[str], work_dir: str, canvas: Dict[str, Any],
) -> str:
    seg_id = segment["id"]
    target_seconds = max(0.05, (segment.get("actual_duration_ms") or segment.get("estimated_duration_ms") or 0) / 1000.0)
    clips = segment.get("clips") or []

    if not clips:
        visual_path = os.path.join(work_dir, f"{seg_id}_visual.mp4")
        build_blank_segment(target_seconds, visual_path, canvas=canvas)
    else:
        clip_paths = []
        for i, clip in enumerate(clips):
            clip_path = os.path.join(work_dir, f"{seg_id}_clip_{i}.mp4")
            extract_source_subclip(source_video_path, clip.get("start_ms", 0), clip.get("end_ms", 0), clip_path, canvas=canvas)
            clip_paths.append(clip_path)
        raw_visual_path = clip_paths[0] if len(clip_paths) == 1 else os.path.join(work_dir, f"{seg_id}_raw.mp4")
        if len(clip_paths) > 1:
            concat_video_clips(clip_paths, raw_visual_path, work_dir)
        visual_path = os.path.join(work_dir, f"{seg_id}_visual.mp4")
        pad_or_trim_to_duration(raw_visual_path, target_seconds, visual_path)

    if not narration_path or not os.path.exists(narration_path):
        return visual_path

    final_path = os.path.join(work_dir, f"{seg_id}_final.mp4")
    duck_and_mix_narration(visual_path, narration_path, final_path)
    return final_path


def _build_original_segment_clip(segment: Dict[str, Any], source_video_path: str, work_dir: str, canvas: Dict[str, Any]) -> str:
    seg_id = segment["id"]
    output_path = os.path.join(work_dir, f"{seg_id}_final.mp4")
    extract_source_subclip(source_video_path, segment.get("start_ms", 0), segment.get("end_ms", 0), output_path, canvas=canvas)
    return output_path


def render_edit_plan(
    *, plan: Dict[str, Any], source_video_path: str, voiceover_paths_by_segment_id: Dict[str, str],
    work_dir: str, final_output_path: str, preview_output_path: str,
    on_segment_done: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, Any]:
    """Assemble the validated edit plan into a preview and a final MP4
    (spec 7.10). Returns {"segment_count", "final_duration_seconds"}.

    Every segment (each its own ffmpeg re-encode, sometimes several for a
    multi-clip voice-over block) runs sequentially inside this one call --
    for a plan with many segments this can legitimately take a long time,
    and previously reported no progress at all between the 45% mark (start
    of rendering) and 90% (after this whole function returns), making a
    genuinely slow-but-working render indistinguishable from a hang.
    `on_segment_done(index, total)`, called synchronously after each
    segment's clip finishes (this runs inside asyncio.to_thread, so the
    callback must itself be thread-safe -- see app.py's caller), lets the
    caller report real incremental progress instead."""
    os.makedirs(work_dir, exist_ok=True)
    canvas = _target_canvas(source_video_path)

    segments = sorted(plan.get("segments") or [], key=lambda s: s.get("sequence", 0))
    if not segments:
        raise FilmSummaryValidationError(FilmSummaryErrorCode.RENDER_FAILED, "Plan has no segments to render")

    segment_clip_paths = []
    for index, segment in enumerate(segments):
        logger.info("Rendering segment %s (%d/%d, type=%s)", segment.get("id"), index + 1, len(segments), segment.get("type"))
        if segment.get("type") == SEGMENT_TYPE_VOICE_OVER:
            narration_path = voiceover_paths_by_segment_id.get(segment["id"])
            clip_path = _build_voice_over_segment_clip(segment, source_video_path, narration_path, work_dir, canvas)
        else:
            clip_path = _build_original_segment_clip(segment, source_video_path, work_dir, canvas)
        segment_clip_paths.append(clip_path)
        if on_segment_done:
            on_segment_done(index, len(segments))

    logger.info("All %d segment clips built, concatenating", len(segments))
    concatenated_path = os.path.join(work_dir, "concatenated.mp4")
    concat_video_clips(segment_clip_paths, concatenated_path, work_dir)

    normalize_audio_loudness(concatenated_path, final_output_path)
    encode_preview(final_output_path, preview_output_path)

    return {
        "segment_count": len(segments),
        "final_duration_seconds": _probe_duration_seconds(final_output_path),
    }
