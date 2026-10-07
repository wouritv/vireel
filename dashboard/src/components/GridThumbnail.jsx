import React from "react";
import { ImageOff } from "lucide-react";

/**
 * Shared grid-card media thumbnail: a cover-fit preview (or an empty
 * placeholder when there's no image), duration/status badges pinned to
 * two corners, and a floating action-button overlay revealed on hover --
 * the same group-hover pattern ResultCard.jsx already uses for its own
 * video preview (group/video + opacity-0 -> group-hover:opacity-100),
 * just extracted here since every grid card now needs the same
 * treatment instead of duplicating it six times.
 */
export default function GridThumbnail({
    imageUrl,
    aspect = "video", // "video" (16:9 landscape) | "portrait" (9:16 story/shorts)
    durationLabel,
    statusBadge, // { label, className } -- className mirrors statusClass()'s output
    badgePosition = "top", // "top" | "bottom"
    actions, // ReactNode -- action buttons floated on hover
    onClick,
    alt = "",
    emptyLabel,
}) {
    const aspectClass = aspect === "portrait" ? "aspect-[9/16]" : "aspect-video";
    const badgeRowClass = badgePosition === "bottom" ? "bottom-2" : "top-2";

    return (
        <div
            className={`group/thumb relative w-full ${aspectClass} overflow-hidden rounded-lg bg-zinc-900 ${onClick ? "cursor-pointer" : ""}`}
            onClick={onClick}
        >
            {imageUrl ? (
                <img src={imageUrl} alt={alt} className="h-full w-full object-cover" loading="lazy" />
            ) : (
                <div className="flex h-full w-full flex-col items-center justify-center gap-1 bg-gradient-to-br from-zinc-800 via-zinc-700 to-zinc-800 text-zinc-500">
                    <ImageOff size={24} />
                    {emptyLabel ? <span className="text-[10px]">{emptyLabel}</span> : null}
                </div>
            )}

            {(durationLabel || statusBadge) ? (
                <div className={`pointer-events-none absolute inset-x-2 ${badgeRowClass} flex items-center justify-between gap-2`}>
                    {durationLabel ? (
                        <span className="rounded-md bg-black/70 px-1.5 py-0.5 text-[10px] font-medium text-white">
                            {durationLabel}
                        </span>
                    ) : <span />}
                    {statusBadge ? (
                        <span className={`rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${statusBadge.className}`}>
                            {statusBadge.label}
                        </span>
                    ) : null}
                </div>
            ) : null}

            {actions ? (
                <div
                    className="absolute inset-0 flex items-center justify-center gap-2 bg-black/50 opacity-0 pointer-events-none backdrop-blur-sm transition-opacity duration-200 group-hover/thumb:opacity-100 group-hover/thumb:pointer-events-auto"
                    onClick={(e) => e.stopPropagation()}
                >
                    {actions}
                </div>
            ) : null}
        </div>
    );
}
