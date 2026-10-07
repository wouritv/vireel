import os
import subprocess

EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
FFPROBE_TIMEOUT_SECONDS = int(os.environ.get("FFPROBE_TIMEOUT_SECONDS", "60"))
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))

# Spec: ~50% of the frame for the image, ~50% for the video. Not
# user-configurable in V1. subtitles.py's bottom-split subtitle
# repositioning assumes this exact ratio -- keep both in sync if it ever
# changes.
SPLIT_IMAGE_RATIO = 0.50


def _probe_video_dimensions(video_path):
    """Returns (width, height) of video_path's first video stream, or the
    same 1080x1920 vertical-reel fallback used elsewhere in this codebase
    (hooks.py, subtitles.py) if ffprobe fails."""
    try:
        cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path,
        ]
        output = subprocess.check_output(cmd, timeout=FFPROBE_TIMEOUT_SECONDS).decode().strip()
        width, height = map(int, output.split('x'))
        return width, height
    except Exception:
        return 1080, 1920


def _even(value) -> int:
    """libx264/yuv420p require even width/height -- round down to the
    nearest even integer so every scale/crop/pad target stays encodable."""
    n = int(round(value))
    return n if n % 2 == 0 else n - 1


# boxblur radius for the image's own blurred-backdrop fill (see
# build_visuals_filter_complex) -- soft enough to read as an intentional
# background, not a visible single pass box artifact.
IMAGE_BACKDROP_BLUR_RADIUS = 20


