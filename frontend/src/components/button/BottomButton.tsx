import { css } from "@emotion/react";
import { ButtonHTMLAttributes, DetailedHTMLProps } from "react";
import {
  ACCENT_BLUE,
  BG_GLASS,
  INK,
  pressable,
  SHADOW_MD,
  SHADOW_SM,
  SHADOW_PRESS,
  TEXT_PRIMARY,
} from "@/theme/color";

interface ButtonProps
  extends DetailedHTMLProps<
    ButtonHTMLAttributes<HTMLButtonElement>,
    HTMLButtonElement
  > {
  isShow?: boolean;
}

const secondaryButtonStyles = css({
  color: TEXT_PRIMARY,
  backgroundColor: BG_GLASS,
  border: `2.5px solid ${INK}`,
  padding: "0.8rem 1.05rem",
  borderRadius: "12px",
  fontWeight: 700,
  fontSize: "13px",
  letterSpacing: "0.01em",
  cursor: "pointer",
  transition: pressable.transition,
  alignItems: "center",
  gap: "0.5rem",
  minHeight: "46px",
  boxShadow: SHADOW_MD,
  ":hover": {
    transform: "translate(-1px, -1px)",
    boxShadow: "4px 4px 0px #0F172A",
  },
  ":active": {
    transform: "translate(2px, 2px)",
    boxShadow: SHADOW_PRESS,
  },
  ":disabled": {
    cursor: "not-allowed",
    opacity: 0.45,
    transform: "none",
    boxShadow: SHADOW_SM,
  },
});

const primaryButtonStyles = css({
  color: "#FFFFFF",
  backgroundColor: ACCENT_BLUE,
  border: `2.5px solid ${INK}`,
  padding: "0.8rem 1.05rem",
  borderRadius: "12px",
  fontWeight: 800,
  fontSize: "13px",
  letterSpacing: "0.01em",
  cursor: "pointer",
  transition: pressable.transition,
  alignItems: "center",
  gap: "0.5rem",
  minHeight: "46px",
  boxShadow: SHADOW_MD,
  ":hover": {
    transform: "translate(-1px, -1px)",
    boxShadow: "4px 4px 0px #0F172A",
  },
  ":active": {
    transform: "translate(2px, 2px)",
    boxShadow: SHADOW_PRESS,
  },
  ":disabled": {
    cursor: "not-allowed",
    opacity: 0.45,
    transform: "none",
    boxShadow: SHADOW_SM,
  },
});

export function NextButton({ isShow, ...props }: ButtonProps) {
  return (
    <button
      css={[
        primaryButtonStyles,
        css({ display: isShow ? "inline-flex" : "none" }),
      ]}
      {...props}
    >
      {props.children}
    </button>
  );
}

export function PrevButton({ isShow, ...props }: ButtonProps) {
  return (
    <button
      css={[
        secondaryButtonStyles,
        css({ display: isShow ? "inline-flex" : "none" }),
      ]}
      {...props}
    >
      {props.children}
    </button>
  );
}

export function Button({ isShow, ...props }: ButtonProps) {
  return (
    <button
      css={[
        primaryButtonStyles,
        css({ display: isShow ? "inline-flex" : "none" }),
      ]}
      {...props}
    >
      {props.children}
    </button>
  );
}
