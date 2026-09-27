import os
import re
import subprocess
from dataclasses import dataclass


EXPORT_VIDEO_CRF = os.environ.get("VIREEL_EXPORT_CRF", "20")
EXPORT_VIDEO_PRESET = os.environ.get("VIREEL_EXPORT_PRESET", "medium")
EXPORT_AUDIO_BITRATE = os.environ.get("VIREEL_EXPORT_AUDIO_BITRATE", "192k")
# Security: hard ceiling so a pathological input can't hang a worker
# indefinitely while burning subtitles (audit finding H13).
FFMPEG_STEP_TIMEOUT_SECONDS = int(os.environ.get("FFMPEG_STEP_TIMEOUT_SECONDS", str(2 * 3600)))


def transcribe_audio(video_path):
    """
    Transcribe audio from a video file using faster-whisper.
    Returns transcript in the same format as main.py for compatibility.
    """
    from faster_whisper import WhisperModel

    print(f"🎙️  Transcribing audio from: {video_path}")

    # Run on CPU with INT8 quantization for speed
    model = WhisperModel("base", device="cpu", compute_type="int8")

    segments, info = model.transcribe(video_path, word_timestamps=True)

    transcript = {
        "segments": [],
        "language": info.language
    }

    for segment in segments:
        seg_data = {
            "start": segment.start,
            "end": segment.end,
            "text": segment.text,
            "words": []
        }
        if segment.words:
            for word in segment.words:
                seg_data["words"].append({
                    "word": word.word.strip(),
                    "start": word.start,
                    "end": word.end
                })
        transcript["segments"].append(seg_data)

    print(f"✅ Transcription complete. Language: {info.language}")
    return transcript


def generate_srt_from_video(video_path, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4):
    """
    Transcribe a video and generate SRT directly.
    Used for dubbed videos that don't have a pre-existing transcript.
    """
    transcript = transcribe_audio(video_path)

    # Get video duration to use as clip_end
    import cv2
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frame_count / fps if fps else 0
    cap.release()

    return generate_srt(
        transcript,
        0,
        duration,
        output_path,
        max_chars=max_chars,
        max_duration=max_duration,
        max_words_per_line=max_words_per_line,
    )


def _extract_words_in_range(transcript, clip_start, clip_end):
    return [
        word_info
        for segment in transcript.get('segments', [])
        for word_info in segment.get('words', [])
        if word_info['end'] > clip_start and word_info['start'] < clip_end
    ]


def _should_flush_block(current_block, block_start, next_word_end, next_word_text, max_chars, max_duration, max_words_per_line):
    if not current_block:
        return False
    current_text_len = sum(len(w['word']) + 1 for w in current_block)
    duration = next_word_end - block_start
    return (
        len(current_block) >= max_words_per_line
        or current_text_len + len(next_word_text) > max_chars
        or duration > max_duration
    )


def _flush_srt_block(current_block, clip_start, block_start, index):
    if not current_block:
        return index, ""
    block_end = current_block[-1]['end'] - clip_start
    text = " ".join(w['word'] for w in current_block).strip()
    return index + 1, format_srt_block(index, block_start, block_end, text)


def generate_srt(transcript, clip_start, clip_end, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4):
    """
    Generates an SRT file from the transcript for a specific time range.
    Groups words into short lines suitable for vertical video.
    """
    
    words = _extract_words_in_range(transcript, clip_start, clip_end)

    if not words:
        return False

    srt_content = ""
    index = 1

    current_block = []
    block_start = None

    for word in words:
        # Adjust times relative to clip
        start = max(0, word['start'] - clip_start)
        end = max(0, word['end'] - clip_start)
        
        if not current_block:
            current_block.append(word)
            block_start = start
            continue

        if _should_flush_block(current_block, block_start, end, word['word'], max_chars, max_duration, max_words_per_line):
            index, block_text = _flush_srt_block(current_block, clip_start, block_start, index)
            srt_content += block_text
            current_block = [word]
            block_start = start
        else:
            current_block.append(word)

    # Final block
    if current_block:
        _, block_text = _flush_srt_block(current_block, clip_start, block_start, index)
        srt_content += block_text

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)
        
    return True

def format_srt_block(index, start, end, text):
    def format_time(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds - int(seconds)) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
        
    return f"{index}\n{format_time(start)} --> {format_time(end)}\n{text}\n\n"