def build_visuals_filter_complex(visuals, video_width: int, video_height: int) -> str:
    """Builds the -filter_complex string for burning `visuals` into a
    video of (video_width, video_height). `visuals` must already be
    sorted ascending by start_time and validated non-overlapping by the
    caller -- this function does not re-check either.

    Each visual dict needs: position ('TOP'|'BOTTOM'), start_time,
    duration. Input 0 is the video; input (index+1) is that visual's
    image, in the same order they appear in `visuals`.

    Technique: for each visual, split the current video stream into an
    untouched "full screen" copy and a copy that gets cover-fit cropped
    into its half of the split layout, padded onto a full-canvas black
    frame, then overlaid with the (likewise cover-fit) image to build one
    full-size "split frame". That split frame is overlaid back onto the
    untouched full-screen copy, gated with enable='between(t,start,end)'
    -- a full-size, time-gated overlay is effectively "replace the frame
    for this window only", so outside any visual's window the output is
    byte-identical to the plain video, with no duration/audio impact
    (audio is never touched by this filter graph; see apply_visuals_to_video).
    Visuals are chained stage-to-stage, which is safe only because their
    windows never overlap (validated upstream).

    Both the video and the image are cover-fit via the standard
    scale(force_original_aspect_ratio=increase)+crop idiom: scale up just
    enough that both target dimensions are covered (never distorting the
    source's own aspect ratio), then crop the overflow -- explicitly
    centered ((iw-ow)/2:(ih-oh)/2, matching crop's own default), which is
    also the fallback this pipeline needs: there is no persisted
    subject/focal-point data surviving from the original reel-generation
    pass (see main.py's face/speaker tracking) by the time a visual is
    burned in here, in a later, separate request, so a plain centered
    crop is the correct behavior, not a missing feature.

    The image gets one extra step the video doesn't need: PNG/WebP visuals
    can carry an alpha channel, and alpha-blending that straight onto the
    pad's black fill would show black (or a black tint) through any
    transparent/semi-transparent pixel once overlaid. So the image is
    first flattened onto its own blurred, stretch-to-fill copy (the same
    "blurred backdrop" idea as main.py's _build_blurred_background, just
    expressed as an ffmpeg filter since this pipeline is ffmpeg-based) --
    that backdrop is forced opaque (format=yuv420p drops any alpha plane),
    so nothing can ever show through it, and it already covers 100% of
    the zone by construction (a stretch fill, not a crop)."""
    video_width = _even(video_width)
    video_height = _even(video_height)
    image_height = _even(video_height * SPLIT_IMAGE_RATIO)
    video_half_height = _even(video_height - image_height)

    filter_parts = []
    # Square pixels on the base video stream -- a source with a
    # non-1:1 SAR (anamorphic footage) would otherwise scale/crop
    # correctly in raw pixel space while still carrying mismatched
    # display-aspect metadata into the final encode, next to the
    # image overlay (always SAR 1:1) and the plain-video segments
    # outside any visual's window. Applied once, up front, so every
    # stage downstream -- split, fullscreen, and all composited
    # windows alike -- shares the same normalized SAR.
    filter_parts.append("[0:v]setsar=1[vsar]")
    current_label = "vsar"
    last_index = len(visuals) - 1
    for index, visual in enumerate(visuals):
        start = max(0.0, float(visual["start_time"]))
        end = start + max(0.0, float(visual["duration"]))
        is_bottom = str(visual["position"]).upper() == "BOTTOM"
        image_input_index = index + 1

        full_label = f"vfull{index}"
        src_label = f"vsrc{index}"
        cropped_label = f"vcrop{index}"
        padded_label = f"vpad{index}"
        img_src_label = f"vimgsrc{index}"
        img_bg_src_label = f"vimgbgsrc{index}"
        img_bg_label = f"vimgbg{index}"
        img_fg_label = f"vimgfg{index}"
        img_label = f"vimg{index}"
        composed_label = f"vsplit{index}"
        out_label = "out" if index == last_index else f"vstage{index}"

        # BOTTOM: video on top (y=0), image below it (y=video_half_height).
        # TOP: image on top (y=0), video below it (y=image_height).
        video_y = 0 if is_bottom else image_height
        image_y = video_half_height if is_bottom else 0

        filter_parts.append(f"[{current_label}]split=2[{full_label}][{src_label}]")
        filter_parts.append(
            f"[{src_label}]scale={video_width}:{video_half_height}:force_original_aspect_ratio=increase,"
            f"crop={video_width}:{video_half_height}:(iw-ow)/2:(ih-oh)/2[{cropped_label}]"
        )
        filter_parts.append(
            f"[{cropped_label}]pad={video_width}:{video_height}:0:{video_y}:black[{padded_label}]"
        )
        filter_parts.append(f"[{image_input_index}:v]split=2[{img_bg_src_label}][{img_src_label}]")
        filter_parts.append(
            f"[{img_bg_src_label}]scale={video_width}:{image_height},"
            f"boxblur={IMAGE_BACKDROP_BLUR_RADIUS}:1,format=yuv420p[{img_bg_label}]"
        )
        filter_parts.append(
            f"[{img_src_label}]scale={video_width}:{image_height}:force_original_aspect_ratio=increase,"
            f"crop={video_width}:{image_height}:(iw-ow)/2:(ih-oh)/2[{img_fg_label}]"
        )
        filter_parts.append(f"[{img_bg_label}][{img_fg_label}]overlay=0:0[{img_label}]")
        filter_parts.append(f"[{padded_label}][{img_label}]overlay=0:{image_y}[{composed_label}]")
        filter_parts.append(
            f"[{full_label}][{composed_label}]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{out_label}]"
        )

        current_label = out_label

    return ";".join(filter_parts)


def apply_visuals_to_video(video_path: str, visuals, output_path: str) -> bool:
    """Burns `visuals` (each a dict with image_path, position, start_time,
    duration, already sorted and validated non-overlapping) into
    video_path, writing the result to output_path. Video is re-encoded
    (the split compositing requires it); audio is copied through
    untouched -- this never changes duration or audio sync."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video {video_path} not found")
    if not visuals:
        raise ValueError("No visuals to apply")

    video_width, video_height = _probe_video_dimensions(video_path)
    filter_complex = build_visuals_filter_complex(visuals, video_width, video_height)

    cmd = ['ffmpeg', '-y', '-i', video_path]
    for visual in visuals:
        cmd += ['-i', visual['image_path']]
    cmd += [
        '-filter_complex', filter_complex,
        '-map', '[out]', '-map', '0:a?',
        '-c:a', 'copy',
        '-c:v', 'libx264', '-preset', EXPORT_VIDEO_PRESET, '-crf', EXPORT_VIDEO_CRF,
        '-pix_fmt', 'yuv420p',
        output_path,
    ]

    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=FFMPEG_STEP_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"FFmpeg timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s while applying visuals") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(f"FFmpeg failed: {exc.stderr.decode() if exc.stderr else 'unknown error'}") from exc

    return True
