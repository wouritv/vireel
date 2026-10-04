import { useMemo, useRef, useState } from "react";
import { AlertTriangle, Compass, Loader2, Plus, Sparkles, X } from "lucide-react";
import { formatMsClock, rankSceneSuggestionsForSegment, usedClipSignaturesExcluding } from "../lib/filmSummary";
import FilmSummaryShotTimeline from "./FilmSummaryShotTimeline";

const MAX_SUGGESTIONS = 12;

// The new primary editing surface (see the Film Summary feature's "Remplacer
// l'experience de selection manuelle" redesign): instead of forcing the
// creator to rebuild the whole cut from a flat scene browser, this picker is
// scoped to ONE narrative block (segment) at a time. It opens with ranked
// suggestions (rankSceneSuggestionsForSegment, pure/client-side -- no new
// backend call) and keeps "Explorer toutes les scenes" as a secondary,
// explicit tab inside the same picker rather than a separate full-page mode.
// Reuses FilmSummaryShotTimeline unchanged (same toggle/trim mechanics
// FilmSummaryClipPickerEditor already uses) for the segment's own clips,
// just scoped to this one segment instead of the whole plan.
function SceneSuggestionRow({ scene, onAdd, onSeek, t }) {
    return (
        <div
            role="button"
            tabIndex={0}
            onClick={() => onSeek(scene.start_ms)}
            onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSeek(scene.start_ms);
                }
            }}
            className="flex w-full cursor-pointer items-start gap-2 rounded-lg border border-slate-200 dark:border-white/10 bg-white/5 px-3 py-2 text-left hover:bg-white/10"
        >
            <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                    <span className="font-mono text-xs text-slate-500 dark:text-zinc-500">
                        {formatMsClock(scene.start_ms)} - {formatMsClock(scene.end_ms)}
                    </span>
                    {scene.speakers?.length ? (
                        <span className="rounded-full border border-slate-300/50 dark:border-white/10 px-1.5 py-0.5 text-[10px] text-slate-500 dark:text-zinc-400">
                            {scene.speakers.join(", ")}
                        </span>
                    ) : null}
                    {scene.alreadyUsedElsewhere ? (
                        <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-300">
                            <AlertTriangle size={10} />
                            {t("filmSummary.swapPicker.alreadyUsedElsewhere", "Deja utilise ailleurs")}
                        </span>
                    ) : null}
                </div>
                <p className="mt-1 truncate text-xs text-slate-600 dark:text-zinc-300">
                    {scene.transcript_overlap || t("filmSummary.swapPicker.noDialogue", "(Aucun dialogue transcrit sur ce plan)")}
                </p>
            </div>
            <button
                type="button"
                onClick={(e) => {
                    e.stopPropagation();
                    onAdd(scene);
                }}
                title={t("filmSummary.swapPicker.addClip", "Utiliser cet extrait")}
                className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-primary/40 bg-primary/10 px-2 py-1 text-[11px] font-medium text-primary hover:bg-primary/20"
            >
                <Plus size={12} /> {t("filmSummary.swapPicker.addClip", "Utiliser cet extrait")}
            </button>
        </div>
    );
}

