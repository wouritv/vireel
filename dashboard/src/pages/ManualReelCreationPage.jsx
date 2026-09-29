import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Film, Loader2, Scissors } from "lucide-react";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";

// "Creation manuelle" at the project level: promotes the job-scoped
// CustomReelModal trim UI to something reachable any time from a reel
// project's page (see the "Creation manuelle" button in ReelsPage.jsx),
// with a waveform view of the full scene and a transcript panel whose
// words highlight in sync with playback -- so picking a range to cut
// doesn't require scrubbing blind. Backed by GET /api/projects/{id}/
// manual-scene (source video + waveform image + whole-scene transcript)
// and the existing POST /api/reels/{job_id}/custom-clip (with an explicit
// project_id, since this page can be opened long after the generation
// job's in-memory state is gone).

const MIN_CLIP_SECONDS = 3;
const MAX_CLIP_SECONDS = 120;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const formatTime = (seconds) => {
    const total = Math.max(0, Math.round(seconds));
    const m = Math.floor(total / 60);
    const s = total % 60;
    return `${m}:${String(s).padStart(2, "0")}`;
};

// Mirrors remotion/lib/captions.ts's getActiveWordIndex, kept as a small
// standalone copy here (this page renders as a plain <video>, driven by
// its own timeupdate event, not Remotion's frame clock).
function findActiveWordIndex(words, timeMs) {
    for (let i = 0; i < words.length; i += 1) {
        if (timeMs >= words[i].startMs && timeMs < words[i].endMs) return i;
    }
    return -1;
}

