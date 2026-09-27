import { useEffect, useState } from "react";
import { X, Loader2, Share2, Calendar, Clock, Facebook, Linkedin, CheckCircle, AlertCircle, Check, Ban, Plus, Trash2, Link as LinkIcon, Image as ImageIcon } from "lucide-react";
import { getApiUrl } from "../config";
import { getAuthHeaders } from "../lib/apiAuth";
import { describePlatformPublishError } from "../lib/anonymousStories";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";

// "Faire une publication": a user-authored post (optionally with a
// Facebook-only colored background, same catalog as anonymous stories --
// see AnonymousStoryPublishModal) published to Facebook and/or LinkedIn,
// together with zero or more follow-up comments posted by the connected
// account itself right after the post goes live (see POST /api/social/posts
// in app.py). Unlike AnonymousStoryPublishModal this modal is
// self-contained: it fetches its own background catalog rather than being
// controlled by the parent page, since SocialPublicationsPage has no other
// reason to hold that state.

const NO_BACKGROUND_ID = "none";
const PUBLISH_PLATFORMS = ["facebook", "linkedin"];
const PLATFORM_ICONS = { facebook: Facebook, linkedin: Linkedin };
const PLATFORM_LABELS = { facebook: "Facebook", linkedin: "LinkedIn" };

function backgroundGradient(preset) {
    const colors = preset?.colors && preset.colors.length ? preset.colors : ["#0f2027"];
    const gradientColors = colors.length > 1 ? colors : [colors[0], colors[0]];
    return `linear-gradient(135deg, ${gradientColors.join(", ")})`;
}

// Facebook's own text-background posts show only the first ~130 characters
// inline behind a "See more" expander (see AnonymousStoryPublishModal) --
// mirroring that here keeps the preview honest when a background is chosen.
const PREVIEW_TEXT_LIMIT = 130;

function buildPreviewSnippet(text, seeMoreLabel) {
    const trimmed = (text || "").trim();
    if (trimmed.length <= PREVIEW_TEXT_LIMIT) return trimmed;
    return `${trimmed.slice(0, PREVIEW_TEXT_LIMIT).trimEnd()}… ${seeMoreLabel}`;
}

// Auto-detects the first URL typed anywhere in a comment's free text so it
// can be shown as a link preview right below it, instead of asking the user
// to paste the link into a second field -- the link lives only in the text.
const URL_REGEX = /(https?:\/\/[^\s]+)/i;

function detectFirstUrl(text) {
    const match = (text || "").match(URL_REGEX);
    return match ? match[1] : "";
}

function urlHostname(url) {
    try {
        return new URL(url).hostname;
    } catch {
        return url;
    }
}

function faviconUrlFor(url) {
    return `https://www.google.com/s2/favicons?sz=32&domain=${encodeURIComponent(urlHostname(url))}`;
}

let commentLocalIdSeq = 0;
function nextCommentLocalId() {
    commentLocalIdSeq += 1;
    return `comment-${commentLocalIdSeq}`;
}

function emptyComment() {
    return { localId: nextCommentLocalId(), text: "", imageUrl: "", imageDraft: "", addingImage: false };
}

