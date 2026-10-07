import { useEffect, useMemo, useState } from "react";
import { Edit3, FolderOpen, Loader2, Plus, Search, Trash2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { getApiUrl } from "../config";
import GridThumbnail from "../components/GridThumbnail";
import MobileFilterDropdown from "../components/MobileFilterDropdown";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";
import { statusClass, statusLabel } from "../lib/status";
import { getAuthHeaders } from "../lib/apiAuth";

// Hard character cap with an ellipsis, on top of the CSS line-clamp: a
// single long unbroken word (no spaces to wrap on) can still stretch a
// table-fixed column and force horizontal scroll even with overflow
// clipping, so the string itself needs to be cut down.
function truncateText(value, maxLength) {
    const text = String(value || "").trim();
    if (!text || text.length <= maxLength) return text;
    return `${text.slice(0, maxLength).trimEnd()}…`;
}

function formatDurationHms(value) {
    const total = Number(value || 0);
    if (!Number.isFinite(total) || total <= 0) return "-";
    const sec = Math.max(0, Math.round(total));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function CaptionProjectsPage() {
    const { user } = useAuth();
    const { t } = useTranslation();
    const navigate = useNavigate();

    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [page, setPage] = useState(1);
    const [pageSize] = useState(15);
    const [total, setTotal] = useState(0);
    const [queryInput, setQueryInput] = useState("");
    const [query, setQuery] = useState("");
    const [status, setStatus] = useState("");
    const [savingId, setSavingId] = useState("");
    const [deletingId, setDeletingId] = useState("");
    const statusOptions = [
        { value: "", label: t("reels.allStatuses", "All statuses") },
        { value: "processing", label: t("reels.statusInProgress", "In progress") },
        { value: "completed", label: t("reels.statusDone", "Done") },
        { value: "failed", label: t("reels.statusFailed", "Failed") },
        { value: "cancelled", label: t("projects.statusCancelled", "Cancelled") },
    ];

    const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [total, pageSize]);

    useEffect(() => {
        const timer = setTimeout(() => {
            setPage(1);
            setQuery(queryInput.trim());
        }, 350);
        return () => clearTimeout(timer);
    }, [queryInput]);

    const loadProjects = async () => {
        if (!user?.id) return;
        setLoading(true);
        setError("");
        try {
            const params = new URLSearchParams({
                page: String(page),
                page_size: String(pageSize),
                project_type: "caption",
            });
            if (query) params.set("q", query);
            if (status) params.set("status", status);

            const response = await fetch(getApiUrl(`/api/projects?${params.toString()}`), {
                headers: getAuthHeaders(user.id),
            });
            const data = await response.json();
            if (!response.ok) {
                setError(data?.detail || "Unable to load projects");
                setItems([]);
                return;
            }
            setItems(Array.isArray(data.items) ? data.items : []);
            setTotal(Number(data.total || 0));
        } catch (err) {
            setError(err.message || "Unable to load projects");
            setItems([]);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadProjects();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [user?.id, page, pageSize, query, status]);

    const handleOpenProject = (project) => {
        const projectId = project?.id;
        if (!projectId) return;

        if (project?.status === "completed") {
            navigate(`/dashboard/captions/projects/${projectId}?autoplay=1`);
            return;
        }

        if (project?.status === "processing" || project?.status === "failed" || project?.status === "cancelled") {
            navigate(`/dashboard/captions/new?project_id=${encodeURIComponent(projectId)}`);
            return;
        }

        // Defensive fallback: always keep project context attached.
        navigate(`/dashboard/captions/new?project_id=${encodeURIComponent(projectId)}`);
    };

    const handleRename = async (project) => {
        if (!project?.id || !user?.id) return;
        const nextName = globalThis.prompt(t("projects.renamePrompt", "Nouveau nom du projet"), project.name || "");
        if (nextName == null) return;
        const trimmed = nextName.trim();
        if (!trimmed || trimmed === project.name) return;

        setSavingId(project.id);
        try {
            const response = await fetch(getApiUrl(`/api/projects/${project.id}`), {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(user.id),
                },
                body: JSON.stringify({ name: trimmed }),
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Rename failed");
                return;
            }
            await loadProjects();
        } catch (err) {
            setError(err.message || "Rename failed");
        } finally {
            setSavingId("");
        }
    };

    const handleDelete = async (project) => {
        if (!project?.id || !user?.id) return;
        if (!globalThis.confirm(t("projects.confirmDelete", "Supprimer ce projet ?"))) return;

        setDeletingId(project.id);
        try {
            const response = await fetch(getApiUrl(`/api/projects/${project.id}`), {
                method: "DELETE",
                headers: getAuthHeaders(user.id),
            });
            if (!response.ok) {
                const detail = await response.text();
                setError(detail || "Delete failed");
                return;
            }
            await loadProjects();
        } catch (err) {
            setError(err.message || "Delete failed");
        } finally {
            setDeletingId("");
        }
    };

    return (
        <div className="captions-page-shell flex-1 overflow-y-auto p-8 space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <h1 className="text-3xl font-black tracking-tight">{t("common.soustitres", "Mes sous-titres")}</h1>
                    <p className="mt-2 text-sm text-slate-500 dark:text-zinc-400">{t("common.page-des", "Organisez vos opérations sans changer vos actions habituelles.")}</p>
                </div>
                <button
                    type="button"
                    onClick={() => navigate("/dashboard/captions/new")}
                    className="w-full md:w-auto flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 text-white text-sm font-bold shadow-lg shadow-blue-500/20 hover:from-blue-500 hover:to-indigo-500 transition-all"
                >
                    <Plus size={16} />
                    {t("app.newOperation", "Nouveau projet")}
                </button>
            </div>

            <section className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-4 md:p-5 space-y-4">
                {error ? <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">{error}</div> : null}

                <div className="grid gap-3 grid-cols-1 sm:grid-cols-2 md:grid-cols-[1fr_220px_auto]">
                    <label className="relative">
                        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-zinc-500" />
                        <input
                            value={queryInput}
                            onChange={(e) => setQueryInput(e.target.value)}
                            placeholder={t("projects.searchPlaceholder", "Rechercher par nom ou description...")}
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
                        ariaLabel={t("reels.allStatuses", "All statuses")}
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
                        onClick={loadProjects}
                        className="rounded-xl border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-4 py-2.5 text-sm font-medium text-slate-800 dark:text-zinc-200 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10"
                    >
                        {t("settings.refresh", "Refresh")}
                    </button>
                </div>

                {loading ? (
                    <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">
                        <span className="inline-flex items-center gap-2"><Loader2 size={14} className="animate-spin" /> {t("reels.loading", "Loading...")}</span>
                    </div>
                ) : null}

                {!loading && items.length === 0 ? (
                    <div className="rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-3 py-6 text-center text-slate-500 dark:text-zinc-400">{t("common.noItemsFound", "Aucun element trouve")}</div>
                ) : null}

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                    {!loading && !error && items.map((item) => (
                        <div key={item.id} className="space-y-2">
                            <GridThumbnail
                                imageUrl={item.thumbnail_url}
                                aspect="video"
                                durationLabel={formatDurationHms(item.source_duration)}
                                statusBadge={{ label: statusLabel(item.status), className: statusClass(item.status) }}
                                badgePosition="top"
                                onClick={() => handleOpenProject(item)}
                                emptyLabel={t("projects.noPreview", "Aucun aperçu")}
                                actions={
                                    <>
                                        <button
                                            type="button"
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleOpenProject(item);
                                            }}
                                            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-sky-800 shadow-sm hover:bg-white"
                                            title={t("projects.open", "Ouvrir")}
                                        >
                                            <FolderOpen size={16} />
                                        </button>
                                        <button
                                            type="button"
                                            disabled={savingId === item.id}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleRename(item);
                                            }}
                                            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-amber-800 shadow-sm hover:bg-white disabled:opacity-50"
                                            title={t("projects.rename", "Renommer")}
                                        >
                                            {savingId === item.id ? <Loader2 size={16} className="animate-spin" /> : <Edit3 size={16} />}
                                        </button>
                                        <button
                                            type="button"
                                            disabled={deletingId === item.id}
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                handleDelete(item);
                                            }}
                                            className="inline-flex h-9 w-9 items-center justify-center rounded-full bg-white/90 text-red-700 shadow-sm hover:bg-white disabled:opacity-50"
                                            title={t("projects.delete", "Supprimer")}
                                        >
                                            {deletingId === item.id ? <Loader2 size={16} className="animate-spin" /> : <Trash2 size={16} />}
                                        </button>
                                    </>
                                }
                            />
                            <p
                                className="cursor-pointer text-sm font-semibold text-slate-900 dark:text-white line-clamp-2"
                                onClick={() => handleOpenProject(item)}
                            >
                                {item.name || t("generatedMedia.untitled", "Untitled")}
                            </p>
                        </div>
                    ))}
                </div>

                <div className="flex flex-col sm:flex-row items-center justify-between gap-2 sm:gap-0 border-t border-slate-300 dark:border-white/10 pt-4 text-sm">
                    <p className="text-slate-500 dark:text-zinc-400">{total} {t("projects.count", "projet(s)")}</p>
                    <div className="flex w-full sm:w-auto items-center gap-2">
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.max(1, p - 1))}
                            disabled={page <= 1}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t("reels.previous", "Previous")}
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400 text-xs md:text-sm">{t("reels.page", "Page")} {page} / {totalPages}</span>
                        <button
                            type="button"
                            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                            disabled={page >= totalPages}
                            className="w-full sm:w-auto rounded-lg border border-slate-300 dark:border-white/10 bg-slate-100 dark:bg-white/5 px-2 md:px-3 py-1.5 text-xs md:text-sm font-medium text-slate-800 dark:text-zinc-300 shadow-sm hover:bg-slate-200 dark:hover:bg-white/10 disabled:opacity-40"
                        >
                            {t("reels.next", "Next")}
                        </button>
                    </div>
                </div>
            </section>
        </div>
    );
}

