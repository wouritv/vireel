import { getApiUrl } from "../config";
import { getAuthHeaders } from "./apiAuth";

const STORAGE_KEY = "vireel_referral_code";
const FRESH_SIGNUP_WINDOW_MS = 2 * 60 * 1000;

export function storeReferralCode(code) {
    if (!code) return;
    try {
        localStorage.setItem(STORAGE_KEY, String(code));
    } catch {
        // Private browsing / quota exceeded -- the code is simply not captured.
    }
}

export function getStoredReferralCode() {
    try {
        return localStorage.getItem(STORAGE_KEY) || null;
    } catch {
        return null;
    }
}

export function clearStoredReferralCode() {
    try {
        localStorage.removeItem(STORAGE_KEY);
    } catch {
        // Nothing to clean up if storage isn't available.
    }
}

/**
 * Heuristic only -- the trigger for WHEN to attempt association after an
 * OAuth login. The backend independently re-verifies server-side whether
 * the account is actually new before granting anything.
 */
export function looksLikeFreshSignup(user) {
    try {
        const createdAt = Date.parse(user?.created_at);
        const lastSignInAt = Date.parse(user?.last_sign_in_at);
        if (!Number.isFinite(createdAt) || !Number.isFinite(lastSignInAt)) return false;
        return Math.abs(lastSignInAt - createdAt) <= FRESH_SIGNUP_WINDOW_MS;
    } catch {
        return false;
    }
}

/**
 * Attempts the association exactly once for this code: the stored code is
 * cleared after the call resolves (success OR failure), since the backend
 * DB becomes the source of truth once this has been attempted.
 */
export async function associateReferralCode(userId, code) {
    if (!code) return null;
    try {
        const res = await fetch(getApiUrl("/api/referrals/associate"), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(userId),
            },
            body: JSON.stringify({ referral_code: code }),
        });
        if (!res.ok) return null;
        return await res.json();
    } catch {
        return null;
    } finally {
        clearStoredReferralCode();
    }
}
