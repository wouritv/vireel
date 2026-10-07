import { useEffect, useMemo, useState } from "react";
import { Play, Plus, Download, Loader2, Scissors, Search, Share2, Trash2, X } from "lucide-react";
import { fetchAppConfig, getApiUrl, getDefaultHideSocialPlatforms } from "../config";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";
import ResultCard from "../components/ResultCard";
import SharePostModal from "../components/SharePostModal";
import MobileFilterDropdown from "../components/MobileFilterDropdown";
import GridThumbnail from "../components/GridThumbnail";
import Breadcrumbs from "../components/Breadcrumbs";
import { toResultCardClip } from "../lib/clips";
import { statusLabel, statusClass } from "../lib/status";
import { getAuthHeaders } from "../lib/apiAuth";
import { useTranslation } from "../state/LanguageContext";
import { describePublishError } from "../lib/publishErrors";
import { describeMediaAvailability } from "../lib/mediaAvailability";

export default function ReelsPage({ projectId = "" }) {
    const { user } = useAuth();
    const { credits, hasActiveSubscription } = useUserCredits();
    const {t} = useTranslation();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [page, setPage] = useState(1);
    const [pageSize] = useState(15);
    const [total, setTotal] = useState(0);
    const [queryInput, setQueryInput] = useState("");
    const [query, setQuery] = useState("");
    const [status, setStatus] = useState("");
    const [sharingId, setSharingId] = useState("");
    const [shareResult, setShareResult] = useState(null);
    const [shareModalItem, setShareModalItem] = useState(null);
    const [shareTitle, setShareTitle] = useState("");
    const [shareDescription, setShareDescription] = useState("");
    // Keyed by account id (not platform) -- SharePostModal fetches the
    // user's real connected accounts and lets them pick specific ones.
    const [sharePlatforms, setSharePlatforms] = useState({});
    const [shareScheduling, setShareScheduling] = useState(false);
    const [shareScheduleDate, setShareScheduleDate] = useState("");
    const [deletingId, setDeletingId] = useState("");
    const [previewItem, setPreviewItem] = useState(null);
    const [previewUrl, setPreviewUrl] = useState("");
    const [hideSocialPlatforms, setHideSocialPlatforms] = useState(getDefaultHideSocialPlatforms());
    const [projectMeta, setProjectMeta] = useState(null);
    const navigate = useNavigate();

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);
    const hasAnyReelCredit = Number(credits || 0) > 0;
    const canShareReel = hasActiveSubscription === true;
    const statusOptions = [
        { value: "", label: t('reels.allStatuses', 'All statuses') },
        { value: "en_cours", label: t("reels.statusInProgress", "In progress") },
        { value: "termine", label: t("reels.statusDone", "Done") },
        { value: "echec", label: t("reels.statusFailed", "Failed") },
    ];


    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    useEffect(() => {
        let active = true;
        fetchAppConfig()
            .then((cfg) => {
                if (!active || !cfg || typeof cfg.hideSocialPlatforms !== "boolean") return;
                setHideSocialPlatforms(cfg.hideSocialPlatforms);
            })
            .catch(() => {});
        return () => {
            active = false;
        };
    }, []);

    useEffect(() => {
        if (!user?.id) return;

        let cancelled = false;
        async function loadReels() {
            setLoading(true);
            setError("");

            try {
                let response;
                if (projectId) {
                    response = await fetch(getApiUrl(`/api/projects/${projectId}/reels`), {
                        headers: {
                            ...getAuthHeaders(user.id),
                        },
                    });
                } else {
                    const params = new URLSearchParams({
                        page: String(page),
                        page_size: String(pageSize),
                    });
                    if (query) params.set("q", query);
                    if (status) params.set("status", status);
                    response = await fetch(getApiUrl(`/api/reels?${params.toString()}`), {
                        headers: {
                            ...getAuthHeaders(user.id),
                        },
                    });
                }

                const data = await response.json();
                if (cancelled) return;

                if (!response.ok) {
                    const detail = data?.detail || "Unable to load reels";
                    setError(detail);
                    setItems([]);
                    return;
                }

                const rawItems = projectId ? data.reels : data.items;
                const nextItems = Array.isArray(rawItems) ? rawItems : [];
                const filteredItems = projectId
                    ? nextItems.filter((item) => {
                        const matchesQuery = !query || `${item.reel_title || ""} ${item.reel_description || ""}`.toLowerCase().includes(query.toLowerCase());
                        const matchesStatus = !status || item.reel_status === status;
                        return matchesQuery && matchesStatus;
                    })
                    : nextItems;

                setItems(filteredItems);
                setTotal(projectId ? filteredItems.length : Number(data.total || 0));
            } catch (err) {
                if (cancelled) return;
                setError(err.message || "Unable to load reels");
                setItems([]);
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        async function loadProjectMeta() {
            if (!projectId) {
                setProjectMeta(null);
                return;
            }
            try {
                const response = await fetch(getApiUrl(`/api/projects/${projectId}`), {
                    headers: {
                        ...getAuthHeaders(user.id),
                    },
                });
                const data = await response.json();
                if (cancelled) return;
                if (response.ok) {
                    setProjectMeta(data || null);
                }
            } catch {
                // Best effort only for heading context.
            }
        }

        loadProjectMeta();
        loadReels();
        return () => {
            cancelled = true;
        };
    }, [user?.id, page, pageSize, query, status, projectId]);

    const refresh = async () => {
        if (!user?.id) return;
        setLoading(true);
        try {
            let response;
            if (projectId) {
                response = await fetch(getApiUrl(`/api/projects/${projectId}/reels`), {
                    headers: { ...getAuthHeaders(user.id) },
                });
            } else {
                const params = new URLSearchParams({
                    page: String(page),
                    page_size: String(pageSize),
                });
                if (query) params.set("q", query);
                if (status) params.set("status", status);
                response = await fetch(getApiUrl(`/api/reels?${params.toString()}`), {
                    headers: { ...getAuthHeaders(user.id) },
                });
            }
            const data = await response.json();
            if (!response.ok) {
                setError(data?.detail || "Refresh failed");
                setItems([]);
                return;
            }
            const rawItems = projectId ? data.reels : data.items;
            const nextItems = Array.isArray(rawItems) ? rawItems : [];
            const filteredItems = projectId
                ? nextItems.filter((item) => {
                    const matchesQuery = !query || `${item.reel_title || ""} ${item.reel_description || ""}`.toLowerCase().includes(query.toLowerCase());
                    const matchesStatus = !status || item.reel_status === status;
                    return matchesQuery && matchesStatus;
                })
                : nextItems;
            setItems(filteredItems);
            setTotal(projectId ? filteredItems.length : Number(data.total || 0));
        } catch (err) {
            setError(err.message || "Refresh failed");
        } finally {
            setLoading(false);
        }
    };

    const fetchFreshMediaUrl = async (reelId) => {
        const response = await fetch(getApiUrl(`/api/reels/${reelId}/media-url`), {
            headers: { ...getAuthHeaders(user.id) },
        });
        if (!response.ok) return null;
        const data = await response.json();
        return data.media_url || null;
    };

    const handleDelete = async (reelId) => {
        if (!user?.id) return;
        if (!globalThis.confirm(t("reels.confirmDelete", "Delete this reel?"))) return;

        setDeletingId(reelId);
        try {
            const response = await fetch(getApiUrl(`/api/reels/${reelId}`), {
                method: "DELETE",
                headers: {
                    ...getAuthHeaders(user.id),
                },
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Delete failed");
                return;
            }
            await refresh();
        } catch (err) {
            globalThis.alert(err.message || "Delete failed");
        } finally {
            setDeletingId("");
        }
    };

    const handleDownload = async (reelId) => {
        if (!user?.id) return;
        const currentItem = items.find((item) => item.id === reelId);
        const fallbackUrl = currentItem?.reel_download_url || currentItem?.reel_playback_url || currentItem?.reel_url || null;
        const mediaUrl = await fetchFreshMediaUrl(reelId);
        if (!mediaUrl) {
            if (fallbackUrl) {
                globalThis.open(fallbackUrl, "_blank", "noopener,noreferrer");
                return;
            }
            globalThis.alert(t("reels.noDownloadUrl", "No download URL available"));
            return;
        }

        globalThis.open(mediaUrl, "_blank", "noopener,noreferrer");
    };

    const handleShare = (item) => {
        if (!canShareReel) {
            setShareResult({ success: false, msg: t("reels.shareDisabledNoSubscription", "Un abonnement actif est requis pour publier.") });
            return;
        }
        setSharePlatforms({});
        setShareTitle(item?.reel_title || t("reels.defaultShareTitle", "Viral Short"));
        setShareDescription(item?.reel_description || "");
        setShareScheduling(false);
        setShareScheduleDate("");
        setShareResult(null);
        setShareModalItem(item);
    };

    const submitShare = async () => {
        if (!user?.id) return;
        if (!shareModalItem?.id) return;
        if (!canShareReel) {
            setShareResult({ success: false, msg: t("reels.shareDisabledNoSubscription", "Un abonnement actif est requis pour publier.") });
            return;
        }

        const selectedAccountIds = Object.keys(sharePlatforms).filter((k) => Boolean(sharePlatforms[k]));
        if (selectedAccountIds.length === 0) {
            setShareResult({ success: false, msg: t("reels.selectAtLeastOnePlatform", "Select at least one platform.") });
            return;
        }
        if (shareScheduling && !shareScheduleDate) {
            setShareResult({ success: false, msg: t("reels.selectDateTime", "Please select a date and time.") });
            return;
        }

        setSharingId(shareModalItem.id);
        setShareResult(null);
        try {
            const payload = {
                account_ids: selectedAccountIds,
                title: shareTitle || undefined,
                description: shareDescription || undefined,
            };
            if (shareScheduling && shareScheduleDate) {
                payload.scheduled_date = new Date(shareScheduleDate).toISOString();
                payload.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
            }

            const response = await fetch(getApiUrl(`/api/reels/${shareModalItem.id}/share`), {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(user.id),
                },
                body: JSON.stringify(payload),
            });

            if (!response.ok) {
                const errText = await response.text();
                let msg = t("reels.shareFailed", "Share failed");
                try {
                    const parsed = JSON.parse(errText);
                    msg = describePublishError(t, parsed?.detail, errText || msg);
                } catch {
                    msg = errText || msg;
                }
                setShareResult({ success: false, msg: `${t("reels.failedPrefix", "Failed")}: ${msg}` });
                return;
            }

            setShareResult({ success: true, msg: t("reels.shareSent", "Share request sent.") });
            setTimeout(() => {
                setShareResult(null);
                setShareModalItem(null);
            }, 1500);
        } catch (err) {
            setShareResult({ success: false, msg: `${t("reels.failedPrefix", "Failed")}: ${err.message || t("reels.shareFailed", "Share failed")}` });
        } finally {
            setSharingId("");
        }
    };



    const handlePreview = async (item) => {
        setPreviewItem(item);
        setPreviewUrl(item.media_url || item.reel_playback_url || item.reel_download_url || item.reel_url || "");
        const mediaUrl = await fetchFreshMediaUrl(item.id);
        if (mediaUrl) setPreviewUrl(mediaUrl);
    };

    const previewClip = previewItem ? toResultCardClip(previewItem, previewUrl) : null;
    const previewClipIndex = Number.isFinite(Number(previewItem?.reel_clip_index))
        ? Number(previewItem?.reel_clip_index)
        : 0;
    const previewJobId = typeof previewItem?.reel_job_id === "string" ? previewItem.reel_job_id : "";

    const breadcrumbItems = projectId
        ? [
            { label: t("breadcrumbs.dashboard", "Dashboard"), href: "/dashboard" },
            { label: t("breadcrumbs.reels", "Reels"), href: "/dashboard/reels" },
            { label: projectMeta?.name || t("projects.reelProjectTitle", "Projet Reel") },
        ]
        : [];

    return (
        <div className="flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div className="min-w-0 space-y-2">
                    {projectId ? (
                        <Breadcrumbs items={breadcrumbItems} ariaLabel={t('breadcrumbs.ariaLabel', 'Breadcrumb')} />
                    ) : (
                        <h1 className="text-3xl font-black tracking-tight">{t('reels.title', 'Generated reels')}</h1>
                    )} <br/>
                    {!projectId ? (
                        <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">
                            {t('reels.subtitle', 'Search, filter, delete, share and download.')}
                        </p>
                    ) : null}
                </div>

                {projectId ? (
                    <div className="flex flex-wrap items-center gap-2">
                        <button
                            type="button"
                            onClick={() => navigate(`/dashboard/reels/projects/${projectId}/manual`)}
                            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-500 to-green-500 px-4 py-2.5 text-sm font-bold text-black shadow-lg shadow-emerald-500/20 hover:from-emerald-400 hover:to-green-400"
                        >
                            <Scissors size={14} />
                            {t('projects.manualCreationButton', 'Creation manuelle')}
                        </button>
                    </div>
                ) : (
                    <button
                        type="button"
                        onClick={() => {
                            navigate("/dashboard/reel-generator?new=1");
                        }}
                        className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-bold shadow-lg shadow-blue-500/20 hover:from-blue-500 hover:to-indigo-500 transition-all"
                    >
                        <Plus size={16} />
                        {t('app.newOperation', 'Nouveau projet')}
                    </button>
                )}
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {!hasAnyReelCredit ? (
                    <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
                        {t("common.insufficientCreditsStart", "Insufficient credits to start this operation.")}
                    </div>
                ) : null}
                {shareResult ? (
                    <div className={`rounded-lg border px-3 py-2 text-xs ${shareResult.success ? 'border-green-500/30 bg-green-500/10 text-green-300' : 'border-red-500/30 bg-red-500/10 text-red-300'}`}>
                        {shareResult.msg}
                    </div>
                ) : null}
                <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-[1fr_220px_auto_auto]">
                    <label className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                        <input
                            value={queryInput}
                            onChange={(e) => setQueryInput(e.target.value)}
                            placeholder={t('reels.searchPlaceholder', 'Search by title or description...')}
                            className="w-full rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 py-2.5 pl-10 pr-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-primary/60"
                        />
                    </label>

                    <MobileFilterDropdown
                        value={status}
                        onChange={(nextValue) => {
                            setPage(1);
                            setStatus(nextValue);
                        }}
                        options={statusOptions}
                        ariaLabel={t('reels.allStatuses', 'All statuses')}
                    />

                    <select
                        value={status}
                        onChange={(e) => {
                            setPage(1);
                            setStatus(e.target.value);
                        }}
                        className="hidden rounded-xl border border-slate-300 dark:border-white/10 bg-black/30 px-3 py-2.5 text-sm text-white focus:outline-none focus:border-primary/60 md:block"
                    >
                        {statusOptions.map((option) => (
                            <option key={option.value || "all"} value={option.value}>{option.label}</option>
                        ))}
                    </select>

                    <button
                        type="button"
                        onClick={refresh}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                    >
                        {t('settings.refresh', 'Refresh')}
                    </button>

                </div>

                {loading && (
                    <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                        <span className="inline-flex items-center gap-2">
                            <Loader2 size={14} className="animate-spin" /> {t('reels.loading', 'Loading...')}
                        </span>
                    </div>
                )}

                {!loading && error && (
                    <div className="rounded-xl border border-red-500/30 bg-red-500/10 px-3 py-6 text-center text-red-300">{error}</div>
                )}

                {!loading && !error && items.length === 0 && (
                    <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                        {t('common.noItemsFound', 'Aucun element trouve')}
                    </div>
                )}

                <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
                    {!loading && !error && items.map((item) => {
                        const media = describeMediaAvailability(item.media_status, item.media_expires_at);
                        return (
                            <div key={item.id} className="space-y-2">
                                <GridThumbnail
                                    imageUrl={item.reel_thumbnail_url}
                                    aspect="portrait"
                                    durationLabel={`${item.reel_duration}s`}
                                    statusBadge={{ label: statusLabel(item.reel_status), className: statusClass(item.reel_status) }}
                                    badgePosition="bottom"
                                    onClick={() => handlePreview(item)}
                                    emptyLabel={t("generatedMedia.noPreview", "No preview available.")}
                                    alt={item.reel_title || ""}
                                    actions={
                                        <>
                                            <button
                                                type="button"
                                                onClick={(e) => { e.stopPropagation(); handlePreview(item); }}
                                                className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-slate-800 shadow-sm hover:bg-white"
                                                title={t('reels.preview', 'Preview')}
                                            >
                                                <Play size={16} />
                                            </button>

                                            <button
                                                type="button"
                                                onClick={(e) => { e.stopPropagation(); handleDownload(item.id); }}
                                                disabled={media.disabled}
                                                className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-slate-800 shadow-sm hover:bg-white disabled:opacity-50 disabled:cursor-not-allowed"
                                                title={t('reels.download', 'Download')}
                                            >
                                                <Download size={16} />
                                            </button>

                                            {!hideSocialPlatforms ? (
                                                <button
                                                    type="button"
                                                    onClick={(e) => { e.stopPropagation(); handleShare(item); }}
                                                    disabled={sharingId === item.id || !canShareReel}
                                                    className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-slate-800 shadow-sm hover:bg-white disabled:opacity-50"
                                                    title={t('reels.share', 'Share')}
                                                >
                                                    {sharingId === item.id ? <Loader2 size={16} className="animate-spin" /> : <Share2 size={16} />}
                                                </button>
                                            ) : null}

                                            <button
                                                type="button"
                                                onClick={(e) => { e.stopPropagation(); handleDelete(item.id); }}
                                                disabled={deletingId === item.id}
                                                className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-red-600 shadow-sm hover:bg-white disabled:opacity-50"
                                                title={t('reels.delete', 'Delete')}
                                            >
                                                {deletingId === item.id ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                                            </button>
                                        </>
                                    }
                                />
                                <p className="text-sm font-semibold text-slate-900 dark:text-white line-clamp-2">{item.reel_title || t("generatedMedia.untitled", "Untitled")}</p>
                                <p className="text-xs text-slate-500 dark:text-zinc-400 line-clamp-3">{item.reel_description || "-"}</p>
                                {media.translationKey ? (
                                    <p className="text-xs text-slate-500 dark:text-zinc-400">{t(media.translationKey, media.translationKey, media.params)}</p>
                                ) : null}
                            </div>
                        );
                    })}
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-2 sm:gap-0 border-t border-slate-300 dark:border-white/10 pt-4 text-sm">
                    <p className="text-slate-500 dark:text-zinc-400">{total} {t("reels.reelCount", "reel(s)")}</p>
                    <div className="flex w-full sm:w-auto items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t('reels.previous', 'Previous')}
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400 text-xs md:text-sm">
                            {t('reels.page', 'Page')} {page} / {totalPages}
                        </span>
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t('reels.next', 'Next')}
                        </button>
                    </div>
                </div>
            </section>

            {!hideSocialPlatforms ? (
                <SharePostModal
                    isOpen={Boolean(shareModalItem)}
                    onClose={() => setShareModalItem(null)}
                    title={shareTitle}
                    onTitleChange={setShareTitle}
                    description={shareDescription}
                    onDescriptionChange={setShareDescription}
                    isScheduling={shareScheduling}
                    onSchedulingChange={setShareScheduling}
                    scheduleDate={shareScheduleDate}
                    onScheduleDateChange={setShareScheduleDate}
                    selectedAccountIds={sharePlatforms}
                    onAccountToggle={(accountId, checked) => setSharePlatforms((prev) => ({ ...prev, [accountId]: checked }))}
                    isSubmitting={Boolean(shareModalItem && sharingId === shareModalItem.id)}
                    result={shareResult}
                    onSubmit={submitShare}
                />
            ) : null}

            {previewItem && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4 backdrop-blur-md">
                    <div className="flex w-full max-w-5xl flex-col overflow-hidden rounded-3xl border border-slate-300 dark:border-white/10 bg-white dark:bg-zinc-950 shadow-2xl">
                        <div className="flex items-center justify-between border-b border-slate-300 dark:border-white/10 px-4 py-3">
                            <div>
                                <p className="text-sm font-semibold text-slate-900 dark:text-white">{previewItem.reel_title || t("reels.previewTitle", "Reel preview")}</p>
                                <p className="text-xs text-slate-500 dark:text-zinc-400">{t("reels.previewSubtitle", "Preview with the same actions as generated clips.")}</p>
                            </div>
                            <button
                                type="button"
                                onClick={() => {
                                    setPreviewItem(null);
                                    setPreviewUrl("");
                                }}
                                className="rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 p-2 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-white/10"
                                title={t('app.close', 'Close')}
                            >
                                <X size={16} />
                            </button>
                        </div>
                        <div className="max-h-[88vh] overflow-y-auto p-4 custom-scrollbar bg-slate-50 dark:bg-zinc-950">
                            {previewClip && (
                                <ResultCard
                                    clip={previewClip}
                                    index={previewClipIndex}
                                    jobId={previewJobId}
                                    compactActions={false}
                                    hideVideoPreview
                                />
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
