import { useEffect, useMemo, useState } from "react";
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
    return {
        localId: nextCommentLocalId(), text: "", imageUrl: "", imageDraft: "", addingImage: false,
        imageUploading: false, imageError: "", isDraggingImage: false,
    };
}

const COMMENT_IMAGE_MAX_BYTES = 10 * 1024 * 1024;
const POST_MEDIA_MAX_BYTES = 200 * 1024 * 1024;

export default function SocialPostComposerModal({ isOpen, onClose, onCreated }) {
    const { t } = useTranslation();
    const { user } = useAuth();

    const [text, setText] = useState("");
    const [socialAccounts, setSocialAccounts] = useState([]);
    const [selectedAccountIds, setSelectedAccountIds] = useState({});
    const [backgrounds, setBackgrounds] = useState([]);
    const [backgroundId, setBackgroundId] = useState(NO_BACKGROUND_ID);
    // A photo/video attached to the post itself (not a comment's image --
    // see uploadCommentImage below). Mutually exclusive with the Facebook
    // background: the backend drops the background the moment media is
    // attached (see _build_social_post_publish_payload in app.py).
    const [mediaUrl, setMediaUrl] = useState("");
    const [mediaType, setMediaType] = useState("");
    const [mediaUploading, setMediaUploading] = useState(false);
    const [mediaError, setMediaError] = useState("");
    const [isDraggingMedia, setIsDraggingMedia] = useState(false);
    const [comments, setComments] = useState([]);
    const [isScheduling, setIsScheduling] = useState(false);
    const [scheduleDate, setScheduleDate] = useState("");
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [result, setResult] = useState(null);

    useEffect(() => {
        if (!isOpen) return;
        setText("");
        setSelectedAccountIds({});
        setBackgroundId(NO_BACKGROUND_ID);
        setMediaUrl("");
        setMediaType("");
        setMediaUploading(false);
        setMediaError("");
        setIsDraggingMedia(false);
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
        (async () => {
            try {
                const response = await fetch(getApiUrl("/api/social/accounts"), {
                    headers: { ...getAuthHeaders(user?.id) },
                });
                if (!response.ok) return;
                const data = await response.json();
                const accounts = Array.isArray(data?.accounts) ? data.accounts : [];
                if (!cancelled) setSocialAccounts(accounts.filter((a) => PUBLISH_PLATFORMS.includes(a.platform)));
            } catch {
                // Best-effort: the composer simply shows no connected accounts.
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [isOpen, user?.id]);

    // Accounts to pick from, grouped by platform -- a plan can have several
    // pages/profiles per network (see max_social_account), so this is a
    // multi-select of specific accounts, not a per-platform checkbox.
    const accountsByPlatform = useMemo(() => {
        const next = {};
        for (const account of socialAccounts) {
            (next[account.platform] ||= []).push(account);
        }
        return next;
    }, [socialAccounts]);

    if (!isOpen) return null;

    const selectedPreset = backgrounds.find((preset) => preset.id === backgroundId);
    const hasBackground = Boolean(selectedPreset) && selectedPreset.id !== NO_BACKGROUND_ID;

    const handleAccountToggle = (accountId, checked) => {
        setSelectedAccountIds((prev) => ({ ...prev, [accountId]: checked }));
    };

    const addComment = () => setComments((prev) => [...prev, emptyComment()]);
    const removeComment = (localId) => setComments((prev) => prev.filter((c) => c.localId !== localId));
    const updateComment = (localId, field, value) => {
        setComments((prev) => prev.map((c) => (c.localId === localId ? { ...c, [field]: value } : c)));
    };

    // Drag-and-drop (or a plain <input type="file">) upload path for a
    // comment's image, alongside the existing "paste a URL" one above --
    // the file has to actually go to the backend (see
    // /api/social/comment-image/upload in app.py) because Facebook fetches
    // the comment's attachment_url itself server-side, so a local blob: URL
    // would never resolve for it.
    const uploadCommentImage = async (localId, file) => {
        if (!file) return;
        if (!file.type.startsWith("image/")) {
            updateComment(localId, "imageError", t("social.postComposerCommentImageInvalidType", "Ce fichier n'est pas une image."));
            return;
        }
        if (file.size > COMMENT_IMAGE_MAX_BYTES) {
            updateComment(localId, "imageError", t("social.postComposerCommentImageTooLarge", "Image trop volumineuse (10 Mo max)."));
            return;
        }

        setComments((prev) =>
            prev.map((c) => (c.localId === localId ? { ...c, imageUploading: true, imageError: "" } : c))
        );
        try {
            const formData = new FormData();
            formData.append("file", file);
            const response = await fetch(getApiUrl("/api/social/comment-image/upload"), {
                method: "POST",
                headers: { ...getAuthHeaders(user?.id) },
                body: formData,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data?.image_url) {
                throw new Error(data?.detail || t("social.postComposerCommentImageUploadFailed", "Echec de l'envoi de l'image."));
            }
            setComments((prev) =>
                prev.map((c) =>
                    c.localId === localId
                        ? { ...c, imageUrl: data.image_url, imageUploading: false, addingImage: false, imageDraft: "" }
                        : c
                )
            );
        } catch (err) {
            setComments((prev) =>
                prev.map((c) =>
                    c.localId === localId
                        ? { ...c, imageUploading: false, imageError: err.message || t("social.postComposerCommentImageUploadFailed", "Echec de l'envoi de l'image.") }
                        : c
                )
            );
        }
    };

    const handleCommentImageDrop = (localId, e) => {
        e.preventDefault();
        e.stopPropagation();
        updateComment(localId, "isDraggingImage", false);
        const file = e.dataTransfer?.files?.[0];
        if (file) uploadCommentImage(localId, file);
    };

    // Photo/video attached to the post itself, distinct from a comment's
    // image above -- goes to /api/social/post-media/upload, which also
    // detects and returns media_type ("image" or "video") so the backend
    // knows whether to route it as PublishRequest.image_url or .video_url.
    const uploadPostMedia = async (file) => {
        if (!file) return;
        const isImage = file.type.startsWith("image/");
        const isVideo = file.type.startsWith("video/");
        if (!isImage && !isVideo) {
            setMediaError(t("social.postComposerMediaInvalidType", "Ce fichier doit etre une image ou une video."));
            return;
        }
        if (file.size > POST_MEDIA_MAX_BYTES) {
            setMediaError(t("social.postComposerMediaTooLarge", "Fichier trop volumineux (200 Mo max)."));
            return;
        }

        setMediaUploading(true);
        setMediaError("");
        try {
            const formData = new FormData();
            formData.append("file", file);
            const response = await fetch(getApiUrl("/api/social/post-media/upload"), {
                method: "POST",
                headers: { ...getAuthHeaders(user?.id) },
                body: formData,
            });
            const data = await response.json().catch(() => ({}));
            if (!response.ok || !data?.media_url) {
                throw new Error(data?.detail || t("social.postComposerMediaUploadFailed", "Echec de l'envoi du fichier."));
            }
            setMediaUrl(data.media_url);
            setMediaType(data.media_type || (isVideo ? "video" : "image"));
            // A background can't be combined with media -- see backend
            // _build_social_post_publish_payload.
            setBackgroundId(NO_BACKGROUND_ID);
        } catch (err) {
            setMediaError(err.message || t("social.postComposerMediaUploadFailed", "Echec de l'envoi du fichier."));
        } finally {
            setMediaUploading(false);
        }
    };

    const handlePostMediaDrop = (e) => {
        e.preventDefault();
        e.stopPropagation();
        setIsDraggingMedia(false);
        const file = e.dataTransfer?.files?.[0];
        if (file) uploadPostMedia(file);
    };

    const removePostMedia = () => {
        setMediaUrl("");
        setMediaType("");
        setMediaError("");
    };

    const handleSubmit = async () => {
        if (!user?.id) return;

        const selectedAccountIdList = Object.keys(selectedAccountIds).filter((id) => selectedAccountIds[id]);
        // results/comments_results come back keyed by account id -- resolve
        // each back to "Platform - Account name" for error messages instead
        // of showing a raw uuid.
        const accountLabel = (accountId) => {
            const account = socialAccounts.find((a) => a.id === accountId);
            if (!account) return accountId;
            return `${PLATFORM_LABELS[account.platform] || account.platform} - ${account.platform_account_name || accountId}`;
        };

        if (!text.trim()) {
            setResult({ success: false, msg: t("social.postComposerTextRequired", "Ecrivez le texte de votre publication.") });
            return;
        }
        if (selectedAccountIdList.length === 0) {
            setResult({ success: false, msg: t("anonymousStories.publishSelectPlatform", "Selectionnez au moins une plateforme.") });
            return;
        }
        if (isScheduling && !scheduleDate) {
            setResult({ success: false, msg: t("anonymousStories.publishSelectDateTime", "Selectionnez une date et une heure.") });
            return;
        }
        if (mediaUploading) {
            setResult({ success: false, msg: t("social.postComposerMediaStillUploading", "Attendez la fin de l'envoi du fichier.") });
            return;
        }

        setIsSubmitting(true);
        setResult(null);
        try {
            const payload = {
                text: text.trim(),
                account_ids: selectedAccountIdList,
                background_id: mediaUrl ? undefined : (backgroundId || undefined),
                media_url: mediaUrl || undefined,
                media_type: mediaUrl ? mediaType : undefined,
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
                const failedAccounts = Object.entries(data?.results || {}).filter(([, r]) => !r?.success);
                const accountNames = failedAccounts.map(([accountId]) => accountLabel(accountId)).join(", ");
                const firstError = failedAccounts.length ? describePlatformPublishError(t, failedAccounts[0][1]?.error) : "";
                setResult({
                    success: false,
                    msg: failedAccounts.length
                        ? t(
                              "anonymousStories.publishPartialFailure",
                              "Echec de la publication sur : {{platforms}}. {{error}}",
                              { platforms: accountNames, error: firstError }
                          )
                        : t("social.postComposerFailed", "La publication a echoue."),
                });
                return;
            }

            // The post itself can succeed while a follow-up comment fails
            // (e.g. a stale connected token missing the comment-posting
            // permission) -- create_social_post's top-level "success" only
            // reflects the post, so check each account's own
            // comments_results here instead of silently showing "success"
            // while comments never actually appeared.
            const failedComments = !isScheduling
                ? Object.entries(data?.results || {}).flatMap(([accountId, r]) =>
                      (r?.comments_results || [])
                          .filter((c) => !c?.success)
                          .map((c) => ({ accountId, error: c?.error }))
                  )
                : [];

            if (failedComments.length > 0) {
                const accountNames = [...new Set(failedComments.map((c) => accountLabel(c.accountId)))].join(", ");
                setResult({
                    success: false,
                    msg: t(
                        "social.postComposerCommentsFailed",
                        "Publication envoyee, mais {{count}} commentaire(s) n'ont pas pu etre postes sur : {{platforms}}. {{error}}",
                        { count: failedComments.length, platforms: accountNames, error: describePlatformPublishError(t, failedComments[0].error) }
                    ),
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
                            {t("social.postComposerMediaLabel", "Photo ou video (optionnel)")}
                        </label>
                        {mediaUrl ? (
                            <div className="relative inline-block">
                                {mediaType === "video" ? (
                                    <video src={mediaUrl} className="max-h-40 rounded-lg border border-slate-200 dark:border-white/10" controls muted />
                                ) : (
                                    <img src={mediaUrl} alt="" className="max-h-40 rounded-lg border border-slate-200 dark:border-white/10" />
                                )}
                                <button
                                    type="button"
                                    onClick={removePostMedia}
                                    className="absolute -top-2 -right-2 bg-rose-500 text-white rounded-full p-0.5 shadow"
                                    title={t("common.remove", "Remove")}
                                >
                                    <X size={12} />
                                </button>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                <label
                                    htmlFor="post-media-file"
                                    onDragOver={(e) => {
                                        e.preventDefault();
                                        setIsDraggingMedia(true);
                                    }}
                                    onDragLeave={() => setIsDraggingMedia(false)}
                                    onDrop={handlePostMediaDrop}
                                    className={`flex flex-col items-center justify-center gap-1 p-4 rounded-md border-2 border-dashed cursor-pointer transition-colors ${
                                        isDraggingMedia
                                            ? "border-primary bg-primary/10"
                                            : "border-slate-300 dark:border-white/20 hover:border-primary/60"
                                    }`}
                                >
                                    <input
                                        id="post-media-file"
                                        type="file"
                                        accept="image/*,video/*"
                                        className="hidden"
                                        disabled={mediaUploading}
                                        onChange={(e) => {
                                            const file = e.target.files?.[0];
                                            e.target.value = "";
                                            if (file) uploadPostMedia(file);
                                        }}
                                    />
                                    {mediaUploading ? (
                                        <>
                                            <Loader2 size={18} className="animate-spin text-primary" />
                                            <span className="text-[11px] text-slate-500 dark:text-zinc-400">
                                                {t("social.postComposerMediaUploading", "Envoi en cours...")}
                                            </span>
                                        </>
                                    ) : (
                                        <>
                                            <ImageIcon size={18} className="text-slate-400 dark:text-zinc-500" />
                                            <span className="text-[11px] text-slate-500 dark:text-zinc-400 text-center">
                                                {t("social.postComposerMediaDropzone", "Glissez une photo ou une video ici, ou cliquez pour parcourir")}
                                            </span>
                                        </>
                                    )}
                                </label>
                                {mediaError ? <p className="text-[11px] text-rose-500">{mediaError}</p> : null}
                            </div>
                        )}
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishSelectPlatformLabel", "Choisir les comptes")}
                        </label>
                        {socialAccounts.length === 0 ? (
                            <p className="text-xs text-slate-400 dark:text-zinc-500">
                                {t("social.postComposerNoAccounts", "Aucun compte Facebook/LinkedIn connecte. Connectez-en un dans Parametres.")}
                            </p>
                        ) : (
                            <div className="space-y-3">
                                {PUBLISH_PLATFORMS.map((platform) => {
                                    const accounts = accountsByPlatform[platform] || [];
                                    if (accounts.length === 0) return null;
                                    const Icon = PLATFORM_ICONS[platform];
                                    return (
                                        <div key={platform}>
                                            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-1">
                                                <Icon size={13} /> {t(`social.${platform}`, PLATFORM_LABELS[platform])}
                                            </div>
                                            <div className="grid grid-cols-1 gap-2">
                                                {accounts.map((account) => (
                                                    <label
                                                        key={account.id}
                                                        className="flex items-center gap-3 p-3 bg-slate-100 dark:bg-white/5 rounded-lg cursor-pointer hover:bg-slate-200 dark:hover:bg-white/10 transition-colors border border-slate-200 dark:border-white/5"
                                                    >
                                                        <input
                                                            type="checkbox"
                                                            checked={Boolean(selectedAccountIds[account.id])}
                                                            onChange={(e) => handleAccountToggle(account.id, e.target.checked)}
                                                            className="w-4 h-4 rounded border-zinc-600 bg-black/50 text-primary focus:ring-primary"
                                                        />
                                                        <span className="text-sm text-slate-800 dark:text-white truncate">
                                                            {account.platform_account_name || account.platform}
                                                        </span>
                                                    </label>
                                                ))}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>

                    {!mediaUrl ? (
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
                    ) : null}

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">
                            {t("anonymousStories.publishPreviewLabel", "Apercu de la publication")}
                        </label>
                        {mediaUrl ? (
                            <div className="rounded-xl overflow-hidden border border-slate-200 dark:border-white/5 bg-slate-100 dark:bg-white/5">
                                {mediaType === "video" ? (
                                    <video src={mediaUrl} className="w-full max-h-52 object-cover" controls muted />
                                ) : (
                                    <img src={mediaUrl} alt="" className="w-full max-h-52 object-cover" />
                                )}
                                {text.trim() ? (
                                    <p className="p-3 text-sm text-slate-800 dark:text-white whitespace-pre-wrap break-words">{text}</p>
                                ) : null}
                            </div>
                        ) : (
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
                        )}
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
                                            <div className="space-y-2">
                                                <label
                                                    htmlFor={`comment-image-file-${comment.localId}`}
                                                    onDragOver={(e) => {
                                                        e.preventDefault();
                                                        updateComment(comment.localId, "isDraggingImage", true);
                                                    }}
                                                    onDragLeave={() => updateComment(comment.localId, "isDraggingImage", false)}
                                                    onDrop={(e) => handleCommentImageDrop(comment.localId, e)}
                                                    className={`flex flex-col items-center justify-center gap-1 p-4 rounded-md border-2 border-dashed cursor-pointer transition-colors ${
                                                        comment.isDraggingImage
                                                            ? "border-primary bg-primary/10"
                                                            : "border-slate-300 dark:border-white/20 hover:border-primary/60"
                                                    }`}
                                                >
                                                    <input
                                                        id={`comment-image-file-${comment.localId}`}
                                                        type="file"
                                                        accept="image/*"
                                                        className="hidden"
                                                        disabled={comment.imageUploading}
                                                        onChange={(e) => {
                                                            const file = e.target.files?.[0];
                                                            e.target.value = "";
                                                            if (file) uploadCommentImage(comment.localId, file);
                                                        }}
                                                    />
                                                    {comment.imageUploading ? (
                                                        <>
                                                            <Loader2 size={18} className="animate-spin text-primary" />
                                                            <span className="text-[11px] text-slate-500 dark:text-zinc-400">
                                                                {t("social.postComposerCommentImageUploading", "Envoi en cours...")}
                                                            </span>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <ImageIcon size={18} className="text-slate-400 dark:text-zinc-500" />
                                                            <span className="text-[11px] text-slate-500 dark:text-zinc-400 text-center">
                                                                {t(
                                                                    "social.postComposerCommentImageDropzone",
                                                                    "Glissez une image ici, ou cliquez pour parcourir"
                                                                )}
                                                            </span>
                                                        </>
                                                    )}
                                                </label>

                                                {comment.imageError ? <p className="text-[11px] text-rose-500">{comment.imageError}</p> : null}

                                                <div className="flex items-center gap-2">
                                                    <div className="flex-1 h-px bg-slate-200 dark:bg-white/10" />
                                                    <span className="text-[10px] uppercase text-slate-400 dark:text-zinc-500">
                                                        {t("common.or", "ou")}
                                                    </span>
                                                    <div className="flex-1 h-px bg-slate-200 dark:bg-white/10" />
                                                </div>

                                                <div className="flex items-center gap-2">
                                                    <input
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
                                                            updateComment(comment.localId, "imageError", "");
                                                        }}
                                                        className="px-2 py-2 rounded-md bg-slate-200 dark:bg-white/10 text-slate-600 dark:text-zinc-300"
                                                    >
                                                        <X size={14} />
                                                    </button>
                                                </div>
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
