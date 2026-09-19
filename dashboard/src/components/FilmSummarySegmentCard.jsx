import { Play } from "lucide-react";
import { formatMsClock, SEGMENT_TYPE_BREATHING, SEGMENT_TYPE_ORIGINAL_DIALOGUE, SEGMENT_TYPE_VOICE_OVER } from "../lib/filmSummary";

// One card per edit-plan segment inside FilmSummaryReviewPanel -- pulled
// into its own file to keep the review panel's own size manageable (same
// split-out-a-subcomponent convention as AnonymousStoryPublishModal.jsx).
function SegmentTypeBadge({ type, t }) {
    const config = {
        [SEGMENT_TYPE_VOICE_OVER]: {
            label: t("filmSummary.segmentVoiceOver", "Voix off"),
            className: "border-primary/30 bg-primary/10 text-primary",
        },
        [SEGMENT_TYPE_ORIGINAL_DIALOGUE]: {
            label: t("filmSummary.segmentOriginalDialogue", "Dialogue original"),
            className: "border-sky-500/30 bg-sky-500/10 text-sky-300",
        },
        [SEGMENT_TYPE_BREATHING]: {
            label: t("filmSummary.segmentBreathing", "Respiration"),
            className: "border-slate-400/30 bg-slate-400/10 text-slate-300",
        },
    }[type] || { label: type, className: "border-slate-400/30 bg-slate-400/10 text-slate-300" };

    return <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] font-medium ${config.className}`}>{config.label}</span>;
}

export default function FilmSummarySegmentCard({ segment, onNarrationChange, onSeek, t }) {
    const isVoiceOver = segment.type === SEGMENT_TYPE_VOICE_OVER;
    const isDialogue = segment.type === SEGMENT_TYPE_ORIGINAL_DIALOGUE;
    const clips = isVoiceOver ? (segment.clips || []) : [];

    return (
        <div className="rounded-xl border border-slate-200 dark:border-white/5 bg-black/20 p-3 space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-slate-500 dark:text-zinc-500">#{segment.sequence}</span>
                    <SegmentTypeBadge type={segment.type} t={t} />
                </div>
                <span className="text-xs text-slate-500 dark:text-zinc-400">
                    {isVoiceOver
                        ? formatMsClock(segment.actual_duration_ms || segment.estimated_duration_ms)
                        : `${formatMsClock(segment.start_ms)} - ${formatMsClock(segment.end_ms)}`}
                </span>
            </div>

            {isVoiceOver ? (
                <>
                    <textarea
                        value={segment.narration || ""}
                        onChange={(e) => onNarrationChange(segment.id, e.target.value)}
                        rows={3}
                        className="input-field w-full resize-y text-sm dark:text-white"
                        placeholder={t("filmSummary.narrationFieldLabel", "Narration")}
                    />
                    {clips.length ? (
                        <div className="space-y-1">
                            <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-zinc-500">
                                {t("filmSummary.clipsLabel", "Extraits utilises")}
                            </p>
                            {clips.map((clip, index) => (
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
                                    <span className="truncate">{clip.description || clip.scene_id}</span>
                                </button>
                            ))}
                        </div>
                    ) : null}
                </>
            ) : (
                <button
                    type="button"
                    onClick={() => onSeek(segment.start_ms)}
                    className="w-full rounded-lg border border-slate-200 dark:border-white/5 bg-white/5 px-3 py-2 text-left hover:bg-white/10"
                >
                    {isDialogue ? (
                        <p className="text-sm italic text-slate-700 dark:text-zinc-300">&ldquo;{segment.transcript_excerpt}&rdquo;</p>
                    ) : (
                        <p className="text-xs text-slate-500 dark:text-zinc-400">{t("filmSummary.segmentBreathing", "Respiration")}</p>
                    )}
                    {segment.speaker_ids?.length ? (
                        <p className="mt-1 text-[11px] text-slate-500 dark:text-zinc-500">
                            {t("filmSummary.speakersLabel", "Locuteurs")}: {segment.speaker_ids.join(", ")}
                        </p>
                    ) : null}
                </button>
            )}
        </div>
    );
}