def hex_to_ass_color(hex_color, opacity=1.0):
    """Convert #RRGGBB to ASS &HAABBGGRR format. opacity: 0.0=transparent, 1.0=opaque"""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    alpha = round((1.0 - opacity) * 255)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"


def _normalize_subtitle_text_case(srt_path, text_case):
    mode = (text_case or "none").lower()
    if mode not in {"uppercase", "lowercase"}:
        return

    try:
        with open(srt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        normalized = []
        for line in lines:
            stripped = line.strip()
            if stripped and '-->' not in line and not stripped.isdigit():
                normalized.append(line.upper() if mode == "uppercase" else line.lower())
            else:
                normalized.append(line)

        with open(srt_path, 'w', encoding='utf-8') as f:
            f.writelines(normalized)
    except Exception:
        return


@dataclass
class SubtitleStyleOptions:
    font_name: str = "Verdana"
    font_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: int = 2
    bg_color: str = "#000000"
    bg_opacity: float = 0.0
    text_shadow_color: str = "#000000"
    shadow_blur: int = 6
    shadow_offset_x: int = 0
    shadow_offset_y: int = 2
    bold: bool = True
    italic: bool = False
    text_case: str = "none"


def _probe_video_resolution(video_path):
    """Returns (width, height) of video_path's first video stream, or
    (None, None) if ffprobe fails (missing binary, unreadable file, ...) --
    burn_subtitles falls back to a fixed vertical-reel resolution rather
    than failing the whole burn when this can't be determined."""
    try:
        probe_cmd = [
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', video_path,
        ]
        output = subprocess.check_output(probe_cmd, timeout=30).decode().strip()
        width, height = map(int, output.split('x'))
        return width, height
    except Exception:
        return None, None


_SRT_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3})")


def _parse_srt_time(text: str) -> float:
    match = _SRT_TIME_RE.match(text.strip())
    if not match:
        return 0.0
    hours, minutes, seconds, millis = (int(x) for x in match.groups())
    return hours * 3600 + minutes * 60 + seconds + millis / 1000.0


def _parse_srt_blocks(srt_path):
    """Parses an .srt file back into (start_seconds, end_seconds, text)
    tuples, so burn_subtitles can re-emit it as a proper .ass script (see
    burn_subtitles for why a bare .srt can't be burned directly at a
    predictable font size)."""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    blocks = []
    for raw_block in re.split(r"\n\s*\n", content.strip()):
        lines = [ln for ln in raw_block.splitlines() if ln.strip()]
        if not lines:
            continue
        time_line_index = 1 if len(lines) > 1 and '-->' in lines[1] else 0
        if time_line_index >= len(lines) or '-->' not in lines[time_line_index]:
            continue
        start_str, end_str = (p.strip() for p in lines[time_line_index].split('-->'))
        text = " ".join(lines[time_line_index + 1:]).strip()
        if not text:
            continue
        blocks.append((_parse_srt_time(start_str), _parse_srt_time(end_str), text))
    return blocks


def _format_ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    centis = int(round(seconds * 100))
    hours, remainder = divmod(centis, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _escape_ass_text(text: str) -> str:
    return text.replace('\\', '\\\\').replace('{', '\\{').replace('}', '\\}').replace('\n', '\\N')


def _build_ass_document(
    blocks, width: int, height: int, ass_alignment: int, font_name: str, fontsize: int,
    primary_colour: str, outline_colour: str, back_colour: str, border_style: int,
    outline_width: int, shadow: int, bold: int, italic: int,
) -> str:
    """Builds a complete .ass script with its own [Script Info] PlayResX/
    PlayResY set to the video's real resolution -- unlike a bare .srt (which
    carries no resolution info of its own and makes ffmpeg's `subtitles`
    filter fall back to a small built-in virtual canvas, historically
    384x288, then scale everything up to the real frame size -- on a
    1080x1920 vertical reel that stretches a nominal Fontsize by roughly
    6.7x), a genuine .ass file's own header is what libass actually reads,
    so Fontsize maps 1:1 to real pixels here, matching how the same
    font_size looks in the Remotion-based manual caption editor (whose
    composition is sized to the real output resolution and treats fontSize
    as literal CSS pixels -- see remotion/src/Root.tsx)."""
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_name},{fontsize},{primary_colour},{primary_colour},{outline_colour},{back_colour},"
        f"{bold},{italic},0,0,100,100,0,0,{border_style},{outline_width},{shadow},{ass_alignment},10,10,25,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = "".join(
        f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,{_escape_ass_text(text)}\n"
        for start, end, text in blocks
    )
    return header + events


