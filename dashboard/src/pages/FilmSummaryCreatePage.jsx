import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowLeft, Check, Loader2, Pause, Play } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import { getApiUrl, fetchAppConfig } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useTranslation } from "../state/LanguageContext";
import MediaInput from "../components/MediaInput";
import FilmSummaryProcessingPanel from "../components/FilmSummaryProcessingPanel";
import { errorMessageForCode, normalizeFilmSummaryJobStatus as normalizeStatus } from "../lib/filmSummary";

const NARRATION_STYLE_KEYS = [
    {
        value: "cinematic", labelKey: "filmSummary.narrationStyleCinematic", fallback: "Cinematographique",
        descKey: "filmSummary.narrationStyleCinematicDesc",
        descFallback: "Ton immersif proche d'une bande-annonce, met l'accent sur l'emotion et le suspense.",
    },
    {
        value: "dramatic", labelKey: "filmSummary.narrationStyleDramatic", fallback: "Dramatique",
        descKey: "filmSummary.narrationStyleDramaticDesc",
        descFallback: "Rythme soutenu qui insiste sur les enjeux et les tensions entre les personnages.",
    },
    {
        value: "documentary", labelKey: "filmSummary.narrationStyleDocumentary", fallback: "Documentaire",
        descKey: "filmSummary.narrationStyleDocumentaryDesc",
        descFallback: "Ton neutre et informatif, a la maniere d'une voix off de reportage.",
    },
    {
        value: "energetic", labelKey: "filmSummary.narrationStyleEnergetic", fallback: "Energique",
        descKey: "filmSummary.narrationStyleEnergeticDesc",
        descFallback: "Rythme rapide et dynamique, adapte a un resume court et percutant.",
    },
];

// Same language set as CaptionsModal.jsx's FALLBACK_LANGUAGES, for a
// consistent dropdown across the app's language pickers.
const LANGUAGE_OPTIONS = [
    { value: "fr", labelKey: "filmSummary.languageFrench", fallback: "Francais" },
    { value: "en", labelKey: "filmSummary.languageEnglish", fallback: "Anglais" },
    { value: "es", labelKey: "filmSummary.languageSpanish", fallback: "Espagnol" },
    { value: "de", labelKey: "filmSummary.languageGerman", fallback: "Allemand" },
    { value: "it", labelKey: "filmSummary.languageItalian", fallback: "Italien" },
    { value: "pt", labelKey: "filmSummary.languagePortuguese", fallback: "Portugais" },
];

