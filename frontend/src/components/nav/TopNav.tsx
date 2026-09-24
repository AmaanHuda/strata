import {
  ACCENT_BLUE,
  INK,
  pressable,
  SHADOW_SM,
  TEXT_PRIMARY,
} from "@/theme/color";
import { css } from "@emotion/react";
import { DetailedHTMLProps, ButtonHTMLAttributes } from "react";
import {
  Layers3,
  MapPinned,
  Boxes,
  Building2,
  ChevronRight,
  RotateCcw,
  ArrowLeft,
} from "lucide-react";
import { useAreaStore } from "@/state/areaStore";

const TOP_PANEL_HEIGHT = "4.5rem";

interface NavButtonProps
  extends DetailedHTMLProps<
    ButtonHTMLAttributes<HTMLButtonElement>,
    HTMLButtonElement
  > {
  isShow?: boolean;
}

const STEPS = [
  { label: "Select Area", icon: MapPinned },
  { label: "3D City", icon: Boxes },
  { label: "Building", icon: Building2 },
];

export function TopNav() {
  const appStep = useAreaStore((state) => state.appStep);
  const setAppStep = useAreaStore((state) => state.setAppStep);
  const setSelectedBuildingDetail = useAreaStore(
    (state) => state.setSelectedBuildingDetail
  );

  const goToStep = (step: number) => {
    if (step >= appStep) return;
    if (step < 2) setSelectedBuildingDetail(null);
    setAppStep(step);
  };

  const handleReset = () => {
    setSelectedBuildingDetail(null);
    setAppStep(0);
    window.location.reload();
  };

  return (
    <div
      css={css({
        display: "flex",
        position: "fixed",
        top: 0,
        left: 0,
        width: "100%",
        minHeight: TOP_PANEL_HEIGHT,
        padding: "0.75rem 1.5rem",
        background: "rgba(255, 255, 255, 0.96)",
        backdropFilter: "blur(12px)",
        borderBottom: `2.5px solid ${INK}`,
        boxShadow: "0 3px 0px #0F172A",
        zIndex: 9999,
        alignItems: "center",
        gap: "0.6rem",
      })}
    >
      {/* Logo */}
      <button
        onClick={() => goToStep(0)}
        title="Back to start"
        css={css({
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
          background: "none",
          border: "none",
          padding: 0,
          cursor: appStep > 0 ? "pointer" : "default",
        })}
      >
        <div
          css={css({
            width: "2.35rem",
            height: "2.35rem",
            borderRadius: "12px",
            display: "grid",
            placeItems: "center",
            background: ACCENT_BLUE,
            border: `2px solid ${INK}`,
            boxShadow: "1px 1px 0px #0F172A",
            color: "#fff",
            flexShrink: 0,
          })}
        >
          <Layers3 size={18} strokeWidth={2.5} />
        </div>

        <div
          css={css({
            fontFamily: '"Plus Jakarta Sans", sans-serif',
            fontSize: "17px",
            fontWeight: 800,
            color: TEXT_PRIMARY,
            lineHeight: 1.1,
            letterSpacing: "-0.02em",
            whiteSpace: "nowrap",
          })}
        >
          STRATA
        </div>
      </button>

      {/* Step breadcrumb */}
      <nav
        aria-label="Progress"
        css={css({
          display: "flex",
          alignItems: "center",
          gap: "0.35rem",
          marginLeft: "1rem",
          flex: 1,
          minWidth: 0,
          overflowX: "auto",
        })}
      >
        {STEPS.map((step, i) => {
          const Icon = step.icon;
          const isActive = i === appStep;
          const isDone = i < appStep;
          return (
            <div
              key={step.label}
              css={css({
                display: "flex",
                alignItems: "center",
                gap: "0.35rem",
                flexShrink: 0,
              })}
            >
              {i > 0 && (
                <ChevronRight
                  size={14}
                  strokeWidth={2.5}
                  color={isDone || isActive ? "#0F172A" : "#94A3B8"}
                />
              )}
              <button
                onClick={() => goToStep(i)}
                disabled={!isDone}
                aria-current={isActive ? "step" : undefined}
                title={isDone ? `Back to ${step.label}` : step.label}
                css={css({
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "0.45rem",
                  padding: "0.45rem 0.8rem",
                  borderRadius: "10px",
                  border: `2px solid ${INK}`,
                  fontFamily: '"Plus Jakarta Sans", sans-serif',
                  fontWeight: 800,
                  fontSize: "12px",
                  letterSpacing: "0.01em",
                  whiteSpace: "nowrap",
                  color: isActive ? "#FFFFFF" : isDone ? TEXT_PRIMARY : "#94A3B8",
                  background: isActive
                    ? ACCENT_BLUE
                    : isDone
                      ? "#FFFFFF"
                      : "#F1F5F9",
                  boxShadow: isDone || isActive ? SHADOW_SM : "none",
                  cursor: isDone ? "pointer" : "default",
                  transition: pressable.transition,
                  ":hover":
                    isDone
                      ? {
                          transform: "translate(-1px, -1px)",
                          boxShadow: "3px 3px 0px #0F172A",
                        }
                      : undefined,
                  ":active":
                    isDone
                      ? {
                          transform: "translate(2px, 2px)",
                          boxShadow: "0px 0px 0px #0F172A",
                        }
                      : undefined,
                  "@media (max-width: 640px)": {
                    span: { display: "none" },
                    padding: "0.45rem 0.6rem",
                  },
                })}
              >
                <Icon size={14} strokeWidth={2.5} />
                <span>{step.label}</span>
              </button>
            </div>
          );
        })}
      </nav>

      {/* Right-side actions */}
      {appStep > 0 && (
        <>
          <NavButton
            isShow
            onClick={() => goToStep(appStep - 1)}
            title="Go back one step"
          >
            <ArrowLeft size={14} strokeWidth={2.5} />
            <span>Back</span>
          </NavButton>
          <NavButton
            isShow
            onClick={handleReset}
            title="Reset the demo"
            css={css({ color: "#BA1A1A" })}
          >
            <RotateCcw size={14} strokeWidth={2.5} />
            <span>Reset</span>
          </NavButton>
        </>
      )}
    </div>
  );
}

export function NavButton({ isShow, ...props }: NavButtonProps) {
  return (
    <button
      css={css({
        color: TEXT_PRIMARY,
        background: "#FFFFFF",
        border: `2px solid ${INK}`,
        padding: "0.6rem 0.95rem",
        borderRadius: "12px",
        fontWeight: 800,
        fontSize: "12px",
        letterSpacing: "0.01em",
        display: isShow ? "inline-flex" : "none",
        cursor: "pointer",
        alignItems: "center",
        gap: "0.45rem",
        boxShadow: SHADOW_SM,
        ...pressable,
      })}
      {...props}
    >
      {props.children}
    </button>
  );
}
