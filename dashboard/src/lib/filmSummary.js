// Shared helpers for the "Resume de film" (Film Summary) feature pages.
// Mostly pure UI logic (mirrors the anonymousStories.js module's
// conventions) plus, further down, a small set of fetch() wrappers for the
// manual-editor endpoints (audio/subtitle settings, manual clip selection,
// narration generation) -- see FilmSummaryStatus / FilmSummaryStage /
// FilmSummaryErrorCode in film_summary.py for the backend side of this
// contract.

import { resolveJobStepState, errorMessageForCodeWithNamespace } from "./jobStepStatus";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "./apiAuth";

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

// edit_mode values (film_summary row field) -- "manual" is set server-side
// by PUT .../manual-selection the moment a selection is saved, so the
// frontend never writes it directly.
export const EDIT_MODE_AUTOMATIC = "automatic";
export const EDIT_MODE_MANUAL = "manual";

/**
 * Shared response reader for the manual-editor endpoints below: parses the
 * JSON body (tolerating an empty/invalid one) and, on a non-2xx response,
 * throws an Error carrying the backend's `detail` when present -- same
 * shape every film-summary page already builds inline around its own
 * fetch() calls, just not duplicated four more times here.
 */
async function readJsonOrThrow(response, fallbackMessage) {
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(typeof data?.detail === "string" ? data.detail : fallbackMessage);
    }
    return data;
}

/**
 * PATCH /api/film-summaries/{id}/audio-settings -- `patch` is any subset of
 * {dialogue_volume, subtitles_enabled, subtitle_style}; callers send only
 * the fields they changed. `dialogue_volume` (when sent) is an integer
 * 0-100 (default 20) controlling how audible the film's own original audio
 * stays under the AI-generated narration -- 0 mutes it entirely, 100 keeps
 * it at full volume. Returns the normalized full-content film summary row.
 */
export async function updateFilmSummaryAudioSettings(filmSummaryId, userId, patch) {
    const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummaryId}/audio-settings`), {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...getAuthHeaders(userId) },
        body: JSON.stringify(patch || {}),
    });
    return readJsonOrThrow(response, "Impossible d'enregistrer les reglages audio/sous-titres.");
}

/**
 * PUT /api/film-summaries/{id}/manual-selection -- `manualSelection` is the
 * chronologically-ordered list of {scene_id, start_ms, end_ms} the user
 * kept from the shot picker. Sets edit_mode to "manual" server-side.
 * Returns the normalized full-content film summary row.
 */
export async function saveFilmSummaryManualSelection(filmSummaryId, userId, manualSelection) {
    const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummaryId}/manual-selection`), {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...getAuthHeaders(userId) },
        body: JSON.stringify({ manual_selection: manualSelection || [] }),
    });
    return readJsonOrThrow(response, "Impossible d'enregistrer la selection des plans.");
}

/**
 * POST /api/film-summaries/{id}/generate-narration -- no body; the server
 * reads the already-persisted manual_selection and has the AI write
 * narration grouped over those exact clips. Call this right after a
 * successful saveFilmSummaryManualSelection(). Returns the normalized
 * full-content row with `edit_plan` populated.
 */
