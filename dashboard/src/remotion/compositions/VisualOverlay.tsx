import * as React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import type { VisualConfig } from "../lib/types";

// The image half always takes 35% of the frame height, the video the
// other 65% (see ShortVideo.tsx, which shrinks <Video> into that other
// 65% for the same time window) -- matches visuals.py's FFmpeg split on
// the backend closely enough for preview purposes (not pixel-perfect).
export const VISUAL_IMAGE_HEIGHT_PERCENT = 35;

interface VisualOverlayProps {
  visuals: VisualConfig[];
}

/**
 * Renders the image half of every configured visual, each in its own
 * <Sequence> so it only mounts during its own [startSec, startSec +
 * durationSec) window -- same time-windowing primitive as HookOverlay.
 * Visuals never overlap (enforced both client- and server-side), so at
 * most one of these Sequences is ever active at once.
 */
export const VisualOverlay: React.FC<VisualOverlayProps> = ({ visuals }) => {
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill>
      {visuals.map((visual) => {
        const startFrame = Math.max(0, Math.round((visual.startSec || 0) * fps));
        const durationFrames = Math.max(1, Math.round((visual.durationSec || 0) * fps));
        return (
          <Sequence key={visual.id} from={startFrame} durationInFrames={durationFrames} layout="none">
            <VisualImageHalf visual={visual} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};

const VisualImageHalf: React.FC<{ visual: VisualConfig }> = ({ visual }) => {
  const isTop = visual.position === "TOP";
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        height: `${VISUAL_IMAGE_HEIGHT_PERCENT}%`,
        top: isTop ? 0 : undefined,
        bottom: isTop ? undefined : 0,
      }}
    >
      {/* eslint-disable-next-line jsx-a11y/alt-text -- decorative split-screen fill, no textual content to convey */}
      <img
        src={visual.imageUrl}
        crossOrigin="anonymous"
        style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
      />
    </div>
  );
};

/**
 * The visual (if any) whose [startSec, startSec + durationSec) window
 * covers the current frame. ShortVideo.tsx uses this to shrink/reposition
 * <Video> into the other 65% for that same window -- kept here alongside
 * VisualOverlay so both read the exact same "which visual is active"
 * logic.
 */
export function useActiveVisual(visuals: VisualConfig[] | null | undefined): VisualConfig | null {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  if (!visuals || visuals.length === 0) return null;
  const timeSec = frame / fps;
  return (
    visuals.find((visual) => {
      const start = visual.startSec || 0;
      const end = start + (visual.durationSec || 0);
      return timeSec >= start && timeSec < end;
    }) || null
  );
}
