import * as React from "react";
import { AbsoluteFill } from "remotion";
import { Video } from "@remotion/media";
import type { ShortVideoProps } from "../lib/types";
import { Subtitles } from "./Subtitles";
import { HookOverlay } from "./HookOverlay";
import { VideoEffects } from "./VideoEffects";
import { VisualOverlay, useActiveVisual, VISUAL_IMAGE_HEIGHT_PERCENT } from "./VisualOverlay";

/**
 * Main composition that layers all post-processing on top of the base video.
 * Uses @remotion/media Video for browser-side rendering compatibility.
 */
export const ShortVideo: React.FC<Record<string, unknown>> = (rawProps) => {
  const { videoUrl, subtitles, hook, effects, visuals } =
    rawProps as unknown as ShortVideoProps;

  // When a visual is active for the current frame, the video shrinks into
  // the 65% of the frame the image half (rendered by VisualOverlay below)
  // doesn't occupy -- otherwise it fills the whole frame as usual.
  const activeVisual = useActiveVisual(visuals);
  const videoRegionStyle: React.CSSProperties = activeVisual
    ? {
        position: "absolute",
        left: 0,
        right: 0,
        top: activeVisual.position === "TOP" ? `${VISUAL_IMAGE_HEIGHT_PERCENT}%` : 0,
        height: `${100 - VISUAL_IMAGE_HEIGHT_PERCENT}%`,
      }
    : { position: "absolute", top: 0, left: 0, right: 0, bottom: 0 };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Layer 1: Base video with optional zoom/color effects, shrunk into
          its 65% region while a visual is active */}
      <div style={videoRegionStyle}>
        <VideoEffects config={effects}>
          <Video
            src={videoUrl}
            crossOrigin="anonymous"
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        </VideoEffects>
      </div>

      {/* Layer 2: Animated subtitles */}
      {subtitles && <Subtitles config={subtitles} />}

      {/* Layer 3: Hook text overlay */}
      {hook && <HookOverlay config={hook} />}

      {/* Layer 4: Manual split-screen image overlays */}
      {visuals && visuals.length > 0 && <VisualOverlay visuals={visuals} />}
    </AbsoluteFill>
  );
};