export default function SocialPostComposerModal({ isOpen, onClose, onCreated }) {
    const { t } = useTranslation();
    const { user } = useAuth();

    const [text, setText] = useState("");
    const [platforms, setPlatforms] = useState({ facebook: false, linkedin: false });
    const [backgrounds, setBackgrounds] = useState([]);
    const [backgroundId, setBackgroundId] = useState(NO_BACKGROUND_ID);
    const [comments, setComments] = useState([]);
    const [isScheduling, setIsScheduling] = useState(false);
    const [scheduleDate, setScheduleDate] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [result, setResult] = useState(null);

    useEffect(() => {
        if (!isOpen) return;
        setText("");
        setPlatforms({ facebook: false, linkedin: false });
        setBackgroundId(NO_BACKGROUND_ID);
        setComments([]);
        setIsScheduling(false);
        setScheduleDate("");
        setResult(null);
        setIsSubmitting(false);

        let cancelled = false;
        (async () => {
            try {
                const response = await fetch(getApiUrl("/api/anonymous-stories/backgrounds"), {
                    headers: { ...getAuthHeaders(user?.id) },
                });
                if (!response.ok) return;
                const data = await response.json();
                if (!cancelled) setBackgrounds(Array.isArray(data.items) ? data.items : []);
            } catch {
                // Best-effort: the composer simply shows no background swatches.
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [isOpen, user?.id]);

    if (!isOpen) return null;

    const selectedPreset = backgrounds.find((preset) => preset.id === backgroundId);
    const hasBackground = Boolean(selectedPreset) && selectedPreset.id !== NO_BACKGROUND_ID;

    const handlePlatformChange = (platform, checked) => {
        setPlatforms((prev) => ({ ...prev, [platform]: checked }));
    };

    const addComment = () => setComments((prev) => [...prev, emptyComment()]);
    const removeComment = (localId) => setComments((prev) => prev.filter((c) => c.localId !== localId));
    const updateComment = (localId, field, value) => {
        setComments((prev) => prev.map((c) => (c.localId === localId ? { ...c, [field]: value } : c)));
    };

    const handleSubmit = async () => {
        if (!user?.id) return;

        const selectedPlatforms = Object.keys(platforms).filter((key) => platforms[key]);
        if (!text.trim()) {
            setResult({ success: false, msg: t("social.postComposerTextRequired", "Ecrivez le texte de votre publication.") });
            return;
        }
        if (selectedPlatforms.length === 0) {
            setResult({ success: false, msg: t("anonymousStories.publishSelectPlatform", "Selectionnez au moins une plateforme.") });
            return;
        }
        if (isScheduling && !scheduleDate) {
            setResult({ success: false, msg: t("anonymousStories.publishSelectDateTime", "Selectionnez une date et une heure.") });
            return;
        }

        setIsSubmitting(true);
        setResult(null);
        try {
            const payload = {
                text: text.trim(),
                platforms: selectedPlatforms,
                background_id: backgroundId || undefined,
                comments: comments
                    .filter((c) => c.text.trim() || c.imageUrl.trim())
                    .map((c) => ({
                        text: c.text.trim(),
                        link: detectFirstUrl(c.text) || undefined,
                        image_url: c.imageUrl.trim() || undefined,
                    })),
            };
            if (isScheduling && scheduleDate) {
                payload.scheduled_date = new Date(scheduleDate).toISOString();
                payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            }

            const response = await fetch(getApiUrl("/api/social/posts"), {
                method: "POST",
                headers: { "Content-Type": "application/json", ...getAuthHeaders(user.id) },
                body: JSON.stringify(payload),
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setResult({ success: false, msg: data?.detail || t("social.postComposerFailed", "La publication a echoue.") });
                return;
            }

            if (!data?.success) {
                const failedPlatforms = Object.entries(data?.results || {}).filter(([, r]) => !r?.success);
                const platformNames = failedPlatforms.map(([platform]) => platform).join(", ");
                const firstError = failedPlatforms.length ? describePlatformPublishError(t, failedPlatforms[0][1]?.error) : "";
                setResult({
                    success: false,
                    msg: failedPlatforms.length
                        ? t(
                              "anonymousStories.publishPartialFailure",
                              "Echec de la publication sur : {{platforms}}. {{error}}",
                              { platforms: platformNames, error: firstError }
                          )
                        : t("social.postComposerFailed", "La publication a echoue."),
                });
                return;
            }

            setResult({
                success: true,
                msg: isScheduling
                    ? t("anonymousStories.publishScheduledSuccess", "Publication programmee avec succes.")
                    : t("anonymousStories.publishSuccess", "Publication envoyee avec succes."),
            });
            onCreated?.(data);
            setTimeout(() => {
                setResult(null);
                onClose?.();
            }, 1500);
        } catch (err) {
            setResult({ success: false, msg: err.message || t("social.postComposerFailed", "La publication a echoue.") });
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-xl shadow-2xl relative max-h-[92vh] overflow-y-auto custom-scrollbar">
                <button onClick={onClose} className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white">
                    <X size={20} />
                </button>

                <h3 className="title-contrast text-lg font-bold mb-4">{t("social.postComposerTitle", "Faire une publication")}</h3>

                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("social.postComposerTextLabel", "Texte de la publication")}
                        </label>
                        <textarea
                            value={text}
                            onChange={(e) => setText(e.target.value)}
                            rows={5}
                            placeholder={t("social.postComposerTextPlaceholder", "Ecrivez votre publication...")}
                            className="w-full bg-slate-100 dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-3 text-sm text-slate-900 dark:text-white resize-y"
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishSelectPlatformLabel", "Choisir les plateformes")}
                        </label>
                        <div className="grid grid-cols-1 gap-2">
                            {PUBLISH_PLATFORMS.map((platform) => {
                                const Icon = PLATFORM_ICONS[platform];
                                return (
                                    <label
                                        key={platform}
                                        className="flex items-center gap-3 p-3 bg-slate-100 dark:bg-white/5 rounded-lg cursor-pointer hover:bg-slate-200 dark:hover:bg-white/10 transition-colors border border-slate-200 dark:border-white/5"
                                    >
                                        <input
                                            type="checkbox"
                                            checked={Boolean(platforms[platform])}
                                            onChange={(e) => handlePlatformChange(platform, e.target.checked)}
                                            className="w-4 h-4 rounded border-zinc-600 bg-black/50 text-primary focus:ring-primary"
                                        />
                                        <div className="flex items-center gap-2 text-sm text-slate-800 dark:text-white">
                                            <Icon size={16} className="text-slate-700 dark:text-zinc-300" /> {t(`social.${platform}`, PLATFORM_LABELS[platform])}
                                        </div>
                                    </label>
                                );
                            })}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishBackgroundLabel", "Arriere-plan de la publication")}
                        </label>
                        <p className="mb-2 text-[11px] text-slate-500 dark:text-zinc-400">
                            {t(
                                "anonymousStories.publishBackgroundFacebookOnly",
                                "Facebook uniquement : LinkedIn ne prend pas en charge ces arriere-plans et publie toujours en texte seul."
                            )}
                        </p>
                        <div className="flex flex-wrap gap-2 max-h-[180px] overflow-y-auto pr-1 custom-scrollbar">
                            {backgrounds.map((preset) => {
                                const isSelected = backgroundId === preset.id;
                                const isNoBackground = preset.id === NO_BACKGROUND_ID;

                                if (isNoBackground) {
                                    return (
                                        <button
                                            key={preset.id}
                                            type="button"
                                            onClick={() => setBackgroundId(preset.id)}
                                            title={t("anonymousStories.publishBackgroundNone", "No background (text only)")}
                                            className={`relative w-[50px] h-[50px] shrink-0 rounded-lg border-2 border-dashed flex flex-col items-center justify-center gap-0.5 text-[9px] font-medium transition ${isSelected ? "border-primary text-primary" : "border-slate-300 dark:border-white/20 text-slate-500 dark:text-zinc-400"}`}
                                        >
                                            <Ban size={12} />
                                            {t("anonymousStories.publishBackgroundNoneShort", "None")}
                                        </button>
                                    );
                                }

                                return (
                                    <button
                                        key={preset.id}
                                        type="button"
                                        onClick={() => setBackgroundId(preset.id)}
                                        title={preset.name}
                                        className={`relative w-[50px] h-[50px] shrink-0 rounded-lg border-2 transition ${isSelected ? "border-primary" : "border-transparent"}`}
                                        style={{ background: backgroundGradient(preset) }}
                                    >
                                        {isSelected ? (
                                            <span className="absolute inset-0 flex items-center justify-center">
                                                <Check size={14} className="text-white drop-shadow" />
                                            </span>
                                        ) : null}
                                    </button>
                                );
                            })}
                        </div>
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishPreviewLabel", "Apercu de la publication")}
                        </label>
                        <div
                            className={`min-h-[120px] rounded-xl p-4 flex items-center justify-center text-center border border-slate-200 dark:border-white/5 ${hasBackground ? "" : "bg-slate-100 dark:bg-white/5"}`}
                            style={
                                hasBackground
                                    ? { background: backgroundGradient(selectedPreset), color: selectedPreset.text_color || "#FFFFFF" }
                                    : undefined
                            }
                        >
                            <p className={`text-sm font-semibold whitespace-pre-wrap break-words ${hasBackground ? "" : "text-slate-800 dark:text-white"}`}>
                                {(hasBackground ? buildPreviewSnippet(text, t("anonymousStories.publishPreviewSeeMore", "Voir plus")) : text) ||
                                    t("anonymousStories.publishPreviewEmpty", "Le texte de la publication apparaitra ici.")}
                            </p>
                        </div>
                    </div>

                    <div>
                        <div className="flex items-center justify-between mb-2">
                            <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400">
                                {t("social.postComposerCommentsLabel", "Commentaires (publies par la page)")}
                            </label>
                            <button
                                type="button"
                                onClick={addComment}
                                className="flex items-center gap-1 text-xs font-semibold text-primary hover:text-blue-400"
                            >
                                <Plus size={14} /> {t("social.postComposerAddComment", "Ajouter un commentaire")}
                            </button>
                        </div>
                        {comments.length === 0 ? (
                            <p className="text-xs text-slate-400 dark:text-zinc-500">
                                {t("social.postComposerNoComments", "Aucun commentaire pour l'instant.")}
                            </p>
                        ) : null}
                        <div className="space-y-3">
                            {comments.map((comment, index) => {
                                const detectedLink = detectFirstUrl(comment.text);
                                return (
                                    <div key={comment.localId} className="p-3 rounded-lg border border-slate-200 dark:border-white/10 bg-slate-50 dark:bg-white/5 space-y-2">
                                        <div className="flex items-center justify-between">
                                            <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 dark:text-zinc-500">
                                                {t("social.postComposerCommentN", "Commentaire {{n}}", { n: index + 1 })}
                                            </span>
                                            <button
                                                type="button"
                                                onClick={() => removeComment(comment.localId)}
                                                className="text-rose-500 hover:text-rose-400"
                                            >
                                                <Trash2 size={14} />
                                            </button>
                                        </div>
                                        <textarea
                                            value={comment.text}
                                            onChange={(e) => updateComment(comment.localId, "text", e.target.value)}
                                            rows={3}
                                            placeholder={t("social.postComposerCommentTextPlaceholder", "Texte du commentaire, collez un lien ou ajoutez des #hashtags...")}
                                            className="w-full bg-white dark:bg-black/30 border border-slate-300 dark:border-white/10 rounded-md p-2 text-xs text-slate-900 dark:text-white resize-y"
                                        />

                                        {/* A URL typed anywhere in the text above is picked up automatically
                                            -- no separate "link" field to fill in. */}
                                        {detectedLink ? (
                                            <a
                                                href={detectedLink}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="flex items-center gap-2 p-2 rounded-md border border-slate-200 dark:border-white/10 bg-white dark:bg-black/20 hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
                                            >
                                                <img src={faviconUrlFor(detectedLink)} alt="" className="w-4 h-4 shrink-0 rounded-sm" />
                                                <span className="text-xs text-slate-600 dark:text-zinc-400 truncate">{urlHostname(detectedLink)}</span>
                                                <LinkIcon size={12} className="ml-auto text-slate-400 dark:text-zinc-500 shrink-0" />
                                            </a>
                                        ) : null}

                                        {comment.imageUrl ? (
                                            <div className="relative inline-block">
                                                <img
                                                    src={comment.imageUrl}
                                                    alt=""
                                                    className="max-h-28 rounded-md border border-slate-200 dark:border-white/10"
                                                    onError={(e) => {
                                                        e.currentTarget.style.display = "none";
                                                    }}
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => updateComment(comment.localId, "imageUrl", "")}
                                                    className="absolute -top-2 -right-2 bg-rose-500 text-white rounded-full p-0.5 shadow"
                                                    title={t("common.remove", "Remove")}
                                                >
                                                    <X size={12} />
                                                </button>
                                            </div>
                                        ) : comment.addingImage ? (
                                            <div className="flex items-center gap-2">
                                                <input
                                                    autoFocus
                                                    value={comment.imageDraft}
                                                    onChange={(e) => updateComment(comment.localId, "imageDraft", e.target.value)}
                                                    placeholder={t("social.postComposerCommentImagePlaceholder", "Collez l'URL de l'image...")}
                                                    className="flex-1 bg-white dark:bg-black/30 border border-slate-300 dark:border-white/10 rounded-md p-2 text-xs text-slate-900 dark:text-white"
                                                />
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        updateComment(comment.localId, "imageUrl", comment.imageDraft.trim());
                                                        updateComment(comment.localId, "addingImage", false);
                                                    }}
                                                    disabled={!comment.imageDraft.trim()}
                                                    className="px-2 py-2 rounded-md bg-primary text-white disabled:opacity-40"
                                                >
                                                    <Check size={14} />
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => {
                                                        updateComment(comment.localId, "addingImage", false);
                                                        updateComment(comment.localId, "imageDraft", "");
                                                    }}
                                                    className="px-2 py-2 rounded-md bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-zinc-300"
                                                >
                                                    <X size={14} />
                                                </button>
                                            </div>
                                        ) : (
                                            <button
                                                type="button"
                                                onClick={() => updateComment(comment.localId, "addingImage", true)}
                                                className="flex items-center gap-1 text-xs font-medium text-slate-600 dark:text-zinc-300 hover:text-primary"
                                            >
                                                <ImageIcon size={14} /> {t("social.postComposerAddImage", "Ajouter une image")}
                                            </button>
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>

                    <div className="p-3 bg-slate-100 dark:bg-white/5 rounded-lg border border-slate-200 dark:border-white/5">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 text-sm text-slate-800 dark:text-white font-medium">
                                <Calendar size={16} className="text-purple-400" /> {t("social.postSchedule", "Schedule Post")}
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" checked={isScheduling} onChange={(e) => setIsScheduling(e.target.checked)} className="sr-only peer" />
                                <div className="w-9 h-5 bg-zinc-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-purple-600"></div>
                            </label>
                        </div>

                        {isScheduling ? (
                            <div className="mt-3 animate-[fadeIn_0.2s_ease-out]">
                                <label className="block text-xs text-slate-500 dark:text-zinc-400 mb-1">{t("social.postSchedulePlaceholder", "Select Date & Time")}</label>
                                <div className="relative">
                                    <input
                                        type="datetime-local"
                                        value={scheduleDate}
                                        onChange={(e) => setScheduleDate(e.target.value)}
                                        className="w-full bg-slate-50 dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 pl-9 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-purple-500/50 [color-scheme:light] dark:[color-scheme:dark]"
                                    />
                                    <Clock size={14} className="absolute left-3 top-2.5 text-slate-400 dark:text-zinc-500" />
                                </div>
                            </div>
                        ) : null}
                    </div>
                </div>

                {result ? (
                    <div className={`mb-4 p-3 rounded-lg text-xs flex items-start gap-2 ${result.success ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                        {result.success ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <AlertCircle size={14} className="mt-0.5 shrink-0" />}
                        <div>{result.msg}</div>
                    </div>
                ) : null}

                <button
                    onClick={handleSubmit}
                    disabled={isSubmitting}
                    className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white font-bold shadow-lg shadow-blue-500/20 transition-all hover:from-blue-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                    {isSubmitting ? (
                        <>
                            <Loader2 size={16} className="animate-spin" />
                            {isScheduling ? t("social.postScheduling", "Scheduling...") : t("social.postPublishing", "Publishing...")}
                        </>
                    ) : (
                        <>
                            <Share2 size={16} />
                            {isScheduling ? t("social.postScheduleButton", "Schedule Post") : t("social.postPublishButton", "Publish Now")}
                        </>
                    )}
                </button>
            </div>
        </div>
    );
}
