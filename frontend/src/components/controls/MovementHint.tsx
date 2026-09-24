import { css } from "@emotion/react";
import { useCarStore } from "@/state/carStore";

export function MovementHint({ isVisible }: { isVisible: boolean }) {
  const thirdMode = useCarStore((state) => state.thirdMode);

  if (!isVisible || !thirdMode) return null;

  return (
    <div
      css={css({
        position: "fixed",
        right: "1.5rem",
        bottom: "6.5rem",
        zIndex: 9999,
        maxWidth: "min(20rem, calc(100vw - 2rem))",
        pointerEvents: "none",
        userSelect: "none",
        padding: "0.8rem 0.95rem",
        borderRadius: "12px",
        background: "#FFFFFF",
        border: `2.5px solid #0F172A`,
        boxShadow: "3px 3px 0px #0F172A",
        color: "#0F172A",
        fontSize: "12px",
        fontWeight: 700,
        lineHeight: 1.55,
      })}
    >
      Use W/A/S/D or arrow keys to drive. Move the mouse to steer. Press Esc
      to exit car mode.
    </div>
  );
}
