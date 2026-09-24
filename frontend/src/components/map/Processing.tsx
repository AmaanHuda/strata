import { css, keyframes } from "@emotion/react";
import { Building2, Layers, Ruler } from "lucide-react";
import { useEffect, useState } from "react";
import {
  ACCENT_BLUE,
  ACCENT_TEAL,
  INK,
  TEXT_PRIMARY,
  TEXT_SECONDARY,
} from "@/theme/color";

export interface Building {
  id: number;
  tags: { [key: string]: string | undefined };
  geometry?: { lat: number; lng: number }[];
}

const spin = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

const pulse = keyframes`
  0%, 100% { transform: scale(1); opacity: 0.9; }
  50% { transform: scale(1.08); opacity: 1; }
`;

const shimmer = keyframes`
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
`;

const LOADING_PHRASES = [
  "Fetching parcel data...",
  "Accessing building records...",
  "Triangulating coordinates...",
  "Cross-referencing ULPIN records...",
  "Validating floor topology...",
  "Rendering vertical property data...",
];

export function BuildingHeights({
  buildings,
  loading,
}: {
  buildings: Building[];
  loading: boolean;
}) {
  const [phraseIndex, setPhraseIndex] = useState(0);

  useEffect(() => {
    if (!loading) {
      setPhraseIndex(0);
      return;
    }
    const interval = setInterval(() => {
      setPhraseIndex((prev) => (prev + 1) % LOADING_PHRASES.length);
    }, 1800);
    return () => clearInterval(interval);
  }, [loading]);

  return (
    <div
      css={css({
        position: "relative",
        paddingTop: "0.25rem",
      })}
    >
      {loading && (
        <div
          css={css({
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "2.5rem 1.5rem",
            margin: "0.5rem 0",
            borderRadius: "14px",
            border: `2px solid ${INK}`,
            background: "#FFFFFF",
            boxShadow: "3px 3px 0px #0F172A",
            textAlign: "center",
            gap: "1.25rem",
          })}
        >
          {/* Spinning & pulsing indicator */}
          <div
            css={css({
              position: "relative",
              width: "56px",
              height: "56px",
              display: "grid",
              placeItems: "center",
            })}
          >
            {/* Outer spinning ring */}
            <div
              css={css({
                position: "absolute",
                inset: 0,
                borderRadius: "50%",
                border: "2px solid #E2E8F0",
                borderTopColor: ACCENT_BLUE,
                borderRightColor: ACCENT_TEAL,
                animation: `${spin} 1.4s cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite`,
              })}
            />
            {/* Inner pulsing core */}
            <div
              css={css({
                width: "36px",
                height: "36px",
                borderRadius: "50%",
                background: "#EFF6FF",
                border: `1.5px solid ${INK}`,
                boxShadow: "1px 1px 0px #0F172A",
                display: "grid",
                placeItems: "center",
                color: ACCENT_BLUE,
                animation: `${pulse} 2s ease-in-out infinite`,
              })}
            >
              <Layers size={18} />
            </div>
          </div>

          {/* Rotating status phrase & progress hint */}
          <div
            css={css({
              display: "flex",
              flexDirection: "column",
              gap: "0.35rem",
            })}
          >
            <div
              key={phraseIndex}
              css={css({
                fontSize: "14px",
                fontWeight: 700,
                color: TEXT_PRIMARY,
                letterSpacing: "-0.01em",
                transition: "opacity 0.25s ease",
              })}
            >
              {LOADING_PHRASES[phraseIndex]}
            </div>
            <div
              css={css({
                fontSize: "12px",
                color: TEXT_SECONDARY,
                fontWeight: 600,
              })}
            >
              Processing spatial topology & building models
            </div>
          </div>

          {/* Shimmer line bar */}
          <div
            css={css({
              width: "140px",
              height: "4px",
              borderRadius: "999px",
              border: `1.5px solid ${INK}`,
              background:
                "linear-gradient(90deg, #EFF6FF 0%, #2563EB 50%, #EFF6FF 100%)",
              backgroundSize: "200% 100%",
              animation: `${shimmer} 2s infinite linear`,
            })}
          />
        </div>
      )}

      {!loading && buildings.length > 0 && (
        <div
          css={css({
            display: "inline-flex",
            alignItems: "center",
            gap: "0.65rem",
            color: TEXT_SECONDARY,
            fontSize: "13px",
            fontWeight: 600,
            marginBottom: "0.65rem",
            background: "#FFFFFF",
            border: `2px solid ${INK}`,
            boxShadow: "2px 2px 0px #0F172A",
            borderRadius: "12px",
            padding: "0.55rem 0.85rem",
          })}
        >
          <Building2 size={14} color="#2563EB" strokeWidth={2.5} />
          <span css={css({ color: "#2563EB", fontWeight: 800 })}>
            {buildings.length}
          </span>
          buildings loaded. Click Next Step to view in 3D.
        </div>
      )}

      {!loading && buildings.length === 0 && (
        <div
          css={css({
            padding: "1.5rem",
            textAlign: "center",
            color: TEXT_SECONDARY,
            fontSize: "13px",
            fontWeight: 600,
            borderRadius: "12px",
            border: `2px solid ${INK}`,
            background: "#FFFFFF",
            boxShadow: "2px 2px 0px #0F172A",
          })}
        >
          No 3D building footprints found in the selected region. You can still proceed to 3D view or go back to select another area.
        </div>
      )}

      {!loading && buildings.length > 0 && (
        <ul
          css={css({
            overflow: "auto",
            zIndex: 999,
            position: "relative",
            maxHeight: "42vh",
            listStyle: "none",
            padding: 0,
            margin: "0.5rem 0 0",
            color: "#374151",
            fontSize: "12px",
            display: "grid",
            gap: "0.6rem",
          })}
        >
          {buildings.map((b) => (
            <li
              key={b.id}
              css={css({
                padding: "0.85rem 0.95rem",
                borderRadius: "10px",
                border: `2px solid ${INK}`,
                background: "#FFFFFF",
                boxShadow: "2px 2px 0px #0F172A",
              })}
            >
              <div
                css={css({
                  display: "flex",
                  justifyContent: "space-between",
                  gap: "1rem",
                  marginBottom: "0.4rem",
                  alignItems: "center",
                })}
              >
                <div css={css({ fontWeight: 800, color: TEXT_PRIMARY })}>
                  Building {b.id}
                </div>
                <span
                  css={css({
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "0.35rem",
                    padding: "0.25rem 0.5rem",
                    borderRadius: "999px",
                    background: "#ECFDF5",
                    border: `1.5px solid ${INK}`,
                    color: "#006C49",
                    fontWeight: 800,
                    fontSize: "11px",
                  })}
                >
                  <Ruler size={12} />
                  {b.tags.height || "No height"}
                </span>
              </div>
              {b.geometry ? (
                <div css={css({ fontSize: "11px", color: "#64748B", fontWeight: 600 })}>
                  {b.geometry.length} vertices
                </div>
              ) : (
                <div css={css({ fontSize: "11px", color: "#64748B", fontWeight: 600 })}>
                  No geometry info
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
