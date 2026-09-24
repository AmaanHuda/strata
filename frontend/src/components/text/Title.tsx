import { css } from "@emotion/react";
import { SUBTITLE_COLOR } from "@/theme/color";

export function Title({ children }: { children?: React.ReactNode }) {
  return (
    <p
      css={css({
        margin: 0,
        color: SUBTITLE_COLOR,
        fontSize: "1.45rem",
        fontWeight: 800,
        letterSpacing: "-0.02em",
        fontFamily: '"Plus Jakarta Sans", sans-serif',
      })}
    >
      {children}
    </p>
  );
}
