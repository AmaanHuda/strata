import { css } from "@emotion/react";
import { Code2, Share2, TerminalSquare } from "lucide-react";
import { INK } from "@/theme/color";

const breakpoints = [768];
const mq = breakpoints.map((bp) => `@media (max-width: ${bp}px)`);

export function SiteFooter() {
  const iconBtn = css({
    width: "2.4rem",
    height: "2.4rem",
    display: "grid",
    placeItems: "center",
    background: "#FFFFFF",
    border: `2px solid ${INK}`,
    boxShadow: "2px 2px 0px #0F172A",
    borderRadius: "10px",
    color: "#0F172A",
    cursor: "pointer",
    transition: "transform 0.16s ease, box-shadow 0.16s ease",
    ":hover": {
      transform: "translate(-1px, -1px)",
      boxShadow: "3px 3px 0px #0F172A",
    },
    ":active": {
      transform: "translate(2px, 2px)",
      boxShadow: "0px 0px 0px #0F172A",
    },
  });

  return (
    <footer
      css={css({
        width: "100%",
        background: "#EAEDFF",
        padding: "2.5rem 1.5rem 1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "2rem",
      })}
    >
      <div
        css={css({
          maxWidth: "80rem",
          width: "100%",
          margin: "0 auto",
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr",
          gap: "2rem",
          paddingBottom: "1.5rem",
          borderBottom: `1.5px solid #C3C6D7`,
          [mq[0]]: { gridTemplateColumns: "1fr" },
        })}
      >
        {/* Brand */}
        <div
          css={css({
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
          })}
        >
          <div
            css={css({ display: "flex", alignItems: "center", gap: "0.5rem" })}
          >
            <span
              css={css({
                fontSize: "1.1rem",
                fontWeight: 800,
                letterSpacing: "-0.02em",
                color: "#0F172A",
              })}
            >
              STRATA 3D Studio
            </span>
          </div>
          <p
            css={css({
              margin: 0,
              fontSize: "13px",
              fontWeight: 500,
              lineHeight: 1.6,
              color: "#434655",
              maxWidth: "26rem",
            })}
          >
            Next-generation point-cloud segmentation and high-fidelity 3D city
            mesh reconstruction engine. Developed for Ministry of Housing and
            Urban Affairs (MoHUA).
          </p>
          <div css={css({ display: "flex", gap: "0.5rem", flexWrap: "wrap" })}>
            <span
              css={css({
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.3rem 0.7rem",
                background: "#FFFFFF",
                border: `1.5px solid ${INK}`,
                boxShadow: "1px 1px 0px #0F172A",
                borderRadius: "8px",
                fontSize: "11px",
                fontWeight: 800,
                color: "#0F172A",
              })}
            >
              <span
                css={css({
                  width: "8px",
                  height: "8px",
                  borderRadius: "999px",
                  background: "#10B981",
                  display: "inline-block",
                })}
              />
              API Engine Online
            </span>
            <span
              css={css({
                display: "inline-flex",
                alignItems: "center",
                gap: "0.4rem",
                padding: "0.3rem 0.7rem",
                background: "#FFFFFF",
                border: `1.5px solid ${INK}`,
                boxShadow: "1px 1px 0px #0F172A",
                borderRadius: "8px",
                fontSize: "11px",
                fontWeight: 800,
                color: "#0F172A",
              })}
            >
              <span
                css={css({
                  width: "8px",
                  height: "8px",
                  borderRadius: "999px",
                  background: "#2563EB",
                  display: "inline-block",
                })}
              />
              LiDAR Cluster 99.98%
            </span>
          </div>
        </div>

        {/* Problem Context */}
        <div
          css={css({ display: "flex", flexDirection: "column", gap: "0.6rem" })}
        >
          <span
            css={css({
              fontSize: "12px",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#0F172A",
            })}
          >
            Problem Context
          </span>
          <p
            css={css({
              margin: 0,
              fontSize: "13px",
              fontWeight: 600,
              color: "#434655",
            })}
          >
            SIH 2024 PS #1648
          </p>
          <p
            css={css({
              margin: 0,
              fontSize: "13px",
              fontWeight: 500,
              lineHeight: 1.6,
              color: "#434655",
            })}
          >
            Rapid Automated Digital Elevation and 3D Urban Volumetric Modeling
            from Dual-Stream Stereoscopic Data.
          </p>
        </div>

        {/* Repository & Team */}
        <div
          css={css({ display: "flex", flexDirection: "column", gap: "0.6rem" })}
        >
          <span
            css={css({
              fontSize: "12px",
              fontWeight: 800,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              color: "#0F172A",
            })}
          >
            Repository & Team
          </span>
          <div css={css({ display: "flex", gap: "0.5rem" })}>
            <button css={iconBtn} aria-label="Source code">
              <Code2 size={18} strokeWidth={2.5} />
            </button>
            <button css={iconBtn} aria-label="Share">
              <Share2 size={18} strokeWidth={2.5} />
            </button>
            <button css={iconBtn} aria-label="Terminal">
              <TerminalSquare size={18} strokeWidth={2.5} />
            </button>
          </div>
          <p
            css={css({
              margin: 0,
              fontSize: "11px",
              fontWeight: 600,
              color: "#434655",
            })}
          >
            Team Aeranoix • Grand Finale Cohort
          </p>
        </div>
      </div>

      {/* Legal Row */}
      <div
        css={css({
          maxWidth: "80rem",
          width: "100%",
          margin: "0 auto",
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "1rem",
          fontSize: "12px",
          fontWeight: 600,
          color: "#434655",
          [mq[0]]: { flexDirection: "column", textAlign: "center" },
        })}
      >
        <span>
          © 2026 Solution to SIH PS #26011 • Developed by Team Aeranoix
        </span>
      </div>
    </footer>
  );
}
