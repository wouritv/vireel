import { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Sparkles } from "lucide-react";
import { useTranslation } from "../state/LanguageContext";
import {
    formatMsClock,
    saveFilmSummaryManualSelection,
    generateFilmSummaryNarration,
} from "../lib/filmSummary";
import FilmSummaryShotTimeline from "./FilmSummaryShotTimeline";

// Builds the initial per-shot selection map: everything the user already
// kept in a previous manual_selection stays enabled with its saved
// start/end; everything else starts *disabled* with its full original
// boundaries, so opening the editor for the very first time -- when there's
// no manual_selection yet at all -- presents an empty cut the user builds up
// shot by shot, instead of starting with everything already selected.
function buildInitialSelections(shots, manualSelection) {
    const savedByShotId = new Map((manualSelection || []).map((entry) => [entry.scene_id, entry]));
    const next = {};
    shots.forEach((shot) => {
        const saved = savedByShotId.get(shot.scene_id);
        next[shot.scene_id] = saved
            ? { enabled: true, startMs: saved.start_ms, endMs: saved.end_ms }
            : { enabled: false, startMs: shot.start_ms, endMs: shot.end_ms };
    });
    return next;
}

function buildManualSelectionPayload(shots, selections) {
    return shots
        .filter((shot) => selections[shot.scene_id]?.enabled)
        .map((shot) => ({
            scene_id: shot.scene_id,
            start_ms: Math.round(selections[shot.scene_id].startMs),
            end_ms: Math.round(selections[shot.scene_id].endMs),
        }));
}

