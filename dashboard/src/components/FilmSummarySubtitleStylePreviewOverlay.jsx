import { useEffect, useState } from "react";

// Best-effort, purely cosmetic CSS preview of the chosen subtitle style,
// meant to sit on top of the real <video> element (its parent must be
// `position: relative`) on the completed film-summary page so tweaking a
// style control in FilmSummaryCompletedSubtitlesPanel gives instant visual
// feedback -- NOT real, word-synced captions: there is no per-word timing
// available client-side for the already-assembled final video, so this
// just renders a single sample line styled to roughly match what the
// server-side burn-in (POST .../apply-subtitles) will actually produce.
function mapTextCaseToCss(textCase) {
    if (textCase === "uppercase") return "uppercase";
    if (textCase === "lowercase") return "lowercase";
    if (textCase === "capitalize") return "capitalize";
    return "none";
}

// "#RRGGBB" + an opacity (0-1) -> "rgba(r, g, b, a)", so the background box
// can honor the style's bgOpacity instead of always being fully opaque.
function hexToRgba(hex, opacity) {
    const normalized = String(hex || "#000000").replace("#", "");
    const r = parseInt(normalized.slice(0, 2), 16) || 0;
    const g = parseInt(normalized.slice(2, 4), 16) || 0;
    const b = parseInt(normalized.slice(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${Math.min(1, Math.max(0, opacity))})`;
}

export default function FilmSummarySubtitleStylePreviewOverlay({ style, sampleText }) {
    // Gentle fade cycle, only as a cosmetic nod to the chosen animation --
    // skipped entirely when animation is "none".
    const [dimmed, setDimmed] = useState(false);

    useEffect(() => {
        if (!style || style.animation === "none") {
            setDimmed(false);
            return undefined;
        }
        const interval = setInterval(() => setDimmed((prev) => !prev), 1800);
        return () => clearInterval(interval);
    }, [style?.animation]);

    if (!style) return null;

    const bgOpacity = Number(style.bgOpacity) || 0;
    const shadowOffsetX = Number(style.shadowOffsetX) || 0;
    const shadowOffsetY = Number(style.shadowOffsetY) || 0;
    const shadowBlur = Number(style.shadowBlur) || 0;
    const fontSize = Math.max(10, Math.round((Number(style.fontSize) || 14) * 1.3));

    return (
        <div className="pointer-events-none absolute inset-0 overflow-hidden" style={{ zIndex: 5 }}>
            <div
                className="absolute max-w-[90%] -translate-x-1/2 -translate-y-1/2 whitespace-pre-line text-center transition-opacity duration-700"
                style={{
                    left: `${Number(style.positionX) || 50}%`,
                    top: `${Number(style.positionY) || 82}%`,
                    fontFamily: style.fontFamily || "Montserrat",
                    fontSize: `${fontSize}px`,
                    lineHeight: 1.3,
                    color: style.fontColor || "#FFFFFF",
                    fontWeight: style.bold ? "bold" : "normal",
                    fontStyle: style.italic ? "italic" : "normal",
                    textTransform: mapTextCaseToCss(style.textCase),
                    WebkitTextStroke: Number(style.borderWidth) > 0 ? `${style.borderWidth}px ${style.borderColor || "#000000"}` : undefined,
                    textShadow: shadowBlur || shadowOffsetX || shadowOffsetY ? `${shadowOffsetX}px ${shadowOffsetY}px ${shadowBlur}px ${style.textShadowColor || "#000000"}` : "none",
                    backgroundColor: bgOpacity > 0 ? hexToRgba(style.bgColor || "#000000", bgOpacity) : "transparent",
                    padding: bgOpacity > 0 ? "0.2em 0.5em" : 0,
                    borderRadius: bgOpacity > 0 ? "0.25em" : 0,
                    opacity: style.animation !== "none" && dimmed ? 0.45 : 1,
                }}
            >
                {sampleText || "Exemple de sous-titre"}
            </div>
        </div>
    );
}
