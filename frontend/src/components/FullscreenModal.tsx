import { css } from "@emotion/react";
import React from "react";
import { INK } from "@/theme/color";

export function FullscreenModal({
  children,
  isOpen = false,
}: {
  children: React.ReactNode;
  isOpen?: boolean;
}) {
  return (
    <div
      css={css({
        width: "100%",
        height: "100%",
        position: "absolute",
        top: 0,
        left: 0,
        zIndex: 999,
        background: "#F8FAFC",
        display: isOpen ? "flex" : "none",
        overflowY: "auto",
        overflowX: "hidden",
      })}
    >
      <div
        css={css({
          padding: "1.5rem",
          paddingTop: "7rem",
          paddingBottom: "3rem",
          width: "100%",
          maxWidth: "1400px",
          margin: "0 auto",
          display: "flex",
          flexDirection: "column",
        })}
      >
        {children}
      </div>
    </div>
  );
}