export async function generateFilmSummaryNarration(filmSummaryId, userId) {
    const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummaryId}/generate-narration`), {
        method: "POST",
        headers: getAuthHeaders(userId),
    });
    return readJsonOrThrow(response, "Impossible de generer la narration a partir des plans choisis.");
}

/**
 * POST /api/film-summaries/{id}/translate-narration -- body
 * {narration_language}. Has the AI retranslate the already-generated
 * narration into the given language (e.g. when the wrong one was picked at
 * creation time). Returns the normalized full-content film summary row with
 * `edit_plan` updated.
 */
export async function translateFilmSummaryNarration(filmSummaryId, userId, narrationLanguage) {
    const response = await fetch(getApiUrl(`/api/film-summaries/${filmSummaryId}/translate-narration`), {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders(userId) },
        body: JSON.stringify({ narration_language: narrationLanguage }),
    });
    return readJsonOrThrow(response, "Impossible de retraduire la narration.");
}

// Same language set as CaptionsModal.jsx's FALLBACK_LANGUAGES, for a
// consistent dropdown across the app's language pickers. Shared here (moved
// out of FilmSummaryCreatePage.jsx) since the review panel's narration
// retranslation picker needs the exact same options.
export const NARRATION_LANGUAGE_OPTIONS = [
    { value: "fr", labelKey: "filmSummary.languageFrench", fallback: "Francais" },
    { value: "en", labelKey: "filmSummary.languageEnglish", fallback: "Anglais" },
    { value: "es", labelKey: "filmSummary.languageSpanish", fallback: "Espagnol" },
    { value: "de", labelKey: "filmSummary.languageGerman", fallback: "Allemand" },
    { value: "it", labelKey: "filmSummary.languageItalian", fallback: "Italien" },
    { value: "pt", labelKey: "filmSummary.languagePortuguese", fallback: "Portugais" },
];

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
// _run_film_summary_render_pipeline_stages reports them (10-40/45/90/95%).
// "adding_subtitles" is only ever reported when subtitles_enabled is set on
// the row -- otherwise the pipeline jumps straight from rendering_final to
// completed, and resolveJobStepState's "complete -> every step done" rule
// still marks it done retroactively, same as any other step a given plan
// happens to skip (e.g. generating_voice with zero voice_over segments).
const RENDER_STAGE_ORDER = ["generating_voice", "rendering_preview", "rendering_final", "adding_subtitles"];

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
    { key: "adding_subtitles", labelFallback: "Ajout des sous-titres", descFallback: "Incrustation des sous-titres choisis dans la video finale." },
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

// ---------------------------------------------------------------------------
// Per-segment clip-replacement suggestions (FilmSummaryClipSwapPicker): the
// main review editor now lets the creator replace a single narrative
// block's clips from ranked suggestions instead of rebuilding the whole cut
// from a flat scene browser. Pure, client-side, no new backend call --
// scene_index already carries everything used here (see film_summary.py's
// build_scene_index: scene_id/start_ms/end_ms/duration_ms/speakers/
// transcript_overlap/quality_flags).
// ---------------------------------------------------------------------------

function clipSignature(clip) {
    return `${clip?.scene_id}|${clip?.start_ms}|${clip?.end_ms}`;
}

/**
 * Every exact (scene_id, start_ms, end_ms) clip signature used by any
 * voice_over segment of `segments` other than `excludeSegmentId` -- mirrors
 * film_summary.py's _voice_over_clip_signature. Used only to flag a
 * suggestion as "already used elsewhere" in the picker UI (a soft warning,
 * never a block -- unlike the automatic planner, a deliberate user edit
 * here is never silently overridden).
 */
export function usedClipSignaturesExcluding(segments, excludeSegmentId) {
    const signatures = new Set();
    (segments || []).forEach((seg) => {
        if (seg.id === excludeSegmentId) return;
        (seg.clips || []).forEach((clip) => signatures.add(clipSignature(clip)));
    });
    return signatures;
}

const STOPWORDS = new Set([
    "le", "la", "les", "un", "une", "des", "de", "du", "et", "est", "il", "elle", "que", "qui", "dans", "sur",
    "pour", "avec", "au", "aux", "ce", "ces", "son", "sa", "ses", "the", "a", "an", "of", "in", "on", "and",
    "is", "to", "it", "that", "was", "were", "not", "you", "this",
]);

function tokenize(text) {
    return (text || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[̀-ͯ]/g, "")
        .match(/[a-z0-9]+/g) || [];
}

function significantWords(text) {
    return new Set(tokenize(text).filter((word) => word.length > 2 && !STOPWORDS.has(word)));
}

/**
 * Cheap lexical-overlap relevance score (0-1, higher is more relevant)
 * between a segment's narration and a candidate scene's transcribed
 * dialogue -- the fraction of the smaller word set's significant words
 * that also appear in the other text. No AI call; only ever used to rank
 * suggestions, never to validate the plan.
 */
export function narrationSceneOverlapScore(narration, transcriptOverlap) {
    const narrationWords = significantWords(narration);
    const sceneWords = significantWords(transcriptOverlap);
    if (!narrationWords.size || !sceneWords.size) return 0;
    let shared = 0;
    narrationWords.forEach((word) => {
        if (sceneWords.has(word)) shared += 1;
    });
    return shared / Math.min(narrationWords.size, sceneWords.size);
}

/**
 * Ranks every scene_index entry as a clip-replacement suggestion for
 * `segment`, highest relevance first, excluding scenes already used by
 * that same segment. Rewards narration/dialogue word overlap and
 * continuity with speakers already present in the segment's current
 * clips, favors temporal proximity to those clips (nearby footage tends to
 * match the same narrated beat), and penalizes a scene flagged by scene
 * detection (quality_flags, e.g. blurred/black/transition frames -- same
 * signal VISUAL MATCHING RULE 4 asks the planner to avoid) or already used
 * by another segment of the plan (surfaced via `alreadyUsedElsewhere`, not
 * excluded -- the creator decides, this is their deliberate edit).
 */
export function rankSceneSuggestionsForSegment({ segment, sceneIndex, allSegments }) {
    const clips = segment?.clips || [];
    const currentSceneIds = new Set(clips.map((clip) => clip.scene_id));
    const sceneById = new Map((sceneIndex || []).map((scene) => [scene.scene_id, scene]));
    const currentSpeakers = new Set();
    clips.forEach((clip) => {
        (sceneById.get(clip.scene_id)?.speakers || []).forEach((speaker) => currentSpeakers.add(speaker));
    });
    const referenceMs = clips.length ? clips[0].start_ms : null;
    const usedElsewhere = usedClipSignaturesExcluding(allSegments, segment?.id);

    return (sceneIndex || [])
        .filter((scene) => !currentSceneIds.has(scene.scene_id))
        .map((scene) => {
            const overlapScore = narrationSceneOverlapScore(segment?.narration, scene.transcript_overlap);
            const sharedSpeakerCount = (scene.speakers || []).filter((speaker) => currentSpeakers.has(speaker)).length;
            let score = overlapScore * 3 + sharedSpeakerCount * 1.5;
            if (referenceMs != null) {
                const distanceMs = Math.abs((scene.start_ms ?? 0) - referenceMs);
                score += Math.max(0, 2 - distanceMs / 60000);
            }
            score -= (scene.quality_flags?.length || 0) * 1.5;
            const alreadyUsedElsewhere = usedElsewhere.has(clipSignature(scene));
            if (alreadyUsedElsewhere) score -= 5;
            return { ...scene, score, overlapScore, sharedSpeakerCount, alreadyUsedElsewhere };
        })
        .sort((a, b) => b.score - a.score);
}