def burn_subtitles(video_path, srt_path, output_path, alignment=2, fontsize=16, style_options=None):
    """
    Burns subtitles into the video using FFmpeg.
    Supports two modes:
    - Outline mode (bg_opacity=0): Text with colored outline/border
    - Box mode (bg_opacity>0): Text with semi-transparent background box
    """
    style = style_options or SubtitleStyleOptions()

    # Position mapping
    ass_alignment = 2
    align_lower = str(alignment).lower()
    if align_lower == 'top':
        ass_alignment = 6
    elif align_lower == 'middle':
        ass_alignment = 10
    elif align_lower == 'bottom':
        ass_alignment = 2

    width, height = _probe_video_resolution(video_path)
    if not width or not height:
        # Sane vertical-reel fallback: better than ever letting this fall
        # through to ffmpeg's own tiny default virtual canvas.
        width, height = 1080, 1920

    final_fontsize = max(10, int(fontsize))

    _normalize_subtitle_text_case(srt_path, style.text_case)

    # Font name is the one style field echoed verbatim into the generated
    # .ass file. Restrict it to a safe character set so a crafted font_name
    # can't break out of the Style line or inject extra script sections.
    safe_font_name = re.sub(r"[^A-Za-z0-9 _.\-]", "", style.font_name or "")[:64].strip() or "Verdana"

    # Convert colors to ASS format and build style
    primary_colour = hex_to_ass_color(style.font_color, 1.0)
    shadow_colour = hex_to_ass_color(style.text_shadow_color, 1.0)
    _ = (shadow_colour, style.shadow_offset_x, style.shadow_offset_y)  # Kept for API compatibility; ASS shadow offset/colour are limited.

    if style.bg_opacity > 0:
        # Box mode: opaque background box
        border_style = 3
        outline_colour = hex_to_ass_color(style.bg_color, style.bg_opacity)
        outline_width = 1
    else:
        # Outline mode: text border/outline
        border_style = 1
        outline_colour = hex_to_ass_color(style.border_color, 1.0)
        outline_width = max(1, style.border_width)

    back_colour = hex_to_ass_color("#000000", 0.0)

    blocks = _parse_srt_blocks(srt_path)
    ass_content = _build_ass_document(
        blocks, width, height, ass_alignment, safe_font_name, final_fontsize,
        primary_colour, outline_colour, back_colour, border_style, outline_width,
        max(0, int(style.shadow_blur)), 1 if style.bold else 0, 1 if style.italic else 0,
    )
    ass_path = f"{os.path.splitext(srt_path)[0]}.ass"
    with open(ass_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)

    try:
        # Escape single quotes so a path cannot break out of the quoted
        # subtitles='...' filter argument (defense in depth; job_id is
        # already validated by the caller, but this keeps the guarantee
        # local to the function that actually builds the filtergraph
        # string).
        safe_ass_path = ass_path.replace('\\', '/').replace(':', '\\:').replace("'", "\\'")

        cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', f"subtitles='{safe_ass_path}'",
            '-c:a', 'copy',
            '-c:v', 'libx264', '-preset', EXPORT_VIDEO_PRESET, '-crf', EXPORT_VIDEO_CRF,
            '-pix_fmt', 'yuv420p',
            output_path
        ]

        print(f"🎬 Burning subtitles: {' '.join(cmd)}")
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=FFMPEG_STEP_TIMEOUT_SECONDS
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"FFmpeg timed out after {FFMPEG_STEP_TIMEOUT_SECONDS}s while burning subtitles") from exc

        if result.returncode != 0:
            print(f"❌ FFmpeg Subtitle Error: {result.stderr.decode()}")
            raise RuntimeError(f"FFmpeg failed: {result.stderr.decode()}")

        return True
    finally:
        try:
            if os.path.exists(ass_path):
                os.remove(ass_path)
        except Exception:
            pass

