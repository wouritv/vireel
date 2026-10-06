import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ImagePlus, Loader2, MoveVertical, Plus, Trash2, Upload, X } from 'lucide-react';
import { getApiUrl } from '../config';
import { getAuthHeaders } from '../lib/apiAuth';
import { useAuth } from '../state/AuthContext';
import { useTranslation } from '../state/LanguageContext';
import { validateVisualImageFile, validateVisualTiming } from '../lib/reelVisuals';
import RemotionPreview from './RemotionPreview';

const NEW_VISUAL_ID = '__new_visual__';
const MIN_VISUAL_DURATION = 0.2;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const toTwoDecimals = (value) => Math.round((Number(value) || 0) * 100) / 100;

// Every visual error code below is shared with the backend's own
// `detail.code` (see app.py's _validate_reel_visual_timing /
// _validate_reel_visual_image_upload) plus a couple of purely
// client-side ones (missing_file) -- one i18n lookup covers both.
const parseVisualErrorDetail = (detail, t) => {
    if (detail && typeof detail === 'object' && detail.code) {
        return t(`visualsModal.errors.${detail.code}`, detail.message || t('visualsModal.genericError', 'Une erreur est survenue.'), detail);
    }
    if (typeof detail === 'string' && detail) return detail;
    return t('visualsModal.genericError', 'Une erreur est survenue.');
};

const parseVisualApiErrorResponse = async (res, t) => {
    const raw = await res.text();
    let detail = raw;
    try {
        detail = JSON.parse(raw)?.detail ?? raw;
    } catch {
        // Keep raw fallback.
    }
    return parseVisualErrorDetail(detail, t);
};

const translateValidationError = (code, t) => t(`visualsModal.errors.${code}`, t('visualsModal.genericError', 'Une erreur est survenue.'));

