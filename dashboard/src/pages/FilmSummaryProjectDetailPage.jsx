import { useEffect, useState } from "react";
import { AlertCircle, ArrowLeft, Ban, Download, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";
import { getApiUrl, fetchAppConfig } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";
import { errorMessageForCode } from "../lib/filmSummary";
import FilmSummaryProcessingPanel from "../components/FilmSummaryProcessingPanel";
import FilmSummaryReviewPanel from "../components/FilmSummaryReviewPanel";

// Statuses for which the film summary's own job_id is still meaningful to
// poll via the generic /api/status/{job_id} endpoint -- "rendering" reuses
// this same row field for the *second* (render) job_id, set by POST
// .../render (see app.py's render_film_summary_endpoint).
const ACTIVE_JOB_STATUSES = ["draft", "queued", "processing", "rendering"];

// Same "project detail" role as AnonymousStoryProjectDetailPage, but the
// film summary goes through a much richer state machine (see
// FilmSummaryStatus in film_summary.py) instead of a single generated-text
// editor -- this page is the state machine's single source of truth,
// switching between a progress panel, a rejection/failure view, the
// awaiting_review editor and the completed player.
export default function FilmSummaryProjectDetailPage() {
    const { projectId } = useParams();
    const { user } = useAuth();
    const { t } = useTranslation();
    const navigate = useNavigate();

    const [filmSummary, setFilmSummary] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [currentStep, setCurrentStep] = useState("");
    const [cancelling, setCancelling] = useState(false);
    const [retrying, setRetrying] = useState(false);
    const [deleting, setDeleting] = useState(false);
    const [allowedVoices, setAllowedVoices] = useState([]);
    const [defaultVoice, setDefaultVoice] = useState("cedar");

    useEffect(() => {
        let active = true;
        fetchAppConfig()
            .then((cfg) => {
                if (!active || !cfg) return;
                if (Array.isArray(cfg.filmSummaryAllowedVoices)) setAllowedVoices(cfg.filmSummaryAllowedVoices);
                if (cfg.filmSummaryDefaultVoice) setDefaultVoice(cfg.filmSummaryDefaultVoice);
            })
            .catch(() => {});
        return () => {
            active = false;
        };
    }, []);

    const loadFilmSummary = async () => {
        if (!projectId || !user?.id) return;
        setLoading(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/projects/${projectId}/film-summaries`), {
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setError(data?.detail || t("filmSummary.genericError", "Une erreur est survenue."));
                return;
            }
            const found = Array.isArray(data.film_summaries) ? data.film_summaries[0] : null;
            if (!found) {
                setError(t("filmSummary.noFilmSummaryFound", "Aucun resume de film n'a ete trouve pour ce projet."));
                setFilmSummary(null);
                return;
            }
            setFilmSummary(found);
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadFilmSummary();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId, user?.id]);

    const activeJobId = filmSummary && ACTIVE_JOB_STATUSES.includes(filmSummary.status) ? filmSummary.job_id : "";

    useEffect(() => {
        if (!activeJobId) return undefined;
        let cancelled = false;
        let timerId = null;
        let pollFailureCount = 0;

        const poll = async () => {
            try {
                const response = await fetch(getApiUrl(`/api/status/${activeJobId}`), { headers: getAuthHeaders(user?.id) });
                if (!response.ok) {
                    // A session that expires mid-operation (a film summary
                    // analysis can run well past an hour) previously left
                    // this loop polling forever with nothing ever shown --
                    // 401 specifically means no retry will ever succeed, so
                    // stop immediately and say so instead of spinning
                    // silently. Other failures get a few tries (transient
                    // network blips) before giving up the same way.
                    if (response.status === 401) {
                        if (timerId) globalThis.clearInterval(timerId);
                        setError(t("filmSummary.sessionExpired", "Ta session a expire. Reconnecte-toi puis reviens sur cette page pour continuer le suivi."));
                        return;
                    }
                    pollFailureCount += 1;
                    if (pollFailureCount >= 5) {
                        if (timerId) globalThis.clearInterval(timerId);
                        setError(t("filmSummary.genericError", "Une erreur est survenue."));
                    }
                    return;
                }
                pollFailureCount = 0;
                const data = await response.json();
                if (cancelled) return;
                setCurrentStep(String(data.current_step || ""));
                if (data.status === "completed" || data.status === "failed") {
                    // The row's own status (awaiting_review, rejected,
                    // failed or completed) is the source of truth for which
                    // view to show next -- re-fetch it rather than trying to
                    // infer anything from the job's result payload.
                    await loadFilmSummary();
                }
            } catch {
                // Keep polling on transient network errors.
            }
        };

        poll();
        timerId = globalThis.setInterval(poll, 2500);
        return () => {
            cancelled = true;
            if (timerId) globalThis.clearInterval(timerId);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [activeJobId, user?.id, t]);

    const handleCancel = async () => {
        if (!filmSummary?.id || !user?.id) return;
        if (!globalThis.confirm(t("filmSummary.confirmCancel", "Annuler cette operation ? La progression sera perdue."))) return;
        setCancelling(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummary.id}/cancel`), {
                method: "POST",
                headers: getAuthHeaders(user.id),
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                setError(data?.detail || t("filmSummary.genericError", "Une erreur est survenue."));
                return;
            }
            await loadFilmSummary();
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setCancelling(false);
        }
    };

    const handleRetry = async () => {
        if (!filmSummary?.id || !user?.id) return;
        setRetrying(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummary.id}/retry`), {
                method: "POST",
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setError(data?.detail || t("filmSummary.genericError", "Une erreur est survenue."));
                return;
            }
            await loadFilmSummary();
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setRetrying(false);
        }
    };

    const handleDelete = async () => {
        if (!filmSummary?.id || !user?.id) return;
        if (!globalThis.confirm(t("filmSummary.confirmDelete", "Supprimer ce projet de resume de film ? La video source et les fichiers generes seront egalement supprimes."))) return;
        setDeleting(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummary.id}`), {
                method: "DELETE",
                headers: getAuthHeaders(user.id),
            });
            if (!response.ok) {
                const data = await response.json().catch(() => ({}));
                setError(data?.detail || t("filmSummary.genericError", "Une erreur est survenue."));
                return;
            }
            navigate("/dashboard/film-summaries");
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setDeleting(false);
        }
    };

    if (loading && !filmSummary) {
        return (
            <div className="flex flex-1 items-center justify-center p-8">
                <span className="inline-flex items-center gap-2 text-slate-500 dark:text-zinc-400">
                    <Loader2 size={16} className="animate-spin" /> {t("reels.loading", "Loading...")}
                </span>
            </div>
        );
    }

    const status = filmSummary?.status;
    const cancelButton = (
        <button
            type="button"
            onClick={handleCancel}
            disabled={cancelling}
            className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-300 hover:bg-red-500/20 disabled:opacity-50"
        >
            {cancelling ? <Loader2 size={14} className="animate-spin" /> : <Ban size={14} />}
            {t("filmSummary.cancelButton", "Annuler")}
        </button>
    );
    const deleteButton = (
        <button
            type="button"
            onClick={handleDelete}
            disabled={deleting}
            className="inline-flex items-center gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-2.5 text-sm font-medium text-red-300 hover:bg-red-500/20 disabled:opacity-50"
        >
            {deleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
            {t("filmSummary.deleteButton", "Supprimer")}
        </button>
    );

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0">
                    <h1 className="truncate text-3xl font-black tracking-tight">{filmSummary?.title || t("filmSummary.untitled", "Resume de film sans titre")}</h1>
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/film-summaries")}
                    className="inline-flex shrink-0 items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                >
                    <ArrowLeft size={14} />
                    {t("filmSummary.backToList", "Retour aux resumes de film")}
                </button>
            </div>

            {error ? (
                <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                    <AlertCircle size={14} className="shrink-0" /> {error}
                </div>
            ) : null}

            {!filmSummary ? null : (
                <>
                    {status === "queued" || status === "processing" || status === "draft" ? (
                        <div className="space-y-3">
                            <FilmSummaryProcessingPanel
                                status="processing"
                                stage={currentStep || filmSummary.stage}
                                phase="analysis"
                                title={t("filmSummary.processingTitle", "Analyse de ton film")}
                            />
                            {cancelButton}
                        </div>
                    ) : null}

                    {status === "rendering" ? (
                        <div className="space-y-3">
                            <FilmSummaryProcessingPanel
                                status="processing"
                                stage={currentStep || filmSummary.stage}
                                phase="render"
                                title={t("filmSummary.renderingTitle", "Generation de ta video")}
                            />
                            {cancelButton}
                        </div>
                    ) : null}

                    {status === "rejected" ? (
                        <div className="space-y-3 rounded-2xl border border-red-500/30 bg-red-500/10 p-5">
                            <h3 className="text-lg font-bold text-red-300">{t("filmSummary.rejectedTitle", "Cette video a ete rejetee")}</h3>
                            <p className="text-sm text-red-200">
                                {filmSummary.rejection_reason || errorMessageForCode(t, filmSummary.error_code, t("filmSummary.genericError", "Une erreur est survenue."))}
                            </p>
                            <p className="text-xs text-red-300/80">
                                {t("filmSummary.rejectedHint", "Les videos rejetees ne peuvent pas etre relancees -- demarre un nouveau resume avec une autre source.")}
                            </p>
                            {deleteButton}
                        </div>
                    ) : null}

                    {status === "failed" ? (
                        <div className="space-y-3 rounded-2xl border border-amber-500/30 bg-amber-500/10 p-5">
                            <h3 className="text-lg font-bold text-amber-300">{t("filmSummary.failedTitle", "Une erreur est survenue")}</h3>
                            <p className="text-sm text-amber-200">{errorMessageForCode(t, filmSummary.error_code, t("filmSummary.genericError", "Une erreur est survenue."))}</p>
                            <p className="text-xs text-amber-300/80">{t("filmSummary.failedHint", "Une erreur technique s'est produite. Tu peux relancer l'analyse.")}</p>
                            <div className="flex flex-wrap gap-2">
                                <button
                                    type="button"
                                    onClick={handleRetry}
                                    disabled={retrying}
                                    className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
                                >
                                    {retrying ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                                    {t("filmSummary.retryButton", "Reessayer")}
                                </button>
                                {deleteButton}
                            </div>
                        </div>
                    ) : null}

                    {status === "cancelled" ? (
                        <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-5">
                            <h3 className="text-lg font-bold text-slate-700 dark:text-zinc-200">{t("filmSummary.statusCancelled", "Annule")}</h3>
                            {deleteButton}
                        </div>
                    ) : null}

                    {status === "awaiting_review" ? (
                        <FilmSummaryReviewPanel
                            filmSummary={filmSummary}
                            projectId={projectId}
                            user={user}
                            allowedVoices={allowedVoices}
                            defaultVoice={defaultVoice}
                            onRefresh={loadFilmSummary}
                        />
                    ) : null}

                    {status === "completed" ? (
                        <div className="space-y-4">
                            <h3 className="text-lg font-bold text-white">{t("filmSummary.completedTitle", "Ton resume de film est pret")}</h3>
                            <div className="grid gap-4 md:grid-cols-2">
                                {filmSummary.final_url ? (
                                    <div className="space-y-2">
                                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                            {t("filmSummary.finalVideoLabel", "Video finale")}
                                        </label>
                                        <video src={filmSummary.final_url} controls preload="metadata" className="w-full rounded-xl bg-black" />
                                        <a
                                            href={filmSummary.final_url}
                                            download
                                            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                                        >
                                            <Download size={14} /> {t("filmSummary.downloadButton", "Telecharger")}
                                        </a>
                                    </div>
                                ) : null}
                                {filmSummary.preview_url ? (
                                    <div className="space-y-2">
                                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                            {t("filmSummary.previewLabel", "Apercu")}
                                        </label>
                                        <video src={filmSummary.preview_url} controls preload="metadata" className="w-full rounded-xl bg-black" />
                                    </div>
                                ) : null}
                            </div>
                        </div>
                    ) : null}
                </>
            )}
        </div>
    );
}
