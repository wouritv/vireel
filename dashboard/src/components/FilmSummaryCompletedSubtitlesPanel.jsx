import { useEffect, useState } from "react";
import { Loader2, RotateCcw, Subtitles } from "lucide-react";
import { applyFilmSummarySubtitles, removeFilmSummarySubtitles, updateFilmSummaryAudioSettings } from "../lib/filmSummary";
import FilmSummarySubtitleSettings from "./FilmSummarySubtitleSettings";

// Same shape FilmSummaryAudioSubtitleSettings.jsx's DEFAULT_SUBTITLE_STYLE
// uses (itself mirroring CaptionsModal's DEFAULT_STYLE) -- kept identical on
// purpose so a completed film summary that never went through the review
// page's subtitle editor still gets a sane starting style.
const DEFAULT_SUBTITLE_STYLE = {
    positionX: 50,
    positionY: 82,
    fontFamily: "Montserrat",
    fontSize: 14,
    fontColor: "#FFFFFF",
    highlightColor: "#FFDD00",
    borderColor: "#000000",
    borderWidth: 3,
    textShadowColor: "#000000",
    shadowBlur: 8,
    shadowOffsetX: 0,
    shadowOffsetY: 2,
    bgColor: "#000000",
    bgOpacity: 0,
    textCase: "none",
    bold: true,
    italic: false,
    wordsPerLine: 4,
    animation: "word-highlight",
};

// Subtitle management block for the *completed* film summary page -- lets
// someone who skipped subtitles during generation add them afterwards (or
// remove them again), reusing the exact same style editor the review page
// already built (FilmSummarySubtitleSettings) instead of a second one.
// Unlike the review page, there's no "enabled" toggle here: this page only
// ever offers "apply" (burn the current style into the real final video)
// or "remove" (restore the original un-captioned video), so `enabled` is
// just hardcoded true and FilmSummarySubtitleSettings's own checkbox is
// wired to a no-op.
//
// Every local style change is immediately reported to `onLiveStyleChange`
// (if given) so the page can mirror it onto the left-column video via
// FilmSummarySubtitleStylePreviewOverlay -- that's the "appliquer
// automatiquement sur la video a gauche a chaque choix" requirement, done
// entirely client-side with no network call.
export default function FilmSummaryCompletedSubtitlesPanel({ filmSummary, user, onUpdated, onLiveStyleChange, t }) {
    const [subtitleStyle, setSubtitleStyle] = useState({ ...DEFAULT_SUBTITLE_STYLE, ...(filmSummary.subtitle_style || {}) });
    const [saving, setSaving] = useState(false);
    const [savedFlash, setSavedFlash] = useState(false);
    const [saveError, setSaveError] = useState("");
    const [applying, setApplying] = useState(false);
    const [removing, setRemoving] = useState(false);
    const [actionError, setActionError] = useState("");

    useEffect(() => {
        onLiveStyleChange?.(subtitleStyle);
        // Only meant to fire on style changes -- onLiveStyleChange itself is
        // a stable setter from the parent page, not a dependency to re-run
        // this for.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [subtitleStyle]);

    const flashSaved = () => {
        setSavedFlash(true);
        setTimeout(() => setSavedFlash(false), 2000);
    };

    const handleStyleChange = (patch) => setSubtitleStyle((prev) => ({ ...prev, ...patch }));
    const handleApplyTheme = (style) => setSubtitleStyle({ ...DEFAULT_SUBTITLE_STYLE, ...style });

    const handleSave = async () => {
        if (!user?.id) return;
        setSaving(true);
        setSaveError("");
        try {
            const updated = await updateFilmSummaryAudioSettings(filmSummary.id, user.id, {
                subtitle_style: subtitleStyle,
            });
            onUpdated?.(updated);
            flashSaved();
        } catch (err) {
            setSaveError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setSaving(false);
        }
    };

    const handleApply = async () => {
        if (!user?.id) return;
        setApplying(true);
        setActionError("");
        try {
            await updateFilmSummaryAudioSettings(filmSummary.id, user.id, {
                subtitle_style: subtitleStyle,
                subtitles_enabled: true,
            });
            const updated = await applyFilmSummarySubtitles(filmSummary.id, user.id);
            onUpdated?.(updated);
        } catch (err) {
            setActionError(err.message || t("filmSummary.subtitles.applyFailed", "Impossible d'ajouter les sous-titres."));
        } finally {
            setApplying(false);
        }
    };

    const handleRemove = async () => {
        if (!user?.id) return;
        setRemoving(true);
        setActionError("");
        try {
            const updated = await removeFilmSummarySubtitles(filmSummary.id, user.id);
            onUpdated?.(updated);
        } catch (err) {
            setActionError(err.message || t("filmSummary.subtitles.removeFailed", "Impossible de revenir a la video sans sous-titres."));
        } finally {
            setRemoving(false);
        }
    };

    return (
        <div className="space-y-3">
            <FilmSummarySubtitleSettings
                enabled={true}
                style={subtitleStyle}
                onEnabledChange={() => {}}
                onStyleChange={handleStyleChange}
                onApplyTheme={handleApplyTheme}
                onSave={handleSave}
                saving={saving}
                savedFlash={savedFlash}
                error={saveError}
                t={t}
            />

            {actionError ? <p className="text-xs text-red-300">{actionError}</p> : null}

            <button
                type="button"
                onClick={handleApply}
                disabled={applying || removing}
                className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-500 disabled:opacity-50"
            >
                {applying ? <Loader2 size={14} className="animate-spin" /> : <Subtitles size={14} />}
                {t("filmSummary.subtitles.apply", "Ajouter sous-titres")}
            </button>

            {filmSummary.subtitles_enabled ? (
                <button
                    type="button"
                    onClick={handleRemove}
                    disabled={applying || removing}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50"
                >
                    {removing ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
                    {t("filmSummary.subtitles.remove", "Revenir a la video sans sous-titres")}
                </button>
            ) : null}
        </div>
    );
}
