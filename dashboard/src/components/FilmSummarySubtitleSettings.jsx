import { useEffect, useState } from "react";
import { Loader2, Save, Subtitles } from "lucide-react";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import FilmSummarySubtitleStyleEditor from "./FilmSummarySubtitleStyleEditor";

function parseApiDetail(rawText, fallback) {
    try {
        const parsed = JSON.parse(rawText || "{}");
        return String(parsed?.detail || rawText || fallback);
    } catch {
        return String(rawText || fallback);
    }
}

// Subtitles section of FilmSummaryAudioSubtitleSettings: an enable toggle
// plus the exact same theme/style system Reels & Captions already use
// (CaptionsModal) -- same built-in themes, same style shape, same
// GET/POST/DELETE /api/caption-style-themes endpoints -- just reused here
// instead of reinvented. Owns the theme-fetching/saving side-effects so
// FilmSummarySubtitleStyleEditor underneath can stay purely presentational.
export default function FilmSummarySubtitleSettings({ enabled, style, onEnabledChange, onStyleChange, onApplyTheme, onSave, saving, savedFlash, error, t }) {
    const { user } = useAuth();
    const [customThemes, setCustomThemes] = useState([]);
    const [themesLoading, setThemesLoading] = useState(false);
    const [themesError, setThemesError] = useState("");
    const [activeThemeId, setActiveThemeId] = useState(null);
    const [saveThemeName, setSaveThemeName] = useState("");
    const [savingTheme, setSavingTheme] = useState(false);
    const [saveThemeMessage, setSaveThemeMessage] = useState("");

    useEffect(() => {
        if (!enabled) return undefined;
        let cancelled = false;
        setThemesLoading(true);
        setThemesError("");
        fetch(getApiUrl("/api/caption-style-themes"), { headers: getAuthHeaders(user?.id) })
            .then((res) => (res.ok ? res.json() : Promise.reject(new Error("themes_unavailable"))))
            .then((data) => {
                if (!cancelled) setCustomThemes(Array.isArray(data?.themes) ? data.themes : []);
            })
            .catch(() => {
                if (!cancelled) setThemesError(t("filmSummary.subtitles.themesLoadFailed", "Impossible de charger vos themes."));
            })
            .finally(() => {
                if (!cancelled) setThemesLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [enabled, user?.id, t]);

    const handleApplyTheme = (theme) => {
        if (!theme?.style) return;
        onApplyTheme(theme.style);
        setActiveThemeId(theme.id || null);
        setSaveThemeName(theme.name || "");
        setSaveThemeMessage("");
    };

    const handleSaveTheme = async () => {
        const name = saveThemeName.trim();
        if (!name || !user?.id) return;
        setSavingTheme(true);
        setSaveThemeMessage("");
        try {
            const res = await fetch(getApiUrl("/api/caption-style-themes"), {
                method: "POST",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user.id) },
                body: JSON.stringify({ name, style }),
            });
            if (!res.ok) {
                const raw = await res.text();
                throw new Error(parseApiDetail(raw, t("filmSummary.subtitles.themeSaveFailed", "Echec de l'enregistrement du theme.")));
            }
            const saved = await res.json();
            setCustomThemes((prev) => [saved, ...prev.filter((theme) => theme.id !== saved.id)]);
            setActiveThemeId(saved.id);
            setSaveThemeMessage(t("filmSummary.subtitles.themeSaved", "Theme enregistre."));
        } catch (err) {
            setSaveThemeMessage(err.message || t("filmSummary.subtitles.themeSaveFailed", "Echec de l'enregistrement du theme."));
        } finally {
            setSavingTheme(false);
        }
    };

    const handleStyleChange = (patch) => {
        setActiveThemeId(null);
        onStyleChange(patch);
    };

    return (
        <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
            <div className="flex items-center justify-between">
                <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                    <Subtitles size={14} />
                    {t("filmSummary.subtitles.title", "Sous-titres")}
                </label>
                <input type="checkbox" checked={enabled} onChange={(e) => onEnabledChange(e.target.checked)} />
            </div>

            {enabled ? (
                <FilmSummarySubtitleStyleEditor
                    style={style}
                    onStyleChange={handleStyleChange}
                    onApplyTheme={handleApplyTheme}
                    activeThemeId={activeThemeId}
                    customThemes={customThemes}
                    themesLoading={themesLoading}
                    themesError={themesError}
                    saveThemeName={saveThemeName}
                    onSaveThemeNameChange={setSaveThemeName}
                    onSaveTheme={handleSaveTheme}
                    savingTheme={savingTheme}
                    saveThemeMessage={saveThemeMessage}
                    t={t}
                />
            ) : (
                <p className="text-xs text-slate-400 dark:text-zinc-500">
                    {t("filmSummary.subtitles.disabledHint", "Active les sous-titres pour choisir un theme et personnaliser son style.")}
                </p>
            )}

            {error ? <p className="text-xs text-red-300">{error}</p> : null}

            <button
                type="button"
                onClick={onSave}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2 text-xs font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50"
            >
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                {savedFlash ? t("filmSummary.subtitles.saved", "Enregistre") : t("filmSummary.subtitles.save", "Enregistrer les sous-titres")}
            </button>
        </div>
    );
}
