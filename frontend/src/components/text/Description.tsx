import { css } from "@emotion/react";
import { DESC_COLOR } from "@/theme/color";

export function Description({ children }: { children?: React.ReactNode }) {
  return (
    <p
      css={css({
        margin: 0,
        color: DESC_COLOR,
        fontSize: "0.95rem",
        fontWeight: 500,
        lineHeight: 1.6,
        fontFamily: '"Plus Jakarta Sans", sans-serif',
      })}
    >
      {children}
    </p>
  );
}
