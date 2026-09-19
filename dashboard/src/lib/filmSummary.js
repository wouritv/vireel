// Shared helpers for the "Resume de film" (Film Summary) feature pages.
// Pure UI logic only -- no HTTP calls -- mirrors the anonymousStories.js
// module's conventions exactly (see FilmSummaryStatus / FilmSummaryStage /
// FilmSummaryErrorCode in film_summary.py for the backend side of this
// contract).

import { resolveJobStepState, errorMessageForCodeWithNamespace } from "./jobStepStatus";

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
    return errorMessageForCodeWithNamespace(t, "filmSummary", code, fallback);
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

// Step data for both phases -- a plain list instead of two near-identical
// functions, so there's one small builder (buildProcessSteps below) instead
// of duplicated per-phase logic. "uploading" carries a fixedState since the
// source is already fully received/downloaded by the time a job_id exists
// at all (it happens synchronously in the POST handler), so it's always
// shown done once we're polling a job; every other step's state is derived
// from where `stage` falls in its phase's order.
const ANALYSIS_STEPS = [
    { key: "uploading", labelFallback: "Reception de la source", descFallback: "Le film source est pret pour l'analyse.", fixedState: "done" },
    { key: "transcribing", labelFallback: "Transcription de l'audio", descFallback: "Extraction du texte parle avec horodatage." },
    { key: "detecting_scenes", labelFallback: "Detection des scenes", descFallback: "Decoupage du film en scenes exploitables." },
    { key: "validating_film", labelFallback: "Verification du contenu", descFallback: "Confirmation qu'il s'agit bien d'un film narratif." },
    { key: "planning", labelFallback: "Construction du plan de montage", descFallback: "Redaction de la narration et selection des extraits." },
    { key: "validating_plan", labelFallback: "Validation du plan", descFallback: "Verification de la duree et de la coherence du montage." },
];

const RENDER_STEPS = [
    { key: "generating_voice", labelFallback: "Generation de la voix off", descFallback: "Synthese vocale de chaque segment narre." },
    { key: "rendering_preview", labelFallback: "Assemblage de l'apercu", descFallback: "Montage des extraits et de la narration." },
    { key: "rendering_final", labelFallback: "Finalisation de la video", descFallback: "Encodage et enregistrement du resultat final." },
];

// "detecting_scenes" -> "DetectingScenes", matching the stepXxx/stepXxxDesc
// key naming already used in locales/{en,fr}/common.json.
function toStepI18nSuffix(snakeKey) {
    return snakeKey.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join("");
}

function buildProcessSteps(steps, stageOrder, status, stage, t) {
    const stageIndex = stageOrder.indexOf(stage);
    return steps.map((step) => {
        const suffix = toStepI18nSuffix(step.key);
        return {
            key: step.key,
            label: t(`filmSummary.step${suffix}`, step.labelFallback),
            description: t(`filmSummary.step${suffix}Desc`, step.descFallback),
            state: step.fixedState || resolveJobStepState(status, stageIndex, stageOrder.indexOf(step.key)),
        };
    });
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
        ? buildProcessSteps(RENDER_STEPS, RENDER_STAGE_ORDER, status, stage, t)
        : buildProcessSteps(ANALYSIS_STEPS, ANALYSIS_STAGE_ORDER, status, stage, t);
}
