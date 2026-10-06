// Shared helper for the six publish/share endpoints that can hit the daily
// publication quota (POST /api/social/post, /api/social/posts,
// /api/anonymous-stories/{id}/publish, /api/captions/{id}/share,
// /api/film-summaries/{id}/share, /api/reels/{id}/share). Past the quota
// those endpoints behave exactly as before: on error they still raise a
// plain STRING `detail` for everything else they can fail with (e.g. 402
// "no active subscription or valid credit"). Once the quota is hit they
// instead raise an OBJECT `detail`:
//   { code: "publish_quota_exceeded", message, max_daily, used_today, resets_at }
// `resets_at` is always the next UTC midnight (ISO 8601, with an offset).
//
// Every call site used to assume `detail` was a string and either
// template-interpolated it directly (producing the literal text
// "[object Object]") or fed it into a code -> i18n-key mapper that expects
// a short string code. This module centralizes the one place that knows
// how to turn either shape into a string safe to render as-is.

const PUBLISH_QUOTA_EXCEEDED_CODE = "publish_quota_exceeded";

// Matches the hardcoded 'fr-FR' locale used throughout Settings.jsx for
// every other date/time rendered in the dashboard.
const RESET_TIME_LOCALE = "fr-FR";

function formatResetTime(resetsAt) {
    const date = new Date(resetsAt);
    if (Number.isNaN(date.getTime())) return "";
    return date.toLocaleTimeString(RESET_TIME_LOCALE, { hour: "2-digit", minute: "2-digit" });
}

/**
 * Turn a publish/share endpoint's error `detail` into a string safe for a
 * caller to render directly:
 *  - a publish_quota_exceeded object becomes a friendly, translated
 *    message naming the daily cap and the local clock time it resets at;
 *  - a plain (non-empty) string `detail` is returned unchanged, preserving
 *    every existing error message from these same endpoints;
 *  - anything else (null, undefined, empty string, or some other object
 *    shape) falls back to `fallback`, defaulting to a generic message --
 *    never an object for the caller to interpolate into a template string.
 */
export function describePublishError(t, detail, fallback) {
    if (typeof detail === "string" && detail) {
        return detail;
    }

    if (detail && typeof detail === "object" && detail.code === PUBLISH_QUOTA_EXCEEDED_CODE) {
        return t(
            "publishQuota.exceeded",
            "Quota quotidien de {{max}} publications atteint. Vous pourrez publier à nouveau à {{time}}.",
            { max: detail.max_daily, time: formatResetTime(detail.resets_at) }
        );
    }

    return fallback ?? t("publishQuota.genericError", "Une erreur est survenue.");
}
