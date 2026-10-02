import React, {useEffect, useState} from "react";
import {Check, X, CreditCardIcon, Star, Crown, Sparkles, Zap, Building2, Loader2, Coins, Plus, Minus, MessageCircle} from "lucide-react";
import {getApiUrl} from "../config.js";
import { getAuthHeaders } from "../lib/apiAuth";
import { useAuth } from "../state/AuthContext";
import { useUserCredits } from "../state/UserCreditsContext";
import { useTranslation } from "../state/LanguageContext";

// Every value here must be a complete, literal Tailwind class string --
// Tailwind's build-time scanner only picks up classes it can see written
// out in full in source files, so a template literal like
// `bg-gradient-to-br from-${plan.color}-500/30` (the previous approach,
// used directly in the JSX below) can never work: whatever color name
// comes back from the DB, Tailwind never generates that class, so the
// icon chip silently rendered with no gradient at all, for every color.
const colorStyles = {
    zinc: {
        border: "border-zinc-500/20",
        bg: "bg-zinc-500/10",
        gradient: "bg-gradient-to-br from-zinc-500/30 to-zinc-700/30",
        icon: "text-slate-700 dark:text-zinc-300",
        button: "border-zinc-500/20 bg-zinc-500/10 text-slate-700 dark:text-zinc-300 hover:bg-zinc-500/15",
        check: "text-slate-500 dark:text-zinc-400",
    },
    blue: {
        border: "border-blue-500/30",
        bg: "bg-blue-500/10",
        gradient: "bg-gradient-to-br from-blue-500/30 to-blue-700/30",
        // A dark-mode-only shade (e.g. text-blue-300 with no light-mode
        // pairing) sits almost invisibly light against this page's light
        // background -- every color below now pairs a readable light-mode
        // shade with its dark-mode one, matching zinc's existing pattern.
        icon: "text-blue-700 dark:text-blue-300",
        button: "border-blue-500/20 bg-blue-500/10 text-blue-700 dark:text-blue-300 hover:bg-blue-500/15",
        check: "text-blue-600 dark:text-blue-400",
    },
    purple: {
        border: "border-purple-500/20",
        bg: "bg-purple-500/10",
        gradient: "bg-gradient-to-br from-purple-500/30 to-purple-700/30",
        icon: "text-purple-700 dark:text-purple-300",
        button: "border-purple-500/20 bg-purple-500/10 text-purple-700 dark:text-purple-300 hover:bg-purple-500/15",
        check: "text-purple-600 dark:text-purple-400",
    },
    amber: {
        border: "border-amber-500/30",
        bg: "bg-amber-500/10",
        gradient: "bg-gradient-to-br from-amber-500/30 to-amber-700/30",
        icon: "text-amber-700 dark:text-amber-300",
        button: "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500/15",
        check: "text-amber-600 dark:text-amber-400",
    },
    green: {
        border: "border-emerald-500/30",
        bg: "bg-emerald-500/10",
        gradient: "bg-gradient-to-br from-emerald-500/30 to-emerald-700/30",
        icon: "text-emerald-700 dark:text-emerald-300",
        button: "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 hover:bg-emerald-500/15",
        check: "text-emerald-600 dark:text-emerald-400",
    },
    red: {
        border: "border-rose-500/30",
        bg: "bg-rose-500/10",
        gradient: "bg-gradient-to-br from-rose-500/30 to-rose-700/30",
        icon: "text-rose-700 dark:text-rose-300",
        button: "border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300 hover:bg-rose-500/15",
        check: "text-rose-600 dark:text-rose-400",
    },
};
// The abonnement table's "icon" column hasn't reliably matched any
// string this page recognizes (see iconMap below), leaving every plan to
// fall back to the same Star icon -- indistinguishable from one another.
// Keying on the plan's exact name instead is the one mapping guaranteed
// to be right, since it's the one actually confirmed plan-by-plan.
const planIconByName = {
    "ViReel Discover": Star,
    "ViReel Publish": Sparkles,
    "ViReel Creator": Crown,
    "ViReel Studio": Building2,
};
// A plan whose "color" column doesn't match any key above (e.g. a newly
// added plan, or a value not yet mapped) falls back here instead of
// crashing on `styles.border`.
const defaultColorStyle = colorStyles.zinc;

// Keyed defensively on common casings (Crown/crown) since the exact
// string in the DB's "icon" column isn't guaranteed to match a
// component's PascalCase export name.
const iconMap = {
    Crown: Crown, crown: Crown,
    Star: Star, star: Star,
    Sparkles: Sparkles, sparkles: Sparkles,
    Zap: Zap, zap: Zap,
    Building2: Building2, building2: Building2,
};

