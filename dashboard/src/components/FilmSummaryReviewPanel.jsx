import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, Save } from "lucide-react";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useTranslation } from "../state/LanguageContext";
import { formatMsClock } from "../lib/filmSummary";
import FilmSummarySegmentCard from "./FilmSummarySegmentCard";

// The "awaiting_review" editor: source video for reference, the edit plan's
// segment timeline (editable narration for voice_over segments), the
// validation report, a voice picker and the render trigger. Kept as its own
// component (like AnonymousStoryPublishModal was split out of
// AnonymousStoryProjectDetailPage) since FilmSummaryProjectDetailPage
// already carries the whole status state machine on top of this.
export default function FilmSummaryReviewPanel({ filmSummary, projectId, user, allowedVoices, defaultVoice, onRefresh }) {
    const { t } = useTranslation();
    const [draftPlan, setDraftPlan] = useState(filmSummary.edit_plan || {});
    const [validationReport, setValidationReport] = useState(filmSummary.validation_report || {});
    const [voiceId, setVoiceId] = useState(filmSummary.voice_id || defaultVoice || "");
    const [sourceUrl, setSourceUrl] = useState("");
    const [sourceUrlLoading, setSourceUrlLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [validating, setValidating] = useState(false);
    const [rendering, setRendering] = useState(false);
    const [error, setError] = useState("");
    const [savedFlash, setSavedFlash] = useState(false);
    const videoRef = useRef(null);

    // Re-seed the local draft only when we land on a *different* film
    // summary -- while awaiting_review, the parent page never re-fetches on
    // its own (no polling happens outside queued/processing/rendering), so
    // this never clobbers in-flight edits.
    useEffect(() => {
        setDraftPlan(filmSummary.edit_plan || {});
        setValidationReport(filmSummary.validation_report || {});
        setVoiceId(filmSummary.voice_id || defaultVoice || "");
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [filmSummary.id]);

    useEffect(() => {
        let active = true;
        setSourceUrlLoading(true);
        fetch(getApiUrl(`/api/projects/${projectId}/source-url`), { headers: getAuthHeaders(user?.id) })
            .then((response) => (response.ok ? response.json() : null))
            .then((data) => {
                if (active && data?.source_url) setSourceUrl(data.source_url);
            })
            .catch(() => {})
            .finally(() => {
                if (active) setSourceUrlLoading(false);
            });
        return () => {
            active = false;
        };
    }, [projectId, user?.id]);

    const segments = useMemo(() => {
        const list = Array.isArray(draftPlan.segments) ? draftPlan.segments : [];
        return [...list].sort((a, b) => (a.sequence || 0) - (b.sequence || 0));
    }, [draftPlan.segments]);

    const handleSeek = (ms) => {
        if (!videoRef.current) return;
        videoRef.current.currentTime = Math.max(0, Number(ms || 0) / 1000);
        videoRef.current.play().catch(() => {});
    };

    const updateNarration = (segmentId, value) => {
        setDraftPlan((prev) => ({
            ...prev,
            segments: (prev.segments || []).map((seg) => (seg.id === segmentId ? { ...seg, narration: value } : seg)),
        }));
    };

    const handleSaveDraft = async () => {
        if (!user?.id) return;
        setSaving(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummary.id}/plan`), {
                method: "PATCH",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user.id) },
                body: JSON.stringify({ plan: draftPlan }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setError(typeof data?.detail === "string" ? data.detail : t("filmSummary.genericError", "Une erreur est survenue."));
                return;
            }
            setDraftPlan(data.edit_plan || draftPlan);
            setValidationReport(data.validation_report || {});
            setSavedFlash(true);
            setTimeout(() => setSavedFlash(false), 2000);
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setSaving(false);
        }
    };

    const handleRevalidate = async () => {
        if (!user?.id) return;
        setValidating(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummary.id}/validate`), {
                method: "POST",
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setError(t("filmSummary.genericError", "Une erreur est survenue."));
                return;
            }
            setValidationReport(data || {});
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setValidating(false);
        }
    };

    const handleRender = async () => {
        if (!user?.id) return;
        setRendering(true);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummary.id}/render`), {
                method: "POST",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user.id) },
                body: JSON.stringify({ voice_id: voiceId || undefined }),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                // 400 responses carry {validation_report} when the backend's
                // own re-validation caught something the client-side state
                // missed -- surface it the same way a manual re-validate would.
                if (data?.detail?.validation_report) setValidationReport(data.detail.validation_report);
                setError(t("filmSummary.validationInvalid", "Corrige les erreurs ci-dessous avant de generer la video."));
                return;
            }
            // The row now has status "rendering" and a new job_id -- let the
            // parent page re-fetch and switch to its rendering progress view.
            await onRefresh?.();
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setRendering(false);
        }
    };

    const isValid = validationReport?.valid === true;
    const errorsList = Array.isArray(validationReport?.errors) ? validationReport.errors : [];
    const warningsList = Array.isArray(validationReport?.warnings) ? validationReport.warnings : [];
    const voiceOptions = allowedVoices?.length ? allowedVoices : [defaultVoice].filter(Boolean);

    return (
        <div className="space-y-4">
            <div>
                <h2 className="title-contrast text-xl font-bold">{t("filmSummary.reviewTitle", "Valider le plan de montage")}</h2>
                <p className="mt-1 text-sm text-slate-500 dark:text-zinc-400">
                    {t("filmSummary.reviewSubtitle", "Modifie la narration, verifie le rapport de validation, puis genere la video finale.")}
                </p>
            </div>

            {error ? <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div> : null}

            <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
                <section className="space-y-4">
                    <div className="space-y-2 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("filmSummary.sourceVideoLabel", "Video source")}
                        </label>
                        <div className="aspect-video w-full overflow-hidden rounded-xl bg-black">
                            {sourceUrlLoading ? (
                                <div className="flex h-full items-center justify-center text-slate-500 dark:text-zinc-400">
                                    <Loader2 size={20} className="animate-spin" />
                                </div>
                            ) : sourceUrl ? (
                                <video ref={videoRef} src={sourceUrl} controls preload="metadata" className="h-full w-full object-contain" />
                            ) : (
                                <div className="flex h-full items-center justify-center px-4 text-center text-xs text-slate-500 dark:text-zinc-400">
                                    {t("filmSummary.genericError", "Une erreur est survenue.")}
                                </div>
                            )}
                        </div>
                    </div>

                    <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("filmSummary.segmentsLabel", "Segments du plan de montage")}
                        </label>
                        <div className="space-y-3">
                            {segments.map((segment) => (
                                <FilmSummarySegmentCard
                                    key={segment.id}
                                    segment={segment}
                                    onNarrationChange={updateNarration}
                                    onSeek={handleSeek}
                                    t={t}
                                />
                            ))}
                        </div>
                    </div>
                </section>

                <aside className="space-y-4">
                    <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("filmSummary.validationTitle", "Validation")}
                        </label>
                        <div
                            className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
                                isValid ? "border-green-500/30 bg-green-500/10 text-green-300" : "border-amber-500/30 bg-amber-500/10 text-amber-300"
                            }`}
                        >
                            {isValid ? <CheckCircle2 size={14} className="shrink-0" /> : <AlertTriangle size={14} className="shrink-0" />}
                            {isValid
                                ? t("filmSummary.validationValid", "Le plan est valide et pret a etre genere.")
                                : t("filmSummary.validationInvalid", "Corrige les erreurs ci-dessous avant de generer la video.")}
                        </div>

                        {errorsList.length ? (
                            <div className="space-y-1">
                                <p className="text-xs font-semibold text-red-300">{t("filmSummary.validationErrorsLabel", "Erreurs bloquantes")}</p>
                                <ul className="space-y-1 text-xs text-red-300">
                                    {errorsList.map((message, index) => (
                                        // eslint-disable-next-line react/no-array-index-key
                                        <li key={index} className="rounded-lg border border-red-500/20 bg-red-500/5 px-2 py-1">{message}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : null}

                        {warningsList.length ? (
                            <div className="space-y-1">
                                <p className="text-xs font-semibold text-amber-300">{t("filmSummary.validationWarningsLabel", "Avertissements")}</p>
                                <ul className="space-y-1 text-xs text-amber-300">
                                    {warningsList.map((message, index) => (
                                        // eslint-disable-next-line react/no-array-index-key
                                        <li key={index} className="rounded-lg border border-amber-500/20 bg-amber-500/5 px-2 py-1">{message}</li>
                                    ))}
                                </ul>
                            </div>
                        ) : null}

                        {Number.isFinite(validationReport?.total_estimated_duration_ms) ? (
                            <p className="text-xs text-slate-500 dark:text-zinc-400">
                                {t("filmSummary.totalDurationLabel", "Duree totale estimee")}: {formatMsClock(validationReport.total_estimated_duration_ms)}
                            </p>
                        ) : null}

                        <button
                            type="button"
                            onClick={handleRevalidate}
                            disabled={validating}
                            className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50"
                        >
                            {validating ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                            {t("filmSummary.revalidateButton", "Revalider")}
                        </button>
                    </div>

                    <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
                        <label className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("filmSummary.voiceLabel", "Voix du narrateur")}
                        </label>
                        <select value={voiceId} onChange={(e) => setVoiceId(e.target.value)} className="input-field w-full dark:text-white">
                            {voiceOptions.map((voice) => (
                                <option key={voice} value={voice}>{voice}</option>
                            ))}
                        </select>
                    </div>

                    <div className="flex flex-col gap-2">
                        <button
                            type="button"
                            onClick={handleSaveDraft}
                            disabled={saving}
                            className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm transition hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50"
                        >
                            {saving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                            {savedFlash ? t("filmSummary.draftSavedConfirmation", "Brouillon enregistre") : t("filmSummary.saveDraftButton", "Enregistrer le brouillon")}
                        </button>
                        <button
                            type="button"
                            onClick={handleRender}
                            disabled={rendering || !isValid}
                            className="flex items-center justify-center gap-2 rounded-xl bg-primary px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {rendering ? <Loader2 size={16} className="animate-spin" /> : null}
                            {t("filmSummary.generateVideoButton", "Generer la video")}
                        </button>
                        {!isValid ? (
                            <p className="text-xs text-amber-300">{t("filmSummary.renderBlockedHint", "La generation est desactivee tant que le plan n'est pas valide.")}</p>
                        ) : null}
                    </div>
                </aside>
            </div>
        </div>
    );
}
