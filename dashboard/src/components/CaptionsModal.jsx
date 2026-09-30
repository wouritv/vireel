import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, Check, Loader2, MessageSquareText, Palette, Plus, RotateCcw, Save, Trash2, X } from 'lucide-react';
import { getApiUrl } from '../config';
import RemotionPreview from './RemotionPreview';
import { ANIMATION_OPTIONS, COLOR_PRESETS, HIGHLIGHT_COLOR_PRESETS, FONT_OPTIONS } from '../lib/subtitleOptions';
import { BUILTIN_CAPTION_THEMES } from '../lib/captionThemes';
import { useTranslation } from '../state/LanguageContext';
import { useAuth } from '../state/AuthContext';
import { getAuthHeaders } from '../lib/apiAuth';

const DEFAULT_STYLE = {
  positionX: 50,
  positionY: 82,
  fontFamily: 'Montserrat',
  fontSize: 14,
  fontColor: '#FFFFFF',
  highlightColor: '#FFDD00',
  borderColor: '#000000',
  borderWidth: 3,
  textShadowColor: '#000000',
  shadowBlur: 8,
  shadowOffsetX: 0,
  shadowOffsetY: 2,
  bgColor: '#000000',
  bgOpacity: 0,
  textCase: 'none',
  bold: true,
  italic: false,
  wordsPerLine: 4,
  animation: 'word-highlight',
};

const FALLBACK_LANGUAGES = {
  fr: 'French',
  en: 'English',
  es: 'Spanish',
  de: 'German',
  it: 'Italian',
  pt: 'Portuguese',
};

const EMOJI_GROUPS = {
  popular: ['🔥', '😂', '😍', '🤯', '😎', '✨', '🎯', '💥', '✅', '🚀', '💡', '👏', '🙌', '💯', '🥳', '🤩', '🤔', '😮', '😭', '❤️'],
  faces: ['😀', '😁', '😄', '😅', '🤣', '😊', '😉', '😌', '😘', '😜', '🤪', '😴', '😤', '😡', '😱', '🥶', '🥵', '🤗', '🫶', '🫠'],
  symbols: ['✅', '❌', '⚠️', '⭐', '🌟', '🔔', '📌', '📍', '➡️', '⬆️', '⬇️', '💬', '📈', '📉', '🧠', '🛠️', '🔍', '💣', '🧲', '🧩'],
  business: ['💼', '📊', '📉', '📈', '🧾', '🏆', '💰', '💵', '💸', '🪙', '⌛', '🧭', '🧮', '🏁', '🎖️', '🚨', '🧠', '📣', '📦', '🗂️'],
  social: ['📱', '🎥', '🎬', '🎤', '🎧', '📸', '📰', '🌍', '💻', '🖥️', '🕒', '📢', '🛰️', '🕹️', '🎮', '📺', '🧵', '🔁', '🔗', '🧷'],
  objects: ['🔋', '💡', '🧯', '🪄', '🎁', '📦', '🧱', '🧪', '🧬', '🔬', '🛰️', '⚙️', '🪛', '🔧', '🪜', '🪵', '🧲', '🧰', '🪙', '🧿'],
  nature: ['🌞', '🌤️', '🌈', '⛈️', '🌙', '⭐', '🌊', '🍀', '🌴', '🌻', '🌸', '🌼', '🍎', '🍋', '🍉', '🥑', '🍓', '🍇', '🌶️', '🥥'],
  flags: ['🇫🇷', '🇺🇸', '🇪🇸', '🇩🇪', '🇮🇹', '🇵🇹', '🇬🇧', '🇨🇦', '🇧🇪', '🇨🇭', '🇲🇦', '🇩🇿', '🇹🇳', '🇸🇳', '🇨🇮', '🇨🇲', '🇯🇵', '🇰🇷', '🇮🇳', '🇧🇷'],
};

const ALL_EMOJIS = Object.values(EMOJI_GROUPS).flat();

const makeLineId = (index) => `line-${index}-${Math.random().toString(36).slice(2, 8)}`;

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

const parseApiDetail = (rawText, fallback) => {
  try {
    const parsed = JSON.parse(rawText || '{}');
    return String(parsed?.detail || rawText || fallback);
  } catch {
    return String(rawText || fallback);
  }
};

const getResponsiveWordsPerLine = () => {
  if (typeof window === 'undefined') return 4;
  const width = window.innerWidth || 0;
  if (width < 480) return 4;
  if (width < 768) return 5;
  if (width < 1200) return 6;
  return 7;
};

const normalizeWord = (word = {}, lineId = '', index = 0) => ({
  id: `${lineId}-word-${index}-${Math.random().toString(36).slice(2, 6)}`,
  text: String(word.text || '').trim(),
  startMs: Number(word.startMs) || 0,
  endMs: Number(word.endMs) || 0,
  color: '#FFFFFF',
  lineId,
});

const buildLinesFromCaptions = (captions = [], chunkSize = 4) => {
  if (!Array.isArray(captions) || !captions.length) return [];
  const size = clamp(Number(chunkSize) || 4, 2, 8);
  const wordsPerBlock = size * 2;
  const lines = [];
  for (let i = 0; i < captions.length; i += wordsPerBlock) {
    const id = makeLineId(i / wordsPerBlock);
    const words = captions.slice(i, i + wordsPerBlock).map((word, idx) => normalizeWord(word, id, idx));
    lines.push({
      id,
      emoji: '',
      words,
      style: { ...DEFAULT_STYLE, wordsPerLine: size },
      startMs: words[0]?.startMs ?? 0,
      endMs: words[words.length - 1]?.endMs ?? 0,
    });
  }
  return lines;
};

const flattenLines = (lines = []) => (
  lines.flatMap((line) => {
    const style = { ...DEFAULT_STYLE, ...(line.style || {}) };
    return (line.words || []).map((word) => ({
      text: String(word.text || '').trim(),
      startMs: Number(word.startMs) || 0,
      endMs: Number(word.endMs) || 0,
      color: word.color || '#FFFFFF',
      lineId: line.id,
      lineEmoji: line.emoji || '',
      linePositionX: style.positionX,
      linePositionY: style.positionY,
      lineFontSize: style.fontSize,
      lineFontFamily: style.fontFamily,
      lineFontColor: style.fontColor,
      lineHighlightColor: style.highlightColor,
      lineAnimation: style.animation,
      lineBold: style.bold,
      lineItalic: style.italic,
      lineBorderColor: style.borderColor,
      lineBorderWidth: style.borderWidth,
      lineBgColor: style.bgColor,
      lineBgOpacity: style.bgOpacity,
      lineTextShadowColor: style.textShadowColor,
      lineShadowBlur: style.shadowBlur,
      lineShadowOffsetX: style.shadowOffsetX,
      lineShadowOffsetY: style.shadowOffsetY,
      lineTextCase: style.textCase,
    }));
  }).filter((word) => word.text.length > 0)
);