export default function AbonnementPage() {
    const { t } = useTranslation();
    const { user } = useAuth();
    const { credits, creditMax, refresh: refreshCredits } = useUserCredits();
    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [souscription, setSouscription] = useState(null);
    const [loadingPlanId, setLoadingPlanId] = useState("");
    const [paymentMessage, setPaymentMessage] = useState("");

    // Buy credits
    const [buyAmount, setBuyAmount] = useState(10);
    const [buyLoading, setBuyLoading] = useState(false);
    const [buyError, setBuyError] = useState("");
    const CREDIT_RATE = 100;
    const creditsToAdd = Math.round(buyAmount * CREDIT_RATE);
    const currentPlan = items.find((plan) => String(plan.id) === String(souscription?.abonnement || "")) || null;

    useEffect(() => {
        const params = new URLSearchParams(globalThis.location.search || "");
        const payment = params.get("payment");
        if (payment === "success") {
            setPaymentMessage(t("abonnement.paiementOK","Paiement confirme. Votre abonnement sera active sous peu."));
            refreshCredits();
        } else if (payment === "cancel") {
            setPaymentMessage(t("abonnement.paiementCancel","Paiement annulé"));
        }
    }, []);

    const handleCheckout = async (plan) => {
        if (!user?.id || !plan?.id) return;
        setLoadingPlanId(plan.id);
        setError("");
        try {
            const response = await fetch(getApiUrl(`/api/stripe/checkout-session`), {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(user.id),
                    ...(user?.email ? { "X-User-Email": user.email } : {}),
                },
                body: JSON.stringify({
                    plan_id: plan.id,
                }),
            });

            const data = await response.json().catch(() => ({}));
            if (!response.ok) {
                setError(data?.detail || t("abonnement.stripeError","Impossible de demarrer le paiement Stripe."));
                return;
            }

            if (!data?.checkout_url) {
                setError(t("abonnement.noCheckoutUrl","Aucune URL de paiement n'a ete retournee."));
                return;
            }

            globalThis.location.href = data.checkout_url;
        } catch (err) {
            setError(err.message ||  t("abonnement.stripeError","Impossible de demarrer le paiement Stripe."));
        } finally {
            setLoadingPlanId("");
        }
    };

    const handleBuyCredits = async () => {
        if (!user?.id) return;
        setBuyLoading(true);
        setBuyError("");
        try {
            const res = await fetch(getApiUrl("/api/stripe/buy-credits"), {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    ...getAuthHeaders(user.id),
                    ...(user?.email ? { "X-User-Email": user.email } : {}),
                },
                body: JSON.stringify({ amount_usd: buyAmount }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(data?.detail || t("abonnement.paiementError","Erreur lors du paiement"));
            if (data?.checkout_url) globalThis.location.href = data.checkout_url;
        } catch (err) {
            setBuyError(err.message || t("abonnement.stripeError","Impossible de démarrer le paiement."));
        } finally {
            setBuyLoading(false);
        }
    };

    useEffect(() => {
        if (!user?.id) return;
        async function fetchSouscription() {
            try {
                const response = await fetch(getApiUrl(`/api/souscription`), {
                    headers: {
                        ...getAuthHeaders(user.id),
                    },
                });

                if (!response.ok) {
                    return;
                }

                const data = await response.json();
                setSouscription(data);
            } catch (err) {
                console.error("Error fetching souscription:", err);
            }
        }

        fetchSouscription();

    }, [user?.id])

    useEffect(() => {
        async function getItems() {

            setLoading(true);
            setError("");

            try {

                const response = await fetch(getApiUrl(`/api/abonnements`),  null);

                if (!response.ok) {
                    const detail = await response.text();
                    setError(detail || "Unable to load plans");
                    setItems([]);
                    return;
                }

                const data = await response.json();
                setItems(Array.isArray(data.plans) ? data.plans : []);

            } catch (err) {
                setError(err.message || "Unable to load reels");
                setItems([]);
            } finally {
                setLoading(false);
            }
        }

        getItems();

    },[])

    return (
        <div className="h-full overflow-y-auto p-8 max-w-7xl mx-auto animate-[fadeIn_0.3s_ease-out]">
            {/* Header */}
            <div className="mb-8">
                <h1 className="text-3xl font-bold mb-2">{t("abonnement.title","Plan d'abonnement")}</h1>
                <p className="text-slate-500 dark:text-zinc-400 text-sm">{t("abonnement.subtitle","Découvrez nos formules d'abonnements et choisissez celle qui vous convient")}</p>
                {currentPlan ? (
                    <p className="mt-2 text-xs text-slate-500 dark:text-zinc-400">
                        {t("settings.currentPlan", "Current plan")}: <span className="text-white font-medium">{currentPlan.name}</span>
                    </p>
                ) : null}
                {paymentMessage ? <p className="mt-3 text-sm text-green-300">{paymentMessage}</p> : null}
            </div>

            {/* Plans -- responsive to however many plans the catalog has
                (was hardcoded to 3 columns, broke once a 4th plan was added) */}
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-8 items-start">

                {loading && (
                    <span className="inline-flex items-center gap-2">
                        <Loader2 size={14} className="animate-spin" /> {t("app.loading","Chargement...")}
                    </span>
                )}

                {!loading && error && (
                    <span className="inline-flex items-center gap-2 text-red-300">
                        {error}
                    </span>
                )}

                {!loading && !error && items.length === 0 && (
                    <span className="inline-flex items-center gap-2 text-slate-500 dark:text-zinc-400">
                        {t("abonnement.noSubscriptionHistory","Aucun abonnement trouve.")}
                    </span>
                )}

                {items.map((plan) => {
                    const styles = colorStyles[plan.color] || defaultColorStyle;
                    const Icon = planIconByName[plan.name] || iconMap[plan.icon] || Star;
                    const buttonLabel = t("abonnement.choisir","Choisir");
                    const commentCount = Number(plan.commentaire);
                    const hasCommentCount = Number.isFinite(commentCount) && commentCount > 0;

                    return (
                        <div
                            key={plan.name}
                            className={`relative flex flex-col rounded-2xl border ${styles.border} ${styles.bg} p-7 ${
                                plan.highlighted ? "z-10 ring-2 ring-blue-500/40 scale-[1.02]" : ""
                            } transition`}
                        >
                            {plan.highlighted && (
                                <span className="absolute -top-3 left-1/2 -translate-x-1/2 rounded-full bg-blue-500 px-3 py-1 text-xs font-semibold text-white">
                                    {t("abonnement.populaire","Populaire")}
                </span>
                            )}

                            {/* Icon + nom */}
                            <div className="flex items-center gap-3 mb-2">
                                <div className={`p-2 rounded-lg ${styles.gradient}`}>
                                    <Icon size={20} className={styles.icon} />
                                </div>
                                <h2 className="text-lg font-bold">{plan.name}</h2>
                            </div>

                            {/* Cible */}
                            {plan.cible && (
                                <p className={`lowercase text-[0.65rem] font-medium mb-3 ${styles.icon}`}>
                                    {plan.cible}
                                </p>
                            )}

                            {/* Description */}
                            {plan.description && (
                                <p className="text-sm text-slate-600 dark:text-zinc-400 mb-4">
                                    {plan.description}
                                </p>
                            )}

                            {/* Prix */}
                            <div className="mb-6">
                                <span className="text-3xl font-bold">{plan.price}€</span>
                                <span className="text-slate-500 dark:text-zinc-400 text-sm"> / {t("abonnement.mois","mois")}</span>
                            </div>

                            {/* Liste des services */}
                            <ul className="flex flex-col gap-3 mb-8 flex-1">
                                {hasCommentCount && (
                                    <li className="flex items-start gap-2 text-sm text-slate-700 dark:text-zinc-300">
                                        <MessageCircle size={16} className={`${styles.check} mt-0.5 shrink-0`} />
                                        <span>{commentCount.toLocaleString()} {t("abonnement.commentsPerPost", "commentaires / publication")}</span>
                                    </li>
                                )}
                                <li className="flex items-start gap-2 text-sm text-slate-700 dark:text-zinc-300">
                                    {plan.statistique ? (
                                        <>
                                            <Check size={16} className={`${styles.check} mt-0.5 shrink-0`} />
                                            <span>{t("abonnement.statsIncluded", "Statistiques sociales sur la page d'accueil")}</span>
                                        </>
                                    ) : (
                                        <>
                                            <X size={16} className="text-slate-400 dark:text-zinc-600 mt-0.5 shrink-0" />
                                            <span className="text-slate-400 dark:text-zinc-500">{t("abonnement.statsExcluded", "Pas de statistiques sociales sur la page d'accueil")}</span>
                                        </>
                                    )}
                                </li>
                                {plan.features.map((feature) => (
                                    <li key={feature} className="flex items-start gap-2 text-sm text-slate-700 dark:text-zinc-300">
                                        <Check size={16} className={`${styles.check} mt-0.5 shrink-0`} />
                                        <span>{feature}</span>
                                    </li>
                                ))}
                            </ul>

                            {/* Bouton */}
                            <button
                                onClick={() => handleCheckout(plan)}
                                disabled={!user?.id || loadingPlanId === plan.id}
                                className={`mt-auto flex items-center justify-center gap-2 rounded-2xl border px-4 py-3 text-sm font-semibold transition ${styles.button}`}
                            >
                                {loadingPlanId === plan.id ? <Loader2 size={18} className="animate-spin" /> : <CreditCardIcon size={18} />}
                                {loadingPlanId === plan.id ? t("abonnement.redirection","Redirection...") : buttonLabel}
                            </button>
                        </div>
                    );
                })}
            </div>

            {/* Included in all offers */}
            <div className="mt-10 rounded-2xl border border-blue-500/20 bg-blue-500/5 p-6">
                <h2 className="text-xl font-semibold mb-4 text-slate-800 dark:text-zinc-100">
                    {t("abonnement.titleOffre","Toutes nos offres contiennent")}
                </h2>
                <ul className="flex flex-col gap-3">
                    {[
                        t("abonnement.offre1", "Génération de réels"),
                        t("abonnement.offre2", "Génération de captions"),
                        t("abonnement.offre3", "Publication et suivi sur les réseaux sociaux"),
                        t("abonnement.offre4", "Génération des sous titres et hooks viraux"),
                        t("abonnement.offre5", "Traduction de texte et sous-titres"),
                    ].map((item) => (
                        <li key={item} className="flex items-start gap-2 text-sm text-slate-700 dark:text-zinc-300">
                            <Check size={16} className="text-blue-400 mt-0.5 shrink-0" />
                            <span>{item}</span>
                        </li>
                    ))}
                </ul>
            </div>

            {/* Buy additional credits */}
            <div className="mt-10 rounded-2xl border border-yellow-500/20 bg-yellow-500/5 p-6">
                <div className="flex items-center gap-3 mb-4">
                    <div className="p-2 rounded-lg bg-yellow-500/10">
                        <Coins size={20} className="text-yellow-400" />
                    </div>
                    <div>
                        <h2 className="text-xl font-semibold">{t("abonnement.fillCredit","Recharger des crédits")}</h2>
                        <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">
                            1 EUR = {CREDIT_RATE} {t("abonnement.creditRate","crédits · solde actuel ")} :{" "}
                            <span className="text-slate-900 dark:text-white font-semibold">{credits.toLocaleString()} / {Number(creditMax || 0).toLocaleString()} cr</span>
                        </p>
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-4">
                    <div className="flex gap-2">
                        {[5, 10, 20, 50].map((amt) => (
                            <button
                                key={amt}
                                onClick={() => setBuyAmount(amt)}
                                className={`px-3 py-1.5 rounded-lg border text-sm font-medium transition ${
                                    buyAmount === amt
                                        ? "border-amber-300 dark:border-yellow-400 bg-amber-100 dark:bg-yellow-400/10 text-amber-800 dark:text-yellow-300"
                                        : "border-slate-300 dark:border-white/10 bg-white/5 text-slate-700 dark:text-zinc-300 hover:border-slate-400 dark:hover:border-white/20"
                                }`}
                            >
                                {amt}€
                            </button>
                        ))}
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setBuyAmount(Math.max(1, buyAmount - 1))}
                            className="p-1.5 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 hover:bg-white/10 text-slate-700 dark:text-zinc-300"
                        >
                            <Minus size={14} />
                        </button>
                        <input
                            type="number"
                            min="1"
                            value={buyAmount}
                            onChange={(e) => setBuyAmount(Math.max(1, Number(e.target.value) || 1))}
                            className="w-20 px-3 py-1.5 bg-white/10 border border-slate-400 dark:border-white/20 rounded-lg text-slate-900 dark:text-white text-sm text-center focus:outline-none focus:border-yellow-500/50"
                        />
                        <button
                            onClick={() => setBuyAmount(buyAmount + 1)}
                            className="p-1.5 rounded-lg bg-white/5 border border-slate-300 dark:border-white/10 hover:bg-white/10 text-slate-700 dark:text-zinc-300"
                        >
                            <Plus size={14} />
                        </button>
                        <span className="text-slate-500 dark:text-zinc-400 text-sm">EUR</span>
                    </div>

                    <div className="ml-auto flex items-center gap-3">
                        <span className="text-sm text-slate-500 dark:text-zinc-400">
                            = <span className="text-amber-700 dark:text-yellow-300 font-semibold">{creditsToAdd.toLocaleString()} crédits</span>
                        </span>
                        <button
                            onClick={handleBuyCredits}
                            disabled={buyLoading || !user?.id}
                            className="flex items-center gap-2 px-4 py-2 bg-amber-500 border border-amber-600 hover:bg-amber-400 disabled:opacity-60 text-white dark:bg-yellow-500/20 dark:border-yellow-500/30 dark:hover:bg-yellow-500/30 dark:text-yellow-300 rounded-xl text-sm font-semibold transition"
                        >
                            {buyLoading ? <Loader2 size={16} className="animate-spin" /> : <CreditCardIcon size={16} />}
                            {buyLoading ? t("abonnement.redirection","Redirection...") : t("abonnement.payer","Payer")}
                        </button>
                    </div>
                </div>

                {buyError && (
                    <p className="mt-3 text-xs text-red-300">{buyError}</p>
                )}
            </div>
        </div>
    );
}
