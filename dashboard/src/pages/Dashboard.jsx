import { ArrowRight, Clapperboard, MessageSquareText, Quote, Sparkles } from "lucide-react";
import { useAuth } from "../state/AuthContext";
import { useNavigate } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import { getApiUrl } from "../config";
import { normalizeFrontendStatus, statusMeta } from "../lib/status";
import { readGenerationSession, SESSION_KEY } from "../lib/session";
import { useTranslation } from "../state/LanguageContext";
import { getAuthHeaders } from "../lib/apiAuth";
import DashboardStatsSection from "../components/dashboard/DashboardStatsSection";
import DashboardAnalyticsSection from "../components/dashboard/DashboardAnalyticsSection";

export default function Dashboard() {

    const { user } = useAuth();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const [generationSession, setGenerationSession] = useState(() => readGenerationSession());
    const [range, setRange] = useState("30d");

    useEffect(() => {
        const syncSession = () => setGenerationSession(readGenerationSession());
        syncSession();

        const interval = globalThis.setInterval(syncSession, 2000);
        return () => globalThis.clearInterval(interval);
    }, []);

    useEffect(() => {
        if (!generationSession?.jobId || generationSession.status !== "processing") return undefined;

        let cancelled = false;
        const pollStatus = async () => {
            try {
                const response = await fetch(getApiUrl(`/api/status/${generationSession.jobId}`), {
                    headers: getAuthHeaders(user?.id),
                });
                if (!response.ok) return;
                const data = await response.json();
                if (cancelled) return;

                const nextSession = {
                    ...generationSession,
                    status: normalizeFrontendStatus(data.status),
                    results: data.result ?? generationSession.results ?? null,
                    timestamp: Date.now(),
                };
                globalThis.localStorage.setItem(SESSION_KEY, JSON.stringify(nextSession));
                setGenerationSession(nextSession);
            } catch {
                // Silent background poll for dashboard summary only.
            }
        };

        pollStatus();
        const interval = globalThis.setInterval(pollStatus, 3000);
        return () => {
            cancelled = true;
            globalThis.clearInterval(interval);
        };
    }, [generationSession?.jobId, generationSession?.status]);

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-10">
            <section className="space-y-4">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">{t("dashboard.startAction","Demarrer une action")}</p>
                    <h3 className="mt-2 text-xl font-bold">{t("dashboard.generationJourney","Parcours de generation")}</h3>
                </div>

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <button
                        onClick={() => navigate("/dashboard/reel-generator")}
                        className="group flex items-center gap-3 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 text-left hover:bg-white/10 transition"
                    >
                        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 text-violet-400">
                            <Sparkles size={16} />
                        </span>
                        <h4 className="title-contrast flex-1 text-sm font-semibold truncate">{t("dashboard.reelgenerator","Générer des reels")}</h4>
                        <ArrowRight size={14} className="shrink-0 text-slate-400 dark:text-zinc-500 group-hover:text-white" />
                    </button>

                    <button
                        onClick={() => navigate("/dashboard/captions/new")}
                        className="group flex items-center gap-3 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 text-left hover:bg-white/10 transition"
                    >
                        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                            <MessageSquareText size={16} />
                        </span>
                        <h4 className="title-contrast flex-1 text-sm font-semibold truncate">{t("dashboard.captionGenerator","Générer des sous-titres")}</h4>
                        <ArrowRight size={14} className="shrink-0 text-slate-400 dark:text-zinc-500 group-hover:text-white" />
                    </button>

                    <button
                        onClick={() => navigate("/dashboard/anonymous-stories/new")}
                        className="group flex items-center gap-3 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 text-left hover:bg-white/10 transition"
                    >
                        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-pink-500/10 text-pink-400">
                            <Quote size={16} />
                        </span>
                        <h4 className="title-contrast flex-1 text-sm font-semibold truncate">{t("dashboard.anonymousStoryGenerator", "Générer une histoire")}</h4>
                        <ArrowRight size={14} className="shrink-0 text-slate-400 dark:text-zinc-500 group-hover:text-white" />
                    </button>

                    <button
                        onClick={() => navigate("/dashboard/film-summaries/new")}
                        className="group flex items-center gap-3 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 p-3 text-left hover:bg-white/10 transition"
                    >
                        <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-teal-500/10 text-teal-400">
                            <Clapperboard size={16} />
                        </span>
                        <h4 className="title-contrast flex-1 text-sm font-semibold truncate">{t("dashboard.filmSummaryGenerator", "Générer un résumé de film")}</h4>
                        <ArrowRight size={14} className="shrink-0 text-slate-400 dark:text-zinc-500 group-hover:text-white" />
                    </button>
                </div>
            </section>

            <DashboardStatsSection range={range} onRangeChange={setRange} />

            <DashboardAnalyticsSection range={range} />
        </div>

    );
}
