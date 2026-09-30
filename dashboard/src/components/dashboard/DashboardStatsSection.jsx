import { useEffect, useState } from "react";
import { Clapperboard, Coins, Loader2, MessageSquareText, Quote, Sparkles, CheckCircle2 } from "lucide-react";
import {
    ResponsiveContainer,
    LineChart,
    Line,
    AreaChart,
    Area,
    BarChart,
    Bar,
    CartesianGrid,
    XAxis,
    YAxis,
    Tooltip,
    Legend,
    Cell,
} from "recharts";
import { useAuth } from "../../state/AuthContext";
import { getApiUrl } from "../../config";
import { getAuthHeaders } from "../../lib/apiAuth";
import { useTranslation } from "../../state/LanguageContext";

const RANGE_OPTIONS = [
    { value: "7d", labelKey: "dashboard.range7d", fallback: "7 jours" },
    { value: "30d", labelKey: "dashboard.range30d", fallback: "30 jours" },
    { value: "90d", labelKey: "dashboard.range90d", fallback: "90 jours" },
    { value: "all", labelKey: "dashboard.rangeAll", fallback: "Tout" },
];

// Fixed per-feature accents, matching dashboard-nav.js's sidebar colors
// (violet/yellow/pink/teal) -- kept stable regardless of the selected
// range so a series never repaints color when the filter changes.
const CONTENT_TYPE_SERIES = [
    { key: "reels", color: "#a78bfa", labelKey: "dashboard.chartLegendReels", fallback: "Réels" },
    { key: "captions", color: "#facc15", labelKey: "dashboard.chartLegendCaptions", fallback: "Sous-titres" },
    { key: "anonymous_stories", color: "#f472b6", labelKey: "dashboard.chartLegendAnonymousStories", fallback: "Histoires anonymes" },
    { key: "film_summaries", color: "#2dd4bf", labelKey: "dashboard.chartLegendFilmSummaries", fallback: "Résumé de film" },
];

const PLATFORM_COLORS = {
    facebook: "#1877F2",
    instagram: "#E4405F",
    tiktok: "#0f172a",
    youtube: "#FF0000",
    linkedin: "#0A66C2",
    default: "#94a3b8",
};

const CARD_CLASS = "rounded-xl border border-slate-300 dark:border-white/10 bg-white dark:bg-white/[0.03]";

function StatTile({ icon: Icon, iconClass, value, label }) {
    return (
        <div className={`${CARD_CLASS} p-4 flex flex-col gap-2`}>
            <span className={`inline-flex h-8 w-8 items-center justify-center rounded-lg ${iconClass}`}>
                <Icon size={16} />
            </span>
            <span className="text-2xl font-black tracking-tight text-slate-900 dark:text-white">{value}</span>
            <span className="text-xs text-slate-500 dark:text-zinc-400">{label}</span>
        </div>
    );
}

function RangePills({ range, onChange, t }) {
    return (
        <div className="flex flex-wrap gap-2">
            {RANGE_OPTIONS.map((opt) => (
                <button
                    key={opt.value}
                    onClick={() => onChange(opt.value)}
                    className={`px-3 py-1.5 rounded-full text-xs font-semibold border transition ${
                        range === opt.value
                            ? "bg-primary/15 border-primary/30 text-primary"
                            : "border-slate-300 dark:border-white/10 text-slate-500 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-white/5"
                    }`}
                >
                    {t(opt.labelKey, opt.fallback)}
                </button>
            ))}
        </div>
    );
}

function formatCredits(value) {
    const num = Number(value) || 0;
    return num % 1 === 0 ? String(num) : num.toFixed(1);
}

function isStatsEmpty(stats) {
    if (!stats) return true;
    const totals = stats.totals || {};
    const allZero = Object.values(totals).every((v) => !v);
    const noDaily = !Array.isArray(stats.daily) || stats.daily.length === 0;
    return allZero && noDaily;
}

async function fetchDashboardStats(userId, range) {
    const response = await fetch(getApiUrl(`/api/dashboard/stats?range=${range}`), {
        headers: getAuthHeaders(userId),
    });
    if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Unable to load dashboard stats");
    }
    return response.json();
}

