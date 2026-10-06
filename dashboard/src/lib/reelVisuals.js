/**
 * Shared validation/overlap logic for manual reel visuals (split-screen
 * image overlays), used by both the VisualsModal timeline UI and its
 * add/edit forms so the user gets instant feedback before ever calling
 * the backend -- which enforces the exact same rules server-side (see
 * app.py's _validate_reel_visual_timing). Error codes below intentionally
 * match the backend's own `detail.code` values so a single i18n lookup
 * (`visualsModal.errors.<code>`) covers both client- and server-raised
 * errors.
 */

export const ALLOWED_VISUAL_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

// Generous client-side guard only -- the backend's own configured limit
// (REEL_VISUAL_MAX_IMAGE_BYTES, 8MB by default) is authoritative and may
// differ; its own error still surfaces to the user if this guard is ever
// looser than what the backend actually accepts.
export const MAX_VISUAL_IMAGE_BYTES = 8 * 1024 * 1024;

/**
 * @param {{start_time: number, duration: number}} a
 * @param {{start_time: number, duration: number}} b
 * @returns {boolean}
 */
export function visualsOverlap(a, b) {
    const aStart = Number(a?.start_time) || 0;
    const aEnd = aStart + (Number(a?.duration) || 0);
    const bStart = Number(b?.start_time) || 0;
    const bEnd = bStart + (Number(b?.duration) || 0);
    return aStart < bEnd && bStart < aEnd;
}

/**
 * @param {{start_time: number, duration: number}} candidate
 * @param {Array<{id?: string, start_time: number, duration: number}>} existingVisuals
 * @param {string} [excludeId] - the visual being edited, skipped from the check
 * @returns {object|null} the first overlapping visual, or null
 */
export function findOverlappingVisual(candidate, existingVisuals, excludeId = null) {
    if (!Array.isArray(existingVisuals)) return null;
    return existingVisuals.find((visual) => {
        if (!visual) return false;
        if (excludeId && String(visual.id) === String(excludeId)) return false;
        return visualsOverlap(candidate, visual);
    }) || null;
}

/**
 * @param {{start_time: number, duration: number}} candidate
 * @param {number} reelDurationSeconds
 * @param {Array<{id?: string, start_time: number, duration: number}>} existingVisuals
 * @param {string} [excludeId]
 * @returns {{valid: boolean, error?: string}}
 */
export function validateVisualTiming(candidate, reelDurationSeconds, existingVisuals, excludeId = null) {
    const startTime = Number(candidate?.start_time);
    const duration = Number(candidate?.duration);
    const reelDuration = Number(reelDurationSeconds);

    if (!Number.isFinite(startTime) || startTime < 0) {
        return { valid: false, error: 'invalid_visual_timing' };
    }
    if (!Number.isFinite(duration) || duration <= 0) {
        return { valid: false, error: 'invalid_visual_timing' };
    }
    if (Number.isFinite(reelDuration) && reelDuration > 0 && startTime + duration > reelDuration + 0.01) {
        return { valid: false, error: 'visual_exceeds_reel_duration' };
    }
    if (findOverlappingVisual({ start_time: startTime, duration }, existingVisuals, excludeId)) {
        return { valid: false, error: 'visual_overlap' };
    }
    return { valid: true };
}

/**
 * Client-side guard for the image picked for a new visual -- JPG/JPEG/PNG/
 * WebP only, under MAX_VISUAL_IMAGE_BYTES. Accepts anything File-shaped
 * ({type, size}), so it's testable without a real DOM File.
 *
 * @param {{type?: string, size?: number}} file
 * @returns {{valid: boolean, error?: string}}
 */
export function validateVisualImageFile(file) {
    if (!file) return { valid: false, error: 'missing_file' };
    const type = String(file.type || '').toLowerCase();
    if (!ALLOWED_VISUAL_IMAGE_TYPES.includes(type)) {
        return { valid: false, error: 'invalid_image_format' };
    }
    if (Number(file.size) > MAX_VISUAL_IMAGE_BYTES) {
        return { valid: false, error: 'image_too_large' };
    }
    return { valid: true };
}
