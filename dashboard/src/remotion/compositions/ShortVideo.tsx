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

  // When a visual is active for the current frame, the video is clipped to
  // the other 50% of the frame while preserving centered cover rendering.
  const activeVisual = useActiveVisual(visuals);
  const videoRegionStyle: React.CSSProperties = activeVisual
    ? {
        position: "absolute",
        left: 0,
        right: 0,
        top: activeVisual.position === "TOP" ? `${VISUAL_IMAGE_HEIGHT_PERCENT}%` : 0,
        bottom: activeVisual.position === "TOP" ? 0 : `${VISUAL_IMAGE_HEIGHT_PERCENT}%`,
        overflow: "hidden",
      }
    : {
        position: "absolute",
        inset: 0,
        overflow: "hidden",
      };

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Layer 1: Base video with optional zoom/color effects, clipped into
          its half while a visual is active. */}
      <div style={videoRegionStyle}>
        <VideoEffects config={effects}>
          <Video
            src={videoUrl}
            crossOrigin="anonymous"
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
              objectPosition: "center center",
              display: "block",
            }}
          />
        </VideoEffects>
      </div>

      {/* Layer 2: Manual split-screen image overlays */}
      {visuals && visuals.length > 0 && <VisualOverlay visuals={visuals} />}

      {/* Layer 3: Animated subtitles */}
      {subtitles && <Subtitles config={subtitles} />}

      {/* Layer 4: Hook text overlay */}
      {hook && <HookOverlay config={hook} />}
    </AbsoluteFill>
  );
};