export default function DashboardStatsSection({ range, onRangeChange }) {
    const { user } = useAuth();
    const { t } = useTranslation();
    const [stats, setStats] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    useEffect(() => {
        if (!user?.id) return undefined;
        let cancelled = false;
        (async () => {
            try {
                setLoading(true);
                setError("");
                const data = await fetchDashboardStats(user.id, range);
                if (!cancelled) setStats(data);
            } catch (err) {
                if (!cancelled) setError(err.message || t("dashboard.statsError", "Impossible de charger les statistiques."));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [user?.id, range, t]);

    const totals = stats?.totals || {};
    const daily = Array.isArray(stats?.daily) ? stats.daily : [];
    const publicationsByPlatform = Array.isArray(stats?.publications_by_platform) ? stats.publications_by_platform : [];

    return (
        <section className="space-y-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-400 dark:text-zinc-500">
                        {t("dashboard.statsEyebrow", "Vue d'ensemble")}
                    </p>
                    <h3 className="mt-2 text-xl font-bold">{t("dashboard.statsTitle", "Statistiques")}</h3>
                </div>
                <RangePills range={range} onChange={onRangeChange} t={t} />
            </div>

            {error ? (
                <div className="p-4 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
            ) : loading ? (
                <div className="flex items-center justify-center h-40">
                    <Loader2 size={28} className="text-primary animate-spin" />
                </div>
            ) : isStatsEmpty(stats) ? (
                <div className={`${CARD_CLASS} p-8 text-center text-sm text-slate-500 dark:text-zinc-400`}>
                    {t("dashboard.statsEmpty", "Aucune donnee sur cette periode.")}
                </div>
            ) : (
                <>
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
                        <StatTile icon={Sparkles} iconClass="bg-violet-500/10 text-violet-400" value={totals.reels ?? 0} label={t("dashboard.statReels", "Reels")} />
                        <StatTile icon={MessageSquareText} iconClass="bg-yellow-500/10 text-yellow-500" value={totals.captions ?? 0} label={t("dashboard.statCaptions", "Sous-titres")} />
                        <StatTile icon={Quote} iconClass="bg-pink-500/10 text-pink-400" value={totals.anonymous_stories ?? 0} label={t("dashboard.statAnonymousStories", "Histoires anonymes")} />
                        <StatTile icon={Clapperboard} iconClass="bg-teal-500/10 text-teal-400" value={totals.film_summaries ?? 0} label={t("dashboard.statFilmSummaries", "Résumés de film")} />
                        <StatTile icon={CheckCircle2} iconClass="bg-emerald-500/10 text-emerald-400" value={totals.publications_done ?? 0} label={t("dashboard.statPublicationsDone", "Publications réussies")} />
                        <StatTile icon={Coins} iconClass="bg-amber-500/10 text-amber-400" value={formatCredits(totals.credits_consumed)} label={t("dashboard.statCreditsConsumed", "Crédits consommés")} />
                    </div>

                    <div className="grid gap-4 lg:grid-cols-2">
                        <div className={`${CARD_CLASS} p-4`}>
                            <p className="text-sm font-semibold mb-3 text-slate-700 dark:text-zinc-200">
                                {t("dashboard.chartActivity", "Activité par type de contenu")}
                            </p>
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={daily} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-white/10" />
                                        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <Tooltip />
                                        <Legend wrapperStyle={{ fontSize: 11 }} />
                                        {CONTENT_TYPE_SERIES.map((series) => (
                                            <Line
                                                key={series.key}
                                                type="monotone"
                                                dataKey={series.key}
                                                name={t(series.labelKey, series.fallback)}
                                                stroke={series.color}
                                                strokeWidth={2}
                                                dot={false}
                                            />
                                        ))}
                                    </LineChart>
                                </ResponsiveContainer>
                            </div>
                        </div>

                        <div className={`${CARD_CLASS} p-4`}>
                            <p className="text-sm font-semibold mb-3 text-slate-700 dark:text-zinc-200">
                                {t("dashboard.chartCredits", "Crédits consommés")}
                            </p>
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <AreaChart data={daily} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-white/10" />
                                        <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} />
                                        <Tooltip />
                                        <Area
                                            type="monotone"
                                            dataKey="credits_consumed"
                                            name={t("dashboard.statCreditsConsumed", "Crédits consommés")}
                                            stroke="#f59e0b"
                                            fill="#f59e0b"
                                            fillOpacity={0.2}
                                        />
                                    </AreaChart>
                                </ResponsiveContainer>
                            </div>
                        </div>
                    </div>

                    <div className={`${CARD_CLASS} p-4`}>
                        <p className="text-sm font-semibold mb-3 text-slate-700 dark:text-zinc-200">
                            {t("dashboard.chartPublicationsByPlatform", "Publications par plateforme")}
                        </p>
                        {publicationsByPlatform.length === 0 ? (
                            <p className="text-sm text-slate-500 dark:text-zinc-400 py-6 text-center">
                                {t("dashboard.statsEmpty", "Aucune donnee sur cette periode.")}
                            </p>
                        ) : (
                            <div className="h-64">
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={publicationsByPlatform} margin={{ top: 4, right: 8, left: -16, bottom: 0 }}>
                                        <CartesianGrid strokeDasharray="3 3" className="stroke-slate-200 dark:stroke-white/10" />
                                        <XAxis dataKey="platform" tick={{ fontSize: 11 }} />
                                        <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                                        <Tooltip />
                                        <Bar dataKey="count" name={t("dashboard.publications", "Publications")} radius={[6, 6, 0, 0]}>
                                            {publicationsByPlatform.map((entry) => (
                                                <Cell key={entry.platform} fill={PLATFORM_COLORS[entry.platform] || PLATFORM_COLORS.default} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            </div>
                        )}
                    </div>
                </>
            )}
        </section>
    );
}
