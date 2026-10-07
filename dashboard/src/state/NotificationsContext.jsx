import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useAuth } from "./AuthContext";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";

const NotificationsContext = createContext(null);

/**
 * Provides the current user's in-app notifications to the app. Fetches
 * once on mount, refreshes when the window regains focus, and exposes a
 * manual `refresh()` method -- mirrors UserCreditsContext's pattern.
 */
export function NotificationsProvider({ children }) {
    const { user, isAuthenticated } = useAuth();
    const [items, setItems] = useState([]);
    const [unreadCount, setUnreadCount] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const fetching = useRef(false);

    const fetchNotifications = useCallback(async () => {
        if (!user?.id || fetching.current) return;
        fetching.current = true;
        setLoading(true);
        setError("");
        try {
            const res = await fetch(getApiUrl("/api/notifications?limit=20"), {
                headers: getAuthHeaders(user.id),
            });
            if (!res.ok) {
                const text = await res.text();
                throw new Error(text || "Unable to load notifications");
            }
            const data = await res.json();
            setItems(Array.isArray(data?.items) ? data.items : []);
            setUnreadCount(Number(data?.unread_count) || 0);
        } catch (err) {
            setError(err.message || "Unable to load notifications");
        } finally {
            setLoading(false);
            fetching.current = false;
        }
    }, [user?.id]);

    useEffect(() => {
        if (isAuthenticated) {
            fetchNotifications();
        } else {
            setItems([]);
            setUnreadCount(0);
        }
    }, [isAuthenticated, fetchNotifications]);

    useEffect(() => {
        const onFocus = () => {
            if (isAuthenticated) fetchNotifications();
        };
        window.addEventListener("focus", onFocus);
        return () => window.removeEventListener("focus", onFocus);
    }, [isAuthenticated, fetchNotifications]);

    const markRead = useCallback(async (id) => {
        if (!user?.id || !id) return;
        // Optimistic local update -- the dropdown should react immediately.
        setItems((prev) => prev.map((n) => (n.id === id && !n.read_at ? { ...n, read_at: new Date().toISOString() } : n)));
        setUnreadCount((prev) => Math.max(0, prev - 1));
        try {
            await fetch(getApiUrl(`/api/notifications/${id}/read`), {
                method: "POST",
                headers: getAuthHeaders(user.id),
            });
        } catch {
            // Best effort: a stale badge is corrected on the next refresh.
        }
    }, [user?.id]);

    const markAllRead = useCallback(async () => {
        if (!user?.id) return;
        setItems((prev) => prev.map((n) => (n.read_at ? n : { ...n, read_at: new Date().toISOString() })));
        setUnreadCount(0);
        try {
            await fetch(getApiUrl("/api/notifications/read-all"), {
                method: "POST",
                headers: getAuthHeaders(user.id),
            });
        } catch {
            // Best effort: a stale badge is corrected on the next refresh.
        }
    }, [user?.id]);

    const value = useMemo(() => ({
        items,
        unreadCount,
        loading,
        error,
        refresh: fetchNotifications,
        markRead,
        markAllRead,
    }), [items, unreadCount, loading, error, fetchNotifications, markRead, markAllRead]);

    return (
        <NotificationsContext.Provider value={value}>
            {children}
        </NotificationsContext.Provider>
    );
}

export function useNotifications() {
    const ctx = useContext(NotificationsContext);
    if (!ctx) throw new Error("useNotifications must be used inside NotificationsProvider");
    return ctx;
}
