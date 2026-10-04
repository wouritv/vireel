import { useEffect, useMemo, useRef, useState } from "react";
import { Check, X } from "lucide-react";
import { formatMsClock } from "../lib/filmSummary";

// The manual clip-picker's bottom track: one block per scene_index entry,
// laid out left-to-right over the *full source duration* (not just the
// enabled shots), each with a toggle and two drag handles to trim its
// start/end -- the drag mechanics are adapted from ManualReelCreationPage's
// single start/end handle pair, just keyed per-shot instead of global, and
// clamped to that shot's own original [start_ms, end_ms] rather than the
// whole timeline. Kept decoupled from the video player / submit logic,
// which FilmSummaryClipPickerEditor owns.

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const MIN_TRIM_MS = 300;

function msFromClientX(trackEl, clientX, durationMs) {
    if (!trackEl || durationMs <= 0) return 0;
    const rect = trackEl.getBoundingClientRect();
    if (rect.width <= 0) return 0;
    const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
    return ratio * durationMs;
}

function ShotHandle({ label, leftPercent, onPointerDown }) {
    return (
        <div
            role="slider"
            aria-label={label}
            onPointerDown={onPointerDown}
            className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-7 w-3 rounded-sm bg-emerald-500 border-2 border-white dark:border-[#121214] shadow cursor-ew-resize z-10"
            style={{ left: `${leftPercent}%` }}
        />
    );
}

function ShotBlock({ shot, selection, durationMs, onToggle, onHandlePointerDown, t }) {
    const originalStartPercent = clamp((shot.start_ms / durationMs) * 100, 0, 100);
    const originalEndPercent = clamp((shot.end_ms / durationMs) * 100, 0, 100);
    const trimStartPercent = clamp((selection.startMs / durationMs) * 100, 0, 100);
    const trimEndPercent = clamp((selection.endMs / durationMs) * 100, 0, 100);

    return (
        <div
            className="absolute top-1 bottom-1 rounded-md overflow-visible"
            style={{ left: `${originalStartPercent}%`, width: `${Math.max(0.3, originalEndPercent - originalStartPercent)}%` }}
        >
            {/* Full original shot extent, dimmed when disabled */}
            <div
                className={`absolute inset-0 rounded-md border ${
                    selection.enabled ? "border-emerald-500/40 bg-emerald-500/10" : "border-slate-400/30 bg-slate-400/10"
                }`}
            />
            {selection.enabled ? (
                <div
                    className="absolute top-0 bottom-0 rounded-md bg-emerald-500/40"
                    style={{
                        left: `${clamp(((selection.startMs - shot.start_ms) / Math.max(1, shot.end_ms - shot.start_ms)) * 100, 0, 100)}%`,
                        right: `${clamp(((shot.end_ms - selection.endMs) / Math.max(1, shot.end_ms - shot.start_ms)) * 100, 0, 100)}%`,
                    }}
                />
            ) : null}

            <button
                type="button"
                onClick={(e) => {
                    e.stopPropagation();
                    onToggle(shot.scene_id);
                }}
                title={selection.enabled ? t("filmSummary.manual.disableShot", "Retirer ce plan") : t("filmSummary.manual.enableShot", "Garder ce plan")}
                className={`absolute -top-2 left-1/2 -translate-x-1/2 inline-flex h-4 w-4 items-center justify-center rounded-full border shadow z-20 ${
                    selection.enabled
                        ? "border-emerald-400 bg-emerald-500 text-black"
                        : "border-slate-400 bg-white dark:bg-black/60 text-slate-400"
                }`}
            >
                {selection.enabled ? <Check size={10} /> : <X size={10} />}
            </button>

            {selection.enabled ? (
                <>
                    <ShotHandle
                        label={t("filmSummary.manual.trimStart", "Debut du plan")}
                        leftPercent={clamp(((selection.startMs - shot.start_ms) / Math.max(1, shot.end_ms - shot.start_ms)) * 100, 0, 100)}
                        onPointerDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onHandlePointerDown(shot.scene_id, "start");
                        }}
                    />
                    <ShotHandle
                        label={t("filmSummary.manual.trimEnd", "Fin du plan")}
                        leftPercent={clamp(((selection.endMs - shot.start_ms) / Math.max(1, shot.end_ms - shot.start_ms)) * 100, 0, 100)}
                        onPointerDown={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            onHandlePointerDown(shot.scene_id, "end");
                        }}
                    />
                </>
            ) : null}
        </div>
    );
}

export default function FilmSummaryShotTimeline({ shots, selections, durationMs, currentTimeMs, onToggleShot, onTrimChange, onSeek, t }) {
    const trackRef = useRef(null);
    const [dragging, setDragging] = useState(null); // { sceneId, edge } | null

    const shotsById = useMemo(() => new Map(shots.map((shot) => [shot.scene_id, shot])), [shots]);
    const safeDurationMs = Math.max(1000, durationMs);

    useEffect(() => {
        if (!dragging) return undefined;
        const shot = shotsById.get(dragging.sceneId);
        const selection = selections[dragging.sceneId];
        if (!shot || !selection) return undefined;

        const handleMove = (e) => {
            const ms = msFromClientX(trackRef.current, e.clientX, safeDurationMs);
            if (dragging.edge === "start") {
                const next = clamp(ms, shot.start_ms, selection.endMs - MIN_TRIM_MS);
                onTrimChange(shot.scene_id, { startMs: next, endMs: selection.endMs });
                onSeek(next);
            } else {
                const next = clamp(ms, selection.startMs + MIN_TRIM_MS, shot.end_ms);
                onTrimChange(shot.scene_id, { startMs: selection.startMs, endMs: next });
                onSeek(next);
            }
        };
        const handleUp = () => setDragging(null);
        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
        return () => {
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dragging, shotsById, selections, safeDurationMs]);

    const handleTrackClick = (e) => {
        if (dragging) return;
        onSeek(msFromClientX(trackRef.current, e.clientX, safeDurationMs));
    };

    const playheadPercent = clamp((currentTimeMs / safeDurationMs) * 100, 0, 100);

    return (
        <div
            ref={trackRef}
            onClick={handleTrackClick}
            className="relative h-20 w-full select-none touch-none rounded-lg bg-slate-200 dark:bg-black/40 cursor-pointer"
        >
            <div className="absolute top-0 h-full w-[2px] bg-white/80 z-30" style={{ left: `${playheadPercent}%` }} />
            {shots.map((shot) => {
                const selection = selections[shot.scene_id];
                if (!selection) return null;
                return (
                    <ShotBlock
                        key={shot.scene_id}
                        shot={shot}
                        selection={selection}
                        durationMs={safeDurationMs}
                        onToggle={onToggleShot}
                        onHandlePointerDown={(sceneId, edge) => setDragging({ sceneId, edge })}
                        t={t}
                    />
                );
            })}
        </div>
    );
}

export function shotTimelineLegend(shot, selection, t) {
    if (!selection?.enabled) return t("filmSummary.manual.shotDisabled", "Non inclus");
    return `${formatMsClock(selection.startMs)} - ${formatMsClock(selection.endMs)}`;
}
