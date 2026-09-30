import React, { useEffect, useState } from 'react';
import { X, Loader2, Share2, Calendar, Clock, Instagram, Youtube, Video, Facebook, Linkedin, CheckCircle, AlertCircle } from 'lucide-react';
import { SUPPORTED_SOCIAL_PLATFORMS, PLATFORM_LABELS } from '../lib/platforms';
import { getApiUrl } from '../config';
import { getAuthHeaders } from '../lib/apiAuth';
import { useAuth } from '../state/AuthContext';
import { useTranslation } from "../state/LanguageContext";

const PLATFORM_ICONS = {
    instagram: Instagram,
    youtube: Youtube,
    facebook: Facebook,
    linkedin: Linkedin,
    tiktok: Video,
};

export default function SharePostModal({
    isOpen,
    onClose,
    title,
    onTitleChange,
    description,
    onDescriptionChange,
    isScheduling,
    onSchedulingChange,
    scheduleDate,
    onScheduleDateChange,
    selectedAccountIds,
    onAccountToggle,
    isSubmitting,
    result,
    onSubmit,
}) {

    const { t } = useTranslation();
    const { user } = useAuth();
    const [accounts, setAccounts] = useState([]);

    // Fetched fresh every time the modal opens rather than relying on a
    // parent-owned "connected platforms" cache -- a plan can have several
    // accounts per platform (see max_social_account), so the real list of
    // specific pages/profiles has to come from the API, not a boolean per
    // platform.
    useEffect(() => {
        if (!isOpen) return;
        let cancelled = false;
        (async () => {
            try {
                const response = await fetch(getApiUrl("/api/social/accounts"), {
                    headers: { ...getAuthHeaders(user?.id) },
                });
                if (!response.ok) return;
                const data = await response.json();
                const rows = Array.isArray(data?.accounts) ? data.accounts : [];
                if (!cancelled) setAccounts(rows.filter((a) => SUPPORTED_SOCIAL_PLATFORMS.includes(a.platform)));
            } catch {
                // Best-effort: the modal simply shows no connected accounts.
            }
        })();
        return () => {
            cancelled = true;
        };
    }, [isOpen, user?.id]);

    if (!isOpen) return null;

    const accountsByPlatform = {};
    for (const account of accounts) {
        (accountsByPlatform[account.platform] ||= []).push(account);
    }

    return (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-[fadeIn_0.2s_ease-out]">
            <div className="bg-white dark:bg-[#121214] border border-slate-300 dark:border-white/10 p-6 rounded-2xl w-full max-w-md shadow-2xl relative max-h-[90vh] overflow-y-auto custom-scrollbar">
                <button
                    onClick={onClose}
                    className="absolute top-4 right-4 text-slate-400 dark:text-zinc-500 hover:text-slate-700 dark:hover:text-white"
                >
                    <X size={20} />
                </button>

                <h3 className="title-contrast text-lg font-bold mb-4">{t("social.title", "Post / Schedule")}</h3>


                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-1">{t("social.videoTile", "Video Title")}</label>
                        <input
                            type="text"
                            value={title}
                            onChange={(e) => onTitleChange(e.target.value)}
                            className="w-full bg-slate-50 dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-primary/50 placeholder-slate-400 dark:placeholder-zinc-600"
                            placeholder={t("social.videoTile", "Enter a catchy title...")}
                        />
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-1">{t("social.postResume", "Caption / Description")}</label>
                        <textarea
                            value={description}
                            onChange={(e) => onDescriptionChange(e.target.value)}
                            rows={4}
                            className="w-full bg-slate-50 dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-primary/50 placeholder-slate-400 dark:placeholder-zinc-600 resize-none"
                            placeholder={t("social.postResumePlaceholder", "Write a caption for your post...")}
                        />
                    </div>

                    <div className="p-3 bg-slate-100 dark:bg-white/5 rounded-lg border border-slate-200 dark:border-white/5">
                        <div className="flex items-center justify-between mb-2">
                            <div className="flex items-center gap-2 text-sm text-slate-800 dark:text-white font-medium">
                                <Calendar size={16} className="text-purple-400" /> {t("social.postSchedule", "Schedule Post")}
                            </div>
                            <label className="relative inline-flex items-center cursor-pointer">
                                <input type="checkbox" checked={isScheduling} onChange={(e) => onSchedulingChange(e.target.checked)} className="sr-only peer" />
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
                                        onChange={(e) => onScheduleDateChange(e.target.value)}
                                        className="w-full bg-slate-50 dark:bg-black/40 border border-slate-300 dark:border-white/10 rounded-lg p-2 pl-9 text-sm text-slate-900 dark:text-white focus:outline-none focus:border-purple-500/50 [color-scheme:light] dark:[color-scheme:dark]"
                                    />
                                    <Clock size={14} className="absolute left-3 top-2.5 text-slate-400 dark:text-zinc-500" />
                                </div>
                            </div>
                        ) : null}
                    </div>

                    <div>
                        <label className="block text-xs font-bold text-slate-500 dark:text-zinc-400 mb-2">{t("social.postSelectPlatform", "Select Accounts")}</label>
                        {accounts.length === 0 ? (
                            <p className="text-xs text-slate-400 dark:text-zinc-500">
                                {t("social.noPlatformConnected", "Aucun compte connecte. Connectez-en un dans Parametres.")}
                            </p>
                        ) : (
                            <div className="space-y-3">
                                {SUPPORTED_SOCIAL_PLATFORMS.map((platform) => {
                                    const platformAccounts = accountsByPlatform[platform] || [];
                                    if (platformAccounts.length === 0) return null;
                                    const Icon = PLATFORM_ICONS[platform] || Video;
                                    return (
                                        <div key={platform}>
                                            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400 dark:text-zinc-500 mb-1">
                                                <Icon size={13} /> {t(`social.${platform}`, PLATFORM_LABELS[platform])}
                                            </div>
                                            <div className="grid grid-cols-1 gap-2">
                                                {platformAccounts.map((account) => (
                                                    <label key={account.id} className="flex items-center gap-3 p-3 bg-slate-100 dark:bg-white/5 rounded-lg cursor-pointer hover:bg-slate-200 dark:hover:bg-white/10 transition-colors border border-slate-200 dark:border-white/5">
                                                        <input
                                                            type="checkbox"
                                                            checked={Boolean(selectedAccountIds[account.id])}
                                                            onChange={(e) => onAccountToggle(account.id, e.target.checked)}
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
                </div>

                {result ? (
                    <div className={`mb-4 p-3 rounded-lg text-xs flex items-start gap-2 ${result.success ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                        {result.success ? <CheckCircle size={14} className="mt-0.5 shrink-0" /> : <AlertCircle size={14} className="mt-0.5 shrink-0" />}
                        <div>{result.msg}</div>
                    </div>
                ) : null}

                <button
                    onClick={onSubmit}
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
