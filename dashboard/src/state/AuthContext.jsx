import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getSupabaseBrowserClient } from "../lib/supabase-browser";
import { setCachedAccessToken } from "../lib/apiAuth";
import { associateReferralCode, getStoredReferralCode } from "../lib/referral";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
    const [session, setSession] = useState(null);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const supabase = getSupabaseBrowserClient();
        let mounted = true;

        supabase.auth.getSession().then(({ data, error }) => {
            if (!mounted) return;

            if (error) {
                setCachedAccessToken(null);
                setSession(null);
                setUser(null);
                setLoading(false);
                return;
            }

            // Security: pushed synchronously, in this same callback and
            // before the state update below triggers dependent effects
            // elsewhere (useEffects keyed on `isAuthenticated`/`user.id`) --
            // otherwise those effects' first fetch races an independent,
            // still-pending token lookup and gets sent without a token,
            // failing auth (see apiAuth.js for the full race explanation).
            setCachedAccessToken(data.session?.access_token ?? null);
            setSession(data.session ?? null);
            setUser(data.session?.user ?? null);
            setLoading(false);
        });

        const { data: authListener } = supabase.auth.onAuthStateChange((_event, nextSession) => {
            setCachedAccessToken(nextSession?.access_token ?? null);
            setSession(nextSession ?? null);
            setUser(nextSession?.user ?? null);
            setLoading(false);
        });

        return () => {
            mounted = false;
            authListener.subscription.unsubscribe();
        };
    }, []);

    // Retries the referral association on every authenticated session this
    // browser gets, as long as a code is still stored -- covers OAuth
    // signup, and email/password signup when Supabase requires email
    // confirmation (signUp() returns no session, so Login.jsx's own
    // immediate attempt 401s before a session exists; the code is only
    // cleared on a terminal response, see associateReferralCode, so it
    // survives for this effect to pick up once the user actually confirms
    // and signs in). No freshness heuristic needed here: the backend
    // independently re-verifies the account is new enough before granting
    // anything, so attempting this for a long-stale code is harmless --
    // it just comes back {"associated": false} and clears it.
    useEffect(() => {
        if (!user) return;
        const referralCode = getStoredReferralCode();
        if (!referralCode) return;
        associateReferralCode(user.id, referralCode);
    }, [user]);

    async function logout() {
        const supabase = getSupabaseBrowserClient();
        await supabase.auth.signOut();
        setSession(null);
        setUser(null);
    }

    const value = useMemo(
        () => ({
            session,
            user,
            loading,
            isAuthenticated: Boolean(user),
            logout,
        }),
        [session, user, loading]
    );

    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
    const ctx = useContext(AuthContext);

    if (!ctx) {
        throw new Error("useAuth must be used inside AuthProvider");
    }

    return ctx;
}