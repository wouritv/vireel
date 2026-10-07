// Pure helper that turns the `media_status` / `media_expires_at` fields now
// returned on each item of GET /api/reels, /api/captions,
// /api/anonymous-stories and /api/film-summaries into a renderable
// description, without depending on `t()` itself -- the caller translates
// using the returned `translationKey`/`params`, the same split used by
// `daysUntilDate` (see ../lib/formatting.js) feeding callers that do their
// own translated rendering.
//
// `media_status` is one of "AVAILABLE", "EXPIRED", "DELETED", "MISSING", or
// null (no retention info available, e.g. historical content from before
// this feature -- treated exactly like "unknown": render nothing).
//
// Deliberately separate from ../lib/status.js's statusClass/statusLabel,
// which describe job-lifecycle status (queued/processing/completed/failed),
// a different concept from this physical media-availability status.

import { daysUntilDate } from "./formatting";

const UNKNOWN = { variant: "unknown", translationKey: null, params: {}, disabled: false };

const GONE_STATUSES = new Set(["EXPIRED", "DELETED", "MISSING"]);

/**
 * Describe whether a reel/caption/story/film-summary's underlying media
 * file is still available for download.
 * @param {"AVAILABLE"|"EXPIRED"|"DELETED"|"MISSING"|null|undefined} mediaStatus
 * @param {string|null|undefined} mediaExpiresAt ISO 8601 date string
 * @returns {{ variant: string, translationKey: string|null, params: object, disabled: boolean }}
 */
export function describeMediaAvailability(mediaStatus, mediaExpiresAt) {
    if (mediaStatus == null) return UNKNOWN;

    if (mediaStatus === "AVAILABLE") {
        if (!mediaExpiresAt) return UNKNOWN;

        const days = daysUntilDate(mediaExpiresAt);
        if (days === null) return UNKNOWN;

        if (days <= 3) {
            return { variant: "expiringSoon", translationKey: "media.expiresInDays", params: { days }, disabled: false };
        }

        const date = new Date(mediaExpiresAt).toLocaleDateString("fr-FR", { day: "numeric", month: "long" });
        return { variant: "available", translationKey: "media.availableUntil", params: { date }, disabled: false };
    }

    if (GONE_STATUSES.has(mediaStatus)) {
        return { variant: "expired", translationKey: "media.expired", params: {}, disabled: true };
    }

    return UNKNOWN;
}
