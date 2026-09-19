import { useMemo } from "react";
import { Activity, AlertCircle, CheckCircle2, Clock3, Loader2 } from "lucide-react";
import { useTranslation } from "../state/LanguageContext";
import { buildFilmSummaryProcessSteps } from "../lib/filmSummary";

// Same "Suivi du processus" card (eyebrow + title + status pill, progress
// bar, step cards with icon/label/description) as AnonymousStoryCreatePage's
// ProcessingChecklist -- pulled into its own component here since it's
// reused for both the analysis phase (create page + detail page while
// queued/processing) and the render phase (detail page while rendering).
function StepStatusIcon({ state }) {
    if (state === "done") return <CheckCircle2 size={16} className="text-green-400" />;
    if (state === "active") return <Loader2 size={16} className="text-primary animate-spin" />;
    if (state === "error") return <AlertCircle size={16} className="text-red-400" />;
    return <Clock3 size={16} className="text-slate-400 dark:text-zinc-500" />;
}

export default function FilmSummaryProcessingPanel({ status, stage, phase, title, isLoadingStatus = false }) {
    const { t } = useTranslation();
    const steps = useMemo(() => buildFilmSummaryProcessSteps({ status, stage, phase, t }), [status, stage, phase, t]);
    const doneCount = steps.filter((step) => step.state === "done").length;
    const totalCount = steps.length;
    const progressPercent = Math.round((doneCount / totalCount) * 100);

    return (
        <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                        {t("reels.processFollowup", "Suivi du processus")}
                    </p>
                    <h3 className="title-contrast mt-1 text-lg font-bold">{title}</h3>
                </div>
                <div className="flex items-center gap-2 rounded-full border border-slate-300 dark:border-white/10 bg-black/20 px-3 py-1.5 text-xs text-slate-700 dark:text-zinc-300">
                    <Activity size={14} className={status === "processing" ? "text-primary animate-pulse" : "text-slate-500 dark:text-zinc-400"} />
                    <span>{isLoadingStatus ? t("app.loading", "Chargement...") : status}</span>
                </div>
            </div>

            <div className="mt-4 rounded-xl border border-slate-300 dark:border-white/10 bg-black/20 p-3">
                <div className="mb-2 flex items-center justify-between text-xs">
                    <span className="text-slate-500 dark:text-zinc-400">{t("reels.progress", "Progression")}</span>
                    <span className="font-medium text-zinc-200">{doneCount}/{totalCount} {t("reel.step", "etapes")} ({progressPercent}%)</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                        className="h-full rounded-full bg-primary transition-all duration-500"
                        style={{ width: `${progressPercent}%` }}
                    />
                </div>
            </div>

            <div className="mt-5 space-y-3">
                {steps.map((step) => (
                    <div key={step.key} className="flex items-start gap-3 rounded-xl border border-slate-200 dark:border-white/5 bg-black/20 px-4 py-3">
                        <div className="mt-0.5 shrink-0">
                            <StepStatusIcon state={step.state} />
                        </div>
                        <div className="min-w-0">
                            <p className="text-sm font-semibold text-white">{step.label}</p>
                            <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">{step.description}</p>
                        </div>
                    </div>
                ))}
            </div>
        </section>
    );
}
