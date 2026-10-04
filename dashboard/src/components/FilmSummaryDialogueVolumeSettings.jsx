import { Loader2, Save, Volume2 } from "lucide-react";
import { useState } from "react";
import { updateFilmSummaryAudioSettings } from "../lib/filmSummary";

// Dialogue-volume section of FilmSummaryAudioSubtitleSettings: a single
// slider controlling how audible the film's own original audio (dialogue,
// ambience, ...) stays underneath the AI-generated narration. Replaces the
// background-music picker this panel used to show -- there's no music
// anymore, just the original film audio mixed under the voice-over, and the
// user decides its intensity themselves instead of it being silenced by
// default. Saved independently via the same
// PATCH /api/film-summaries/{id}/audio-settings endpoint the other
// sections here already use, just with a different key
// ({dialogue_volume: <0-100>}).
export default function FilmSummaryDialogueVolumeSettings({ filmSummary, user, onUpdated, t }) {
    const initialVolume = filmSummary?.dialogue_volume ?? 20;
    const [dialogueVolume, setDialogueVolume] = useState(initialVolume);
    const [saving, setSaving] = useState(false);
    const [savedFlash, setSavedFlash] = useState(false);
    const [error, setError] = useState("");

    const handleSave = async () => {
        if (!user?.id) return;
        setSaving(true);
        setError("");
        try {
            const updated = await updateFilmSummaryAudioSettings(filmSummary.id, user.id, {
                dialogue_volume: dialogueVolume,
            });
            onUpdated?.(updated);
            setSavedFlash(true);
            setTimeout(() => setSavedFlash(false), 2000);
        } catch (err) {
            setError(err.message || t("filmSummary.genericError", "Une erreur est survenue."));
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="space-y-3 rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5">
            <label className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                <Volume2 size={14} />
                {t("filmSummary.dialogueVolume.title", "Intensite du volume des dialogues du film")}
            </label>

            <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                    <span>{t("filmSummary.dialogueVolume.label", "Volume")}</span>
                    <span>{dialogueVolume}</span>
                </div>
                <input
                    type="range"
                    min={0}
                    max={100}
                    step={1}
                    value={dialogueVolume}
                    onChange={(e) => setDialogueVolume(Number(e.target.value))}
                    className="w-full accent-emerald-500"
                />
            </div>

            <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                {t(
                    "filmSummary.dialogueVolume.hint",
                    "Volume du son original du film sous la voix off generee par l'IA. 0 = coupe entierement (silence), 100 = volume original complet."
                )}
            </p>

            {error ? <p className="text-xs text-red-300">{error}</p> : null}

            <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2 text-xs font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-50"
            >
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                {savedFlash ? t("filmSummary.dialogueVolume.saved", "Enregistre") : t("filmSummary.dialogueVolume.save", "Enregistrer le volume")}
            </button>
        </div>
    );
}