// The "Mode manuel" shot picker: the full original source video on top, the
// chronological shot track (FilmSummaryShotTimeline) at the bottom. Once the
// user confirms their cut, this saves it (PUT .../manual-selection) then
// kicks off the AI narration pass over exactly those clips (POST
// .../generate-narration), showing a loading state throughout, and hands
// the resulting row back to the parent page so it can route into the
// existing FilmSummaryReviewPanel -- same role as
// FilmSummaryProjectDetailPage already does for the automatic flow. No way
// back to the automatic review once opened (by design) -- the user commits
// to building a manual cut and confirms it via handleConfirm below.
export default function FilmSummaryClipPickerEditor({ filmSummary, user, onNarrationReady }) {
    const { t } = useTranslation();
    const videoRef = useRef(null);

    const shots = useMemo(
        () => (Array.isArray(filmSummary.scene_index) ? [...filmSummary.scene_index].sort((a, b) => a.start_ms - b.start_ms) : []),
        [filmSummary.scene_index]
    );

    const [selections, setSelections] = useState(() => buildInitialSelections(shots, filmSummary.manual_selection));
    const [currentTimeMs, setCurrentTimeMs] = useState(0);
    const [sourceDurationMs, setSourceDurationMs] = useState(0);
    const [saving, setSaving] = useState(false);
    const [generating, setGenerating] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        setSelections(buildInitialSelections(shots, filmSummary.manual_selection));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filmSummary.id]);

    const lastShotEndMs = shots.length ? shots[shots.length - 1].end_ms : 0;
    const timelineDurationMs = Math.max(sourceDurationMs, lastShotEndMs, 1000);

    const enabledCount = useMemo(() => Object.values(selections).filter((s) => s.enabled).length, [selections]);

    const handleToggleShot = (sceneId) => {
        setSelections((prev) => ({
            ...prev,
            [sceneId]: { ...prev[sceneId], enabled: !prev[sceneId]?.enabled },
        }));
    };

    const handleTrimChange = (sceneId, { startMs, endMs }) => {
        setSelections((prev) => ({ ...prev, [sceneId]: { ...prev[sceneId], startMs, endMs } }));
    };

    const seekTo = (ms) => {
        if (videoRef.current) videoRef.current.currentTime = Math.max(0, ms) / 1000;
    };

    const handleTimeUpdate = () => {
        if (videoRef.current) setCurrentTimeMs(videoRef.current.currentTime * 1000);
    };

    const handleLoadedMetadata = () => {
        if (videoRef.current?.duration) setSourceDurationMs(videoRef.current.duration * 1000);
    };

    const handleConfirm = async () => {
        if (!user?.id || enabledCount === 0) return;
        setError("");
        setSaving(true);
        try {
            const manualSelection = buildManualSelectionPayload(shots, selections);
            await saveFilmSummaryManualSelection(filmSummary.id, user.id, manualSelection);
            setSaving(false);
            setGenerating(true);
            const generated = await generateFilmSummaryNarration(filmSummary.id, user.id);
            onNarrationReady?.(generated);
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setSaving(false);
            setGenerating(false);
        }
    };

    const busy = saving || generating;

    return (
        <div className="space-y-4">
            <div>
                <h2 className="title-contrast text-xl font-bold">{t("filmSummary.manual.title", "Mode manuel -- choix des plans")}</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-zinc-400">
                    {t(
                        "filmSummary.manual.subtitle",
                        "Active ou desactive chaque plan et ajuste son debut/sa fin, puis laisse l'IA ecrire la voix off correspondante."
                    )}
                </p>
            </div>

            {error ? <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div> : null}

            <div className="space-y-2 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                <div className="aspect-video w-full overflow-hidden rounded-xl bg-black">
                    {filmSummary.source_url ? (
                        <video
                            ref={videoRef}
                            src={filmSummary.source_url}
                            controls
                            preload="metadata"
                            onTimeUpdate={handleTimeUpdate}
                            onLoadedMetadata={handleLoadedMetadata}
                            className="h-full w-full object-contain"
                        />
                    ) : (
                        <div className="flex h-full items-center justify-center px-4 text-center text-xs text-slate-500 dark:text-zinc-400">
                            {t("filmSummary.genericError", "Une erreur est survenue.")}
                        </div>
                    )}
                </div>
            </div>

            <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500 dark:text-zinc-400">
                    <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                        {t("filmSummary.manual.shotsLabel", "Plans de la scene")}
                    </label>
                    <span>
                        {t("filmSummary.manual.shotsSelectedCount", "{{count}} plan(s) sur {{total}} selectionne(s)", {
                            count: enabledCount,
                            total: shots.length,
                        })}
                    </span>
                </div>

                {shots.length === 0 ? (
                    <p className="text-xs text-slate-400 dark:text-zinc-500">{t("filmSummary.manual.noShots", "Aucun plan detecte pour cette scene.")}</p>
                ) : (
                    <>
                        <FilmSummaryShotTimeline
                            shots={shots}
                            selections={selections}
                            durationMs={timelineDurationMs}
                            currentTimeMs={currentTimeMs}
                            onToggleShot={handleToggleShot}
                            onTrimChange={handleTrimChange}
                            onSeek={seekTo}
                            t={t}
                        />

                        <div className="max-h-56 space-y-1.5 overflow-y-auto custom-scrollbar pr-1">
                            {shots.map((shot, index) => {
                                const selection = selections[shot.scene_id];
                                const startMs = selection?.startMs ?? shot.start_ms;
                                const endMs = selection?.endMs ?? shot.end_ms;
                                return (
                                    <div
                                        key={shot.scene_id}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => seekTo(startMs)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") {
                                                e.preventDefault();
                                                seekTo(startMs);
                                            }
                                        }}
                                        className={`flex w-full cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-xs ${
                                            selection?.enabled
                                                ? "border-emerald-500/30 bg-emerald-500/5 text-slate-700 dark:text-zinc-200"
                                                : "border-slate-300 dark:border-white/10 bg-white/5 text-slate-400 dark:text-zinc-500"
                                        }`}
                                    >
                                        <span className="flex flex-1 items-center gap-2 truncate text-left">
                                            <span className="font-mono text-slate-500 dark:text-zinc-500">#{index + 1}</span>
                                            <span className="truncate">{formatMsClock(startMs)} - {formatMsClock(endMs)}</span>
                                        </span>
                                        <input
                                            type="checkbox"
                                            checked={!!selection?.enabled}
                                            onClick={(e) => e.stopPropagation()}
                                            onChange={(e) => {
                                                e.stopPropagation();
                                                handleToggleShot(shot.scene_id);
                                            }}
                                            aria-label={
                                                selection?.enabled
                                                    ? t("filmSummary.manual.disableShot", "Retirer ce plan")
                                                    : t("filmSummary.manual.enableShot", "Garder ce plan")
                                            }
                                            className="h-4 w-4 shrink-0 cursor-pointer accent-emerald-500"
                                        />
                                    </div>
                                );
                            })}
                        </div>
                    </>
                )}
            </div>

            <div className="flex flex-col items-end gap-2">
                {enabledCount === 0 ? (
                    <p className="text-xs text-amber-300">{t("filmSummary.manual.needAtLeastOneShot", "Selectionne au moins un plan pour continuer.")}</p>
                ) : null}
                <button
                    type="button"
                    onClick={handleConfirm}
                    disabled={busy || enabledCount === 0}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-primary px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                    {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
                    {saving
                        ? t("filmSummary.manual.saving", "Enregistrement de la selection...")
                        : generating
                        ? t("filmSummary.manual.generating", "L'IA redige la narration...")
                        : t("filmSummary.manual.confirmButton", "Valider les plans et generer la narration")}
                </button>
            </div>
        </div>
    );
}
