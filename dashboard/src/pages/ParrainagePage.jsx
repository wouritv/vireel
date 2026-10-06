import { useEffect, useState } from "react";
import { Check, Copy, Gift, Loader2, Users } from "lucide-react";
import { getApiUrl } from "../config.js";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useTranslation } from "../state/LanguageContext";

const STATUS_CHIP_STYLE = {
    pending: "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300",
    rewarded: "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
    invalid: "border-slate-300 dark:border-white/10 bg-white/5 text-slate-500 dark:text-zinc-400",
};

export default function ParrainagePage() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const [config, setConfig] = useState(null);
    const [referralInfo, setReferralInfo] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        if (!user?.id) return;
        let cancelled = false;

        async function loadData() {
            setLoading(true);
            setError("");
            try {
                const [configRes, meRes] = await Promise.all([
                    fetch(getApiUrl("/api/referrals/config")),
                    fetch(getApiUrl("/api/referrals/me"), { headers: getAuthHeaders(user.id) }),
                ]);

                if (cancelled) return;

                if (configRes.ok) setConfig(await configRes.json());
                if (!meRes.ok) {
                    setError(t("parrainage.loadError", "Impossible de charger tes informations de parrainage."));
                    return;
                }
                setReferralInfo(await meRes.json());
            } catch {
                if (!cancelled) setError(t("parrainage.loadError", "Impossible de charger tes informations de parrainage."));
            } finally {
                if (!cancelled) setLoading(false);
            }
        }

        loadData();
        return () => {
            cancelled = true;
        };
    }, [user?.id]);

    const handleCopy = async () => {
        if (!referralInfo?.link) return;
        try {
            await navigator.clipboard.writeText(referralInfo.link);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        } catch {
            // Clipboard access denied -- the link is still visible to copy manually.
        }
    };

    const statusLabel = (status) => {
        if (status === "pending") return t("parrainage.statusPending", "En attente d'abonnement");
        if (status === "rewarded") return t("parrainage.statusRewarded", "Récompense attribuée");
        return t("parrainage.statusInvalid", "Invalide");
    };

    if (loading) {
        return (
            <div className="h-full flex items-center justify-center p-8">
                <Loader2 size={20} className="animate-spin text-primary" />
            </div>
        );
    }

    return (
        <div className="h-full overflow-y-auto p-8 max-w-4xl mx-auto animate-[fadeIn_0.3s_ease-out]">
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">{t("parrainage.title", "Parrainage")}</h1>
                <p className="text-slate-500 dark:text-zinc-400 text-sm">
                    {t("parrainage.subtitle", "Invite tes amis sur Vireel et gagnez tous les deux des crédits promotionnels.")}
                </p>
            </div>

            {error && (
                <p className="mb-6 text-sm text-red-400">{error}</p>
            )}

            {referralInfo && (
                <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-6 mb-6">
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-3">
                        {t("parrainage.yourLink", "Ton lien de parrainage")}
                    </p>
                    <div className="flex flex-wrap items-center gap-3">
                        <code className="flex-1 min-w-[200px] rounded-xl border border-slate-300 dark:border-white/10 bg-black/20 px-4 py-3 text-sm text-slate-800 dark:text-zinc-200 break-all">
                            {referralInfo.link}
                        </code>
                        <button
                            type="button"
                            onClick={handleCopy}
                            className="inline-flex items-center gap-2 rounded-xl border border-slate-300 dark:border-white/10 bg-white/5 px-4 py-3 text-sm font-medium text-slate-800 dark:text-zinc-200 hover:bg-white/10 transition"
                        >
                            {copied ? <Check size={16} className="text-emerald-400" /> : <Copy size={16} />}
                            {copied ? t("parrainage.copied", "Copié !") : t("parrainage.copy", "Copier")}
                        </button>
                    </div>
                </div>
            )}

            {config && (
                <div className="rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6 mb-6">
                    <div className="flex items-center gap-3 mb-3">
                        <div className="p-2 rounded-lg bg-blue-500/10">
                            <Gift size={20} className="text-blue-400" />
                        </div>
                        <h2 className="text-lg font-semibold">{t("parrainage.rewardsTitle", "Comment ça marche")}</h2>
                    </div>
                    <p className="text-sm leading-6 text-slate-700 dark:text-zinc-300">
                        {t(
                            "parrainage.rewardsCopy",
                            "Ton ami reçoit {{signupBonus}} crédits promotionnels à l'inscription. Toi, tu reçois {{monthlyBonus}} crédits s'il choisit un abonnement mensuel, {{annualBonus}} crédits s'il choisit annuel. Aucune limite de parrainage.",
                            {
                                signupBonus: config.signup_bonus_credits,
                                monthlyBonus: config.monthly_bonus_credits,
                                annualBonus: config.annual_bonus_credits,
                            }
                        )}
                    </p>
                </div>
            )}

            {referralInfo && (
                <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-5">
                        <p className="text-xs text-slate-500 dark:text-zinc-400 mb-1">{t("parrainage.referredCount", "Filleuls")}</p>
                        <p className="text-2xl font-bold">{referralInfo.referred_count ?? 0}</p>
                    </div>
                    <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-5">
                        <p className="text-xs text-slate-500 dark:text-zinc-400 mb-1">{t("parrainage.rewardedCount", "Récompenses obtenues")}</p>
                        <p className="text-2xl font-bold">{referralInfo.rewarded_count ?? 0}</p>
                    </div>
                </div>
            )}

            <div className="rounded-2xl border border-slate-300 dark:border-white/10 bg-white/5 p-6">
                <div className="flex items-center gap-3 mb-4">
                    <Users size={20} className="text-slate-500 dark:text-zinc-400" />
                    <h2 className="text-lg font-semibold">{t("parrainage.referralsListTitle", "Tes filleuls")}</h2>
                </div>

                {(!referralInfo?.referrals || referralInfo.referrals.length === 0) ? (
                    <p className="text-sm text-slate-500 dark:text-zinc-400">
                        {t("parrainage.noReferrals", "Aucun filleul pour le moment. Partage ton lien pour commencer !")}
                    </p>
                ) : (
                    <ul className="flex flex-col gap-3">
                        {referralInfo.referrals.map((referral, index) => (
                            <li
                                key={`${referral.label}-${index}`}
                                className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 dark:border-white/5 bg-black/20 px-4 py-3"
                            >
                                <span className="text-sm font-medium text-slate-800 dark:text-zinc-200">{referral.label}</span>
                                <span className={`text-xs px-2.5 py-1 rounded-full border ${STATUS_CHIP_STYLE[referral.status] || STATUS_CHIP_STYLE.invalid}`}>
                                    {statusLabel(referral.status)}
                                </span>
                            </li>
                        ))}
                    </ul>
                )}
            </div>
        </div>
    );
}