const styleFromSavedWord = (word = {}, fallbackWordsPerLine = 4) => ({
  ...DEFAULT_STYLE,
  positionX: Number.isFinite(Number(word.linePositionX)) ? Number(word.linePositionX) : DEFAULT_STYLE.positionX,
  positionY: Number.isFinite(Number(word.linePositionY)) ? Number(word.linePositionY) : DEFAULT_STYLE.positionY,
  fontSize: Number.isFinite(Number(word.lineFontSize)) ? Number(word.lineFontSize) : DEFAULT_STYLE.fontSize,
  fontFamily: String(word.lineFontFamily || DEFAULT_STYLE.fontFamily),
  fontColor: String(word.lineFontColor || DEFAULT_STYLE.fontColor),
  highlightColor: String(word.lineHighlightColor || DEFAULT_STYLE.highlightColor),
  borderColor: String(word.lineBorderColor || DEFAULT_STYLE.borderColor),
  borderWidth: Number.isFinite(Number(word.lineBorderWidth)) ? Number(word.lineBorderWidth) : DEFAULT_STYLE.borderWidth,
  bgColor: String(word.lineBgColor || DEFAULT_STYLE.bgColor),
  bgOpacity: Number.isFinite(Number(word.lineBgOpacity)) ? Number(word.lineBgOpacity) : DEFAULT_STYLE.bgOpacity,
  textShadowColor: String(word.lineTextShadowColor || DEFAULT_STYLE.textShadowColor),
  shadowBlur: Number.isFinite(Number(word.lineShadowBlur)) ? Number(word.lineShadowBlur) : DEFAULT_STYLE.shadowBlur,
  shadowOffsetX: Number.isFinite(Number(word.lineShadowOffsetX)) ? Number(word.lineShadowOffsetX) : DEFAULT_STYLE.shadowOffsetX,
  shadowOffsetY: Number.isFinite(Number(word.lineShadowOffsetY)) ? Number(word.lineShadowOffsetY) : DEFAULT_STYLE.shadowOffsetY,
  textCase: String(word.lineTextCase || DEFAULT_STYLE.textCase),
  animation: String(word.lineAnimation || DEFAULT_STYLE.animation),
  bold: Boolean(word.lineBold ?? DEFAULT_STYLE.bold),
  italic: Boolean(word.lineItalic ?? DEFAULT_STYLE.italic),
  wordsPerLine: clamp(Number(fallbackWordsPerLine) || DEFAULT_STYLE.wordsPerLine, 2, 8),
});

const buildLinesFromSavedSubtitleConfig = (subtitleConfig = {}) => {
  if (!subtitleConfig || typeof subtitleConfig !== 'object') return [];
  const captions = Array.isArray(subtitleConfig.captions) ? subtitleConfig.captions : [];
  if (!captions.length) return [];

  const fallbackWordsPerLine = clamp(Number(subtitleConfig?.style?.wordsPerLine) || getResponsiveWordsPerLine(), 2, 8);
  const grouped = new Map();
  captions.forEach((word, idx) => {
    const lineId = String(word?.lineId || `line-${Math.floor(idx / (fallbackWordsPerLine * 2))}`);
    if (!grouped.has(lineId)) grouped.set(lineId, []);
    grouped.get(lineId).push(word || {});
  });

  return Array.from(grouped.entries()).map(([lineId, words]) => {
    const lineWords = words.map((word, idx) => ({
      id: `${lineId}-word-${idx}-${Math.random().toString(36).slice(2, 6)}`,
      text: String(word?.text || '').trim(),
      startMs: Number(word?.startMs) || 0,
      endMs: Number(word?.endMs) || 0,
      color: String(word?.color || '#FFFFFF'),
      lineId,
    })).filter((word) => word.text.length > 0);
    const seedWord = words[0] || {};
    const lineStart = lineWords[0]?.startMs ?? 0;
    const lineEnd = lineWords[lineWords.length - 1]?.endMs ?? lineStart;
    return {
      id: lineId,
      emoji: String(seedWord?.lineEmoji || ''),
      words: lineWords,
      style: styleFromSavedWord(seedWord, fallbackWordsPerLine),
      startMs: lineStart,
      endMs: lineEnd,
    };
  }).filter((line) => line.words.length > 0);
};

const rebalanceLineWords = (line, words) => {
  const base = words.filter((word) => String(word.text || '').trim().length > 0);
  if (!base.length) return line.words;
  const lineStart = Number(line.startMs || base[0].startMs || 0);
  const lineEnd = Math.max(lineStart + 300, Number(line.endMs || base[base.length - 1].endMs || lineStart + 1200));
  const segment = Math.max(120, Math.floor((lineEnd - lineStart) / base.length));
  return base.map((word, idx) => {
    const startMs = lineStart + idx * segment;
    return {
      ...word,
      startMs,
      endMs: idx === base.length - 1 ? lineEnd : startMs + segment,
      id: word.id || `${line.id}-word-${idx}`,
    };
  });
};

