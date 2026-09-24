import React from "react";
import { css } from "@emotion/react";
import { X, Building2, Home, Layers, Zap, CheckCircle2, AlertCircle, Info } from "lucide-react";
import { INK, SHADOW_LG } from "@/theme/color";
import { useAreaStore } from "@/state/areaStore";

export interface BuildingInfo {
  id: string;
  type: string;
  height: number;
  floors: number;
  flats: number;
  occupancy: string;
  energyRating: string;
  area: number;
  /** Human readable property name */
  name?: string;
  /** Broad object category: building, park, water, road, poi, parcel ... */
  category?: string;
  /** Exact clicked coordinates */
  lng?: number;
  lat?: number;
  /** Free text address / locality when available */
  address?: string;
  /** Where the data came from */
  dataSource?: string;
  /** False for flat objects (parks, roads, water) that have no floors */
  isStructure?: boolean;
  /** Extrusion base elevation in meters */
  baseHeight?: number;
  /** Building footprint geometry for 3D rendering */
  geometry?: {
    type: string;
    coordinates: unknown;
  };
  /** Source color when available */
  mapColor?: string;
}

interface BuildingSidebarProps {
  info: BuildingInfo | null;
  onClose: () => void;
}

const IconSize = css({
  width: "18px",
  height: "18px",
  color: "#434655",
});

const labelStyle = css({
  fontSize: "0.7rem",
  textTransform: "uppercase",
  letterSpacing: "0.05em",
  color: "#64748B",
  fontWeight: 700,
  marginBottom: "0.25rem",
});

const valueStyle = css({
  fontSize: "1rem",
  color: "#0F172A",
  fontWeight: 800,
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
});

const notAvailableStyle = css({
  fontSize: "0.85rem",
  color: "#94A3B8",
  fontWeight: 600,
  fontStyle: "italic",
});

const gridItemStyle = css({
  background: "#F8FAFC",
  border: `1.5px solid ${INK}`,
  boxShadow: "2px 2px 0px #0F172A",
  borderRadius: "10px",
  padding: "1rem",
  display: "flex",
  flexDirection: "column",
});

/** Renders a value or a styled "Not available" placeholder — never fabricates data. */
function ValueOrNA({
  value,
  suffix = "",
}: {
  value: string | number | null | undefined;
  suffix?: string;
}) {
  if (value === null || value === undefined || value === "" || value === "Not available" || value === "N/A") {
    return <span css={notAvailableStyle}>Not available</span>;
  }
  return (
    <span css={valueStyle}>
      {value}{suffix}
    </span>
  );
}

