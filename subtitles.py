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


def _probe_video_duration_seconds(video_path):
    """Returns video_path's duration in seconds via ffprobe, or 0.0 if it
    can't be determined (missing binary, unreadable file, ...). Used
    instead of deriving duration from cv2.VideoCapture's frame_count/fps
    (CAP_PROP_FRAME_COUNT is well known to read back 0 or wrong for many
    ffmpeg-produced H.264/mp4 containers), which silently collapsed the
    word-timestamp range generate_srt_from_video transcribes against to
    [0, 0) and made every subtitle disappear without any error at all."""
    try:
        probe_cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', video_path,
        ]
        output = subprocess.check_output(probe_cmd, timeout=30).decode().strip()
        return max(0.0, float(output))
    except Exception:
        return 0.0


def generate_srt_from_video(video_path, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4, highlight=False):
    """
    Transcribe a video and generate SRT directly.
    Used for dubbed videos that don't have a pre-existing transcript.
    Returns False (and writes no file) when the video has no detectable
    speech, or no duration at all -- callers must check this and treat it
    as subtitle generation failing, not silently ship a video with no
    subtitles burned in.
    """
    transcript = transcribe_audio(video_path)
    duration = _probe_video_duration_seconds(video_path)

    generator = generate_highlighted_srt if highlight else generate_srt
    return generator(
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


def _group_words_into_relative_blocks(words, clip_start, max_chars, max_duration, max_words_per_line):
    """Groups words into the same line-sized blocks generate_srt renders,
    tagging each word with its own clip-relative start/end ('rel_start'/
    'rel_end') alongside its original fields -- generate_srt only needs the
    block boundaries, but generate_highlighted_srt needs each word's own
    timing to know exactly when it's the one being spoken."""
    blocks = []
    current_block = []
    block_start = None

    for word in words:
        start = max(0, word['start'] - clip_start)
        end = max(0, word['end'] - clip_start)
        rel_word = {**word, 'rel_start': start, 'rel_end': end}

        if not current_block:
            current_block.append(rel_word)
            block_start = start
            continue

        if _should_flush_block(current_block, block_start, end, word['word'], max_chars, max_duration, max_words_per_line):
            blocks.append(current_block)
            current_block = [rel_word]
            block_start = start
        else:
            current_block.append(rel_word)

    if current_block:
        blocks.append(current_block)

    return blocks


def generate_srt(transcript, clip_start, clip_end, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4):
    """
    Generates an SRT file from the transcript for a specific time range.
    Groups words into short lines suitable for vertical video.
    """
    words = _extract_words_in_range(transcript, clip_start, clip_end)

    if not words:
        return False

    blocks = _group_words_into_relative_blocks(words, clip_start, max_chars, max_duration, max_words_per_line)

    srt_content = ""
    index = 1
    for block in blocks:
        index, block_text = _flush_srt_block(block, clip_start, block[0]['rel_start'], index)
        srt_content += block_text

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(srt_content)

    return True


# Wraps the word an SRT entry produced by generate_highlighted_srt should
# highlight -- a control character so it can never collide with real
# caption text, and passes through untouched to the .srt/.ass files where
# _escape_ass_text_with_highlight (see below) turns it into an inline ASS
# colour override instead of visible text.
_HIGHLIGHT_MARKER = "\x01"


def generate_highlighted_srt(transcript, clip_start, clip_end, output_path, max_chars=20, max_duration=2.0, max_words_per_line=4):
    """Like generate_srt, but marks up whichever word is actively being
    spoken in each entry (wrapped in _HIGHLIGHT_MARKER) so burn_subtitles
    can colour it with the style's highlight colour -- reproducing, in the
    burned-in video, the same word-by-word highlight the dashboard's own
    Remotion preview already renders for every caption animation except
    "none" (see Subtitles.tsx: `isActive -> color = style.highlightColor`).

    Emits one SRT entry per spoken word, plus an unmarked filler entry for
    any silent gap before/between/after words, so the line never goes
    blank between highlights.
    """
    words = _extract_words_in_range(transcript, clip_start, clip_end)

    if not words:
        return False

    blocks = _group_words_into_relative_blocks(words, clip_start, max_chars, max_duration, max_words_per_line)

    srt_content = ""
    index = 1
    for block in blocks:
        block_words = [w['word'] for w in block]
        cursor = block[0]['rel_start']
        for i, word in enumerate(block):
            if word['rel_start'] > cursor:
                plain_text = " ".join(block_words).strip()
                srt_content += format_srt_block(index, cursor, word['rel_start'], plain_text)
                index += 1

            highlighted_text = " ".join(
                f"{_HIGHLIGHT_MARKER}{w}{_HIGHLIGHT_MARKER}" if i == j else w
                for j, w in enumerate(block_words)
            ).strip()
            srt_content += format_srt_block(index, word['rel_start'], word['rel_end'], highlighted_text)
            index += 1
            cursor = word['rel_end']

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
    highlight_color: str = "#FFDD00"


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


def _ass_inline_colour_tag(ass_colour: str) -> str:
    """Converts a &HAABBGGRR Style-line colour (see hex_to_ass_color) into
    an inline \\c override usable inside a Dialogue's Text field -- \\c only
    takes the BBGGRR bytes, without the leading alpha byte a Style line
    colour carries."""
    hex_part = ass_colour[2:] if ass_colour.upper().startswith("&H") else ass_colour
    bgr = hex_part[-6:].rjust(6, "0")
    return f"\\c&H{bgr}&"


def _escape_ass_text_with_highlight(text: str, normal_colour: str, highlight_colour: str) -> str:
    """Escapes Dialogue text for the .ass file, turning the single word
    generate_highlighted_srt wrapped in _HIGHLIGHT_MARKER (if any) into an
    inline colour override instead of visible text -- this is what actually
    makes the currently-spoken word light up in highlight_colour when the
    burned-in video plays. Text with no marker (plain SRT, or a
    generate_highlighted_srt filler entry) is escaped exactly as before."""
    if _HIGHLIGHT_MARKER not in text:
        return _escape_ass_text(text)
    before, word, after = text.split(_HIGHLIGHT_MARKER, 2)
    return (
        _escape_ass_text(before)
        + "{" + _ass_inline_colour_tag(highlight_colour) + "}"
        + _escape_ass_text(word)
        + "{" + _ass_inline_colour_tag(normal_colour) + "}"
        + _escape_ass_text(after)
    )


@dataclass
class _AssStyleParams:
    """Bundles everything _build_ass_document needs to know about the
    video canvas and the [V4+ Styles] line it writes -- kept as one object
    instead of a long parameter list, since burn_subtitles resolves all of
    these together from a single SubtitleStyleOptions anyway."""
    width: int
    height: int
    ass_alignment: int
    font_name: str
    fontsize: int
    primary_colour: str
    outline_colour: str
    back_colour: str
    border_style: int
    outline_width: int
    shadow: int
    bold: int
    italic: int
    highlight_colour: str = ""


def _build_ass_document(blocks, params: _AssStyleParams) -> str:
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
    p = params
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {p.width}\n"
        f"PlayResY: {p.height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{p.font_name},{p.fontsize},{p.primary_colour},{p.primary_colour},{p.outline_colour},{p.back_colour},"
        f"{p.bold},{p.italic},0,0,100,100,0,0,{p.border_style},{p.outline_width},{p.shadow},{p.ass_alignment},10,10,25,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    effective_highlight_colour = p.highlight_colour or p.primary_colour
    events = "".join(
        f"Dialogue: 0,{_format_ass_time(start)},{_format_ass_time(end)},Default,,0,0,0,,"
        f"{_escape_ass_text_with_highlight(text, p.primary_colour, effective_highlight_colour)}\n"
        for start, end, text in blocks
    )
    return header + events


def _resolve_ass_alignment(alignment) -> int:
    return {'top': 6, 'middle': 10, 'bottom': 2}.get(str(alignment).lower(), 2)


def _resolve_ass_border_params(style: "SubtitleStyleOptions") -> tuple:
    """Returns (border_style, outline_colour, outline_width) for either of
    burn_subtitles' two rendering modes: an opaque background box
    (bg_opacity > 0) or a plain text outline/border."""
    if style.bg_opacity > 0:
        return 3, hex_to_ass_color(style.bg_color, style.bg_opacity), 1
    return 1, hex_to_ass_color(style.border_color, 1.0), max(1, style.border_width)


def _run_ffmpeg_subtitle_burn(cmd: list) -> None:
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


def burn_subtitles(video_path, srt_path, output_path, alignment=2, fontsize=16, style_options=None):
    """
    Burns subtitles into the video using FFmpeg.
    Supports two modes:
    - Outline mode (bg_opacity=0): Text with colored outline/border
    - Box mode (bg_opacity>0): Text with semi-transparent background box
    """
    style = style_options or SubtitleStyleOptions()

    width, height = _probe_video_resolution(video_path)
    if not width or not height:
        # Sane vertical-reel fallback: better than ever letting this fall
        # through to ffmpeg's own tiny default virtual canvas.
        width, height = 1080, 1920

    _normalize_subtitle_text_case(srt_path, style.text_case)

    # Font name is the one style field echoed verbatim into the generated
    # .ass file. Restrict it to a safe character set so a crafted font_name
    # can't break out of the Style line or inject extra script sections.
    safe_font_name = re.sub(r"[^A-Za-z0-9 _.\-]", "", style.font_name or "")[:64].strip() or "Verdana"

    border_style, outline_colour, outline_width = _resolve_ass_border_params(style)

    ass_params = _AssStyleParams(
        width=width, height=height, ass_alignment=_resolve_ass_alignment(alignment),
        font_name=safe_font_name, fontsize=max(10, int(fontsize)),
        primary_colour=hex_to_ass_color(style.font_color, 1.0),
        outline_colour=outline_colour, back_colour=hex_to_ass_color("#000000", 0.0),
        border_style=border_style, outline_width=outline_width,
        shadow=max(0, int(style.shadow_blur)), bold=1 if style.bold else 0, italic=1 if style.italic else 0,
        highlight_colour=hex_to_ass_color(style.highlight_color, 1.0),
    )

    blocks = _parse_srt_blocks(srt_path)
    ass_content = _build_ass_document(blocks, ass_params)
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

        _run_ffmpeg_subtitle_burn(cmd)

        return True
    finally:
        try:
            if os.path.exists(ass_path):
                os.remove(ass_path)
        except Exception:
            pass

