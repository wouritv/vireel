import { getApiUrl } from '../config';
import { getAuthHeaders } from './apiAuth';

export const ALLOWED_VISUAL_IMAGE_TYPES = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];

// Generous client-side guard only -- backend validation stays authoritative.
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
 * @param {string} [excludeId]
 * @returns {object|null}
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

export class ReelVisualsApiError extends Error {
    constructor(message, status, detail = null) {
        super(message || 'Request failed');
        this.name = 'ReelVisualsApiError';
        this.status = Number(status) || 0;
        this.detail = detail;
    }
}

const parseApiErrorDetail = async (response) => {
    const raw = await response.text();
    try {
        const parsed = JSON.parse(raw || '{}');
        return parsed?.detail || raw || 'Request failed';
    } catch {
        return raw || 'Request failed';
    }
};

const requestJson = async (path, { method = 'GET', userId, body, headers = {} } = {}) => {
    const response = await fetch(getApiUrl(path), {
        method,
        headers: {
            ...getAuthHeaders(userId),
            ...headers,
        },
        body,
    });

    if (!response.ok) {
        const detail = await parseApiErrorDetail(response);
        const message = typeof detail === 'string' ? detail : (detail?.message || JSON.stringify(detail));
        throw new ReelVisualsApiError(message, response.status, detail);
    }

    return response.json().catch(() => ({}));
};

export async function listReelVisuals(jobId, clipIndex, userId) {
    return requestJson(`/api/reels/${jobId}/${clipIndex}/visuals`, { userId });
}

export async function applyReelVisuals(jobId, clipIndex, userId, payload = {}) {
    return requestJson(`/api/reels/${jobId}/${clipIndex}/visuals/apply`, {
        method: 'POST',
        userId,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload || {}),
    });
}

export async function resetReelVisuals(jobId, clipIndex, userId) {
    return requestJson(`/api/reels/${jobId}/${clipIndex}/visuals/reset`, {
        method: 'POST',
        userId,
        headers: { 'Content-Type': 'application/json' },
    });
}
