import { useEffect, useState } from "react";
import { fetchFilmSummaryMusicTracks, updateFilmSummaryAudioSettings } from "../lib/filmSummary";
import FilmSummaryMusicSettings from "./FilmSummaryMusicSettings";
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

// Audio/subtitles panel for a film summary while awaiting_review: music
// (mood-grouped track from the existing library + a start/end range over
// the final video) and subtitles (enable toggle + the Reels/Captions theme
// system), each its own small sub-component, each saved independently via
// PATCH /api/film-summaries/{id}/audio-settings. Available for both the
// automatic and manual edit modes -- it's unrelated to clip picking.
export default function FilmSummaryAudioSubtitleSettings({ filmSummary, user, totalDurationMs, onUpdated, t }) {
    const [tracksByMood, setTracksByMood] = useState({});
    const [tracksLoading, setTracksLoading] = useState(true);
    const [tracksError, setTracksError] = useState("");

    const [musicTrackId, setMusicTrackId] = useState(filmSummary.music_track_id || null);
    const [musicStartMs, setMusicStartMs] = useState(Number.isFinite(filmSummary.music_start_ms) ? filmSummary.music_start_ms : 0);
    const [musicEndMs, setMusicEndMs] = useState(Number.isFinite(filmSummary.music_end_ms) ? filmSummary.music_end_ms : totalDurationMs);
    const [savingMusic, setSavingMusic] = useState(false);
    const [musicSavedFlash, setMusicSavedFlash] = useState(false);
    const [musicError, setMusicError] = useState("");

    const [subtitlesEnabled, setSubtitlesEnabled] = useState(Boolean(filmSummary.subtitles_enabled));
    const [subtitleStyle, setSubtitleStyle] = useState({ ...DEFAULT_SUBTITLE_STYLE, ...(filmSummary.subtitle_style || {}) });
    const [savingSubtitles, setSavingSubtitles] = useState(false);
    const [subtitleSavedFlash, setSubtitleSavedFlash] = useState(false);
    const [subtitleError, setSubtitleError] = useState("");

    useEffect(() => {
        let cancelled = false;
        setTracksLoading(true);
        fetchFilmSummaryMusicTracks(user?.id)
            .then((data) => {
                if (!cancelled) setTracksByMood(data?.tracks_by_mood || {});
            })
            .catch((err) => {
                if (!cancelled) setTracksError(err.message || t("filmSummary.music.loadFailed", "Impossible de charger la bibliotheque musicale."));
            })
            .finally(() => {
                if (!cancelled) setTracksLoading(false);
            });
        return () => {
            cancelled = true;
        };
    }, [user?.id, t]);

    const flashSaved = (setFlash) => {
        setFlash(true);
        setTimeout(() => setFlash(false), 2000);
    };

    const handleMusicChange = (patch) => {
        if ("musicTrackId" in patch) setMusicTrackId(patch.musicTrackId);
        if ("musicStartMs" in patch) setMusicStartMs(patch.musicStartMs);
        if ("musicEndMs" in patch) setMusicEndMs(patch.musicEndMs);
    };

    const handleSaveMusic = async () => {
        if (!user?.id) return;
        setSavingMusic(true);
        setMusicError("");
        try {
            const updated = await updateFilmSummaryAudioSettings(filmSummary.id, user.id, {
                music_track_id: musicTrackId,
                music_start_ms: musicTrackId ? Math.round(musicStartMs) : null,
                music_end_ms: musicTrackId ? Math.round(musicEndMs) : null,
            });
            onUpdated?.(updated);
            flashSaved(setMusicSavedFlash);
        } catch (err) {
            setMusicError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setSavingMusic(false);
        }
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
            <FilmSummaryMusicSettings
                tracksByMood={tracksByMood}
                tracksLoading={tracksLoading}
                tracksError={tracksError}
                musicTrackId={musicTrackId}
                musicStartMs={musicStartMs}
                musicEndMs={musicEndMs}
                totalDurationMs={totalDurationMs}
                onChange={handleMusicChange}
                onSave={handleSaveMusic}
                saving={savingMusic}
                savedFlash={musicSavedFlash}
                error={musicError}
                t={t}
            />
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
