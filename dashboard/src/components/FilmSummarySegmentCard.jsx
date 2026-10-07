import { Pencil, Play } from "lucide-react";
import { formatMsClock } from "../lib/filmSummary";

// One card per edit-plan segment inside FilmSummaryReviewPanel -- pulled
// into its own file to keep the review panel's own size manageable (same
// split-out-a-subcomponent convention as AnonymousStoryPublishModal.jsx).
// Every segment is voice_over -- there is no other segment type ("il ne
// dois y avoir aucune parole du film originale, uniquement les sequences
// videos + voix off de narration").
export default function FilmSummarySegmentCard({ segment, onNarrationChange, onEditClips, onSeek, t }) {
    const clips = segment.clips || [];

    return (
        <div className="rounded-xl border border-slate-200 dark:border-white/5 bg-black/20 p-3 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500 dark:text-zinc-500">#{segment.sequence}</span>
                    <span className="inline-flex rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">
                        {t("filmSummary.segmentVoiceOver", "Voix off")}
                    </span>
                </div>
                <span className="text-xs text-slate-500 dark:text-zinc-400">
                    {formatMsClock(segment.actual_duration_ms || segment.estimated_duration_ms)}
                </span>
            </div>

            <textarea
                value={segment.narration || ""}
                onChange={(e) => onNarrationChange(segment.id, e.target.value)}
                rows={3}
                className="input-field w-full resize-y text-sm dark:text-white"
                placeholder={t("filmSummary.narrationFieldLabel", "Narration")}
            />
            <div className="space-y-1">
                <div className="flex items-center justify-between">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                        {t("filmSummary.clipsLabel", "Extraits utilises")}
                    </p>
                    <button
                        type="button"
                        onClick={() => onEditClips(segment.id)}
                        className="inline-flex items-center gap-1 rounded-lg border border-primary/30 bg-primary/5 px-2 py-0.5 text-[11px] font-medium text-primary hover:bg-primary/10"
                    >
                        <Pencil size={11} /> {t("filmSummary.replaceClipsButton", "Remplacer les extraits")}
                    </button>
                </div>
                {clips.length ? (
                    clips.map((clip, index) => (
                        <button
                            // eslint-disable-next-line react/no-array-index-key
                            key={`${clip.scene_id || "clip"}-${index}`}
                            type="button"
                            onClick={() => onSeek(clip.start_ms)}
                            className="flex w-full items-center gap-2 rounded-lg border border-slate-200 dark:border-white/5 bg-white/5 px-2 py-1.5 text-left text-xs text-slate-700 dark:text-zinc-300 hover:bg-white/10"
                        >
                            <Play size={12} className="shrink-0 text-primary" />
                            <span className="shrink-0 font-mono text-slate-500 dark:text-zinc-500">
                                {formatMsClock(clip.start_ms)}-{formatMsClock(clip.end_ms)}
                            </span>
                            <span className="min-w-0 flex-1 truncate">{clip.description || clip.scene_id}</span>
                        </button>
                    ))
                ) : (
                    <p className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-2 py-1 text-xs text-amber-300">
                        {t("filmSummary.noClipsWarning", "Aucun extrait -- ce segment sera un fond noir tant qu'aucun extrait n'est ajoute.")}
                    </p>
                )}
            </div>
        </div>
    );
}