export default function CaptionsModal({
  isOpen,
  onClose,
  onGenerate,
  isProcessing,
  creditBlocked = false,
  creditError = '',
  videoUrl,
  jobId,
  clipIndex,
  existingHook,
  existingEffects,
  onResetStyles,
  isResettingStyles = false,
}) {
  const { t } = useTranslation();
  const { user } = useAuth();
  const previewRef = useRef(null);

  const [lines, setLines] = useState([]);
  const [durationSec, setDurationSec] = useState(30);
  // Clean, pre-caption source resolved server-side (see /api/clip/.../
  // transcript in app.py) -- used as the render base so the new style
  // replaces the default captions instead of stacking on top of them.
  const [cleanVideoUrl, setCleanVideoUrl] = useState('');
  const [captionsLoading, setCaptionsLoading] = useState(false);
  const [fetchError, setFetchError] = useState('');
  const [selectedLineId, setSelectedLineId] = useState(null);
  const [showStyleEditor, setShowStyleEditor] = useState(false);
  const [showThemePicker, setShowThemePicker] = useState(false);
  const [customThemes, setCustomThemes] = useState([]);
  const [themesLoading, setThemesLoading] = useState(false);
  const [themesError, setThemesError] = useState('');
  const [activeThemeId, setActiveThemeId] = useState(null);
  const [saveThemeName, setSaveThemeName] = useState('');
  const [isSavingTheme, setIsSavingTheme] = useState(false);
  const [saveThemeMessage, setSaveThemeMessage] = useState('');
  const [showInlineThemeNamePrompt, setShowInlineThemeNamePrompt] = useState(false);
  const [isSavingDefaultStyle, setIsSavingDefaultStyle] = useState(false);
  const [saveDefaultStyleMessage, setSaveDefaultStyleMessage] = useState('');
  const [deletingThemeId, setDeletingThemeId] = useState(null);

  const [translationEnabled, setTranslationEnabled] = useState(false);
  const [translateText, setTranslateText] = useState(true);
  const [targetLanguage, setTargetLanguage] = useState('fr');
  const [languages, setLanguages] = useState(FALLBACK_LANGUAGES);
  const [isTranslating, setIsTranslating] = useState(false);
  const [translationError, setTranslationError] = useState('');
  const [wordsPerLineTouched, setWordsPerLineTouched] = useState(false);
  const [emojiLineId, setEmojiLineId] = useState(null);
  const [emojiGroup, setEmojiGroup] = useState('popular');
  const [emojiSearch, setEmojiSearch] = useState('');

  const selectedLine = useMemo(() => lines.find((line) => line.id === selectedLineId) || null, [lines, selectedLineId]);
  const flattenedCaptions = useMemo(() => flattenLines(lines), [lines]);

  // A single style applies to the whole video: Subtitles.tsx (both the
  // dashboard preview and the render-service export renderer) only ever
  // reads one SubtitleStyle for the whole composition, not one per line.
  // Every line's `.style` is kept in sync on every edit so that
  // subtitleConfig.style, sourced from lines[0].style, always reflects it.
  const currentStyle = useMemo(() => ({ ...DEFAULT_STYLE, ...(lines[0]?.style || {}) }), [lines]);

  // Which of the user's own saved themes (if any) the style editor is
  // currently "on" -- null when activeThemeId points at a built-in,
  // ready-to-use theme instead, or when no theme has been applied at all
  // (the default view / a from-scratch manual edit). Drives whether the
  // "Enregistrer" button below overwrites this theme directly or first
  // asks for a name to save a new one under.
  const activeCustomTheme = useMemo(
    () => customThemes.find((theme) => theme.id === activeThemeId) || null,
    [customThemes, activeThemeId]
  );

  const subtitleConfig = useMemo(() => ({
    captions: flattenedCaptions,
    style: currentStyle,
  }), [flattenedCaptions, currentStyle]);

  const visibleEmojis = useMemo(() => {
    const term = String(emojiSearch || '').trim();
    if (term) return ALL_EMOJIS.filter((emoji) => emoji.includes(term));
    return EMOJI_GROUPS[emojiGroup] || EMOJI_GROUPS.popular;
  }, [emojiGroup, emojiSearch]);

  const updateLine = (lineId, updater) => {
    setLines((prev) => prev.map((line) => (line.id === lineId ? updater(line) : line)));
  };

  const updateAllLinesStyle = (patch) => {
    setLines((prev) => prev.map((line) => ({ ...line, style: { ...DEFAULT_STYLE, ...(line.style || {}), ...patch } })));
  };

  const resetStyle = () => {
    setLines((prev) => prev.map((line) => ({ ...line, style: { ...DEFAULT_STYLE } })));
  };

  const applyWordsPerLine = (nextWordsPerLine) => {
    const size = clamp(Number(nextWordsPerLine) || 4, 2, 8);
    const allWords = flattenLines(lines).map((word) => ({
      text: word.text,
      startMs: word.startMs,
      endMs: word.endMs,
      color: word.color || '#FFFFFF',
    }));
    const nextLines = buildLinesFromCaptions(allWords, size).map((line) => ({
      ...line,
      style: {
        ...DEFAULT_STYLE,
        ...(lines[0]?.style || {}),
        wordsPerLine: size,
      },
    }));
    setLines(nextLines);
    setSelectedLineId(nextLines[0]?.id || null);
  };

  const focusPreviewLine = (lineId) => {
    const line = lines.find((item) => item.id === lineId);
    if (!line) return;
    previewRef.current?.seekToMs?.(line.startMs || 0);
  };

  const focusSelectedPreview = () => {
    if (selectedLine) focusPreviewLine(selectedLine.id);
  };

  // Applying a theme is a full style replacement, not a merge -- if the
  // theme also changes wordsPerLine, regroup the words into new lines the
  // same way the "Words per line" slider already does (applyWordsPerLine)
  // before laying the theme's style on top, so the stored wordsPerLine
  // value always matches the actual line grouping.
  const applyTheme = (theme, isCustom = false) => {
    if (!theme?.style) return;
    const nextWordsPerLine = clamp(Number(theme.style.wordsPerLine) || DEFAULT_STYLE.wordsPerLine, 2, 8);
    const activeWordsPerLine = currentStyle.wordsPerLine || DEFAULT_STYLE.wordsPerLine;
    if (nextWordsPerLine !== activeWordsPerLine) {
      setWordsPerLineTouched(true);
      applyWordsPerLine(nextWordsPerLine);
    }
    updateAllLinesStyle(theme.style);
    setActiveThemeId(theme.id || null);
    setSaveThemeName(isCustom ? theme.name || '' : '');
    setSaveThemeMessage('');
    setShowInlineThemeNamePrompt(false);
    focusSelectedPreview();
  };

  // `nameOverride` lets the "Enregistrer" button next to "Definir comme
  // style par defaut" update the currently active custom theme directly
  // (its own name, no prompt) while still sharing this same save path with
  // the name-input row below, whose button calls this with no argument
  // (its click handler passes the DOM event, not a string, so that falls
  // back to saveThemeName as before).
  const handleSaveTheme = async (nameOverride) => {
    const name = (typeof nameOverride === 'string' ? nameOverride : saveThemeName).trim();
    if (!name) return;
    setIsSavingTheme(true);
    setSaveThemeMessage('');
    try {
      const res = await fetch(getApiUrl('/api/caption-style-themes'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(user?.id),
        },
        body: JSON.stringify({ name, style: currentStyle }),
      });
      if (!res.ok) {
        const raw = await res.text();
        throw new Error(parseApiDetail(raw, t('captionsModal.themeSaveFailed', "Echec de l'enregistrement du theme.")));
      }
      const saved = await res.json();
      setCustomThemes((prev) => [saved, ...prev.filter((theme) => theme.id !== saved.id)]);
      setActiveThemeId(saved.id);
      setSaveThemeName(saved.name || name);
      setSaveThemeMessage(t('captionsModal.themeSaved', 'Theme enregistre.'));
      setShowInlineThemeNamePrompt(false);
    } catch (error) {
      setSaveThemeMessage(error.message || t('captionsModal.themeSaveFailed', "Echec de l'enregistrement du theme."));
    } finally {
      setIsSavingTheme(false);
    }
  };

  // The single "Enregistrer" button next to "Definir comme style par
  // defaut": on one of the user's own themes, it overwrites it right away;
  // on a ready-to-use built-in theme or the default/manual view, there is
  // no existing name to reuse, so it opens the inline prompt below instead.
  const handleSaveButtonClick = () => {
    if (activeCustomTheme) {
      handleSaveTheme(activeCustomTheme.name);
      return;
    }
    setSaveThemeMessage('');
    setSaveThemeName('');
    setShowInlineThemeNamePrompt(true);
  };

  // Replaces what new reels/captions get auto-captioned with, going
  // forward -- stored server-side as a style_edit_versions row (see
  // PUT /api/caption-style-default in app.py) rather than only ever living
  // as this component's own DEFAULT_STYLE constant, so it survives across
  // sessions/devices and future clips actually pick it up.
  const handleSetAsDefaultStyle = async () => {
    setIsSavingDefaultStyle(true);
    setSaveDefaultStyleMessage('');
    try {
      const res = await fetch(getApiUrl('/api/caption-style-default'), {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(user?.id),
        },
        body: JSON.stringify({
          position: 'bottom',
          position_x: currentStyle.positionX,
          position_y: currentStyle.positionY,
          font_size: currentStyle.fontSize,
          font_name: currentStyle.fontFamily,
          font_color: currentStyle.fontColor,
          highlight_color: currentStyle.highlightColor,
          border_color: currentStyle.borderColor,
          border_width: currentStyle.borderWidth,
          text_shadow_color: currentStyle.textShadowColor,
          shadow_blur: currentStyle.shadowBlur,
          shadow_offset_x: currentStyle.shadowOffsetX,
          shadow_offset_y: currentStyle.shadowOffsetY,
          bg_color: currentStyle.bgColor,
          bg_opacity: currentStyle.bgOpacity,
          text_case: currentStyle.textCase,
          bold: currentStyle.bold,
          italic: currentStyle.italic,
          words_per_line: currentStyle.wordsPerLine,
          animation: currentStyle.animation,
        }),
      });
      if (!res.ok) {
        const raw = await res.text();
        throw new Error(parseApiDetail(raw, t('captionsModal.setDefaultFailed', "Echec de la mise a jour du style par defaut.")));
      }
      setSaveDefaultStyleMessage(t('captionsModal.setDefaultSuccess', 'Ce style est maintenant le style par defaut.'));
    } catch (error) {
      setSaveDefaultStyleMessage(error.message || t('captionsModal.setDefaultFailed', "Echec de la mise a jour du style par defaut."));
    } finally {
      setIsSavingDefaultStyle(false);
      setTimeout(() => setSaveDefaultStyleMessage(''), 3000);
    }
  };

  const handleDeleteTheme = async (themeId) => {
    setDeletingThemeId(themeId);
    try {
      const res = await fetch(getApiUrl(`/api/caption-style-themes/${themeId}`), {
        method: 'DELETE',
        headers: getAuthHeaders(user?.id),
      });
      if (res.ok) {
        setCustomThemes((prev) => prev.filter((theme) => theme.id !== themeId));
        setActiveThemeId((prev) => (prev === themeId ? null : prev));
      }
    } finally {
      setDeletingThemeId(null);
    }
  };

  const updateWordText = (lineId, wordId, text) => {
    updateLine(lineId, (line) => {
      const words = line.words.map((word) => (word.id === wordId ? { ...word, text } : word));
      return { ...line, words: rebalanceLineWords(line, words) };
    });
  };

  const deleteWord = (lineId, wordId) => {
    updateLine(lineId, (line) => {
      const remaining = line.words.filter((word) => word.id !== wordId);
      if (!remaining.length) return line;
      return { ...line, words: rebalanceLineWords(line, remaining) };
    });
  };

  const addWord = (lineId) => {
    updateLine(lineId, (line) => {
      const words = [...line.words, {
        id: `${line.id}-word-${Date.now().toString(36)}`,
        text: t('captionsModal.newWord', 'new'),
        color: '#FFFFFF',
        lineId,
      }];
      return { ...line, words: rebalanceLineWords(line, words) };
    });
  };

  const appendEmojiToLineEnd = (lineId, emoji) => {
    if (!emoji) return;
    updateLine(lineId, (line) => {
      if (!line.words?.length) return line;
      const lastWordIndex = line.words.length - 1;
      return {
        ...line,
        emoji: '',
        words: line.words.map((word, idx) => (
          idx === lastWordIndex
            ? { ...word, text: `${String(word.text || '').trim()} ${emoji}`.trim() }
            : word
        )),
      };
    });
    setEmojiLineId(null);
    setEmojiSearch('');
    focusPreviewLine(lineId);
  };

  useEffect(() => {
    if (!isOpen || !jobId || clipIndex == null || clipIndex < 0) return;
    let cancelled = false;

    const headers = getAuthHeaders(user?.id);

    setCaptionsLoading(true);
    setFetchError('');
    setTranslationError('');
    setEmojiLineId(null);
    setEmojiSearch('');
    fetch(getApiUrl(`/api/clip/${jobId}/${clipIndex}/transcript`), { headers })
      .then(async (res) => {
        if (!res.ok) {
          const raw = await res.text();
          throw new Error(parseApiDetail(raw, t('captionsModal.loadFailed', 'Unable to load subtitles for this clip.')));
        }
        return res.json();
      })
      .then((data) => {
        if (cancelled) return;
        const responsiveWords = getResponsiveWordsPerLine();
        const restoredLines = buildLinesFromSavedSubtitleConfig(data?.subtitleConfig || {});
        const nextLines = restoredLines.length > 0
          ? restoredLines
          : buildLinesFromCaptions(data?.captions || [], responsiveWords);
        if (!nextLines.length) {
          setFetchError(t('captionsModal.noCaptions', 'No captions available for this clip.'));
        }
        setLines(nextLines);
        setSelectedLineId(nextLines[0]?.id || null);
        setDurationSec(Number(data?.durationSec) > 0 ? Number(data.durationSec) : 30);
        setCleanVideoUrl(typeof data?.cleanVideoUrl === 'string' ? data.cleanVideoUrl : '');
        setWordsPerLineTouched(false);
      })
      .catch((err) => {
        if (!cancelled) {
          setLines([]);
          setFetchError(err?.message || t('captionsModal.loadFailed', 'Unable to load subtitles for this clip.'));
        }
      })
      .finally(() => {
        if (!cancelled) setCaptionsLoading(false);
      });

    fetch(getApiUrl('/api/translate/languages'), { headers })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (cancelled || !Array.isArray(data?.languages)) return;
        const mapped = {};
        data.languages.forEach((item) => {
          if (item?.code && item?.name) mapped[item.code] = item.name;
        });
        if (Object.keys(mapped).length > 0) {
          setLanguages(mapped);
          setTargetLanguage((prev) => (mapped[prev] ? prev : Object.keys(mapped)[0]));
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [clipIndex, isOpen, jobId, t, user?.id]);

  useEffect(() => {
    if (!isOpen || wordsPerLineTouched) return;
    const onResize = () => {
      if (!Array.isArray(lines) || lines.length === 0) return;
      applyWordsPerLine(getResponsiveWordsPerLine());
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [isOpen, lines, wordsPerLineTouched]);

  const handleApplyTranslation = async () => {
    if (!translationEnabled || !translateText || !targetLanguage || !jobId) return;
    setIsTranslating(true);
    setTranslationError('');
    try {
      const payload = {
        job_id: jobId,
        clip_index: clipIndex,
        target_language: targetLanguage,
      };
      const stableInput = videoUrl && !videoUrl.startsWith('blob:') ? videoUrl : undefined;
      if (stableInput) payload.input_url = stableInput;
      const res = await fetch(getApiUrl('/api/translate/captions'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(user?.id),
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const errorText = await res.text();
        setTranslationError(errorText || t('captionsModal.translationFailed', 'Subtitle translation failed.'));
        return;
      }
      const data = await res.json();
      const translated = Array.isArray(data?.captions) ? data.captions : [];
      const nextLines = buildLinesFromCaptions(translated, getResponsiveWordsPerLine());
      setLines(nextLines);
      setSelectedLineId(nextLines[0]?.id || null);
      if (Number(data?.durationSec) > 0) setDurationSec(Number(data.durationSec));
    } catch (error) {
      setTranslationError(error.message || t('captionsModal.translationFailed', 'Subtitle translation failed.'));
    } finally {
      setIsTranslating(false);
    }
  };

  useEffect(() => {
    if (showStyleEditor && lines.length === 0) {
      setShowStyleEditor(false);
    }
  }, [showStyleEditor, lines.length]);

  useEffect(() => {
    if (showThemePicker && lines.length === 0) {
      setShowThemePicker(false);
    }
  }, [showThemePicker, lines.length]);

  useEffect(() => {
    if (!isOpen) return undefined;
    let cancelled = false;
    setThemesLoading(true);
    setThemesError('');
    fetch(getApiUrl('/api/caption-style-themes'), { headers: getAuthHeaders(user?.id) })
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error('themes_unavailable'))))
      .then((data) => {
        if (cancelled) return;
        setCustomThemes(Array.isArray(data?.themes) ? data.themes : []);
      })
      .catch(() => {
        if (!cancelled) setThemesError(t('captionsModal.themesLoadFailed', 'Impossible de charger vos themes.'));
      })
      .finally(() => {
        if (!cancelled) setThemesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [isOpen, user?.id, t]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
      <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-5 md:p-6 rounded-2xl w-full max-w-7xl shadow-2xl relative flex flex-col md:flex-row gap-5 md:gap-6 max-h-[92vh] overflow-x-hidden">
        <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white z-10">
          <X size={20} />
        </button>

        <div className="w-full md:w-[50%] rounded-xl border border-slate-300 dark:border-white/10 bg-slate-50 dark:bg-black/30 p-4 md:p-5 overflow-y-auto overflow-x-hidden custom-scrollbar">
          {showStyleEditor && lines.length > 0 ? (
            <>
              <div className="mb-2 flex items-center justify-between gap-2">
                <button onClick={() => setShowStyleEditor(false)} className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <ArrowLeft size={14} /> {t('captionsModal.back', 'Retour')}
                </button>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white">{t('captionsModal.styleEditor', 'Edition de style')}</h4>
              </div>

              <div className="mb-4 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={handleSetAsDefaultStyle}
                    disabled={isSavingDefaultStyle}
                    className="rounded-lg border border-emerald-400/60 dark:border-emerald-500/40 bg-emerald-50 dark:bg-emerald-500/10 hover:bg-emerald-100 dark:hover:bg-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-200 disabled:opacity-40 inline-flex items-center gap-1"
                  >
                    {isSavingDefaultStyle ? <Loader2 size={12} className="animate-spin" /> : null}
                    {t('captionsModal.setAsDefault', 'Definir comme style par defaut')}
                  </button>

                  <button
                    type="button"
                    onClick={handleSaveButtonClick}
                    disabled={isSavingTheme}
                    title={
                      activeCustomTheme
                        ? t('captionsModal.updateThemeHint', 'Met a jour le theme "{{name}}" avec le style actuel', { name: activeCustomTheme.name })
                        : t('captionsModal.saveAsNewThemeHint', 'Enregistrer le style actuel comme nouveau theme')
                    }
                    className="rounded-lg border border-sky-400/60 dark:border-sky-500/40 bg-sky-50 dark:bg-sky-500/10 hover:bg-sky-100 dark:hover:bg-sky-500/20 px-3 py-1.5 text-xs font-semibold text-sky-700 dark:text-sky-200 disabled:opacity-40 inline-flex items-center gap-1"
                  >
                    {isSavingTheme ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                    {activeCustomTheme
                      ? t('captionsModal.updateTheme', 'Enregistrer ({{name}})', { name: activeCustomTheme.name })
                      : t('captionsModal.save', 'Enregistrer')}
                  </button>
                </div>

                {saveDefaultStyleMessage ? <p className="text-[11px] text-slate-500 dark:text-slate-400">{saveDefaultStyleMessage}</p> : null}

                {showInlineThemeNamePrompt && !activeCustomTheme ? (
                  <div className="flex items-center gap-2">
                    <input
                      autoFocus
                      type="text"
                      value={saveThemeName}
                      onChange={(e) => setSaveThemeName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveTheme();
                        if (e.key === 'Escape') setShowInlineThemeNamePrompt(false);
                      }}
                      placeholder={t('captionsModal.themeNamePlaceholder', 'Nom du theme')}
                      className="flex-1 bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                    />
                    <button
                      type="button"
                      onClick={() => handleSaveTheme()}
                      disabled={isSavingTheme || !saveThemeName.trim()}
                      className="rounded-md bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-200 disabled:opacity-50 inline-flex items-center gap-1"
                    >
                      <Check size={12} />
                    </button>
                    <button
                      type="button"
                      onClick={() => setShowInlineThemeNamePrompt(false)}
                      className="rounded-md bg-slate-200 dark:bg-white/10 px-2 py-1.5 text-xs text-slate-600 dark:text-zinc-300"
                    >
                      <X size={12} />
                    </button>
                  </div>
                ) : null}

                {saveThemeMessage && !showInlineThemeNamePrompt ? (
                  <p className="text-[11px] text-slate-500 dark:text-slate-400">{saveThemeMessage}</p>
                ) : null}
              </div>

              <div className="space-y-4">
                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.freePosition', 'Free position (X/Y)')}</label>
                  <div className="mt-2 space-y-2">
                    <label className="block text-[11px] text-slate-600 dark:text-slate-300">X ({currentStyle.positionX}%)
                      <input type="range" min="5" max="95" value={currentStyle.positionX} onChange={(e) => { updateAllLinesStyle({ positionX: Number(e.target.value) || 50 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                    </label>
                    <label className="block text-[11px] text-slate-600 dark:text-slate-300">Y ({currentStyle.positionY}%)
                      <input type="range" min="5" max="95" value={currentStyle.positionY} onChange={(e) => { updateAllLinesStyle({ positionY: Number(e.target.value) || 82 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.textStyle', 'Text style')}</label>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {[
                      { key: 'normal', label: t('captionsModal.normal', 'Normal'), patch: { bold: false, italic: false } },
                      { key: 'bold', label: t('captionsModal.bold', 'Bold'), patch: { bold: true, italic: false } },
                      { key: 'italic', label: t('captionsModal.italic', 'Italic'), patch: { bold: false, italic: true } },
                    ].map((opt) => {
                      const isActive = (opt.key === 'normal' && !currentStyle.bold && !currentStyle.italic)
                        || (opt.key === 'bold' && currentStyle.bold && !currentStyle.italic)
                        || (opt.key === 'italic' && currentStyle.italic && !currentStyle.bold);
                      return (
                        <button
                          key={`style-emph-${opt.key}`}
                          type="button"
                          onClick={() => { updateAllLinesStyle(opt.patch); focusSelectedPreview(); }}
                          className={`rounded-md border px-2 py-1.5 text-xs ${isActive ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}
                        >
                          {opt.label}
                        </button>
                      );
                    })}
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2">
                    {[
                      { value: 'none', label: t('captionsModal.caseNormal', 'Normal') },
                      { value: 'uppercase', label: t('captionsModal.caseUpper', 'UPPER') },
                      { value: 'lowercase', label: t('captionsModal.caseLower', 'lower') },
                    ].map((opt) => (
                      <button
                        key={`style-case-${opt.value}`}
                        type="button"
                        onClick={() => { updateAllLinesStyle({ textCase: opt.value }); focusSelectedPreview(); }}
                        className={`rounded-md border px-2 py-1.5 text-xs ${currentStyle.textCase === opt.value ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}
                      >
                        {opt.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.animation', 'Animation')}</label>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {ANIMATION_OPTIONS.map((opt) => (
                      <button key={`style-anim-${opt.value}`} type="button" onClick={() => { updateAllLinesStyle({ animation: opt.value }); focusSelectedPreview(); }} className={`rounded-md border px-2 py-1.5 text-left ${currentStyle.animation === opt.value ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}>
                        <div className="text-xs font-medium">{opt.label}</div>
                        <div className="mt-0.5 text-[10px] leading-tight opacity-80">{opt.desc}</div>
                      </button>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.fontFamily', 'Font family')}</label>
                  <select value={currentStyle.fontFamily} onChange={(e) => { updateAllLinesStyle({ fontFamily: e.target.value }); focusSelectedPreview(); }} className="mt-2 w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100">
                    {[...new Set(FONT_OPTIONS.map((opt) => opt.category))].map((cat) => (
                      <optgroup key={cat} label={cat}>{FONT_OPTIONS.filter((opt) => opt.category === cat).map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}</optgroup>
                    ))}
                  </select>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.lineSize', 'Line size')} ({currentStyle.fontSize}px)</label>
                  <input type="range" min="14" max="96" value={currentStyle.fontSize} onChange={(e) => { updateAllLinesStyle({ fontSize: Number(e.target.value) || 14 }); focusSelectedPreview(); }} className="mt-2 w-full accent-emerald-500" />
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.textColor', 'Text color')}</label>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {COLOR_PRESETS.map((preset) => (
                      <button key={`style-${preset.color}`} type="button" onClick={() => { updateAllLinesStyle({ fontColor: preset.color }); focusSelectedPreview(); }} className={`h-6 w-6 rounded-full border-2 ${currentStyle.fontColor === preset.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20'}`} style={{ backgroundColor: preset.color }} />
                    ))}
                    <label className="relative h-6 w-6 rounded-full border border-dashed border-slate-400/80 overflow-hidden" title={t('captionsModal.customColor', 'Custom color')}>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-300">+</span>
                      <input type="color" value={currentStyle.fontColor} onChange={(e) => { updateAllLinesStyle({ fontColor: e.target.value }); focusSelectedPreview(); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.highlightColor', 'Highlight color')}</label>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    {HIGHLIGHT_COLOR_PRESETS.map((preset) => (
                      <button key={`style-hl-${preset.color}`} type="button" onClick={() => { updateAllLinesStyle({ highlightColor: preset.color }); focusSelectedPreview(); }} className={`h-6 w-6 rounded-full border-2 ${currentStyle.highlightColor === preset.color ? 'border-white scale-110' : 'border-slate-400 dark:border-white/20'}`} style={{ backgroundColor: preset.color }} />
                    ))}
                    <label className="relative h-6 w-6 rounded-full border border-dashed border-slate-400/80 overflow-hidden" title={t('captionsModal.customColor', 'Custom color')}>
                      <span className="absolute inset-0 flex items-center justify-center text-[10px] text-slate-300">+</span>
                      <input type="color" value={currentStyle.highlightColor} onChange={(e) => { updateAllLinesStyle({ highlightColor: e.target.value }); focusSelectedPreview(); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.shadowColor', 'Shadow color')}</label>
                  <div className="mt-2 flex items-center gap-3 rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 p-2">
                    <label className="relative h-7 w-7 rounded border border-slate-300 dark:border-white/10 overflow-hidden" title={t('captionsModal.shadowColor', 'Shadow color')}>
                      <div className="h-full w-full" style={{ backgroundColor: currentStyle.textShadowColor }} />
                      <input type="color" value={currentStyle.textShadowColor} onChange={(e) => { updateAllLinesStyle({ textShadowColor: e.target.value }); focusSelectedPreview(); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                    <div className="grid flex-1 grid-cols-3 gap-2 text-[10px] text-slate-400">
                      <label>{t('captionsModal.blur', 'Blur')} {currentStyle.shadowBlur}px
                        <input type="range" min="0" max="24" value={currentStyle.shadowBlur} onChange={(e) => { updateAllLinesStyle({ shadowBlur: Number(e.target.value) || 0 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                      <label>{t('captionsModal.offsetX', 'Offset X')} {currentStyle.shadowOffsetX}px
                        <input type="range" min="-20" max="20" value={currentStyle.shadowOffsetX} onChange={(e) => { updateAllLinesStyle({ shadowOffsetX: Number(e.target.value) || 0 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                      <label>{t('captionsModal.offsetY', 'Offset Y')} {currentStyle.shadowOffsetY}px
                        <input type="range" min="-20" max="20" value={currentStyle.shadowOffsetY} onChange={(e) => { updateAllLinesStyle({ shadowOffsetY: Number(e.target.value) || 0 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                    </div>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.border', 'Border')}</label>
                  <div className="mt-2 flex items-center gap-3 rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 p-2">
                    <label className="relative h-7 w-7 rounded border border-slate-300 dark:border-white/10 overflow-hidden" title={t('captionsModal.borderColor', 'Border color')}>
                      <div className="h-full w-full" style={{ backgroundColor: currentStyle.borderColor }} />
                      <input type="color" value={currentStyle.borderColor} onChange={(e) => { updateAllLinesStyle({ borderColor: e.target.value }); focusSelectedPreview(); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                    </label>
                    <label className="flex-1 text-[10px] text-slate-400">{t('captionsModal.thickness', 'Thickness')} ({currentStyle.borderWidth})
                      <input type="range" min="0" max="6" value={currentStyle.borderWidth} onChange={(e) => { updateAllLinesStyle({ borderWidth: Number(e.target.value) || 0 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                    </label>
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.wordsPerLine', 'Words per line')} ({currentStyle.wordsPerLine || 4})</label>
                  <input
                    type="range"
                    min="2"
                    max="8"
                    value={currentStyle.wordsPerLine || 4}
                    onChange={(e) => {
                      const value = clamp(Number(e.target.value) || 4, 2, 8);
                      setWordsPerLineTouched(true);
                      applyWordsPerLine(value);
                      focusSelectedPreview();
                    }}
                    className="mt-2 w-full accent-emerald-500"
                  />
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <div className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300">
                    <span>{t('captionsModal.backgroundBox', 'Background box')}</span>
                    <input
                      type="checkbox"
                      checked={currentStyle.bgOpacity > 0}
                      onChange={(e) => {
                        updateAllLinesStyle({ bgOpacity: e.target.checked ? 0.5 : 0 });
                        focusSelectedPreview();
                      }}
                    />
                  </div>
                  {currentStyle.bgOpacity > 0 ? (
                    <div className="mt-3 flex items-center gap-3">
                      <label className="relative h-7 w-7 rounded border border-slate-300 dark:border-white/10 overflow-hidden" title={t('captionsModal.backgroundColor', 'Background color')}>
                        <div className="h-full w-full" style={{ backgroundColor: currentStyle.bgColor }} />
                        <input type="color" value={currentStyle.bgColor} onChange={(e) => { updateAllLinesStyle({ bgColor: e.target.value }); focusSelectedPreview(); }} className="absolute inset-0 opacity-0 cursor-pointer" />
                      </label>
                      <label className="flex-1 text-[10px] text-slate-400">{t('captionsModal.opacity', 'Opacity')} ({Math.round((currentStyle.bgOpacity || 0) * 100)}%)
                        <input type="range" min="10" max="100" value={Math.round((currentStyle.bgOpacity || 0) * 100)} onChange={(e) => { updateAllLinesStyle({ bgOpacity: (Number(e.target.value) || 0) / 100 }); focusSelectedPreview(); }} className="mt-1 w-full accent-emerald-500" />
                      </label>
                    </div>
                  ) : null}
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button type="button" onClick={resetStyle} className="rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 px-3 py-1.5 text-xs text-slate-700 dark:text-slate-300">
                    {t('captionsModal.resetStyles', 'Reset styles')}
                  </button>
                </div>
              </div>
            </>
          ) : showThemePicker && lines.length > 0 ? (
            <>
              <div className="mb-4 flex items-center justify-between gap-2">
                <button onClick={() => setShowThemePicker(false)} className="inline-flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
                  <ArrowLeft size={14} /> {t('captionsModal.back', 'Retour')}
                </button>
                <h4 className="text-sm font-bold text-slate-900 dark:text-white">{t('captionsModal.themes', 'Themes')}</h4>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.builtinThemes', "Themes prets a l'emploi")}</label>
                  <div className="mt-2 grid grid-cols-2 gap-2">
                    {BUILTIN_CAPTION_THEMES.map((theme) => (
                      <button
                        key={theme.id}
                        type="button"
                        onClick={() => applyTheme(theme, false)}
                        className={`relative rounded-lg border px-3 py-2.5 text-left ${activeThemeId === theme.id ? 'border-emerald-400 bg-emerald-500/15' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30'}`}
                      >
                        <div className="flex items-center gap-2">
                          <span className="text-base leading-none">{theme.emoji}</span>
                          <span className="text-xs font-semibold text-slate-800 dark:text-slate-100">{theme.name}</span>
                          {activeThemeId === theme.id ? <Check size={13} className="ml-auto text-emerald-500" /> : null}
                        </div>
                        <div
                          className="mt-2 h-7 rounded flex items-center justify-center text-xs"
                          style={{
                            backgroundColor: theme.style.bgOpacity > 0 ? theme.style.bgColor : 'transparent',
                            color: theme.style.fontColor,
                            fontFamily: theme.style.fontFamily,
                            textTransform: theme.style.textCase === 'uppercase' ? 'uppercase' : theme.style.textCase === 'lowercase' ? 'lowercase' : 'none',
                            fontWeight: theme.style.bold ? 700 : 400,
                            fontStyle: theme.style.italic ? 'italic' : 'normal',
                            textShadow: `0 0 4px ${theme.style.highlightColor}`,
                          }}
                        >
                          Aa
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.myThemes', 'Mes themes')}</label>
                    {themesLoading ? <Loader2 size={12} className="animate-spin text-slate-400" /> : null}
                  </div>
                  {themesError ? <p className="mt-1 text-[11px] text-red-300">{themesError}</p> : null}
                  {!themesLoading && customThemes.length === 0 ? (
                    <p className="mt-2 text-[11px] text-slate-400">{t('captionsModal.noCustomThemes', 'Personnalisez un theme puis enregistrez-le ici.')}</p>
                  ) : null}
                  <div className="mt-2 space-y-1.5">
                    {customThemes.map((theme) => (
                      <div
                        key={theme.id}
                        className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${activeThemeId === theme.id ? 'border-emerald-400 bg-emerald-500/15' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30'}`}
                      >
                        <button type="button" onClick={() => applyTheme(theme, true)} className="flex-1 text-left text-xs font-semibold text-slate-800 dark:text-slate-100 inline-flex items-center gap-2">
                          <Palette size={13} className="text-slate-400" />
                          {theme.name}
                          {activeThemeId === theme.id ? <Check size={13} className="text-emerald-500" /> : null}
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteTheme(theme.id)}
                          disabled={deletingThemeId === theme.id}
                          className="text-rose-400 hover:text-rose-300 disabled:opacity-40"
                          title={t('captionsModal.deleteTheme', 'Supprimer ce theme')}
                        >
                          {deletingThemeId === theme.id ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border border-slate-300 dark:border-white/10 bg-white/[0.03] px-3 py-3">
                  <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">{t('captionsModal.saveTheme', 'Enregistrer le style actuel comme theme')}</label>
                  <div className="mt-2 flex items-center gap-2">
                    <input
                      type="text"
                      value={saveThemeName}
                      onChange={(e) => setSaveThemeName(e.target.value)}
                      placeholder={t('captionsModal.themeNamePlaceholder', 'Nom du theme')}
                      className="flex-1 bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1.5 text-xs text-slate-900 dark:text-zinc-100"
                    />
                    <button
                      type="button"
                      onClick={handleSaveTheme}
                      disabled={isSavingTheme || !saveThemeName.trim()}
                      className="rounded-md bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 text-xs font-semibold text-emerald-700 dark:text-emerald-200 disabled:opacity-50 inline-flex items-center gap-1"
                    >
                      {isSavingTheme ? <Loader2 size={12} className="animate-spin" /> : null}
                      {t('captionsModal.save', 'Enregistrer')}
                    </button>
                  </div>
                  {saveThemeMessage ? <p className="mt-1.5 text-[11px] text-slate-500 dark:text-slate-400">{saveThemeMessage}</p> : null}
                  <p className="mt-1.5 text-[10px] text-slate-400">{t('captionsModal.saveThemeHint', "Astuce : reutilisez le nom d'un theme existant pour le mettre a jour.")}</p>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <h3 className="title-contrast text-lg font-bold flex items-center gap-2">
                  <MessageSquareText className="text-emerald-400" size={18} />
                  {t('captionsModal.subtitleTitle', 'Sous-titres')}
                </h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => { setShowStyleEditor(false); setShowThemePicker(true); }}
                    disabled={lines.length === 0}
                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 hover:bg-slate-100 dark:hover:bg-white/10 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-40 inline-flex items-center gap-1"
                  >
                    <Palette size={13} />
                    {t('captionsModal.themes', 'Themes')}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowThemePicker(false); setShowStyleEditor(true); }}
                    disabled={lines.length === 0}
                    className="rounded-lg border border-slate-300 dark:border-white/10 bg-white dark:bg-white/5 hover:bg-slate-100 dark:hover:bg-white/10 px-3 py-1.5 text-xs font-semibold text-slate-700 dark:text-slate-200 disabled:opacity-40"
                  >
                    {t('captionsModal.styleEditor', 'Edition de style')}
                  </button>
                  <button
                    type="button"
                    onClick={() => onResetStyles?.()}
                    disabled={isResettingStyles}
                    className="rounded-lg border border-rose-300/60 dark:border-rose-500/40 bg-rose-50 dark:bg-rose-500/10 hover:bg-rose-100 dark:hover:bg-rose-500/20 px-3 py-1.5 text-xs font-semibold text-rose-700 dark:text-rose-200 disabled:opacity-40 inline-flex items-center gap-1"
                  >
                    {isResettingStyles ? <Loader2 size={12} className="animate-spin" /> : <RotateCcw size={12} />}
                    {t('captionsModal.resetVideo', 'Reset')}
                  </button>
                </div>
              </div>

              <p className="mb-3 text-xs text-slate-400 dark:text-zinc-500">{t('captionsModal.clickLineHint', 'Click a line to edit.')}</p>

              <div className="mb-4 rounded-xl border border-slate-300 dark:border-white/10 bg-white/[0.04] p-3 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-700 dark:text-slate-300">{t('captionsModal.translation', 'Traduction')}</span>
                  <input type="checkbox" checked={translationEnabled} onChange={(e) => setTranslationEnabled(e.target.checked)} />
                </div>
                {translationEnabled ? (
                  <>
                    <div className="flex items-center justify-between text-xs text-slate-700 dark:text-slate-300">
                      <span>{t('captionsModal.translationText', 'Texte')}</span>
                      <input type="checkbox" checked={translateText} onChange={(e) => setTranslateText(e.target.checked)} />
                    </div>
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>{t('captionsModal.translationVoice', 'Voix')}</span>
                      <input type="checkbox" checked={false} disabled />
                    </div>
                    <select value={targetLanguage} onChange={(e) => setTargetLanguage(e.target.value)} className="w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-xs text-slate-900 dark:text-zinc-100">
                      {Object.entries(languages).map(([code, name]) => (
                        <option key={code} value={code}>{name}</option>
                      ))}
                    </select>
                    <button type="button" onClick={handleApplyTranslation} disabled={isTranslating || !translateText} className="w-full rounded-md bg-emerald-500/20 border border-emerald-500/40 px-3 py-1.5 text-xs text-emerald-200 disabled:opacity-50">
                      {isTranslating ? t('captionsModal.applying', 'Applying...') : t('captionsModal.apply', 'Appliquer')}
                    </button>
                    {translationError ? <p className="text-[11px] text-red-300">{translationError}</p> : null}
                  </>
                ) : null}
              </div>

              {captionsLoading ? <p className="text-sm text-slate-400">{t('captionsModal.loading', 'Loading subtitles...')}</p> : null}
              {fetchError ? <p className="text-xs text-red-300">{fetchError}</p> : null}
              {creditBlocked ? <p className="text-xs text-amber-300 mb-3">{creditError || t('captionsModal.insufficientCredits', 'Insufficient credits')}</p> : null}

              <div className="space-y-3">
                {lines.map((line, lineIndex) => (
                  <div key={line.id} onClick={() => { setSelectedLineId(line.id); previewRef.current?.seekToMs?.(line.startMs || 0); }} className={`relative rounded-xl border p-3 space-y-3 ${selectedLineId === line.id ? 'border-emerald-400 bg-emerald-500/10' : 'border-slate-300 dark:border-white/10 bg-white/[0.05]'}`}>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[11px] uppercase tracking-wider text-slate-400">{t('captionsModal.line', 'Line')} {lineIndex + 1}</span>
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setEmojiLineId((prev) => (prev === line.id ? null : line.id));
                            setEmojiSearch('');
                            setEmojiGroup('popular');
                          }}
                          className="rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 px-2 py-1 text-[11px] text-slate-700 dark:text-slate-200"
                        >
                          {t('captionsModal.addEmoji', 'Add emoji')}
                        </button>
                        <button type="button" onClick={(e) => { e.stopPropagation(); setLines((prev) => prev.filter((item) => item.id !== line.id)); }} className="rounded-md border border-rose-300 bg-rose-100 px-2 py-1 text-[11px] font-semibold text-rose-800 hover:bg-rose-200 dark:border-rose-500/40 dark:bg-rose-500/15 dark:text-rose-200 dark:hover:bg-rose-500/25">
                          {t('captionsModal.deleteLine', 'Delete line')}
                        </button>
                      </div>
                    </div>

                    {emojiLineId === line.id ? (
                      <div onClick={(e) => e.stopPropagation()} className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-black/50 p-2.5 space-y-2">
                        <input
                          type="text"
                          value={emojiSearch}
                          onChange={(e) => setEmojiSearch(e.target.value)}
                          placeholder={t('captionsModal.searchEmoji', 'Search emoji...')}
                          className="w-full bg-white dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-md px-2 py-1 text-xs text-slate-900 dark:text-zinc-100"
                        />
                        <div className="flex flex-wrap gap-1.5">
                          {Object.keys(EMOJI_GROUPS).map((groupKey) => (
                            <button
                              key={`${line.id}-${groupKey}`}
                              type="button"
                              onClick={() => setEmojiGroup(groupKey)}
                              className={`rounded-md border px-2 py-1 text-[10px] uppercase tracking-wide ${emojiGroup === groupKey ? 'border-emerald-400 bg-emerald-500/15 text-emerald-700 dark:text-emerald-200' : 'border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 text-slate-700 dark:text-slate-300'}`}
                            >
                              {t(`captionsModal.emojiCategory.${groupKey}`, groupKey)}
                            </button>
                          ))}
                        </div>
                        <div className="grid grid-cols-10 gap-1 max-h-32 overflow-y-auto custom-scrollbar pr-1">
                          {visibleEmojis.map((emoji) => (
                            <button
                              key={`${line.id}-${emoji}`}
                              type="button"
                              onClick={() => appendEmojiToLineEnd(line.id, emoji)}
                              className="h-7 rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 hover:bg-slate-200 dark:hover:bg-black/60 text-sm"
                              title={emoji}
                            >
                              {emoji}
                            </button>
                          ))}
                        </div>
                      </div>
                    ) : null}

                    <div className="flex flex-wrap gap-2">
                      {line.words.map((word) => (
                        <div key={word.id} className="inline-flex items-center rounded-md border border-slate-300 dark:border-white/10 bg-white dark:bg-black/30 overflow-hidden">
                          <input
                            value={word.text}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => updateWordText(line.id, word.id, e.target.value)}
                            className="bg-transparent px-2 py-1 text-xs text-slate-900 dark:text-zinc-100 min-w-[72px] outline-none"
                          />
                          <input
                            type="color"
                            value={word.color || '#FFFFFF'}
                            onClick={(e) => e.stopPropagation()}
                            onChange={(e) => updateLine(line.id, (curr) => ({ ...curr, words: curr.words.map((w) => (w.id === word.id ? { ...w, color: e.target.value } : w)) }))}
                            className="h-6 w-6 border-l border-slate-300 dark:border-white/10 bg-transparent"
                          />
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (line.words.length > 1) deleteWord(line.id, word.id);
                            }}
                            className="px-1 text-red-300 text-xs"
                            disabled={line.words.length <= 1}
                          >
                            ×
                          </button>
                        </div>
                      ))}
                      <button type="button" onClick={(e) => { e.stopPropagation(); addWord(line.id); }} className="inline-flex items-center gap-1 rounded-md border border-emerald-300 bg-emerald-100 px-2 py-1 text-[11px] font-semibold text-emerald-800 hover:bg-emerald-200 dark:border-emerald-500/40 dark:bg-emerald-500/15 dark:text-emerald-200 dark:hover:bg-emerald-500/25">
                        <Plus size={11} /> {t('captionsModal.addWord', 'Add word')}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="w-full md:w-[50%] rounded-xl border border-slate-300 dark:border-white/10 bg-slate-50 dark:bg-black/30 p-4 md:p-5 flex flex-col gap-3 overflow-x-hidden">
          <h3 className="title-contrast text-lg font-bold">{t('captionsModal.preview', 'Preview')}</h3>
          <div className="flex-1 rounded-lg border border-slate-300 dark:border-white/10 overflow-hidden bg-black min-h-[360px]">
            <RemotionPreview
              ref={previewRef}
              videoUrl={cleanVideoUrl || videoUrl}
              durationInSeconds={durationSec}
              subtitles={flattenedCaptions.length > 0 ? subtitleConfig : null}
              hook={existingHook || null}
              effects={existingEffects || null}
            />
          </div>

          <button
            type="button"
            onClick={() => onGenerate({ remotion: subtitleConfig, previewDurationSec: durationSec, cleanVideoUrl })}
            disabled={isProcessing || flattenedCaptions.length === 0 || creditBlocked}
            className="w-full py-3 bg-gradient-to-r from-emerald-500 to-green-500 hover:from-emerald-400 hover:to-green-400 text-black font-bold rounded-xl shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98] inline-flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {isProcessing ? <Loader2 size={16} className="animate-spin" /> : <MessageSquareText size={16} />}
            {isProcessing ? t('captionsModal.generating', 'Generating...') : t('captionsModal.generateSubtitles', 'Generate subtitles')}
          </button>
        </div>
      </div>
    </div>
  );
}

