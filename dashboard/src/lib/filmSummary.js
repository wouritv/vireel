// Shared helpers for the "Resume de film" (Film Summary) feature pages.
// Pure UI logic only -- no HTTP calls -- mirrors the anonymousStories.js
// module's conventions exactly (see FilmSummaryStatus / FilmSummaryStage /
// FilmSummaryErrorCode in film_summary.py for the backend side of this
// contract).

/**
 * Normalize a raw /api/status/{job_id} job status to the frontend canonical
 * form used across every feature's progress UI.
 * "completed" -> "complete"  |  "failed" -> "error"  |  else -> "processing"
 */
export function normalizeFilmSummaryJobStatus(status) {
    if (status === "completed") return "complete";
    if (status === "failed") return "error";
    if (status === "queued" || status === "created" || status === "retry_wait") return "processing";
    return status || "idle";
}

/**
 * Map a backend error_code (e.g. "NOT_A_FILM") to its i18n key
 * ("filmSummary.errorNotAFilm"). Falls back to `fallback` when no code is
 * given -- the caller's `t()` call handles a missing translation.
 */
export function errorMessageForCode(t, code, fallback) {
    if (!code) return fallback;
    const camel = String(code).toLowerCase().replace(/_([a-z0-9])/g, (_match, c) => c.toUpperCase());
    const key = `filmSummary.error${camel.charAt(0).toUpperCase()}${camel.slice(1)}`;
    return t(key, fallback);
}

// Mirrors app.py's _FILM_SUMMARY_REJECTION_CODES: these error codes mean the
// *source video itself* was rejected (wrong format, too short/long, not a
// narrative film, ...), so the row lands in `status: "rejected"` (terminal,
// no retry -- only a brand new submission can move forward) instead of
// `status: "failed"` (terminal but retryable via POST .../retry). Exposed so
// a UI that only has a raw error_code in hand (e.g. while the analysis job
// is still being polled, before the film summary row itself is re-fetched)
// can already tell the two apart.
export const FILM_SUMMARY_REJECTION_ERROR_CODES = [
    "SOURCE_TOO_LARGE",
    "SOURCE_TOO_LONG",
    "SOURCE_TOO_SHORT",
    "NO_VIDEO_TRACK",
    "NO_AUDIO_TRACK",
    "INVALID_FORMAT",
    "NOT_A_FILM",
];

export function isFilmSummaryRejectionErrorCode(code) {
    return FILM_SUMMARY_REJECTION_ERROR_CODES.includes(String(code || ""));
}

// Segment types (film_summary.SEGMENT_TYPES).
export const SEGMENT_TYPE_VOICE_OVER = "voice_over";
export const SEGMENT_TYPE_ORIGINAL_DIALOGUE = "original_dialogue";
export const SEGMENT_TYPE_BREATHING = "breathing";

/**
 * Format a millisecond duration as "mm:ss" (or "h:mm:ss" past an hour), for
 * segment/clip timestamps in the review timeline.
 */
export function formatMsClock(ms) {
    const totalSeconds = Math.max(0, Math.round(Number(ms || 0) / 1000));
    const h = Math.floor(totalSeconds / 3600);
    const m = Math.floor((totalSeconds % 3600) / 60);
    const s = totalSeconds % 60;
    if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    return `${m}:${String(s).padStart(2, "0")}`;
}

// Analysis-phase pipeline stages, in the order app.py's
// _run_film_summary_analysis_pipeline_stages reports them via
// reel_job_manager.update_progress (20/40/50/70/90%). "uploading" has no
// stage of its own here -- like anonymous stories' "upload" step, the
// source is already fully received/downloaded by the time a job_id exists
// at all (it happens synchronously in the POST handler), so it's always
// shown done once we're polling a job.
const ANALYSIS_STAGE_ORDER = ["transcribing", "detecting_scenes", "validating_film", "planning", "validating_plan"];

// Render-phase pipeline stages, in the order
// _run_film_summary_render_pipeline_stages reports them (10-40/45/90%).
const RENDER_STAGE_ORDER = ["generating_voice", "rendering_preview", "rendering_final"];

