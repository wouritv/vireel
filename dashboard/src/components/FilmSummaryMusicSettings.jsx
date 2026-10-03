import { Loader2, Music, Save } from "lucide-react";
import { formatMsClock } from "../lib/filmSummary";

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

// Music section of FilmSummaryAudioSubtitleSettings: a mood-grouped track
// picker sourced from the app's existing background-music library (no
// custom upload for film summaries), plus a start/end range over the final
// video's duration telling the renderer where to play it. Kept as its own
// small component so FilmSummaryAudioSubtitleSettings doesn't have to mix
// this with the subtitle section's very different controls.
export default function FilmSummaryMusicSettings({
    tracksByMood,
    tracksLoading,
    tracksError,
    musicTrackId,
    musicStartMs,
    musicEndMs,
    totalDurationMs,
    onChange,
    onSave,
    saving,
    savedFlash,
    error,
    t,
}) {
    const safeDurationMs = Math.max(1000, Math.round(totalDurationMs || 0));
    const hasTrack = Boolean(musicTrackId);

    const handleTrackChange = (e) => {
        const nextTrackId = e.target.value || null;
        onChange({
            musicTrackId: nextTrackId,
            musicStartMs: nextTrackId ? musicStartMs ?? 0 : null,
            musicEndMs: nextTrackId ? musicEndMs ?? safeDurationMs : null,
        });
    };

    const handleStartChange = (e) => {
        const next = clamp(Number(e.target.value) || 0, 0, (musicEndMs ?? safeDurationMs) - 500);
        onChange({ musicStartMs: next });
    };

    const handleEndChange = (e) => {
        const next = clamp(Number(e.target.value) || safeDurationMs, (musicStartMs ?? 0) + 500, safeDurationMs);
        onChange({ musicEndMs: next });
    };

    return (
        <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
            <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                <Music size={14} />
                {t("filmSummary.music.title", "Musique de fond")}
            </label>

            {tracksError ? <p className="text-xs text-red-300">{tracksError}</p> : null}

            <select
                value={musicTrackId || ""}
                onChange={handleTrackChange}
                disabled={tracksLoading}
                className="input-field w-full dark:text-white"
            >
                <option value="">{t("filmSummary.music.none", "Aucune musique")}</option>
                {Object.entries(tracksByMood || {}).map(([mood, tracks]) => (
                    <optgroup key={mood} label={mood}>
                        {tracks.map((track) => (
                            <option key={track.track_id} value={track.track_id}>
                                {track.label}
                            </option>
                        ))}
                    </optgroup>
                ))}
            </select>

            {hasTrack ? (
                <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                        <span>{t("filmSummary.music.startLabel", "Debut")}: {formatMsClock(musicStartMs || 0)}</span>
                        <span>{t("filmSummary.music.endLabel", "Fin")}: {formatMsClock(musicEndMs ?? safeDurationMs)}</span>
                    </div>
                    <label className="block text-[11px] text-slate-500 dark:text-zinc-400">
                        {t("filmSummary.music.startSlider", "Position de debut")}
                        <input
                            type="range"
                            min={0}
                            max={safeDurationMs}
                            step={500}
                            value={musicStartMs || 0}
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
                            value={musicEndMs ?? safeDurationMs}
                            onChange={handleEndChange}
                            className="mt-1 w-full accent-emerald-500"
                        />
                    </label>
                </div>
            ) : null}

            {error ? <p className="text-xs text-red-300">{error}</p> : null}

            <button
                type="button"
                onClick={onSave}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2 text-xs font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50"
            >
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                {savedFlash ? t("filmSummary.music.saved", "Enregistre") : t("filmSummary.music.save", "Enregistrer la musique")}
            </button>
        </div>
    );
}
