import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Film, Loader2, Scissors, X } from 'lucide-react';
import { getApiUrl } from '../config';
import { getAuthHeaders } from '../lib/apiAuth';
import { useAuth } from '../state/AuthContext';
import { useTranslation } from '../state/LanguageContext';

// "Reel personnalise": lets the user pick their own start/end range on the
// full source video (see GET/POST /api/reels/{jobId}/source|custom-clip in
// app.py) instead of one of the AI-selected scenes -- for when the AI
// generation isn't satisfying. The source video is only preserved for a
// limited time after a job completes (see _preserve_source_video_for_
// manual_clipping), which is why this modal is only offered when
// GET .../source reports { available: true }.

const MIN_CLIP_SECONDS = 3;
const MAX_CLIP_SECONDS = 120;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const formatTime = (seconds) => {
  const total = Math.max(0, Math.round(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
};

export default function CustomReelModal({ isOpen, onClose, jobId, sourceUrl, durationSeconds, onCreated }) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const videoRef = useRef(null);
  const trackRef = useRef(null);

  const [videoDurationSec, setVideoDurationSec] = useState(Number(durationSeconds) || 0);
  const [startMs, setStartMs] = useState(0);
  const [endMs, setEndMs] = useState(0);
  const [dragging, setDragging] = useState(null); // 'start' | 'end' | null
  const [title, setTitle] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState('');

  const durationMs = Math.max(1000, Math.round(videoDurationSec * 1000));

  useEffect(() => {
    if (!isOpen) return;
    const initialDurationMs = Math.max(1000, Math.round((Number(durationSeconds) || 0) * 1000));
    setVideoDurationSec(Number(durationSeconds) || 0);
    setStartMs(0);
    setEndMs(Math.min(initialDurationMs, Math.max(MIN_CLIP_SECONDS * 1000, Math.min(30000, initialDurationMs))));
    setTitle('');
    setError('');
    setIsGenerating(false);
  }, [isOpen, jobId, durationSeconds]);

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
      if (dragging === 'start') {
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
    window.addEventListener('pointermove', handleMove);
    window.addEventListener('pointerup', handleUp);
    return () => {
      window.removeEventListener('pointermove', handleMove);
      window.removeEventListener('pointerup', handleUp);
    };
  }, [dragging, startMs, endMs, durationMs]);

  const selectedSeconds = (endMs - startMs) / 1000;
  const durationValid = selectedSeconds >= MIN_CLIP_SECONDS && selectedSeconds <= MAX_CLIP_SECONDS;

  const startPercent = useMemo(() => clamp((startMs / durationMs) * 100, 0, 100), [startMs, durationMs]);
  const endPercent = useMemo(() => clamp((endMs / durationMs) * 100, 0, 100), [endMs, durationMs]);

  if (!isOpen) return null;

  const handleLoadedMetadata = () => {
    const real = videoRef.current?.duration;
    if (Number.isFinite(real) && real > 0) {
      setVideoDurationSec(real);
      setEndMs((prev) => Math.min(prev, Math.round(real * 1000)));
    }
  };

  const previewRange = (ms) => {
    if (videoRef.current) videoRef.current.currentTime = ms / 1000;
  };

  const handleGenerate = async () => {
    if (!durationValid) return;
    setIsGenerating(true);
    setError('');
    try {
      const res = await fetch(getApiUrl(`/api/reels/${jobId}/custom-clip`), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(user?.id),
        },
        body: JSON.stringify({
          start_ms: Math.round(startMs),
          end_ms: Math.round(endMs),
          title: title.trim() || undefined,
        }),
      });
      if (!res.ok) {
        const raw = await res.text();
        let detail = raw;
        try {
          const parsed = JSON.parse(raw);
          detail = parsed?.detail || raw;
        } catch {
          // Keep raw fallback.
        }
        throw new Error(detail || t('customReel.generateFailed', 'La generation du reel personnalise a echoue.'));
      }
      const created = await res.json();
      onCreated?.(created);
      onClose?.();
    } catch (e) {
      setError(e.message || t('customReel.generateFailed', 'La generation du reel personnalise a echoue.'));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-5 md:p-6 rounded-2xl w-full max-w-2xl shadow-2xl relative flex flex-col gap-4 max-h-[92vh] overflow-y-auto custom-scrollbar">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white z-10">
          <X size={20} />
        </button>

        <h3 className="title-contrast text-lg font-bold flex items-center gap-2">
          <Scissors className="text-emerald-400" size={18} />
          {t('customReel.title', 'Reel personnalise')}
        </h3>
        <p className="text-xs text-slate-500 dark:text-zinc-400">
          {t('customReel.subtitle', "Deplacez les curseurs pour choisir vous-meme le passage a transformer en reel.")}
        </p>

        <div className="rounded-xl border border-slate-300 dark:border-white/10 overflow-hidden bg-black">
          <video
            ref={videoRef}
            src={sourceUrl}
            controls
            onLoadedMetadata={handleLoadedMetadata}
            className="w-full max-h-[45vh] bg-black"
          />
        </div>

        <div className="px-1">
          <div className="mb-2 flex items-center justify-between text-xs text-slate-500 dark:text-zinc-400">
            <span>{formatTime(startMs / 1000)}</span>
            <span className={durationValid ? 'font-semibold text-emerald-500' : 'font-semibold text-amber-500'}>
              {selectedSeconds.toFixed(1)}s {t('customReel.selected', 'selectionnees')}
            </span>
            <span>{formatTime(endMs / 1000)}</span>
          </div>
          <div ref={trackRef} className="relative h-3 rounded-full bg-slate-300 dark:bg-white/10 select-none touch-none">
            <div
              className="absolute top-0 h-full rounded-full bg-emerald-500/50"
              style={{ left: `${startPercent}%`, width: `${Math.max(0, endPercent - startPercent)}%` }}
            />
            <div
              role="slider"
              aria-label={t('customReel.startHandle', 'Debut du clip')}
              onPointerDown={(e) => { e.preventDefault(); setDragging('start'); previewRange(startMs); }}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-6 w-6 rounded-full bg-emerald-500 border-2 border-white dark:border-[#121214] shadow cursor-ew-resize"
              style={{ left: `${startPercent}%` }}
            />
            <div
              role="slider"
              aria-label={t('customReel.endHandle', 'Fin du clip')}
              onPointerDown={(e) => { e.preventDefault(); setDragging('end'); previewRange(endMs); }}
              className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 h-6 w-6 rounded-full bg-emerald-500 border-2 border-white dark:border-[#121214] shadow cursor-ew-resize"
              style={{ left: `${endPercent}%` }}
            />
          </div>
          {!durationValid ? (
            <p className="mt-2 text-[11px] text-amber-500">
              {t('customReel.durationHint', 'La duree du clip doit etre comprise entre {{min}} et {{max}} secondes.', { min: MIN_CLIP_SECONDS, max: MAX_CLIP_SECONDS })}
            </p>
          ) : null}
        </div>

        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={t('customReel.titlePlaceholder', 'Titre du reel (optionnel)')}
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
          {isGenerating ? t('customReel.generating', 'Generation en cours...') : t('customReel.generate', 'Generer ce reel')}
        </button>
      </div>
    </div>
  );
}
