import { getApiUrl } from "../config";
import { getAuthHeaders } from "./apiAuth";

const STORAGE_KEY = "vireel_referral_code";
// Generous on purpose: an account that requires email confirmation has no
// session (so no association attempt can even be made) until the user
// opens that email and confirms, which can take well over a couple of
// minutes. The backend re-verifies account freshness itself (its own,
// authoritative window) before granting anything, so a wide client-side
// window here only risks a harmless extra attempt, never a false grant.
const FRESH_SIGNUP_WINDOW_MS = 30 * 60 * 1000;

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
 * Attempts the association for this code. A brand-new signup that requires
 * email confirmation has no Supabase session yet (signUp() returns no
 * access token until the user confirms), so this first attempt comes back
 * 401 before the backend ever looks at the code -- that case must NOT clear
 * the stored code, or the retry AuthContext fires once a real session
 * exists (see looksLikeFreshSignup) would have nothing left to associate.
 * Same for a network failure: we don't know whether the backend was ever
 * reached. Only a response that actually reflects a decision about the
 * code itself (success, or the backend rejecting the code as unknown/
 * invalid) is a terminal outcome worth clearing.
 */
export async function associateReferralCode(userId, code) {
    if (!code) return null;

    let res;
    try {
        res = await fetch(getApiUrl("/api/referrals/associate"), {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                ...getAuthHeaders(userId),
            },
            body: JSON.stringify({ referral_code: code }),
        });
    } catch {
        return null;
    }

    if (res.ok || res.status === 400 || res.status === 404) {
        clearStoredReferralCode();
    }

    if (!res.ok) return null;
    return await res.json();
}
