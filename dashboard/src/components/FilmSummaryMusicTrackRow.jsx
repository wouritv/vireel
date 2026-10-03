import { Pause, Play, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { getApiUrl } from "../config";
import { formatMsClock } from "../lib/filmSummary";

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

// One row of FilmSummaryMusicSettings' multi-track list: a mood-grouped
// track picker (with a small license badge next to tracks that carry
// Incompetech attribution info), a play/pause preview button wired to that
// track's preview_url (same new Audio()-ref toggle pattern
// FilmSummaryCreatePage's voice-preview buttons already use, just without
// the extra fetch since preview_url is already in hand), a start/end range
// over the final video's duration scoped to this entry alone, and a remove
// button. Split out of FilmSummaryMusicSettings so that component stays a
// simple list manager instead of one large function mixing both concerns.
export default function FilmSummaryMusicTrackRow({
    entry,
    tracksByMood,
    tracksById,
    totalDurationMs,
    disabled,
    onChange,
    onRemove,
    t,
}) {
    const safeDurationMs = Math.max(1000, Math.round(totalDurationMs || 0));
    const track = tracksById[entry.track_id] || null;
    const hasRange = entry.start_ms != null || entry.end_ms != null;
    const startMs = entry.start_ms ?? 0;
    const endMs = entry.end_ms ?? safeDurationMs;

    const [isPlaying, setIsPlaying] = useState(false);
    const [previewError, setPreviewError] = useState("");
    const audioRef = useRef(null);

    useEffect(() => {
        return () => {
            audioRef.current?.pause();
        };
    }, []);

    // Stop playback if this row's track changes (or is removed) out from
    // under an in-progress preview.
    useEffect(() => {
        audioRef.current?.pause();
        setIsPlaying(false);
    }, [entry.track_id]);

    const handleTogglePreview = async () => {
        setPreviewError("");
        if (isPlaying) {
            audioRef.current?.pause();
            setIsPlaying(false);
            return;
        }
        if (!track?.preview_url) return;
        try {
            if (!audioRef.current) audioRef.current = new Audio();
            const audio = audioRef.current;
            audio.src = getApiUrl(track.preview_url);
            audio.onended = () => setIsPlaying(false);
            await audio.play();
            setIsPlaying(true);
        } catch {
            setPreviewError(t("filmSummary.music.previewError", "Apercu audio indisponible pour le moment."));
            setIsPlaying(false);
        }
    };

    const handleTrackChange = (e) => {
        onChange({ track_id: e.target.value || null });
    };

    const handleToggleRange = (e) => {
        onChange(e.target.checked ? { start_ms: 0, end_ms: safeDurationMs } : { start_ms: null, end_ms: null });
    };

    const handleStartChange = (e) => {
        const next = clamp(Number(e.target.value) || 0, 0, endMs - 500);
        onChange({ start_ms: next });
    };

    const handleEndChange = (e) => {
        const next = clamp(Number(e.target.value) || safeDurationMs, startMs + 500, safeDurationMs);
        onChange({ end_ms: next });
    };

    return (
        <div className="space-y-2 rounded-xl border border-slate-300 dark:border-white/10 bg-black/10 p-3">
            <div className="flex items-center gap-2">
                <select
                    value={entry.track_id || ""}
                    onChange={handleTrackChange}
                    disabled={disabled}
                    className="input-field w-full dark:text-white"
                >
                    <option value="" disabled>
                        {t("filmSummary.music.choose", "Choisir une musique")}
                    </option>
                    {Object.entries(tracksByMood || {}).map(([mood, moodTracks]) => (
                        <optgroup key={mood} label={mood}>
                            {moodTracks.map((moodTrack) => (
                                <option key={moodTrack.track_id} value={moodTrack.track_id}>
                                    {moodTrack.label}
                                    {moodTrack.license ? ` (${moodTrack.license.license_name})` : ""}
                                </option>
                            ))}
                        </optgroup>
                    ))}
                </select>

                <button
                    type="button"
                    onClick={handleTogglePreview}
                    disabled={!track?.preview_url}
                    title={t("filmSummary.music.listenLabel", "Ecouter un extrait")}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-slate-300 dark:border-white/10 bg-white/5 text-slate-700 dark:text-zinc-200 hover:bg-white/10 disabled:opacity-50"
                >
                    {isPlaying ? <Pause size={14} /> : <Play size={14} />}
                </button>

                <button
                    type="button"
                    onClick={onRemove}
                    title={t("filmSummary.music.remove", "Retirer cette musique")}
                    className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-red-300/40 bg-red-500/5 text-red-500 dark:text-red-300 hover:bg-red-500/10"
                >
                    <Trash2 size={14} />
                </button>
            </div>

            {previewError ? <p className="text-xs text-red-300">{previewError}</p> : null}

            {track?.license ? (
                <span
                    title={
                        track.license.attribution_text ||
                        `${track.license.license_name || ""} - ${track.license.author || ""}`
                    }
                    className="inline-flex items-center gap-1 rounded-full border border-amber-300/40 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:text-amber-300"
                >
                    {track.license.license_name}
                    {track.license.author ? ` - ${track.license.author}` : ""}
                </span>
            ) : null}

            <label className="flex items-center gap-2 text-[11px] text-slate-500 dark:text-zinc-400">
                <input type="checkbox" checked={hasRange} onChange={handleToggleRange} className="accent-emerald-500" />
                {t("filmSummary.music.limitRange", "Limiter a une plage de la video")}
            </label>

            {hasRange ? (
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                        <span>{t("filmSummary.music.startLabel", "Debut")}: {formatMsClock(startMs)}</span>
                        <span>{t("filmSummary.music.endLabel", "Fin")}: {formatMsClock(endMs)}</span>
                    </div>
                    <label className="block text-[11px] text-slate-500 dark:text-zinc-400">
                        {t("filmSummary.music.startSlider", "Position de debut")}
                        <input
                            type="range"
                            min={0}
                            max={safeDurationMs}
                            step={500}
                            value={startMs}
                            onChange={handleStartChange}
                            className="mt-1 w-full accent-emerald-500"
                        />
                    </label>
                    <label className="block text-[11px] text-slate-500 dark:text-zinc-400">
                        {t("filmSummary.music.endSlider", "Position de fin")}
                        <input
                            type="range"
                            min={0}
                            max={safeDurationMs}
                            step={500}
                            value={endMs}
                            onChange={handleEndChange}
                            className="mt-1 w-full accent-emerald-500"
                        />
                    </label>
                </div>
            ) : (
                <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                    {t("filmSummary.music.wholeVideo", "Cette musique joue sur toute la duree de la video.")}
                </p>
            )}
        </div>
    );
}