export default function FilmSummaryCreatePage() {
    const { user } = useAuth();
    const { credits } = useUserCredits();
    const { t } = useTranslation();
    const navigate = useNavigate();
    const location = useLocation();
    const projectIdFromUrl = useMemo(() => new URLSearchParams(location.search || "").get("project_id") || "", [location.search]);

    const [jobId, setJobId] = useState("");
    const [status, setStatus] = useState(projectIdFromUrl ? "processing" : "idle");
    const [currentStep, setCurrentStep] = useState("");
    const [error, setError] = useState("");
    const [projectJobLoading, setProjectJobLoading] = useState(false);
    const pollFailureCountRef = useRef(0);

    // Populated from GET /api/config -- drives the target-duration bounds
    // and the voice picker (see FILM_SUMMARY_* env-backed settings in
    // app.py). Sensible defaults are kept until the config resolves so the
    // form is usable immediately.
    const [minTargetMinutes, setMinTargetMinutes] = useState(3);
    const [maxTargetMinutes, setMaxTargetMinutes] = useState(20);
    const [allowedVoices, setAllowedVoices] = useState([]);
    const [defaultVoice, setDefaultVoice] = useState("cedar");

    const [title, setTitle] = useState("");
    const [targetDurationMinutes, setTargetDurationMinutes] = useState("");
    const [sourceLanguage, setSourceLanguage] = useState("");
    const [narrationLanguage, setNarrationLanguage] = useState("");
    const [narrationStyle, setNarrationStyle] = useState("cinematic");
    const [voiceId, setVoiceId] = useState("");

    // Voice preview playback (GET /api/film-summaries/voice-previews/{voice})
    // -- a short demo line synthesized once server-side and cached, so the
    // user can hear each narrator voice before picking one instead of
    // guessing from a bare id in a dropdown.
    const [playingVoiceId, setPlayingVoiceId] = useState("");
    const [loadingVoiceId, setLoadingVoiceId] = useState("");
    const [voicePreviewError, setVoicePreviewError] = useState("");
    const voicePreviewUrlsRef = useRef({});
    const voiceAudioRef = useRef(null);

    useEffect(() => {
        return () => {
            voiceAudioRef.current?.pause();
        };
    }, []);

    const handlePlayVoicePreview = async (voice) => {
        setVoicePreviewError("");
        if (playingVoiceId === voice) {
            voiceAudioRef.current?.pause();
            setPlayingVoiceId("");
            return;
        }
        try {
            let previewUrl = voicePreviewUrlsRef.current[voice];
            if (!previewUrl) {
                setLoadingVoiceId(voice);
                const response = await fetch(getApiUrl(`/api/film-summaries/voice-previews/${voice}`), {
                    headers: getAuthHeaders(user?.id),
                });
                if (!response.ok) throw new Error("preview_unavailable");
                const data = await response.json();
                previewUrl = getApiUrl(data.preview_url);
                voicePreviewUrlsRef.current[voice] = previewUrl;
            }
            if (!voiceAudioRef.current) voiceAudioRef.current = new Audio();
            const audio = voiceAudioRef.current;
            audio.src = previewUrl;
            audio.onended = () => setPlayingVoiceId("");
            await audio.play();
            setPlayingVoiceId(voice);
        } catch {
            setVoicePreviewError(t("filmSummary.voicePreviewError", "Apercu audio indisponible pour le moment."));
            setPlayingVoiceId("");
        } finally {
            setLoadingVoiceId("");
        }
    };

    const hasCredits = Number(credits || 0) > 0;

    useEffect(() => {
        let active = true;
        fetchAppConfig()
            .then((cfg) => {
                if (!active || !cfg) return;
                if (Number.isFinite(cfg.filmSummaryMinTargetDurationSeconds)) setMinTargetMinutes(Math.round(cfg.filmSummaryMinTargetDurationSeconds / 60));
                if (Number.isFinite(cfg.filmSummaryMaxTargetDurationSeconds)) setMaxTargetMinutes(Math.round(cfg.filmSummaryMaxTargetDurationSeconds / 60));
                if (Array.isArray(cfg.filmSummaryAllowedVoices)) setAllowedVoices(cfg.filmSummaryAllowedVoices);
                if (cfg.filmSummaryDefaultVoice) {
                    setDefaultVoice(cfg.filmSummaryDefaultVoice);
                    setVoiceId((prev) => prev || cfg.filmSummaryDefaultVoice);
                }
            })
            .catch(() => {});
        return () => {
            active = false;
        };
    }, []);

    // Resume an in-progress project opened back from the projects list --
    // same recovery flow as AnonymousStoryCreatePage, adapted to the
    // dedicated film-summaries collection: GET /api/projects/{id}/job (the
    // generic job-by-project lookup) only tells us a job is running, not
    // the film summary's own id/status, so we go straight to the
    // project-scoped film-summaries endpoint instead.
    useEffect(() => {
        if (!projectIdFromUrl || !user?.id) return undefined;
        let cancelled = false;
        const restoreProjectJob = async () => {
            setProjectJobLoading(true);
            try {
                const response = await fetch(getApiUrl(`/api/projects/${projectIdFromUrl}/film-summaries`), {
                    headers: getAuthHeaders(user.id),
                });
                const payload = await response.json().catch(() => ({}));
                if (cancelled) return;
                if (!response.ok) {
                    setStatus("error");
                    setError(payload?.detail || t("filmSummary.genericError", "Une erreur est survenue."));
                    return;
                }
                const found = Array.isArray(payload?.film_summaries) ? payload.film_summaries[0] : null;
                if (!found) {
                    setStatus("error");
                    setError(t("filmSummary.genericError", "Une erreur est survenue."));
                    return;
                }
                if (found.status === "queued" || found.status === "processing") {
                    setJobId(String(found.job_id || ""));
                    setCurrentStep(String(found.stage || ""));
                    setStatus("processing");
                    return;
                }
                // Any other status (awaiting_review, rendering, completed,
                // failed, rejected, cancelled) is best presented by the
                // detail page's own state machine.
                navigate(`/dashboard/film-summaries/projects/${projectIdFromUrl}`);
            } catch {
                if (!cancelled) {
                    setStatus("error");
                    setError(t("filmSummary.genericError", "Une erreur est survenue."));
                }
            } finally {
                if (!cancelled) setProjectJobLoading(false);
            }
        };
        restoreProjectJob();
        return () => {
            cancelled = true;
        };
    }, [projectIdFromUrl, user?.id, navigate, t]);

    useEffect(() => {
        if (!jobId) return undefined;
        let timerId = null;
        let cancelled = false;

        const poll = async () => {
            try {
                const response = await fetch(getApiUrl(`/api/status/${jobId}`), { headers: getAuthHeaders(user?.id) });
                if (!response.ok) {
                    pollFailureCountRef.current += 1;
                    if (pollFailureCountRef.current >= 3) {
                        setError(t("filmSummary.genericError", "Une erreur est survenue."));
                    }
                    return;
                }
                const data = await response.json();
                if (cancelled) return;
                pollFailureCountRef.current = 0;
                setStatus(normalizeStatus(data.status));
                setCurrentStep(String(data.current_step || ""));

                if (data.status === "failed") {
                    setError(errorMessageForCode(t, data?.error?.code, data?.error?.message || t("filmSummary.genericError", "Une erreur est survenue.")));
                }

                if (data.status === "completed" || data.status === "failed") {
                    // The film summary row (awaiting_review, rejected or
                    // failed) and its project both exist by this point --
                    // the detail page is the single source of truth for how
                    // to present whichever terminal state was reached.
                    const resultProjectId = data?.result?.project_id || projectIdFromUrl;
                    setTimeout(() => {
                        if (resultProjectId) {
                            navigate(`/dashboard/film-summaries/projects/${resultProjectId}`);
                        } else {
                            navigate("/dashboard/film-summaries");
                        }
                    }, 500);
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
    }, [jobId, user?.id, navigate, projectIdFromUrl, t]);

    const handleProcess = async (data) => {
        if (!user?.id) {
            setError("Authentication required. Please reconnect your session.");
            return;
        }
        if (!hasCredits) {
            const message = t("common.insufficientCreditsStart", "Credits insuffisants pour initier cette operation.");
            setError(message);
            globalThis.alert(message);
            return;
        }

        setError("");
        setStatus("processing");
        setCurrentStep("");
        try {
            const headers = getAuthHeaders(user.id);
            const targetDurationSeconds = targetDurationMinutes ? Math.round(Number(targetDurationMinutes) * 60) : undefined;
            let body;
            if (data.type === "url") {
                headers["Content-Type"] = "application/json";
                body = JSON.stringify({
                    url: data.payload,
                    acknowledged: !!data.acknowledged,
                    title,
                    target_duration_seconds: targetDurationSeconds,
                    source_language: sourceLanguage,
                    narration_language: narrationLanguage,
                    narration_style: narrationStyle,
                    voice_id: voiceId,
                });
            } else {
                body = new FormData();
                body.append("file", data.payload);
                body.append("acknowledged", data.acknowledged ? "true" : "false");
                if (title) body.append("title", title);
                if (targetDurationSeconds) body.append("target_duration_seconds", String(targetDurationSeconds));
                if (sourceLanguage) body.append("source_language", sourceLanguage);
                if (narrationLanguage) body.append("narration_language", narrationLanguage);
                if (narrationStyle) body.append("narration_style", narrationStyle);
                if (voiceId) body.append("voice_id", voiceId);
            }

            const response = await fetch(getApiUrl("/api/film-summaries"), {
                method: "POST",
                headers,
                body,
            });

            if (!response.ok) {
                const raw = await response.text();
                let detail = raw;
                try {
                    const parsed = JSON.parse(raw)?.detail;
                    detail = (parsed && typeof parsed === "object" ? parsed.message : parsed) || raw;
                } catch {
                    // Keep raw server detail.
                }
                setStatus("error");
                setError(detail || t("filmSummary.genericError", "Une erreur est survenue."));
                if (response.status === 402) {
                    globalThis.alert(detail || t("filmSummary.errorInsufficientCredits", "Credits insuffisants."));
                }
                return;
            }

            const payload = await response.json();
            setJobId(payload.job_id || "");
            setStatus("processing");
        } catch (err) {
            setStatus("error");
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        }
    };

    const isProcessing = normalizeStatus(status) === "processing";

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{t("filmSummary.createTitle", "Creer un resume de film")}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t("filmSummary.createSubtitle", "Importe un film complet ou colle un lien YouTube. Seuls les films narratifs sont pris en charge.")}</p>
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/film-summaries")}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                >
                    <ArrowLeft size={14} />
                    {t("filmSummary.backToList", "Retour aux resumes de film")}
                </button>
            </div>

            {!jobId && !projectIdFromUrl ? (
                <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                    {error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div>
                    ) : null}
                    <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-black/20 px-3 py-2 text-xs text-slate-500 dark:text-zinc-400">
                        {t("filmSummary.sourceNotice", "Seuls les films narratifs complets sont acceptes -- les courts extraits, publicites ou contenus non fictionnels seront rejetes apres analyse.")}
                    </div>
                    {!hasCredits ? (
                        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                            {t("common.insufficientCreditsStart", "Credits insuffisants pour initier cette operation.")}
                        </div>
                    ) : null}

                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                            <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                {t("filmSummary.titleLabel", "Titre")}
                            </label>
                            <input
                                type="text"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder={t("filmSummary.titlePlaceholder", "ex: Mon film (2024)")}
                                className="input-field w-full dark:text-white"
                            />
                            <p className="text-xs text-slate-500 dark:text-zinc-400">{t("filmSummary.titleHint", "Optionnel -- utilise pour nommer le projet genere.")}</p>
                        </div>

                        <div className="space-y-2">
                            <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                {t("filmSummary.targetDurationLabel", "Duree cible du resume")}
                            </label>
                            <input
                                type="number"
                                min={minTargetMinutes}
                                max={maxTargetMinutes}
                                value={targetDurationMinutes}
                                onChange={(e) => setTargetDurationMinutes(e.target.value)}
                                placeholder={t("filmSummary.targetDurationAuto", "Automatique (environ 1/6e de la duree source)")}
                                className="input-field w-full dark:text-white"
                            />
                            <p className="text-xs text-slate-500 dark:text-zinc-400">
                                {t("filmSummary.targetDurationHint", "Optionnel, en minutes. Laisse vide pour laisser le systeme la calculer a partir de la duree source ({{min}}-{{max}} min autorisees).", { min: minTargetMinutes, max: maxTargetMinutes })}
                            </p>
                        </div>

                        <div className="space-y-2">
                            <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                {t("filmSummary.sourceLanguageLabel", "Langue source")}
                            </label>
                            <select
                                value={sourceLanguage}
                                onChange={(e) => setSourceLanguage(e.target.value)}
                                className="input-field w-full dark:text-white"
                            >
                                <option value="">{t("filmSummary.sourceLanguageAuto", "Detection automatique")}</option>
                                {LANGUAGE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>{t(option.labelKey, option.fallback)}</option>
                                ))}
                            </select>
                            <p className="text-xs text-slate-500 dark:text-zinc-400">{t("filmSummary.sourceLanguageHint", "Optionnel -- detectee automatiquement depuis l'audio si laisse vide.")}</p>
                        </div>

                        <div className="space-y-2">
                            <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                                {t("filmSummary.narrationLanguageLabel", "Langue de la narration")}
                            </label>
                            <select
                                value={narrationLanguage}
                                onChange={(e) => setNarrationLanguage(e.target.value)}
                                className="input-field w-full dark:text-white"
                            >
                                <option value="">{t("filmSummary.narrationLanguageAuto", "Meme langue que la source")}</option>
                                {LANGUAGE_OPTIONS.map((option) => (
                                    <option key={option.value} value={option.value}>{t(option.labelKey, option.fallback)}</option>
                                ))}
                            </select>
                        </div>

                    </div>

                    <div className="space-y-2">
                        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("filmSummary.narrationStyleLabel", "Style de narration")}
                        </label>
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                            {NARRATION_STYLE_KEYS.map((option) => {
                                const isSelected = narrationStyle === option.value;
                                return (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => setNarrationStyle(option.value)}
                                        aria-pressed={isSelected}
                                        className={`relative rounded-xl border p-3 text-left transition ${
                                            isSelected
                                                ? "border-primary bg-primary/10"
                                                : "border-slate-300 dark:border-white/10 bg-black/10 hover:bg-white/5"
                                        }`}
                                    >
                                        {isSelected ? (
                                            <span className="absolute right-2 top-2 inline-flex h-4 w-4 items-center justify-center rounded-full bg-primary text-white">
                                                <Check size={10} />
                                            </span>
                                        ) : null}
                                        <p className="pr-5 text-sm font-semibold text-slate-900 dark:text-white">{t(option.labelKey, option.fallback)}</p>
                                        <p className="mt-1 text-xs leading-5 text-slate-500 dark:text-zinc-400">{t(option.descKey, option.descFallback)}</p>
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div className="space-y-2">
                        <label className="block text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                            {t("filmSummary.voiceLabel", "Voix du narrateur")}
                        </label>
                        {voicePreviewError ? (
                            <p className="text-xs text-amber-500 dark:text-amber-400">{voicePreviewError}</p>
                        ) : null}
                        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                            {(allowedVoices.length ? allowedVoices : [defaultVoice]).map((voice) => {
                                const isSelected = (voiceId || defaultVoice) === voice;
                                const isPlaying = playingVoiceId === voice;
                                const isLoading = loadingVoiceId === voice;
                                return (
                                    <div
                                        key={voice}
                                        role="button"
                                        tabIndex={0}
                                        onClick={() => setVoiceId(voice)}
                                        onKeyDown={(e) => {
                                            if (e.key === "Enter" || e.key === " ") setVoiceId(voice);
                                        }}
                                        aria-pressed={isSelected}
                                        className={`relative flex items-center justify-between gap-2 rounded-xl border p-3 text-left transition cursor-pointer ${
                                            isSelected
                                                ? "border-primary bg-primary/10"
                                                : "border-slate-300 dark:border-white/10 bg-black/10 hover:bg-white/5"
                                        }`}
                                    >
                                        <span className="flex items-center gap-2 text-sm font-semibold capitalize text-slate-900 dark:text-white">
                                            {isSelected ? (
                                                <span className="inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary text-white">
                                                    <Check size={10} />
                                                </span>
                                            ) : null}
                                            {voice}
                                        </span>
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handlePlayVoicePreview(voice);
                                            }}
                                            disabled={isLoading}
                                            title={t("filmSummary.voiceListenLabel", "Ecouter un extrait")}
                                            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-300 dark:border-white/10 bg-white/5 text-slate-700 dark:text-zinc-200 hover:bg-white/10 disabled:opacity-50"
                                        >
                                            {isLoading ? (
                                                <Loader2 size={14} className="animate-spin" />
                                            ) : isPlaying ? (
                                                <Pause size={14} />
                                            ) : (
                                                <Play size={14} />
                                            )}
                                        </button>
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <MediaInput
                        onProcess={handleProcess}
                        isProcessing={isProcessing}
                        isCreditBlocked={!hasCredits}
                        disableActions={!hasCredits}
                        creditWarning={!hasCredits ? t("common.insufficientCreditsStart", "Credits insuffisants pour initier cette operation.") : ""}
                        submitLabel={t("filmSummary.generateCta", "Analyser le film")}
                        processingLabel={t("mediaInput.processing", "Processing Video...")}
                    />
                </section>
            ) : (
                <div className="space-y-4">
                    {error ? (
                        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div>
                    ) : null}

                    <FilmSummaryProcessingPanel
                        status={normalizeStatus(status)}
                        stage={currentStep}
                        phase="analysis"
                        title={t("filmSummary.processingTitle", "Analyse de ton film")}
                        isLoadingStatus={projectJobLoading}
                    />
                </div>
            )}
        </div>
    );
}
