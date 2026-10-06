import React from "react";
import { CreditCardIcon, Loader2, RefreshCw, AlertTriangle, Clock } from "lucide-react";
import { useUserCredits } from "../state/UserCreditsContext";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "../state/LanguageContext";
import { daysUntilDate } from "../lib/formatting";

function ProgressBar({ value, max, color = "green", label, unit = "" }) {
    const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0;
    const colors = {
        green:  "bg-green-500",
        blue:   "bg-blue-500",
        red:    "bg-red-500",
        purple: "bg-purple-500",
        zinc:   "bg-zinc-400",
        amber:  "bg-amber-400",
    };
    const barColor = pct < 20 ? "red" : pct < 50 ? "amber" : color;

    return (
        <div className="mb-4">
            <div className="flex justify-between text-xs text-slate-500 dark:text-zinc-400 mb-1">
                <span>{label}</span>
                <span className="font-mono">
                    {value.toLocaleString()}{unit} / {max.toLocaleString()}{unit}
                </span>
            </div>
            <div className="w-full bg-zinc-700/40 rounded-full overflow-hidden h-3">
                <div
                    className={`h-full ${colors[barColor] || colors.green} transition-all duration-500 ease-out rounded-full`}
                    style={{ width: `${pct}%` }}
                />
            </div>
        </div>
    );
}

export default function ServiceUsage() {
    const { credits, storage, creditMax, storageMax, hasCredits, aboCosts, loading, error, refresh, promotionalCredit, promotionalCreditExpirations } = useUserCredits();
    const navigate = useNavigate();
    const { t } = useTranslation();

    // Estimate a "max" credit pool for display.
    // We take 10× the reel cost as the reference maximum (so users see a meaningful bar).
    const creditLimit = Math.max(0, Number(creditMax ?? aboCosts?.credit ?? 0));
    const storageLimit = Math.max(0, Number(storageMax ?? aboCosts?.storage ?? 0));

    if (loading && credits === 0) {
        return (
            <div className="p-4 flex items-center gap-2 text-slate-500 dark:text-zinc-400 text-sm">
                <Loader2 size={16} className="animate-spin" /> Chargement du solde...
            </div>
        );
    }

    return (
        <div className="p-4">
            {error && (
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
                    <AlertTriangle size={14} />
                    <span>{error}</span>
                    <button onClick={refresh} className="ml-auto text-red-300 hover:text-white">
                        <RefreshCw size={13} />
                    </button>
                </div>
            )}

            {/* Credit balance bar */}
            <ProgressBar
                label="Crédits disponibles"
                value={credits}
                max={creditLimit}
                color="blue"
                unit=" cr"
            />

            {/* Standard/promotional split -- total available always combines
                both pools, but they're distinct batches on the backend. */}
            {promotionalCredit > 0 && (
                <div className="mb-4 -mt-2 rounded-lg border border-slate-200 dark:border-white/5 bg-black/10 px-3 py-2">
                    <p className="text-xs text-slate-600 dark:text-zinc-300">
                        {t("serviceUsage.totalAvailable", "{{total}} crédits disponibles", { total: (credits + promotionalCredit).toLocaleString() })}
                    </p>
                    <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">
                        {t("serviceUsage.creditsBreakdown", "{{standard}} crédits standards · {{promo}} crédits promotionnels", {
                            standard: credits.toLocaleString(),
                            promo: promotionalCredit.toLocaleString(),
                        })}
                    </p>
                    {promotionalCreditExpirations.length > 0 && (
                        <ul className="mt-1.5 space-y-0.5">
                            {promotionalCreditExpirations.map((batch, index) => {
                                const days = daysUntilDate(batch.expires_at);
                                if (days === null) return null;
                                return (
                                    <li key={`${batch.expires_at}-${index}`} className="flex items-center gap-1.5 text-[0.7rem] text-amber-600 dark:text-amber-400">
                                        <Clock size={11} />
                                        {t("serviceUsage.expiringBatch", "{{amount}} crédits expirent dans {{days}} jour(s)", {
                                            amount: Number(batch.amount).toLocaleString(),
                                            days,
                                        })}
                                    </li>
                                );
                            })}
                        </ul>
                    )}
                </div>
            )}

            {/* Storage bar (GB) */}
            <ProgressBar
                label="Stockage disponibles"
                value={Number.parseFloat(storage.toFixed(2))}
                max={storageLimit}
                color="purple"
                unit=" Go"
            />

            {/* Warning if low credits */}
            {hasCredits === false && (
                <div className="flex items-center justify-between gap-4 mt-2">
                    <div className="flex-1 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg">
                        <p className="text-xs text-amber-300 leading-relaxed">
                            Crédits insuffisants — rechargez votre compte pour continuer.
                        </p>
                    </div>

                    <button
                        onClick={() => navigate("/dashboard/abonnements")}
                        className="flex shrink-0 items-center justify-center gap-2 rounded-2xl border border-green-500/20 bg-green-500/10 px-4 py-3 text-sm font-semibold text-green-300 transition hover:bg-green-500/15"
                    >
                        <CreditCardIcon size={18} />
                        Gérer
                    </button>
                </div>
            )}


        </div>
    );
}