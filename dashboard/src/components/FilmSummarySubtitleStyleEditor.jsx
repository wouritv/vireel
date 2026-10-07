import { Check, Loader2, Palette, Save } from "lucide-react";
import { ANIMATION_OPTIONS, COLOR_PRESETS, FONT_OPTIONS, HIGHLIGHT_COLOR_PRESETS } from "../lib/subtitleOptions";
import { BUILTIN_CAPTION_THEMES } from "../lib/captionThemes";

// The theme-grid + style-controls half of the subtitle section -- visually
// and behaviorally the same pattern as CaptionsModal's theme picker +
// style editor (built-in theme swatches, the user's own saved themes, then
// a plain set of style controls underneath), just condensed into one
// scrollable panel since film-summary subtitles don't need CaptionsModal's
// per-word/per-line editing. Purely presentational: all state lives in the
// parent (FilmSummarySubtitleSettings).
export default function FilmSummarySubtitleStyleEditor({
    style,
    onStyleChange,
    onApplyTheme,
    activeThemeId,
    customThemes,
    themesLoading,
    themesError,
    saveThemeName,
    onSaveThemeNameChange,
    onSaveTheme,
    savingTheme,
    saveThemeMessage,
    t,
}) {
    return (
        <div className="space-y-4">
            <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                    {t("filmSummary.subtitles.builtinThemes", "Themes prets a l'emploi")}
                </label>
                <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
                    {BUILTIN_CAPTION_THEMES.map((theme) => (
                        <button
                            key={theme.id}
                            type="button"
                            onClick={() => onApplyTheme(theme)}
                            className={`relative rounded-lg border px-3 py-2 text-left ${
                                activeThemeId === theme.id ? "border-emerald-400 bg-emerald-500/15" : "border-slate-300 dark:border-white/10 bg-white dark:bg-black/30"
                            }`}
                        >
                            <span className="flex items-center gap-2">
                                <span className="text-base leading-none">{theme.emoji}</span>
                                <span className="text-xs font-semibold text-slate-800 dark:text-slate-100">{theme.name}</span>
                                {activeThemeId === theme.id ? <Check size={13} className="ml-auto text-emerald-500" /> : null}
                            </span>
                        </button>
                    ))}
                </div>
            </div>

            <div>
                <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.myThemes", "Mes themes")}</label>
                    {themesLoading ? <Loader2 size={12} className="animate-spin text-slate-400" /> : null}
                </div>
                {themesError ? <p className="mt-1 text-[11px] text-red-300">{themesError}</p> : null}
                <div className="mt-2 space-y-1.5">
                    {(customThemes || []).map((theme) => (
                        <button
                            key={theme.id}
                            type="button"
                            onClick={() => onApplyTheme(theme)}
                            className={`flex w-full items-center gap-2 rounded-lg border px-3 py-2 text-left text-xs font-semibold text-slate-800 dark:text-slate-100 ${
                                activeThemeId === theme.id ? "border-emerald-400 bg-emerald-500/15" : "border-slate-300 dark:border-white/10 bg-white dark:bg-black/30"
                            }`}
                        >
                            <Palette size={13} className="text-slate-400" />
                            {theme.name}
                            {activeThemeId === theme.id ? <Check size={13} className="ml-auto text-emerald-500" /> : null}
                        </button>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.position", "Position (X/Y)")}</label>
                <div className="mt-2 space-y-2">
                    <label className="block text-[11px] text-slate-600 dark:text-slate-300">
                        X ({style.positionX}%)
                        <input type="range" min="5" max="95" value={style.positionX} onChange={(e) => onStyleChange({ positionX: Number(e.target.value) || 50 })} className="mt-1 w-full accent-emerald-500" />
                    </label>
                    <label className="block text-[11px] text-slate-600 dark:text-slate-300">
                        Y ({style.positionY}%)
                        <input type="range" min="5" max="95" value={style.positionY} onChange={(e) => onStyleChange({ positionY: Number(e.target.value) || 82 })} className="mt-1 w-full accent-emerald-500" />
                    </label>
                </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.fontFamily", "Police")}</label>
                <select
                    value={style.fontFamily}
                    onChange={(e) => onStyleChange({ fontFamily: e.target.value })}
                    className="mt-2 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                >
                    {[...new Set(FONT_OPTIONS.map((opt) => opt.category))].map((cat) => (
                        <optgroup key={cat} label={cat}>
                            {FONT_OPTIONS.filter((opt) => opt.category === cat).map((opt) => (
                                <option key={opt.value} value={opt.value}>
                                    {opt.label}
                                </option>
                            ))}
                        </optgroup>
                    ))}
                </select>
                <label className="mt-3 block text-[11px] text-slate-600 dark:text-slate-300">
                    {t("filmSummary.subtitles.fontSize", "Taille")} ({style.fontSize}px)
                    <input type="range" min="14" max="96" value={style.fontSize} onChange={(e) => onStyleChange({ fontSize: Number(e.target.value) || 14 })} className="mt-1 w-full accent-emerald-500" />
                </label>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.textColor", "Couleur du texte")}</label>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                    {COLOR_PRESETS.map((preset) => (
                        <button
                            key={`txt-${preset.color}`}
                            type="button"
                            onClick={() => onStyleChange({ fontColor: preset.color })}
                            className={`h-6 w-6 rounded-full border-2 ${style.fontColor === preset.color ? "border-white scale-110" : "border-slate-400 dark:border-white/20"}`}
                            style={{ backgroundColor: preset.color }}
                        />
                    ))}
                    <input type="color" value={style.fontColor} onChange={(e) => onStyleChange({ fontColor: e.target.value })} className="h-6 w-6 rounded-full border border-dashed border-slate-400/80 cursor-pointer" />
                </div>

                <label className="mt-3 block text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.highlightColor", "Couleur de surbrillance")}</label>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                    {HIGHLIGHT_COLOR_PRESETS.map((preset) => (
                        <button
                            key={`hl-${preset.color}`}
                            type="button"
                            onClick={() => onStyleChange({ highlightColor: preset.color })}
                            className={`h-6 w-6 rounded-full border-2 ${style.highlightColor === preset.color ? "border-white scale-110" : "border-slate-400 dark:border-white/20"}`}
                            style={{ backgroundColor: preset.color }}
                        />
                    ))}
                    <input type="color" value={style.highlightColor} onChange={(e) => onStyleChange({ highlightColor: e.target.value })} className="h-6 w-6 rounded-full border border-dashed border-slate-400/80 cursor-pointer" />
                </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.border", "Contour")}</label>
                <div className="mt-2 flex items-center gap-3">
                    <input type="color" value={style.borderColor} onChange={(e) => onStyleChange({ borderColor: e.target.value })} className="h-7 w-7 rounded border border-slate-300 dark:border-white/10 cursor-pointer" />
                    <label className="flex-1 text-[10px] text-slate-400">
                        {t("filmSummary.subtitles.thickness", "Epaisseur")} ({style.borderWidth})
                        <input type="range" min="0" max="6" value={style.borderWidth} onChange={(e) => onStyleChange({ borderWidth: Number(e.target.value) || 0 })} className="mt-1 w-full accent-emerald-500" />
                    </label>
                </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <div className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300">
                    <span>{t("filmSummary.subtitles.backgroundBox", "Fond du texte")}</span>
                    <input type="checkbox" checked={style.bgOpacity > 0} onChange={(e) => onStyleChange({ bgOpacity: e.target.checked ? 0.5 : 0 })} />
                </div>
                {style.bgOpacity > 0 ? (
                    <div className="mt-3 flex items-center gap-3">
                        <input type="color" value={style.bgColor} onChange={(e) => onStyleChange({ bgColor: e.target.value })} className="h-7 w-7 rounded border border-slate-300 dark:border-white/10 cursor-pointer" />
                        <label className="flex-1 text-[10px] text-slate-400">
                            {t("filmSummary.subtitles.opacity", "Opacite")} ({Math.round((style.bgOpacity || 0) * 100)}%)
                            <input
                                type="range"
                                min="10"
                                max="100"
                                value={Math.round((style.bgOpacity || 0) * 100)}
                                onChange={(e) => onStyleChange({ bgOpacity: (Number(e.target.value) || 0) / 100 })}
                                className="mt-1 w-full accent-emerald-500"
                            />
                        </label>
                    </div>
                ) : null}
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.animation", "Animation")}</label>
                <div className="mt-2 grid grid-cols-2 gap-2">
                    {ANIMATION_OPTIONS.map((opt) => (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => onStyleChange({ animation: opt.value })}
                            className={`rounded-md border px-2 py-1.5 text-left text-xs ${
                                style.animation === opt.value ? "border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200" : "border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300"
                            }`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <div className="grid grid-cols-3 gap-2">
                    {[
                        { key: "normal", label: t("filmSummary.subtitles.normal", "Normal"), patch: { bold: false, italic: false } },
                        { key: "bold", label: t("filmSummary.subtitles.bold", "Gras"), patch: { bold: true, italic: false } },
                        { key: "italic", label: t("filmSummary.subtitles.italic", "Italique"), patch: { bold: false, italic: true } },
                    ].map((opt) => {
                        const isActive = (opt.key === "normal" && !style.bold && !style.italic) || (opt.key === "bold" && style.bold) || (opt.key === "italic" && style.italic && !style.bold);
                        return (
                            <button
                                key={opt.key}
                                type="button"
                                onClick={() => onStyleChange(opt.patch)}
                                className={`rounded-md border px-2 py-1.5 text-xs ${isActive ? "border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200" : "border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300"}`}
                            >
                                {opt.label}
                            </button>
                        );
                    })}
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2">
                    {[
                        { value: "none", label: t("filmSummary.subtitles.caseNormal", "Normal") },
                        { value: "uppercase", label: t("filmSummary.subtitles.caseUpper", "MAJ") },
                        { value: "lowercase", label: t("filmSummary.subtitles.caseLower", "min") },
                    ].map((opt) => (
                        <button
                            key={opt.value}
                            type="button"
                            onClick={() => onStyleChange({ textCase: opt.value })}
                            className={`rounded-md border px-2 py-1.5 text-xs ${style.textCase === opt.value ? "border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200" : "border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300"}`}
                        >
                            {opt.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.wordsPerLine", "Mots par ligne")} ({style.wordsPerLine || 4})</label>
                <input
                    type="range"
                    min="2"
                    max="8"
                    value={style.wordsPerLine || 4}
                    onChange={(e) => onStyleChange({ wordsPerLine: Number(e.target.value) || 4 })}
                    className="mt-2 w-full accent-emerald-500"
                />
            </div>

            <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t("filmSummary.subtitles.saveTheme", "Enregistrer ce style comme theme")}</label>
                <div className="mt-2 flex items-center gap-2">
                    <input
                        type="text"
                        value={saveThemeName}
                        onChange={(e) => onSaveThemeNameChange(e.target.value)}
                        placeholder={t("filmSummary.subtitles.themeNamePlaceholder", "Nom du theme")}
                        className="flex-1 bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                    />
                    <button
                        type="button"
                        onClick={() => onSaveTheme()}
                        disabled={savingTheme || !saveThemeName.trim()}
                        className="rounded-md bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-200 disabled:opacity-50 inline-flex items-center gap-1"
                    >
                        {savingTheme ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                    </button>
                </div>
                {saveThemeMessage ? <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">{saveThemeMessage}</p> : null}
            </div>
        </div>
    );
}
