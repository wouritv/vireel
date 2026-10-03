import { Loader2, Music, Plus, Save } from "lucide-react";
import { useMemo } from "react";
import FilmSummaryMusicTrackRow from "./FilmSummaryMusicTrackRow";

// Music section of FilmSummaryAudioSubtitleSettings: a repeatable list of
// background-music tracks sourced from the app's existing mood-grouped
// music library (no custom upload for film summaries) -- "une musique de
// fond peut s'appliquer a une ou plusieurs scenes", so each entry gets its
// own track pick, its own preview, and its own start/end range over the
// final video's duration, instead of the single-track/single-range picker
// this used to be. Per-row UI lives in FilmSummaryMusicTrackRow so this
// component stays a simple list manager (add/remove/patch one entry, then
// save the whole list) instead of one large function mixing both concerns.
export default function FilmSummaryMusicSettings({
    tracksByMood,
    tracksLoading,
    tracksError,
    musicTracks,
    totalDurationMs,
    onChange,
    onSave,
    saving,
    savedFlash,
    error,
    t,
}) {
    const tracksById = useMemo(() => {
        const map = {};
        Object.values(tracksByMood || {}).forEach((moodTracks) => {
            moodTracks.forEach((track) => {
                map[track.track_id] = track;
            });
        });
        return map;
    }, [tracksByMood]);

    const firstTrackId = useMemo(() => {
        const moods = Object.values(tracksByMood || {});
        return moods.length ? moods[0]?.[0]?.track_id || "" : "";
    }, [tracksByMood]);

    const tracks = musicTracks || [];

    const updateEntry = (index, patch) => {
        onChange(tracks.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)));
    };

    const removeEntry = (index) => {
        onChange(tracks.filter((_, i) => i !== index));
    };

    const addEntry = () => {
        onChange([...tracks, { track_id: firstTrackId || null, start_ms: null, end_ms: null }]);
    };

    return (
        <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
            <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                <Music size={14} />
                {t("filmSummary.music.title", "Musique de fond")}
            </label>

            {tracksError ? <p className="text-xs text-red-300">{tracksError}</p> : null}

            {tracks.length === 0 ? (
                <p className="text-xs text-slate-500 dark:text-zinc-400">
                    {t("filmSummary.music.none", "Aucune musique de fond.")}
                </p>
            ) : (
                <div className="space-y-2">
                    {tracks.map((entry, index) => (
                        <FilmSummaryMusicTrackRow
                            key={`music-track-${index}`}
                            entry={entry}
                            tracksByMood={tracksByMood}
                            tracksById={tracksById}
                            totalDurationMs={totalDurationMs}
                            disabled={tracksLoading}
                            onChange={(patch) => updateEntry(index, patch)}
                            onRemove={() => removeEntry(index)}
                            t={t}
                        />
                    ))}
                </div>
            )}

            <button
                type="button"
                onClick={addEntry}
                disabled={tracksLoading || !firstTrackId}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-2 text-xs font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-white/10 disabled:opacity-50"
            >
                <Plus size={13} />
                {t("filmSummary.music.add", "Ajouter une musique")}
            </button>

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
