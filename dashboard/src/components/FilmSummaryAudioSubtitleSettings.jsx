import { useState } from "react";
import { updateFilmSummaryAudioSettings } from "../lib/filmSummary";
import FilmSummarySubtitleSettings from "./FilmSummarySubtitleSettings";

// Same shape CaptionsModal's DEFAULT_STYLE uses for Reels/Captions
// subtitles -- kept identical here on purpose so film-summary subtitles
// stay on that one shared style system (same fields, same
// GET/PUT /api/caption-style-default + /api/caption-style-themes
// endpoints) instead of drifting into a parallel one.
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

// Subtitles panel for a film summary while awaiting_review: enable toggle +
// the Reels/Captions theme system, saved via PATCH
// /api/film-summaries/{id}/audio-settings. There is no dialogue-volume
// control -- the film's own audio is never audible in the final video
// ("il ne dois y avoir aucune parole du film originale"), only the AI
// narration.
export default function FilmSummaryAudioSubtitleSettings({ filmSummary, user, totalDurationMs, onUpdated, t }) {
    const [subtitlesEnabled, setSubtitlesEnabled] = useState(Boolean(filmSummary.subtitles_enabled));
    const [subtitleStyle, setSubtitleStyle] = useState({ ...DEFAULT_SUBTITLE_STYLE, ...(filmSummary.subtitle_style || {}) });
    const [savingSubtitles, setSavingSubtitles] = useState(false);
    const [subtitleSavedFlash, setSubtitleSavedFlash] = useState(false);
    const [subtitleError, setSubtitleError] = useState("");

    const flashSaved = (setFlash) => {
        setFlash(true);
        setTimeout(() => setFlash(false), 2000);
    };

    const handleSaveSubtitles = async () => {
        if (!user?.id) return;
        setSavingSubtitles(true);
        setSubtitleError("");
        try {
            const updated = await updateFilmSummaryAudioSettings(filmSummary.id, user.id, {
                subtitles_enabled: subtitlesEnabled,
                subtitle_style: subtitlesEnabled ? subtitleStyle : null,
            });
            onUpdated?.(updated);
            flashSaved(setSubtitleSavedFlash);
        } catch (err) {
            setSubtitleError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setSavingSubtitles(false);
        }
    };

    return (
        <div className="space-y-4">
            <FilmSummarySubtitleSettings
                enabled={subtitlesEnabled}
                style={subtitleStyle}
                onEnabledChange={setSubtitlesEnabled}
                onStyleChange={(patch) => setSubtitleStyle((prev) => ({ ...prev, ...patch }))}
                onApplyTheme={(style) => setSubtitleStyle({ ...DEFAULT_SUBTITLE_STYLE, ...style })}
                onSave={handleSaveSubtitles}
                saving={savingSubtitles}
                savedFlash={subtitleSavedFlash}
                error={subtitleError}
                t={t}
            />
        </div>
    );
}
