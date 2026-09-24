import { css } from "@emotion/react";
import { useState } from "react";
import { Globe, BookOpen, Zap, CheckCircle2 } from "lucide-react";
import { INK, ACCENT_BLUE } from "@/theme/color";
import { Row } from "@/components/flex/Row";

const breakpoints = [768];
const mq = breakpoints.map((bp) => `@media (max-width: ${bp}px)`);

const HERO_STEPS = ["Select Region", "Elevation Fusion", "Neural 3D Mesh"];

export function HeroSection({ activeStep = 0 }: { activeStep?: number }) {
  const [benchmarkState, setBenchmarkState] = useState<
    "idle" | "processing" | "done"
  >("idle");

  const scrollToStudio = () => {
    document
      .getElementById("strata-map-studio")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const scrollToTeam = () => {
    document
      .getElementById("strata-team")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const runBenchmark = () => {
    if (benchmarkState !== "idle") return;
    setBenchmarkState("processing");
    setTimeout(() => {
      setBenchmarkState("done");
      setTimeout(() => setBenchmarkState("idle"), 2500);
    }, 600);
  };

  return (
    <section
      css={css({
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        textAlign: "center",
        padding: "2.5rem 1rem 3.5rem",
        gap: "1.75rem",
      })}
    >
      {/* Headline */}
      <h1
        css={css({
          margin: 0,
          maxWidth: "56rem",
          fontSize: "clamp(1.8rem, 4.2vw, 2.5rem)",
          fontWeight: 800,
          lineHeight: 1.15,
          letterSpacing: "-0.03em",
          color: "#0F172A",
        })}
      >
        Transform 2D Geospatial Footprints into{" "}
        <span
          css={css({
            display: "inline-block",
            padding: "0.15rem 0.75rem",
            background: "#DAE2FD",
            color: ACCENT_BLUE,
            borderRadius: "12px",
            border: `2px solid ${INK}`,
            boxShadow: "3px 3px 0px #0F172A",
            transform: "rotate(-1deg)",
          })}
        >
          3D Mapping System
        </span>
      </h1>

      {/* Subtitle */}
      <p
        css={css({
          margin: 0,
          maxWidth: "48rem",
          fontSize: "15px",
          fontWeight: 500,
          lineHeight: 1.6,
          color: "#434655",
        })}
      >
        STRATA aggregates stereoscopic satellite imagery, LiDAR point clouds, and
        OpenStreetMap building vectors to synthesize volumetric Level of Detail
        (LOD-3) city meshes in sub-second browser environments.
      </p>

      <style>{`@keyframes strataSpin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }`}</style>
    </section>
  );
}