export default function VisualsModal({
    isOpen,
    onClose,
    jobId,
    clipIndex,
    videoUrl,
    durationInSeconds,
    existingSubtitles = null,
    existingHook = null,
    existingEffects = null,
    onVisualsChange,
    onApply,
    isApplying = false,
    creditBlocked = false,
    creditError = '',
}) {
    const { t } = useTranslation();
    const { user } = useAuth();
    const trackRef = useRef(null);

    const reelDuration = Math.max(1, Number(durationInSeconds) || 30);

    const [visuals, setVisuals] = useState([]);
    const [isLoading, setIsLoading] = useState(false);
    const [loadError, setLoadError] = useState('');

    const [selectedVisualId, setSelectedVisualId] = useState(null);
    const [selectedDraft, setSelectedDraft] = useState(null);
    const [editError, setEditError] = useState('');
    const [isSavingTiming, setIsSavingTiming] = useState(false);
    const [isDeleting, setIsDeleting] = useState(false);

    const [newVisualDraft, setNewVisualDraft] = useState({ position: 'TOP', start_time: 0, duration: 3 });
    const [newFile, setNewFile] = useState(null);
    const [newFileName, setNewFileName] = useState('');
    const [newError, setNewError] = useState('');
    const [isUploading, setIsUploading] = useState(false);

    const [dragging, setDragging] = useState(null); // { id, mode: 'move' | 'resize', grabOffset } | null
    const selectedDraftRef = useRef(null);

    useEffect(() => {
        if (!isOpen || !jobId || clipIndex == null || clipIndex < 0) return;
        let cancelled = false;
        setIsLoading(true);
        setLoadError('');
        setSelectedVisualId(null);
        fetch(getApiUrl(`/api/reels/${jobId}/${clipIndex}/visuals`), { headers: getAuthHeaders(user?.id) })
            .then(async (res) => {
                if (!res.ok) throw new Error(await parseVisualApiErrorResponse(res, t));
                return res.json();
            })
            .then((data) => {
                if (cancelled) return;
                const items = Array.isArray(data?.items) ? data.items : [];
                setVisuals(items);
                onVisualsChange?.(items);
            })
            .catch((err) => {
                if (!cancelled) setLoadError(err.message || t('visualsModal.loadFailed', 'Impossible de charger les visuels de ce reel.'));
            })
            .finally(() => {
                if (!cancelled) setIsLoading(false);
            });
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [isOpen, jobId, clipIndex, user?.id]);

    // Re-sync the selected visual's editable draft only when the selection
    // itself changes -- not on every `visuals` update -- so an in-flight
    // drag or a just-typed number isn't stomped on by an unrelated refetch.
    useEffect(() => {
        if (!selectedVisualId) {
            setSelectedDraft(null);
            setEditError('');
            return;
        }
        const visual = visuals.find((v) => v.id === selectedVisualId);
        if (visual) {
            setSelectedDraft({ start_time: Number(visual.start_time) || 0, duration: Number(visual.duration) || 0 });
            setEditError('');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedVisualId]);

    // Kept in sync so the pointerup handler below (whose effect only
    // re-subscribes when `dragging` changes) can always read the latest
    // dragged-to value without re-adding window listeners on every pixel
    // of movement.
    useEffect(() => {
        selectedDraftRef.current = selectedDraft;
    }, [selectedDraft]);

    const selectedVisual = useMemo(
        () => visuals.find((v) => v.id === selectedVisualId) || null,
        [visuals, selectedVisualId]
    );

    const previewVisuals = useMemo(() => visuals.map((v) => ({
        id: v.id,
        position: v.position,
        startSec: Number(v.start_time) || 0,
        durationSec: Number(v.duration) || 0,
        imageUrl: v.image_url,
    })), [visuals]);

    const patchVisual = async (visualId, patch) => {
        const res = await fetch(getApiUrl(`/api/reels/${jobId}/${clipIndex}/visuals/${visualId}`), {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders(user?.id) },
            body: JSON.stringify(patch),
        });
        if (!res.ok) throw new Error(await parseVisualApiErrorResponse(res, t));
        return res.json();
    };

    const commitSelectedTiming = async (draft) => {
        if (!selectedVisualId || !draft) return;
        const validation = validateVisualTiming(draft, reelDuration, visuals, selectedVisualId);
        if (!validation.valid) {
            setEditError(translateValidationError(validation.error, t));
            const canonical = visuals.find((v) => v.id === selectedVisualId);
            if (canonical) setSelectedDraft({ start_time: Number(canonical.start_time) || 0, duration: Number(canonical.duration) || 0 });
            return;
        }
        setIsSavingTiming(true);
        setEditError('');
        try {
            const updated = await patchVisual(selectedVisualId, {
                start_time: toTwoDecimals(draft.start_time),
                duration: toTwoDecimals(draft.duration),
            });
            const next = visuals.map((v) => (v.id === selectedVisualId ? updated : v));
            setVisuals(next);
            onVisualsChange?.(next);
            setSelectedDraft({ start_time: Number(updated.start_time) || 0, duration: Number(updated.duration) || 0 });
        } catch (err) {
            setEditError(err.message || t('visualsModal.genericError', 'Une erreur est survenue.'));
            const canonical = visuals.find((v) => v.id === selectedVisualId);
            if (canonical) setSelectedDraft({ start_time: Number(canonical.start_time) || 0, duration: Number(canonical.duration) || 0 });
        } finally {
            setIsSavingTiming(false);
        }
    };

    const handleChangeSelectedPosition = async (position) => {
        if (!selectedVisualId || !selectedVisual || selectedVisual.position === position) return;
        setIsSavingTiming(true);
        setEditError('');
        try {
            const updated = await patchVisual(selectedVisualId, { position });
            const next = visuals.map((v) => (v.id === selectedVisualId ? updated : v));
            setVisuals(next);
            onVisualsChange?.(next);
        } catch (err) {
            setEditError(err.message || t('visualsModal.genericError', 'Une erreur est survenue.'));
        } finally {
            setIsSavingTiming(false);
        }
    };

    const handleDeleteSelected = async () => {
        if (!selectedVisualId) return;
        setIsDeleting(true);
        setEditError('');
        try {
            const res = await fetch(getApiUrl(`/api/reels/${jobId}/${clipIndex}/visuals/${selectedVisualId}`), {
                method: 'DELETE',
                headers: getAuthHeaders(user?.id),
            });
            if (!res.ok) throw new Error(await parseVisualApiErrorResponse(res, t));
            const next = visuals.filter((v) => v.id !== selectedVisualId);
            setVisuals(next);
            onVisualsChange?.(next);
            setSelectedVisualId(null);
        } catch (err) {
            setEditError(err.message || t('visualsModal.genericError', 'Une erreur est survenue.'));
        } finally {
            setIsDeleting(false);
        }
    };

    const handleNewFileChange = (e) => {
        const file = e.target.files?.[0] || null;
        if (!file) return;
        const validation = validateVisualImageFile(file);
        if (!validation.valid) {
            setNewError(translateValidationError(validation.error, t));
            setNewFile(null);
            setNewFileName('');
            return;
        }
        setNewError('');
        setNewFile(file);
        setNewFileName(file.name);
    };

    const handleAddVisual = async () => {
        if (!newFile) {
            setNewError(translateValidationError('missing_file', t));
            return;
        }
        const fileValidation = validateVisualImageFile(newFile);
        if (!fileValidation.valid) {
            setNewError(translateValidationError(fileValidation.error, t));
            return;
        }
        const candidate = { start_time: Number(newVisualDraft.start_time), duration: Number(newVisualDraft.duration) };
        const timingValidation = validateVisualTiming(candidate, reelDuration, visuals);
        if (!timingValidation.valid) {
            setNewError(translateValidationError(timingValidation.error, t));
            return;
        }

        setIsUploading(true);
        setNewError('');
        try {
            const formData = new FormData();
            formData.append('file', newFile);
            formData.append('position', newVisualDraft.position);
            formData.append('start_time', String(toTwoDecimals(candidate.start_time)));
            formData.append('duration', String(toTwoDecimals(candidate.duration)));

            const res = await fetch(getApiUrl(`/api/reels/${jobId}/${clipIndex}/visuals`), {
                method: 'POST',
                headers: { ...getAuthHeaders(user?.id) },
                body: formData,
            });
            if (!res.ok) throw new Error(await parseVisualApiErrorResponse(res, t));
            const created = await res.json();
            const next = [...visuals, created];
            setVisuals(next);
            onVisualsChange?.(next);
            setNewFile(null);
            setNewFileName('');
            // Pick the next free slot right after the one just added, so
            // adding several visuals in a row doesn't require retyping a
            // start time that's now guaranteed to overlap.
            const nextStart = clamp(candidate.start_time + candidate.duration, 0, Math.max(0, reelDuration - candidate.duration));
            setNewVisualDraft((prev) => ({ ...prev, start_time: toTwoDecimals(nextStart) }));
        } catch (err) {
            setNewError(err.message || t('visualsModal.genericError', 'Une erreur est survenue.'));
        } finally {
            setIsUploading(false);
        }
    };

    // --- Timeline drag mechanics -- one block per visual plus a dashed
    // draft block for the not-yet-uploaded new visual, all positioned as a
    // % of the reel's total duration. Adapted from FilmSummaryShotTimeline/
    // ManualReelCreationPage's pointermove/pointerup drag handles, keyed
    // per-block instead of a single global range.
    const timeFromClientX = (clientX) => {
        const track = trackRef.current;
        if (!track) return 0;
        const rect = track.getBoundingClientRect();
        if (rect.width <= 0) return 0;
        const ratio = clamp((clientX - rect.left) / rect.width, 0, 1);
        return ratio * reelDuration;
    };

    const startDrag = (id, mode, clientX) => {
        const timeAtPointer = timeFromClientX(clientX);
        const currentStart = id === NEW_VISUAL_ID ? newVisualDraft.start_time : (selectedDraft?.start_time ?? 0);
        setDragging({ id, mode, grabOffset: mode === 'move' ? timeAtPointer - currentStart : 0 });
    };

    useEffect(() => {
        if (!dragging) return undefined;
        const handleMove = (e) => {
            const timeAtPointer = timeFromClientX(e.clientX);
            if (dragging.id === NEW_VISUAL_ID) {
                setNewVisualDraft((prev) => {
                    if (dragging.mode === 'move') {
                        const start = clamp(timeAtPointer - dragging.grabOffset, 0, Math.max(0, reelDuration - prev.duration));
                        return { ...prev, start_time: start };
                    }
                    const duration = clamp(timeAtPointer - prev.start_time, MIN_VISUAL_DURATION, reelDuration - prev.start_time);
                    return { ...prev, duration };
                });
            } else {
                setSelectedDraft((prev) => {
                    if (!prev) return prev;
                    if (dragging.mode === 'move') {
                        const start = clamp(timeAtPointer - dragging.grabOffset, 0, Math.max(0, reelDuration - prev.duration));
                        return { ...prev, start_time: start };
                    }
                    const duration = clamp(timeAtPointer - prev.start_time, MIN_VISUAL_DURATION, reelDuration - prev.start_time);
                    return { ...prev, duration };
                });
            }
        };
        const handleUp = () => {
            const draggedId = dragging.id;
            setDragging(null);
            if (draggedId !== NEW_VISUAL_ID) {
                commitSelectedTiming(selectedDraftRef.current);
            }
        };
        window.addEventListener('pointermove', handleMove);
        window.addEventListener('pointerup', handleUp);
        return () => {
            window.removeEventListener('pointermove', handleMove);
            window.removeEventListener('pointerup', handleUp);
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [dragging, reelDuration]);

    const effectiveVisualTiming = (visual) => {
        if (selectedDraft && visual.id === selectedVisualId) return selectedDraft;
        return { start_time: Number(visual.start_time) || 0, duration: Number(visual.duration) || 0 };
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-5xl shadow-2xl relative flex flex-col md:flex-row gap-6 max-h-[90vh]">
                <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white z-10">
                    <X size={20} />
                </button>

                {/* Left: Preview */}
                <div className="flex-1 flex flex-col items-center justify-center bg-black rounded-lg border border-slate-200 dark:border-white/5 overflow-hidden relative aspect-[9/16] max-h-[600px]">
                    {videoUrl ? (
                        <RemotionPreview
                            videoUrl={videoUrl}
                            durationInSeconds={reelDuration}
                            subtitles={existingSubtitles}
                            hook={existingHook}
                            effects={existingEffects}
                            visuals={previewVisuals}
                        />
                    ) : (
                        <div className="text-xs text-zinc-500">{t('visualsModal.noPreview', 'Aucun aperçu disponible.')}</div>
                    )}
                </div>

                {/* Right: Controls */}
                <div className="w-full md:w-[22rem] flex flex-col">
                    <h3 className="title-contrast text-xl font-bold mb-4 flex items-center gap-2">
                        <ImagePlus className="text-cyan-400" /> {t('visualsModal.title', 'Visuels (split-screen)')}
                    </h3>

                    <div className="space-y-5 flex-1 overflow-y-auto custom-scrollbar pr-2">
                        {loadError ? (
                            <div className="p-2 bg-red-500/10 border border-red-500/20 text-red-400 text-[11px] rounded-lg flex items-center gap-2">
                                <AlertCircle size={12} className="shrink-0" /> {loadError}
                            </div>
                        ) : null}

                        {/* Timeline */}
                        <div>
                            <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 block">
                                {t('visualsModal.timeline', 'Chronologie')}
                            </label>
                            <div
                                ref={trackRef}
                                className="relative h-16 w-full select-none touch-none rounded-lg bg-slate-200 dark:bg-black/40"
                            >
                                {isLoading ? (
                                    <div className="absolute inset-0 flex items-center justify-center">
                                        <Loader2 size={16} className="animate-spin text-slate-400" />
                                    </div>
                                ) : null}
                                {visuals.map((visual) => {
                                    const timing = effectiveVisualTiming(visual);
                                    const leftPercent = clamp((timing.start_time / reelDuration) * 100, 0, 100);
                                    const widthPercent = clamp((timing.duration / reelDuration) * 100, 0.5, 100 - leftPercent);
                                    const isSelected = visual.id === selectedVisualId;
                                    return (
                                        <div
                                            key={visual.id}
                                            onPointerDown={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                setSelectedVisualId(visual.id);
                                                startDrag(visual.id, 'move', e.clientX);
                                            }}
                                            className={`absolute top-1 bottom-1 rounded-md border cursor-grab ${
                                                isSelected ? 'border-cyan-400 bg-cyan-500/30' : 'border-cyan-500/40 bg-cyan-500/15'
                                            }`}
                                            style={{ left: `${leftPercent}%`, width: `${widthPercent}%` }}
                                            title={`${visual.position} ${timing.start_time.toFixed(1)}s-${(timing.start_time + timing.duration).toFixed(1)}s`}
                                        >
                                            <div
                                                role="slider"
                                                aria-label={t('visualsModal.resizeHandle', 'Redimensionner')}
                                                onPointerDown={(e) => {
                                                    e.preventDefault();
                                                    e.stopPropagation();
                                                    setSelectedVisualId(visual.id);
                                                    startDrag(visual.id, 'resize', e.clientX);
                                                }}
                                                className="absolute top-0 bottom-0 right-0 w-2 cursor-ew-resize bg-cyan-400/60 rounded-r-md"
                                            />
                                        </div>
                                    );
                                })}
                                {!selectedVisualId ? (
                                    <div
                                        onPointerDown={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            startDrag(NEW_VISUAL_ID, 'move', e.clientX);
                                        }}
                                        className="absolute top-1 bottom-1 rounded-md border-2 border-dashed border-emerald-400/70 bg-emerald-500/10 cursor-grab"
                                        style={{
                                            left: `${clamp((newVisualDraft.start_time / reelDuration) * 100, 0, 100)}%`,
                                            width: `${clamp((newVisualDraft.duration / reelDuration) * 100, 0.5, 100)}%`,
                                        }}
                                        title={t('visualsModal.newVisualDraft', 'Nouveau visuel (brouillon)')}
                                    >
                                        <div
                                            role="slider"
                                            aria-label={t('visualsModal.resizeHandle', 'Redimensionner')}
                                            onPointerDown={(e) => {
                                                e.preventDefault();
                                                e.stopPropagation();
                                                startDrag(NEW_VISUAL_ID, 'resize', e.clientX);
                                            }}
                                            className="absolute top-0 bottom-0 right-0 w-2 cursor-ew-resize bg-emerald-400/70 rounded-r-md"
                                        />
                                    </div>
                                ) : null}
                            </div>
                            <div className="flex justify-between text-[10px] text-slate-400 dark:text-zinc-500 mt-1">
                                <span>0s</span>
                                <span>{reelDuration.toFixed(0)}s</span>
                            </div>
                        </div>

                        {selectedVisual && selectedDraft ? (
                            <div className="space-y-4 p-3 rounded-lg border border-slate-200 dark:border-white/5 bg-white/5">
                                <div className="flex items-center justify-between">
                                    <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider">
                                        {t('visualsModal.editVisual', 'Visuel sélectionné')}
                                    </label>
                                    <button
                                        type="button"
                                        onClick={() => setSelectedVisualId(null)}
                                        className="text-[11px] text-slate-500 dark:text-zinc-400 hover:text-slate-800 dark:hover:text-white underline"
                                    >
                                        {t('visualsModal.deselect', 'Nouveau visuel')}
                                    </button>
                                </div>

                                <img
                                    src={selectedVisual.image_url}
                                    alt=""
                                    className="w-full h-20 object-cover rounded-md border border-slate-200 dark:border-white/10"
                                />

                                <div>
                                    <label className="text-[11px] font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                                        <MoveVertical size={12} /> {t('visualsModal.position.label', 'Position')}
                                    </label>
                                    <div className="grid grid-cols-2 gap-2">
                                        {['TOP', 'BOTTOM'].map((pos) => (
                                            <button
                                                key={pos}
                                                type="button"
                                                onClick={() => handleChangeSelectedPosition(pos)}
                                                disabled={isSavingTiming}
                                                className={`py-2 px-1 rounded-lg text-xs font-bold transition-all border ${
                                                    selectedVisual.position === pos
                                                        ? 'bg-white text-black border-white'
                                                        : 'bg-white/5 text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-white/5 hover:bg-white/10'
                                                }`}
                                            >
                                                {pos === 'TOP' ? t('visualsModal.position.top', 'Haut') : t('visualsModal.position.bottom', 'Bas')}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-2">
                                    <label className="text-[11px] text-slate-500 dark:text-zinc-400">
                                        {t('visualsModal.startTime', 'Début (s)')}
                                        <input
                                            type="number"
                                            min="0"
                                            step="0.1"
                                            value={selectedDraft.start_time}
                                            onChange={(e) => setSelectedDraft((prev) => ({ ...prev, start_time: Number(e.target.value) || 0 }))}
                                            onBlur={() => commitSelectedTiming(selectedDraft)}
                                            className="mt-1 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                                        />
                                    </label>
                                    <label className="text-[11px] text-slate-500 dark:text-zinc-400">
                                        {t('visualsModal.duration', 'Durée (s)')}
                                        <input
                                            type="number"
                                            min="0.1"
                                            step="0.1"
                                            value={selectedDraft.duration}
                                            onChange={(e) => setSelectedDraft((prev) => ({ ...prev, duration: Number(e.target.value) || 0 }))}
                                            onBlur={() => commitSelectedTiming(selectedDraft)}
                                            className="mt-1 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                                        />
                                    </label>
                                </div>

                                {editError ? <p className="text-[11px] text-red-400">{editError}</p> : null}
                                {isSavingTiming ? <p className="text-[11px] text-slate-400 flex items-center gap-1"><Loader2 size={10} className="animate-spin" /> {t('visualsModal.saving', 'Enregistrement...')}</p> : null}

                                <button
                                    type="button"
                                    onClick={handleDeleteSelected}
                                    disabled={isDeleting}
                                    className="w-full py-2 rounded-lg border border-red-400/60 bg-red-500/10 hover:bg-red-500/20 text-red-300 text-xs font-bold inline-flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                    {isDeleting ? <Loader2 size={14} className="animate-spin" /> : <Trash2 size={14} />}
                                    {t('visualsModal.delete', 'Supprimer')}
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-4 p-3 rounded-lg border border-slate-200 dark:border-white/5 bg-white/5">
                                <label className="text-xs font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider block">
                                    {t('visualsModal.addVisual', 'Ajouter un visuel')}
                                </label>

                                <label className="flex items-center justify-center gap-2 py-3 rounded-lg border border-dashed border-slate-300 dark:border-white/10 text-xs text-slate-500 dark:text-zinc-400 cursor-pointer hover:border-cyan-400/60">
                                    <Upload size={14} />
                                    {newFileName || t('visualsModal.chooseImage', 'Choisir une image (JPG, PNG, WebP)')}
                                    <input type="file" accept="image/jpeg,image/jpg,image/png,image/webp" className="hidden" onChange={handleNewFileChange} />
                                </label>

                                <div>
                                    <label className="text-[11px] font-bold text-slate-500 dark:text-zinc-400 uppercase tracking-wider mb-2 flex items-center gap-2">
                                        <MoveVertical size={12} /> {t('visualsModal.position.label', 'Position')}
                                    </label>
                                    <div className="grid grid-cols-2 gap-2">
                                        {['TOP', 'BOTTOM'].map((pos) => (
                                            <button
                                                key={pos}
                                                type="button"
                                                onClick={() => setNewVisualDraft((prev) => ({ ...prev, position: pos }))}
                                                className={`py-2 px-1 rounded-lg text-xs font-bold transition-all border ${
                                                    newVisualDraft.position === pos
                                                        ? 'bg-white text-black border-white'
                                                        : 'bg-white/5 text-slate-500 dark:text-zinc-400 border-slate-200 dark:border-white/5 hover:bg-white/10'
                                                }`}
                                            >
                                                {pos === 'TOP' ? t('visualsModal.position.top', 'Haut') : t('visualsModal.position.bottom', 'Bas')}
                                            </button>
                                        ))}
                                    </div>
                                </div>

                                <div className="grid grid-cols-2 gap-2">
                                    <label className="text-[11px] text-slate-500 dark:text-zinc-400">
                                        {t('visualsModal.startTime', 'Début (s)')}
                                        <input
                                            type="number"
                                            min="0"
                                            step="0.1"
                                            value={newVisualDraft.start_time}
                                            onChange={(e) => setNewVisualDraft((prev) => ({ ...prev, start_time: Number(e.target.value) || 0 }))}
                                            className="mt-1 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                                        />
                                    </label>
                                    <label className="text-[11px] text-slate-500 dark:text-zinc-400">
                                        {t('visualsModal.duration', 'Durée (s)')}
                                        <input
                                            type="number"
                                            min="0.1"
                                            step="0.1"
                                            value={newVisualDraft.duration}
                                            onChange={(e) => setNewVisualDraft((prev) => ({ ...prev, duration: Number(e.target.value) || 0 }))}
                                            className="mt-1 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                                        />
                                    </label>
                                </div>

                                {newError ? <p className="text-[11px] text-red-400">{newError}</p> : null}

                                <button
                                    type="button"
                                    onClick={handleAddVisual}
                                    disabled={isUploading || !newFile}
                                    className="w-full py-2 rounded-lg border border-emerald-400/60 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 text-xs font-bold inline-flex items-center justify-center gap-2 disabled:opacity-50"
                                >
                                    {isUploading ? <Loader2 size={14} className="animate-spin" /> : <Plus size={14} />}
                                    {isUploading ? t('visualsModal.uploading', 'Envoi...') : t('visualsModal.add', 'Ajouter')}
                                </button>
                            </div>
                        )}

                        <div className="p-3 bg-white/5 rounded-lg border border-slate-200 dark:border-white/5 text-[11px] text-slate-500 dark:text-zinc-400">
                            {t('visualsModal.hint', "Chaque visuel occupe environ 35% de l'écran (image) pendant sa fenêtre de temps, la vidéo gardant le reste. Les visuels ne peuvent jamais se chevaucher.")}
                        </div>
                    </div>

                    {creditBlocked ? (
                        <p className="text-xs text-amber-300 mb-2 mt-2">{creditError || t('visualsModal.insufficientCredits', 'Crédits insuffisants.')}</p>
                    ) : null}

                    <button
                        onClick={() => onApply?.()}
                        disabled={isApplying || creditBlocked || visuals.length === 0}
                        className="w-full py-4 mt-2 bg-gradient-to-r from-cyan-500 to-sky-600 hover:from-cyan-400 hover:to-sky-500 text-black font-bold rounded-xl shadow-lg shadow-cyan-500/20 transition-all active:scale-[0.98] flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
                    >
                        {isApplying ? <Loader2 size={20} className="animate-spin" /> : <ImagePlus size={20} />}
                        {isApplying ? t('visualsModal.applying', 'Application...') : t('visualsModal.apply', 'Appliquer les visuels')}
                    </button>
                </div>
            </div>
        </div>
    );
}