export default function ManualReelCreationPage() {
    const { projectId } = useParams();
    const navigate = useNavigate();
    const { t } = useTranslation();
    const { user } = useAuth();
    const videoRef = useRef(null);
    const trackRef = useRef(null);

    const [scene, setScene] = useState(null);
    const [loading, setLoading] = useState(true);
    const [loadError, setLoadError] = useState("");

    const [startMs, setStartMs] = useState(0);
    const [endMs, setEndMs] = useState(0);
    const [dragging, setDragging] = useState(null); // 'start' | 'end' | null
    const [currentTimeMs, setCurrentTimeMs] = useState(0);
    const [title, setTitle] = useState("");
    const [isGenerating, setIsGenerating] = useState(false);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!user?.id || !projectId) return;
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                setLoadError("");
                const response = await fetch(getApiUrl(`/api/projects/${projectId}/manual-scene`), {
                    headers: { ...getAuthHeaders(user.id) },
                });
                if (!response.ok) {
                    throw new Error(await response.text());
                }
                const data = await response.json();
                if (cancelled) return;
                setScene(data);
                if (data.available) {
                    const durationMs = Math.max(1000, Math.round((data.duration_seconds || 0) * 1000));
                    setStartMs(0);
                    setEndMs(Math.min(durationMs, 30000));
                }
            } catch (err) {
                if (!cancelled) setLoadError(err.message || t("manualReel.loadFailed", "Impossible de charger la scene."));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [user?.id, projectId, t]);

    const durationMs = Math.max(1000, Math.round((scene?.duration_seconds || 0) * 1000));
    const words = scene?.words || [];

    useEffect(() => {
        if (!dragging) return undefined;
        const msFromClientX = (clientX) => {
            const track = trackRef.current;
            if (!track) return 0;
            const rect = track.getBoundingClientRect();
            if (rect.width <= 0) return 0;
            const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
            return Math.round(ratio * durationMs);
        };
        const minGapMs = MIN_CLIP_SECONDS * 1000;
        const handleMove = (e) => {
            const ms = msFromClientX(e.clientX);
            if (dragging === "start") {
                setStartMs((prevStart) => {
                    const next = clamp(ms, 0, durationMs - minGapMs);
                    return Math.min(next, endMs - minGapMs);
                });
            } else {
                setEndMs((prevEnd) => {
                    const next = clamp(ms, minGapMs, durationMs);
                    return Math.max(next, startMs + minGapMs);
                });
            }
            if (videoRef.current) videoRef.current.currentTime = ms / 1000;
        };
        const handleUp = () => setDragging(null);
        window.addEventListener("pointermove", handleMove);
        window.addEventListener("pointerup", handleUp);
        return () => {
            window.removeEventListener("pointermove", handleMove);
            window.removeEventListener("pointerup", handleUp);
        };
    }, [dragging, startMs, endMs, durationMs]);

    const selectedSeconds = (endMs - startMs) / 1000;
    const durationValid = selectedSeconds >= MIN_CLIP_SECONDS && selectedSeconds <= MAX_CLIP_SECONDS;
    const startPercent = useMemo(() => clamp((startMs / durationMs) * 100, 0, 100), [startMs, durationMs]);
    const endPercent = useMemo(() => clamp((endMs / durationMs) * 100, 0, 100), [endMs, durationMs]);
    const playheadPercent = useMemo(() => clamp((currentTimeMs / durationMs) * 100, 0, 100), [currentTimeMs, durationMs]);

    const activeWordIndex = useMemo(() => findActiveWordIndex(words, currentTimeMs), [words, currentTimeMs]);

    const handleTimeUpdate = () => {
        if (videoRef.current) setCurrentTimeMs(videoRef.current.currentTime * 1000);
    };

    const seekTo = (ms) => {
        if (videoRef.current) videoRef.current.currentTime = clamp(ms, 0, durationMs) / 1000;
    };

    const handleTrackClick = (e) => {
        if (dragging) return;
        const track = trackRef.current;
        if (!track) return;
        const rect = track.getBoundingClientRect();
        const ratio = clamp((e.clientX - rect.left) / rect.width, 0, 1);
        seekTo(ratio * durationMs);
    };

    const handleGenerate = async () => {
        if (!durationValid || !scene?.job_id) return;
        setIsGenerating(true);
        setError("");
        try {
            const res = await fetch(getApiUrl(`/api/reels/${scene.job_id}/custom-clip`), {
                method: "POST",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user?.id) },
                body: JSON.stringify({
                    start_ms: Math.round(startMs),
                    end_ms: Math.round(endMs),
                    title: title.trim() || undefined,
                    project_id: projectId,
                }),
            });
            if (!res.ok) {
                const raw = await res.text();
                let detail = raw;
                try {
                    detail = JSON.parse(raw)?.detail || raw;
                } catch {
                    // keep raw fallback
                }
                throw new Error(detail || t("manualReel.generateFailed", "La generation du reel a echoue."));
            }
            navigate(`/dashboard/reels/projects/${projectId}`);
        } catch (err) {
            setError(err.message || t("manualReel.generateFailed", "La generation du reel a echoue."));
        } finally {
            setIsGenerating(false);
        }
    };

    return (
        <div className="h-full flex flex-col bg-background overflow-hidden">
            <div className="border-b border-slate-200 dark:border-white/5 bg-background/50 backdrop-blur-md px-6 py-4 shrink-0 flex items-center justify-between">
                <div>
                    <h1 className="text-2xl font-black tracking-tight flex items-center gap-2">
                        <Scissors className="text-emerald-400" size={22} />
                        {t("manualReel.title", "Creation manuelle")}
                    </h1>
                    <p className="text-sm text-slate-500 dark:text-zinc-400 mt-1">
                        {t("manualReel.subtitle", "Choisissez vous-meme le passage de la scene a transformer en reel.")}
                    </p>
                </div>
                <button
                    type="button"
                    onClick={() => navigate(`/dashboard/reels/projects/${projectId}`)}
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                >
                    <ArrowLeft size={14} />
                    {t("common.back", "Retour")}
                </button>
            </div>

            <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
                {loading ? (
                    <div className="flex items-center justify-center h-64">
                        <Loader2 size={32} className="text-primary animate-spin" />
                    </div>
                ) : loadError ? (
                    <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{loadError}</div>
                ) : !scene?.available ? (
                    <div className="flex items-center justify-center h-64">
                        <div className="text-center max-w-md">
                            <p className="text-slate-500 dark:text-zinc-400 mb-2">
                                {t("manualReel.unavailable", "La video source de ce projet n'est plus disponible pour la creation manuelle.")}
                            </p>
                        </div>
                    </div>
                ) : (
                    <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,1fr)_360px] gap-6">
                        <div className="space-y-4">
                            <div className="rounded-xl border border-slate-300 dark:border-white/10 overflow-hidden bg-black">
                                <video
                                    ref={videoRef}
                                    src={getApiUrl(scene.source_url)}
                                    controls
                                    onTimeUpdate={handleTimeUpdate}
                                    className="w-full max-h-[55vh] bg-black"
                                />
                            </div>

                            <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-4">
                                <div className="mb-2 flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
                                    <span>{formatTime(startMs / 1000)}</span>
                                    <span className={durationValid ? "font-semibold text-emerald-500" : "font-semibold text-amber-500"}>
                                        {selectedSeconds.toFixed(1)}s {t("customReel.selected", "selectionnees")}
                                    </span>
                                    <span>{formatTime(endMs / 1000)}</span>
                                </div>

                                <div
                                    ref={trackRef}
                                    onClick={handleTrackClick}
                                    className="relative h-20 rounded-lg overflow-hidden select-none touch-none bg-slate-200 dark:bg-black/40 cursor-pointer"
                                >
                                    {scene.waveform_url ? (
                                        <img
                                            src={getApiUrl(scene.waveform_url)}
                                            alt=""
                                            draggable={false}
                                            className="absolute inset-0 h-full w-full object-fill opacity-70"
                                        />
                                    ) : null}
                                    <div
                                        className="absolute top-0 h-full bg-emerald-500/30"
                                        style={{ left: `${startPercent}%`, width: `${Math.max(0, endPercent - startPercent)}%` }}
                                    />
                                    <div
                                        className="absolute top-0 h-full w-[2px] bg-white/80"
                                        style={{ left: `${playheadPercent}%` }}
                                    />
                                    <div
                                        role="slider"
                                        aria-label={t("customReel.startHandle", "Debut du clip")}
                                        onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); setDragging("start"); seekTo(startMs); }}
                                        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-8 w-4 rounded-sm bg-emerald-500 border-2 border-white dark:border-[#121214] shadow cursor-ew-resize"
                                        style={{ left: `${startPercent}%` }}
                                    />
                                    <div
                                        role="slider"
                                        aria-label={t("customReel.endHandle", "Fin du clip")}
                                        onPointerDown={(e) => { e.preventDefault(); e.stopPropagation(); setDragging("end"); seekTo(endMs); }}
                                        className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-8 w-4 rounded-sm bg-emerald-500 border-2 border-white dark:border-[#121214] shadow cursor-ew-resize"
                                        style={{ left: `${endPercent}%` }}
                                    />
                                </div>

                                {!durationValid ? (
                                    <p className="mt-2 text-[11px] text-amber-500">
                                        {t("customReel.durationHint", "La duree du clip doit etre comprise entre {{min}} et {{max}} secondes.", { min: MIN_CLIP_SECONDS, max: MAX_CLIP_SECONDS })}
                                    </p>
                                ) : null}
                            </div>

                            <input
                                type="text"
                                value={title}
                                onChange={(e) => setTitle(e.target.value)}
                                placeholder={t("customReel.titlePlaceholder", "Titre du reel (optionnel)")}
                                className="w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-3 py-2 text-sm text-slate-900 dark:text-zinc-100"
                            />

                            {error ? <p className="text-xs text-red-400">{error}</p> : null}

                            <button
                                type="button"
                                onClick={handleGenerate}
                                disabled={!durationValid || isGenerating}
                                className="w-full py-3 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-400 hover:to-green-400 text-black font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] inline-flex items-center justify-center gap-2 disabled:opacity-60"
                            >
                                {isGenerating ? <Loader2 size={16} className="animate-spin" /> : <Film size={16} />}
                                {isGenerating ? t("customReel.generating", "Generation en cours...") : t("customReel.generate", "Generer ce reel")}
                            </button>
                        </div>

                        <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/[0.03] p-4 max-h-[75vh] overflow-y-auto custom-scrollbar">
                            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-3">
                                {t("manualReel.transcript", "Transcription")}
                            </h3>
                            {words.length === 0 ? (
                                <p className="text-xs text-slate-400 dark:text-zinc-500">
                                    {t("manualReel.noTranscript", "Aucune transcription disponible pour cette scene.")}
                                </p>
                            ) : (
                                <p className="text-sm leading-relaxed">
                                    {words.map((word, index) => (
                                        <span
                                            key={`${word.startMs}-${index}`}
                                            onClick={() => seekTo(word.startMs)}
                                            className={`cursor-pointer rounded px-0.5 transition-colors ${
                                                index === activeWordIndex
                                                    ? "bg-emerald-500 text-black font-semibold"
                                                    : "text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-white/10"
                                            }`}
                                        >
                                            {word.text}{" "}
                                        </span>
                                    ))}
                                </p>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