/**
 * State of a single step given the job's overall status, which stage index
 * is currently reported (-1 when none has been reported yet), and this
 * step's own index. Same shape as anonymousStories.js's
 * resolveStoryStepState, kept as its own function for the same reason: a
 * nested closure with this branching counts every branch twice.
 */
function resolveFilmSummaryStepState(status, stageIndex, index) {
    if (status === "complete") return "done";
    if (index < stageIndex) return "done";

    const isCurrentStep = index === stageIndex || (stageIndex === -1 && index === 0);
    if (!isCurrentStep) return "pending";
    return status === "error" ? "error" : "active";
}

function buildAnalysisProcessSteps(status, stage, t) {
    const stageIndex = ANALYSIS_STAGE_ORDER.indexOf(stage);
    const stateFor = (index) => resolveFilmSummaryStepState(status, stageIndex, index);

    return [
        {
            key: "uploading",
            label: t("filmSummary.stepUploading", "Reception de la source"),
            description: t("filmSummary.stepUploadingDesc", "Le film source est pret pour l'analyse."),
            state: "done",
        },
        {
            key: "transcribing",
            label: t("filmSummary.stepTranscribing", "Transcription de l'audio"),
            description: t("filmSummary.stepTranscribingDesc", "Extraction du texte parle avec horodatage."),
            state: stateFor(0),
        },
        {
            key: "detecting_scenes",
            label: t("filmSummary.stepDetectingScenes", "Detection des scenes"),
            description: t("filmSummary.stepDetectingScenesDesc", "Decoupage du film en scenes exploitables."),
            state: stateFor(1),
        },
        {
            key: "validating_film",
            label: t("filmSummary.stepValidatingFilm", "Verification du contenu"),
            description: t("filmSummary.stepValidatingFilmDesc", "Confirmation qu'il s'agit bien d'un film narratif."),
            state: stateFor(2),
        },
        {
            key: "planning",
            label: t("filmSummary.stepPlanning", "Construction du plan de montage"),
            description: t("filmSummary.stepPlanningDesc", "Redaction de la narration et selection des extraits."),
            state: stateFor(3),
        },
        {
            key: "validating_plan",
            label: t("filmSummary.stepValidatingPlan", "Validation du plan"),
            description: t("filmSummary.stepValidatingPlanDesc", "Verification de la duree et de la coherence du montage."),
            state: stateFor(4),
        },
    ];
}

function buildRenderProcessSteps(status, stage, t) {
    const stageIndex = RENDER_STAGE_ORDER.indexOf(stage);
    const stateFor = (index) => resolveFilmSummaryStepState(status, stageIndex, index);

    return [
        {
            key: "generating_voice",
            label: t("filmSummary.stepGeneratingVoice", "Generation de la voix off"),
            description: t("filmSummary.stepGeneratingVoiceDesc", "Synthese vocale de chaque segment narre."),
            state: stateFor(0),
        },
        {
            key: "rendering_preview",
            label: t("filmSummary.stepRenderingPreview", "Assemblage de l'apercu"),
            description: t("filmSummary.stepRenderingPreviewDesc", "Montage des extraits et de la narration."),
            state: stateFor(1),
        },
        {
            key: "rendering_final",
            label: t("filmSummary.stepRenderingFinal", "Finalisation de la video"),
            description: t("filmSummary.stepRenderingFinalDesc", "Encodage et enregistrement du resultat final."),
            state: stateFor(2),
        },
    ];
}

/**
 * Build the step list for the "Suivi du processus" progress card, in the
 * same shape/visual role as anonymousStories.js's
 * buildAnonymousStoryProcessSteps. `phase` picks which pipeline is being
 * followed -- "analysis" (upload -> awaiting_review) or "render"
 * (generating_voice -> completed) -- since a film summary goes through the
 * pipeline twice (once per phase, each with its own job_id). When omitted,
 * it's inferred from `stage` as a convenience, defaulting to "analysis".
 */
export function buildFilmSummaryProcessSteps({ status, stage, t, phase }) {
    const resolvedPhase = phase || (RENDER_STAGE_ORDER.includes(stage) ? "render" : "analysis");
    return resolvedPhase === "render"
        ? buildRenderProcessSteps(status, stage, t)
        : buildAnalysisProcessSteps(status, stage, t);
}