export default function FilmSummaryClipSwapPicker({ segment, sceneIndex, allSegments, sourceUrl, onConfirm, onClose, t }) {
    const videoRef = useRef(null);
    const [clips, setClips] = useState(() => (segment.clips || []).map((c) => ({ ...c })));
    const [exploreAll, setExploreAll] = useState(false);
    const [currentTimeMs, setCurrentTimeMs] = useState(0);
    const [sourceDurationMs, setSourceDurationMs] = useState(0);

    const sceneById = useMemo(() => new Map((sceneIndex || []).map((s) => [s.scene_id, s])), [sceneIndex]);

    // One shot per currently-selected clip, laid out at that scene's
    // *original* detected bounds -- same contract FilmSummaryShotTimeline
    // already expects, trimming is clamped to those original bounds.
    const shots = useMemo(
        () => clips.map((clip) => sceneById.get(clip.scene_id) || { scene_id: clip.scene_id, start_ms: clip.start_ms, end_ms: clip.end_ms }),
        [clips, sceneById]
    );
    const selections = useMemo(() => {
        const next = {};
        clips.forEach((clip) => {
            next[clip.scene_id] = { enabled: true, startMs: clip.start_ms, endMs: clip.end_ms };
        });
        return next;
    }, [clips]);

    const lastShotEndMs = shots.length ? Math.max(...shots.map((s) => s.end_ms)) : 0;
    const timelineDurationMs = Math.max(sourceDurationMs, lastShotEndMs, 1000);

    const segmentForRanking = useMemo(() => ({ ...segment, clips }), [segment, clips]);
    const suggestions = useMemo(
        () => rankSceneSuggestionsForSegment({ segment: segmentForRanking, sceneIndex, allSegments }),
        [segmentForRanking, sceneIndex, allSegments]
    );
    const usedElsewhere = useMemo(() => usedClipSignaturesExcluding(allSegments, segment.id), [allSegments, segment.id]);

    const currentSceneIds = useMemo(() => new Set(clips.map((c) => c.scene_id)), [clips]);
    const exploreList = useMemo(() => {
        return (sceneIndex || [])
            .filter((scene) => !currentSceneIds.has(scene.scene_id))
            .map((scene) => ({ ...scene, alreadyUsedElsewhere: usedElsewhere.has(`${scene.scene_id}|${scene.start_ms}|${scene.end_ms}`) }))
            .sort((a, b) => (a.start_ms || 0) - (b.start_ms || 0));
    }, [sceneIndex, currentSceneIds, usedElsewhere]);

    const seekTo = (ms) => {
        if (videoRef.current) videoRef.current.currentTime = Math.max(0, ms) / 1000;
    };
    const handleTimeUpdate = () => {
        if (videoRef.current) setCurrentTimeMs(videoRef.current.currentTime * 1000);
    };
    const handleLoadedMetadata = () => {
        if (videoRef.current?.duration) setSourceDurationMs(videoRef.current.duration * 1000);
    };

    const handleToggleShot = (sceneId) => {
        // The timeline above only ever renders shots already in `clips`, so
        // toggling one off here means "remove this clip from the segment".
        setClips((prev) => prev.filter((c) => c.scene_id !== sceneId));
    };
    const handleTrimChange = (sceneId, { startMs, endMs }) => {
        setClips((prev) => prev.map((c) => (c.scene_id === sceneId ? { ...c, start_ms: Math.round(startMs), end_ms: Math.round(endMs) } : c)));
    };
    const handleAddScene = (scene) => {
        setClips((prev) => [...prev, { scene_id: scene.scene_id, start_ms: scene.start_ms, end_ms: scene.end_ms }]);
    };

    const list = exploreAll ? exploreList : suggestions.slice(0, MAX_SUGGESTIONS);

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
            <div className="flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-slate-300 dark:border-white/10 bg-white dark:bg-[#121214] shadow-2xl">
                <div className="flex items-center justify-between border-b border-slate-200 dark:border-white/10 px-5 py-4">
                    <div>
                        <h3 className="text-base font-bold text-slate-800 dark:text-white">
                            {t("filmSummary.swapPicker.title", "Remplacer les extraits de ce segment")}
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-zinc-400">
                            {t("filmSummary.swapPicker.subtitle", "Choisis parmi les suggestions pertinentes, ou explore toutes les scenes du film.")}
                        </p>
                    </div>
                    <button type="button" onClick={onClose} className="shrink-0 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:text-zinc-400 dark:hover:bg-white/10">
                        <X size={16} />
                    </button>
                </div>

                <div className="flex-1 space-y-4 overflow-y-auto custom-scrollbar p-5">
                    <div className="aspect-video w-full overflow-hidden rounded-xl bg-black">
                        {sourceUrl ? (
                            <video
                                ref={videoRef}
                                src={sourceUrl}
                                controls
                                preload="metadata"
                                onTimeUpdate={handleTimeUpdate}
                                onLoadedMetadata={handleLoadedMetadata}
                                className="h-full w-full object-contain"
                            />
                        ) : (
                            <div className="flex h-full items-center justify-center text-slate-500 dark:text-zinc-400">
                                <Loader2 size={20} className="animate-spin" />
                            </div>
                        )}
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                            <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                {t("filmSummary.swapPicker.currentClipsLabel", "Extraits actuels de ce segment")}
                            </label>
                            <span>{t("filmSummary.swapPicker.clipCount", "{{count}} extrait(s)", { count: clips.length })}</span>
                        </div>
                        {shots.length ? (
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
                        ) : (
                            <p className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                                {t("filmSummary.swapPicker.noClips", "Ce segment n'a plus aucun extrait -- ajoute-en au moins un ci-dessous.")}
                            </p>
                        )}
                    </div>

                    <div className="space-y-2">
                        <div className="flex items-center gap-2">
                            <button
                                type="button"
                                onClick={() => setExploreAll(false)}
                                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
                                    !exploreAll ? "bg-primary text-white" : "bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-zinc-300"
                                }`}
                            >
                                <Sparkles size={12} /> {t("filmSummary.swapPicker.suggestionsTab", "Suggestions pertinentes")}
                            </button>
                            <button
                                type="button"
                                onClick={() => setExploreAll(true)}
                                className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium ${
                                    exploreAll ? "bg-primary text-white" : "bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-zinc-300"
                                }`}
                            >
                                <Compass size={12} /> {t("filmSummary.swapPicker.exploreAllTab", "Explorer toutes les scenes")}
                            </button>
                        </div>

                        <div className="max-h-64 space-y-1.5 overflow-y-auto custom-scrollbar pr-1">
                            {list.length === 0 ? (
                                <p className="text-xs text-slate-400 dark:text-zinc-500">
                                    {t("filmSummary.swapPicker.noSuggestions", "Aucune autre scene disponible.")}
                                </p>
                            ) : (
                                list.map((scene) => (
                                    <SceneSuggestionRow key={scene.scene_id} scene={scene} onAdd={handleAddScene} onSeek={seekTo} t={t} />
                                ))
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex items-center justify-end gap-2 border-t border-slate-200 dark:border-white/10 px-5 py-4">
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2 text-sm font-medium text-slate-700 dark:text-zinc-200 hover:bg-slate-200 dark:hover:bg-white/10"
                    >
                        {t("filmSummary.swapPicker.cancel", "Annuler")}
                    </button>
                    <button
                        type="button"
                        onClick={() => onConfirm(clips)}
                        disabled={clips.length === 0}
                        className="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {t("filmSummary.swapPicker.confirm", "Valider les extraits")}
                    </button>
                </div>
            </div>
        </div>
    );
}