export function BuildingSidebar({ info, onClose }: BuildingSidebarProps) {
  const backendStructure = useAreaStore((state) => state.backendBuildingStructure);
  const isFetching = useAreaStore((state) => state.isFetchingBackendBuilding);

  if (!info) return null;

  // ULPIN display: strict hierarchy — official > candidate > unavailable
  const officialUlpin = backendStructure?.official_ulpin ?? null;
  const candidateUlpin = backendStructure?.candidate_ulpin ?? null;
  const ulpinStatus = backendStructure?.status ?? null;
  const isVerified = backendStructure?.is_verified ?? false;

  // ML provenance
  const mlDerived = backendStructure?.provenance?.ml_derived ?? null;
  const mlConfidence = backendStructure?.provenance?.ml_confidence_score;
  const mlVersion = backendStructure?.provenance?.ml_model_version;

  // Building metrics from backend (authoritative) or Mapbox (secondary)
  const displayHeight = backendStructure?.height_m ?? (info.isStructure ? info.height : null);
  const displayFloors = backendStructure?.floor_count ?? (info.isStructure ? info.floors : null);
  const displayArea = backendStructure?.footprint_area_sqm
    ? Number(backendStructure.footprint_area_sqm)
    : null;
  const displayName = backendStructure?.building_name || info.name || "Building";
  const displayAddress = backendStructure?.address ?? info.address ?? null;
  const displayDistrict = backendStructure?.district ?? null;
  const totalUnits = backendStructure
    ? backendStructure.floors.reduce((acc, f) => acc + f.units.length, 0)
    : null;
  const backendFloorCount = backendStructure?.floors.length ?? null;

  return (
    <div
      css={css({
        position: "absolute",
        right: "1.5rem",
        top: "1.5rem",
        bottom: "1.5rem",
        width: "380px",
        background: "#FFFFFF",
        borderRadius: "16px",
        border: `3px solid ${INK}`,
        boxShadow: "6px 6px 0px #0F172A",
        padding: "1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem",
        zIndex: 10000,
        overflowY: "auto",
        transform: "translateX(0)",
        animation: "slideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
        "@keyframes slideIn": {
          from: { transform: "translateX(120%)", opacity: 0 },
          to: { transform: "translateX(0)", opacity: 1 },
        },
      })}
    >
      {/* Header */}
      <div
        css={css({
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          borderBottom: `2px solid ${INK}`,
          paddingBottom: "1rem",
        })}
      >
        <div css={css({ display: "flex", alignItems: "center", gap: "0.75rem" })}>
          <div
            css={css({
              background: "#2563EB",
              color: "white",
              border: `2px solid ${INK}`,
              boxShadow: "2px 2px 0px #0F172A",
              padding: "0.5rem",
              borderRadius: "10px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            })}
          >
            <Building2 size={20} strokeWidth={2.5} />
          </div>
          <div>
            <h2 css={css({ margin: 0, fontSize: "1.1rem", color: "#0F172A", fontWeight: 800, lineHeight: 1.2 })}>
              {displayName}
            </h2>
            <p css={css({ margin: 0, fontSize: "0.75rem", color: "#64748B", fontWeight: 600 })}>
              {info.category || info.type}
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          css={css({
            background: "#FFFFFF",
            border: `2px solid ${INK}`,
            boxShadow: "1px 1px 0px #0F172A",
            cursor: "pointer",
            width: "2rem",
            height: "2rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#0F172A",
            borderRadius: "8px",
            transition: "transform 0.16s ease, box-shadow 0.16s ease",
            ":hover": { transform: "translate(-1px, -1px)", boxShadow: "2px 2px 0px #0F172A" },
            ":active": { transform: "translate(1px, 1px)", boxShadow: "0px 0px 0px #0F172A" },
          })}
        >
          <X size={18} strokeWidth={2.5} />
        </button>
      </div>

      {/* Loading indicator */}
      {isFetching && (
        <div
          css={css({
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            padding: "0.6rem 0.85rem",
            background: "#EFF6FF",
            border: `1.5px solid #BFDBFE`,
            borderRadius: "10px",
            fontSize: "12px",
            fontWeight: 700,
            color: "#2563EB",
          })}
        >
          <Layers size={14} strokeWidth={2.5} />
          Fetching real backend data…
        </div>
      )}

      {/* ULPIN Section — Only real backend ULPIN, never generated */}
      <div
        css={css({
          background: "#F8FAFC",
          border: `1.5px solid ${INK}`,
          borderRadius: "12px",
          padding: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.5rem",
        })}
      >
        <div css={css({ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.25rem" })}>
          <Info size={14} color="#2563EB" />
          <span css={css({ fontSize: "0.7rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748B" })}>
            ULPIN / Property ID
          </span>
        </div>

        {officialUlpin ? (
          <div>
            <div css={css({ fontSize: "0.65rem", color: "#16A34A", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.04em" })}>
              ✓ Official ULPIN (Government Issued)
            </div>
            <div css={css({ fontSize: "0.9rem", fontWeight: 800, color: "#0F172A", fontFamily: "monospace", marginTop: "0.2rem" })}>
              {officialUlpin}
            </div>
          </div>
        ) : candidateUlpin ? (
          <div>
            <div css={css({ fontSize: "0.65rem", color: "#B45309", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.04em" })}>
              ⚠ Candidate ULPIN (Not Government-Official)
            </div>
            <div css={css({ fontSize: "0.9rem", fontWeight: 800, color: "#0F172A", fontFamily: "monospace", marginTop: "0.2rem" })}>
              {candidateUlpin}
            </div>
            <div css={css({ fontSize: "0.65rem", color: "#94A3B8", fontWeight: 600, marginTop: "0.2rem", lineHeight: 1.4 })}>
              This is a candidate identifier — not an officially assigned government ULPIN.
            </div>
          </div>
        ) : (
          <div css={css({ fontSize: "0.85rem", color: "#94A3B8", fontStyle: "italic", fontWeight: 600 })}>
            {isFetching ? "Loading…" : "ULPIN not assigned / not in backend registry"}
          </div>
        )}

        {ulpinStatus && (
          <div css={css({ fontSize: "0.7rem", fontWeight: 700, color: "#64748B" })}>
            Status: <span css={css({ color: ulpinStatus === "OFFICIAL" ? "#16A34A" : ulpinStatus === "VALIDATED" ? "#2563EB" : "#B45309" })}>{ulpinStatus}</span>
            {isVerified ? " · Verified" : ""}
          </div>
        )}
      </div>

      {/* Stats Grid — all from backend or "Not available" */}
      <div
        css={css({
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "0.85rem",
        })}
      >
        <div css={gridItemStyle}>
          <span css={labelStyle}>Total Floors</span>
          <span css={valueStyle}>
            <Building2 css={IconSize} />
            {backendFloorCount !== null ? backendFloorCount : displayFloors !== null && displayFloors > 0 ? displayFloors : <span css={notAvailableStyle}>Not available</span>}
          </span>
        </div>

        <div css={gridItemStyle}>
          <span css={labelStyle}>Total Units</span>
          <span css={valueStyle}>
            <Home css={IconSize} />
            {totalUnits !== null ? (totalUnits > 0 ? `${totalUnits} units` : <span css={notAvailableStyle}>Not available</span>) : <span css={notAvailableStyle}>{isFetching ? "Loading…" : "Not available"}</span>}
          </span>
        </div>

        <div css={gridItemStyle}>
          <span css={labelStyle}>Height</span>
          <ValueOrNA value={displayHeight !== null ? displayHeight?.toFixed(1) : null} suffix=" m" />
        </div>

        <div css={gridItemStyle}>
          <span css={labelStyle}>Footprint Area</span>
          <ValueOrNA value={displayArea !== null ? Math.round(displayArea).toLocaleString() : null} suffix=" m²" />
        </div>

        <div css={gridItemStyle}>
          <span css={labelStyle}>District</span>
          <ValueOrNA value={displayDistrict} />
        </div>

        <div css={gridItemStyle}>
          <span css={labelStyle}>Address</span>
          <ValueOrNA value={displayAddress} />
        </div>
      </div>

      {/* ML Provenance — only shown when backend returns it */}
      {mlDerived !== null && (
        <div
          css={css({
            background: mlDerived ? "#EFF6FF" : "#F8FAFC",
            border: `1.5px solid ${INK}`,
            borderRadius: "10px",
            padding: "0.85rem",
            display: "flex",
            flexDirection: "column",
            gap: "0.35rem",
          })}
        >
          <div css={css({ display: "flex", alignItems: "center", gap: "0.4rem" })}>
            <Zap size={14} color={mlDerived ? "#2563EB" : "#94A3B8"} />
            <span css={css({ fontSize: "0.7rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748B" })}>
              ML Engine Result
            </span>
          </div>
          {mlDerived ? (
            <>
              <div css={css({ fontSize: "0.85rem", fontWeight: 700, color: "#0F172A" })}>
                Height estimated by ML pipeline
              </div>
              {mlConfidence !== null && mlConfidence !== undefined && (
                <div css={css({ fontSize: "0.75rem", color: "#64748B", fontWeight: 600 })}>
                  Confidence: {(Number(mlConfidence) * 100).toFixed(1)}%
                  {mlVersion && ` · Model: ${mlVersion}`}
                </div>
              )}
            </>
          ) : (
            <div css={css({ fontSize: "0.8rem", color: "#94A3B8", fontWeight: 600, fontStyle: "italic" })}>
              Not ML-derived — surveyed/manual data
            </div>
          )}
        </div>
      )}

      {/* Data source */}
      {info.dataSource && (
        <div css={css({ fontSize: "0.7rem", color: "#94A3B8", fontWeight: 600, borderTop: `1.5px solid #E2E8F0`, paddingTop: "0.75rem" })}>
          Source: {info.dataSource}
        </div>
      )}

      {/* View in 3D button */}
      <div css={css({ marginTop: "auto" })}>
        <button
          onClick={() => {
            useAreaStore.getState().setSelectedBuildingDetail(info);
            useAreaStore.getState().setAppStep(2);
          }}
          css={css({
            width: "100%",
            background: "#0F172A",
            color: "white",
            border: `2.5px solid ${INK}`,
            boxShadow: SHADOW_LG,
            padding: "1rem",
            borderRadius: "12px",
            fontWeight: 800,
            fontSize: "13px",
            letterSpacing: "0.01em",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            transition: "transform 0.16s ease, box-shadow 0.16s ease",
            ":hover": { transform: "translate(-1px, -1px)", boxShadow: "6px 6px 0px #0F172A" },
            ":active": { transform: "translate(2px, 2px)", boxShadow: "1px 1px 0px #0F172A" },
          })}
        >
          <CheckCircle2 size={18} strokeWidth={2.5} /> View in 3D
        </button>
      </div>
    </div>
  );
}
