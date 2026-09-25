import React, { useState } from "react";
import { css } from "@emotion/react";
import { useAreaStore } from "@/state/areaStore";
import { IsolatedMapboxObject } from "@/components/scene/IsolatedMapboxObject";
import {
  ArrowLeft,
  Building2,
  MapPin,
  Layers,
  Hash,
  Maximize,
  Info,
  Zap,
  AlertCircle,
} from "lucide-react";
import { INK } from "@/theme/color";

export function BuildingIsolateScene() {
  const selectedBuildingDetail = useAreaStore(
    (state) => state.selectedBuildingDetail
  );
  const backendStructure = useAreaStore((state) => state.backendBuildingStructure);
  const backendGeometry = useAreaStore((state) => state.backendBuildingGeometry);
  const isFetching = useAreaStore((state) => state.isFetchingBackendBuilding);
  const backendLookupDone = useAreaStore((state) => state.backendLookupDone);
  const backendFoundData = useAreaStore((state) => state.backendFoundData);
  const setAppStep = useAreaStore((state) => state.setAppStep);
  const [extractedFloor, setExtractedFloor] = useState(0);


  const handleBack = () => {
    setAppStep(1);
  };

  if (!selectedBuildingDetail) {
    return (
      <div
        css={css({
          position: "absolute",
          zIndex: 9999,
          padding: "2rem",
          color: "#0F172A",
        })}
      >
        <p>No building selected.</p>
        <button onClick={handleBack}>Back to Map</button>
      </div>
    );
  }

  // Use real backend data where available; never invent values
  const displayName =
    backendStructure?.building_name ||
    selectedBuildingDetail.name ||
    "Building";

  const displayHeight =
    backendGeometry?.height_m ??
    backendStructure?.height_m ??
    (selectedBuildingDetail.isStructure !== false && selectedBuildingDetail.height > 0
      ? selectedBuildingDetail.height
      : null);

  const displayFloors =
    backendStructure?.floor_count ??
    (selectedBuildingDetail.isStructure !== false && selectedBuildingDetail.floors > 0
      ? selectedBuildingDetail.floors
      : null);

  const displayArea = backendStructure?.footprint_area_sqm
    ? Number(backendStructure.footprint_area_sqm)
    : null;

  const displayAddress =
    backendStructure?.address ?? selectedBuildingDetail.address ?? null;

  const hasCoords =
    typeof selectedBuildingDetail.lng === "number" &&
    Number.isFinite(selectedBuildingDetail.lng) &&
    typeof selectedBuildingDetail.lat === "number" &&
    Number.isFinite(selectedBuildingDetail.lat);

  const coordText = hasCoords
    ? `${selectedBuildingDetail.lat!.toFixed(6)}, ${selectedBuildingDetail.lng!.toFixed(6)}`
    : "Not available";

  const mapsHref =
    hasCoords
      ? `https://www.google.com/maps/search/?api=1&query=${selectedBuildingDetail.lat},${selectedBuildingDetail.lng}`
      : undefined;

  // ULPIN display — strict hierarchy, no generation
  const officialUlpin = backendStructure?.official_ulpin ?? null;
  const candidateUlpin = backendStructure?.candidate_ulpin ?? null;
  const ulpinStatus = backendStructure?.status ?? null;

  // ML provenance
  const mlDerived = backendStructure?.provenance?.ml_derived ?? null;
  const mlConfidence = backendStructure?.provenance?.ml_confidence_score;
  const mlVersion = backendStructure?.provenance?.ml_model_version;

  // Floor count for the slider — use real backend floor list count
  const realFloorCount = backendStructure?.floors.length ?? displayFloors ?? 1;
  const floorCount = Math.max(1, realFloorCount);

  // 3D rendering: use real backend geometry if available
  const renderGeometry = (backendGeometry?.footprint_geojson as { type: string; coordinates: unknown } | null)
    ?? selectedBuildingDetail.geometry
    ?? null;

  const renderHeight = displayHeight ?? 10;

  const infoForScene = {
    ...selectedBuildingDetail,
    geometry: renderGeometry ?? selectedBuildingDetail.geometry,
    height: renderHeight,
    floors: floorCount,
  };

  return (
    <div
      css={css({
        position: "absolute",
        top: "4.5rem",
        left: 0,
        width: "100%",
        height: "calc(100% - 4.5rem)",
        zIndex: 9000,
        display: "flex",
        background: "#F1F5F9",
        overflow: "hidden",
      })}
    >
      {/* Left Sidebar Content Panel */}
      <div
        css={css({
          width: "420px",
          minWidth: "320px",
          background: "#FFFFFF",
          borderRight: `3px solid ${INK}`,
          boxShadow: "3px 0 0 #0F172A",
          display: "flex",
          flexDirection: "column",
          padding: "2rem",
          zIndex: 10,
          overflowY: "auto",
          gap: "0.1rem",
        })}
      >
        <button
          onClick={handleBack}
          css={css({
            background: "#FFFFFF",
            border: `2px solid ${INK}`,
            boxShadow: "2px 2px 0px #0F172A",
            color: "#0F172A",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            cursor: "pointer",
            padding: "0.55rem 0.9rem",
            borderRadius: "10px",
            marginBottom: "1.5rem",
            fontSize: "0.85rem",
            fontWeight: 800,
            width: "fit-content",
            transition: "transform 0.16s ease, box-shadow 0.16s ease",
            ":hover": { transform: "translate(-1px, -1px)", boxShadow: "3px 3px 0px #0F172A" },
            ":active": { transform: "translate(2px, 2px)", boxShadow: "0px 0px 0px #0F172A" },
          })}
        >
          <ArrowLeft size={16} strokeWidth={2.5} /> Back to Map
        </button>

        {/* Building header */}
        <div
          css={css({
            display: "flex",
            alignItems: "center",
            gap: "1rem",
            marginBottom: "1.5rem",
          })}
        >
          <div
            css={css({
              background: "#2563EB",
              color: "white",
              border: `2.5px solid ${INK}`,
              boxShadow: "3px 3px 0px #0F172A",
              padding: "0.75rem",
              borderRadius: "12px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            })}
          >
            <Building2 size={24} strokeWidth={2.5} />
          </div>
          <div>
            <h1
              css={css({
                margin: 0,
                fontSize: "1.3rem",
                color: "#0F172A",
                fontWeight: 800,
                letterSpacing: "-0.02em",
              })}
            >
              {displayName}
            </h1>
            <p
              css={css({
                margin: 0,
                fontSize: "0.8rem",
                color: "#64748B",
                fontWeight: 600,
              })}
            >
              {selectedBuildingDetail.category || "3D Isolated View"}
            </p>
          </div>
        </div>

        {/* Fetching indicator */}
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
              marginBottom: "1rem",
            })}
          >
            <Layers size={14} strokeWidth={2.5} />
            Loading real backend data…
          </div>
        )}

        {/* Property information */}
        <div
          css={css({
            display: "flex",
            flexDirection: "column",
            gap: "0.75rem",
            marginBottom: "1.5rem",
          })}
        >
          <InfoRow icon={<Building2 size={18} />} label="Property Name" value={displayName} />

          {/* ULPIN — strict display */}
          {officialUlpin ? (
            <InfoRow
              icon={<Hash size={18} />}
              label="Official ULPIN (Government)"
              value={officialUlpin}
              badge="OFFICIAL"
              badgeColor="#16A34A"
            />
          ) : candidateUlpin ? (
            <InfoRow
              icon={<Hash size={18} />}
              label="Candidate ULPIN (Not Official)"
              value={candidateUlpin}
              badge="CANDIDATE"
              badgeColor="#B45309"
            />
          ) : (
            <InfoRow
              icon={<Hash size={18} />}
              label="ULPIN"
              value={isFetching ? "Loading…" : "Not Available / Not Verified"}
            />
          )}

          {ulpinStatus && (
            <InfoRow icon={<Info size={18} />} label="ULPIN Status" value={ulpinStatus} />
          )}

          <InfoRow icon={<Info size={18} />} label="Backend ID" value={selectedBuildingDetail.id} />

          {displayAddress ? (
            <InfoRow icon={<MapPin size={18} />} label="Address" value={displayAddress} />
          ) : null}

          <InfoRow icon={<MapPin size={18} />} label="Coordinates" value={coordText} />

          {mapsHref ? (
            <InfoRow
              icon={<MapPin size={18} />}
              label="Location"
              value="View on Maps"
              href={mapsHref}
            />
          ) : null}

          {displayFloors !== null ? (
            <InfoRow icon={<Layers size={18} />} label="Total Floors" value={String(displayFloors)} />
          ) : (
            <InfoRow icon={<Layers size={18} />} label="Total Floors" value="Not available" />
          )}

          {displayHeight !== null ? (
            <InfoRow icon={<Maximize size={18} />} label="Height" value={`${displayHeight.toFixed(1)} m`} />
          ) : (
            <InfoRow icon={<Maximize size={18} />} label="Height" value="Not available" />
          )}

          {displayArea !== null ? (
            <InfoRow
              icon={<Maximize size={18} />}
              label="Footprint Area"
              value={`${Math.round(displayArea).toLocaleString()} m²`}
            />
          ) : (
            <InfoRow icon={<Maximize size={18} />} label="Footprint Area" value="Not available" />
          )}

          {selectedBuildingDetail.dataSource ? (
            <InfoRow icon={<Info size={18} />} label="Data Source" value={selectedBuildingDetail.dataSource} />
          ) : null}
        </div>

        {/* Real Floors & Units from backend */}
        {backendStructure && backendStructure.floors.length > 0 && (
          <div
            css={css({
              background: "#F8FAFC",
              border: `2px solid ${INK}`,
              boxShadow: "3px 3px 0px #0F172A",
              borderRadius: "14px",
              padding: "1.25rem",
              marginBottom: "1.25rem",
            })}
          >
            <div css={css({ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "1rem" })}>
              <Layers size={18} color="#2563EB" strokeWidth={2.5} />
              <h3 css={css({ margin: 0, fontSize: "0.95rem", color: "#0F172A", fontWeight: 800 })}>
                Floors & Units (Backend)
              </h3>
            </div>
            <div css={css({ display: "flex", flexDirection: "column", gap: "0.5rem", maxHeight: "200px", overflowY: "auto" })}>
              {backendStructure.floors.map((floor) => (
                <div
                  key={floor.id}
                  css={css({
                    background: "#FFFFFF",
                    border: `1.5px solid ${INK}`,
                    borderRadius: "8px",
                    padding: "0.6rem 0.85rem",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  })}
                >
                  <div>
                    <div css={css({ fontSize: "0.8rem", fontWeight: 800, color: "#0F172A" })}>
                      {floor.floor_label || `Floor ${floor.floor_number}`}
                    </div>
                    {floor.floor_use && (
                      <div css={css({ fontSize: "0.65rem", color: "#64748B", fontWeight: 600 })}>
                        {floor.floor_use}
                      </div>
                    )}
                  </div>
                  <div css={css({ fontSize: "0.75rem", color: "#2563EB", fontWeight: 800 })}>
                    {floor.units.length > 0 ? `${floor.units.length} units` : "No units"}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ML Provenance */}
        {mlDerived !== null && (
          <div
            css={css({
              background: mlDerived ? "#EFF6FF" : "#F8FAFC",
              border: `1.5px solid ${INK}`,
              borderRadius: "10px",
              padding: "0.85rem",
              marginBottom: "1.25rem",
            })}
          >
            <div css={css({ display: "flex", alignItems: "center", gap: "0.4rem", marginBottom: "0.4rem" })}>
              <Zap size={14} color={mlDerived ? "#2563EB" : "#94A3B8"} />
              <span css={css({ fontSize: "0.7rem", fontWeight: 800, textTransform: "uppercase", letterSpacing: "0.05em", color: "#64748B" })}>
                ML Engine Result
              </span>
            </div>
            {mlDerived ? (
              <>
                <div css={css({ fontSize: "0.85rem", fontWeight: 700, color: "#0F172A" })}>
                  Height estimated via ML pipeline
                </div>
                {mlConfidence !== null && mlConfidence !== undefined && (
                  <div css={css({ fontSize: "0.75rem", color: "#64748B", fontWeight: 600, marginTop: "0.2rem" })}>
                    Confidence: {(Number(mlConfidence) * 100).toFixed(1)}%
                    {mlVersion && ` · v${mlVersion}`}
                  </div>
                )}
              </>
            ) : (
              <div css={css({ fontSize: "0.8rem", color: "#94A3B8", fontWeight: 600, fontStyle: "italic" })}>
                ML not used — manual/surveyed data
              </div>
            )}
          </div>
        )}

        {/* Disclaimer if no backend data — only shown AFTER lookup completes with no result */}
        {backendLookupDone && !backendFoundData && !backendStructure && !isFetching && (
          <div
            css={css({
              display: "flex",
              alignItems: "flex-start",
              gap: "0.5rem",
              padding: "0.85rem",
              background: "#FEF9EC",
              border: `1.5px solid #FCD34D`,
              borderRadius: "10px",
              fontSize: "12px",
              fontWeight: 600,
              color: "#92400E",
              lineHeight: 1.5,
              marginBottom: "1rem",
            })}
          >
            <AlertCircle size={14} style={{ flexShrink: 0, marginTop: "1px" }} />
            No backend record found at this location. 3D view uses Mapbox geometry. Property data is unavailable.
          </div>
        )}


        {/* Floor Extraction Control */}
        <div
          css={css({
            background: "#F8FAFC",
            border: `2px solid ${INK}`,
            boxShadow: "3px 3px 0px #0F172A",
            borderRadius: "14px",
            padding: "1.25rem",
            marginBottom: "1.5rem",
          })}
        >
          <div css={css({ display: "flex", alignItems: "center", gap: "0.65rem", marginBottom: "1rem" })}>
            <Maximize size={18} color="#2563EB" strokeWidth={2.5} />
            <h3 css={css({ margin: 0, fontSize: "1rem", color: "#0F172A", fontWeight: 800 })}>
              Floor Extraction
            </h3>
          </div>
          <p
            css={css({
              margin: 0,
              fontSize: "0.8rem",
              color: "#64748B",
              fontWeight: 600,
              marginBottom: "1.25rem",
              lineHeight: 1.5,
            })}
          >
            Drag the slider to explode floors apart and inspect each level.
            {!backendStructure && " (Floor count from Mapbox geometry — backend not available)"}
          </p>

          <div
            css={css({
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: "0.75rem",
              fontSize: "0.75rem",
              fontWeight: 800,
              color: "#64748B",
              textTransform: "uppercase",
              letterSpacing: "0.04em",
            })}
          >
            <span>Ground Floor</span>
            <span>Roof</span>
          </div>

          <input
            type="range"
            min={0}
            max={floorCount}
            step={1}
            value={extractedFloor}
            onChange={(e) => setExtractedFloor(Number(e.target.value))}
            css={css({
              width: "100%",
              accentColor: "#2563EB",
              height: "8px",
              cursor: "pointer",
            })}
          />

          <div
            css={css({
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginTop: "1rem",
            })}
          >
            <span css={css({ fontSize: "0.75rem", fontWeight: 700, color: "#64748B" })}>
              Extracted floors:
            </span>
            <span css={css({ fontSize: "1.1rem", fontWeight: 800, color: "#2563EB" })}>
              {extractedFloor} / {floorCount}
            </span>
          </div>
        </div>

        <div
          css={css({
            marginTop: "auto",
            padding: "1rem",
            background: "#EFF6FF",
            border: `1.5px solid ${INK}`,
            borderRadius: "12px",
            fontSize: "0.75rem",
            color: "#434655",
            fontWeight: 600,
            lineHeight: 1.5,
          })}
        >
          Tip: use the right-side 3D scene to orbit around the building. Hold
          left-click to rotate, right-click to pan, and scroll to zoom.
        </div>
      </div>

      {/* Right 3D View Panel */}
      <div css={css({ flex: 1, position: "relative", background: "#E2E8F0" })}>
        <IsolatedMapboxObject
          key={selectedBuildingDetail.id}
          info={infoForScene}
          extractedFloor={extractedFloor}
        />
      </div>
    </div>
  );
}

function InfoRow({
  icon,
  label,
  value,
  href,
  badge,
  badgeColor,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  href?: string;
  badge?: string;
  badgeColor?: string;
}) {
  return (
    <div
      css={css({
        display: "flex",
        alignItems: "center",
        gap: "1rem",
        padding: "0.85rem",
        background: "#F8FAFC",
        borderRadius: "10px",
        border: `1.5px solid ${INK}`,
        boxShadow: "2px 2px 0px #0F172A",
      })}
    >
      <div css={css({ color: "#2563EB", display: "flex", flexShrink: 0 })}>{icon}</div>
      <div css={css({ display: "flex", flexDirection: "column", gap: "0.2rem", flex: 1, minWidth: 0 })}>
        <span
          css={css({
            fontSize: "0.65rem",
            textTransform: "uppercase",
            fontWeight: 800,
            color: "#64748B",
            letterSpacing: "0.05em",
          })}
        >
          {label}
        </span>
        <div css={css({ display: "flex", alignItems: "center", gap: "0.4rem", flexWrap: "wrap" })}>
          {href ? (
            <a
              href={href}
              target="_blank"
              rel="noreferrer"
              css={css({
                fontSize: "0.85rem",
                fontWeight: 700,
                color: "#2563EB",
                textDecoration: "none",
                ":hover": { textDecoration: "underline" },
              })}
            >
              {value}
            </a>
          ) : (
            <span
              css={css({
                fontSize: "0.85rem",
                fontWeight: 800,
                color:
                  value === "Not available" || value === "Not assigned" || value === "Loading…"
                    ? "#94A3B8"
                    : "#0F172A",
                fontStyle:
                  value === "Not available" || value === "Not assigned" ? "italic" : "normal",
                fontFamily: label.includes("ULPIN") || label.includes("ID") ? "monospace" : "inherit",
                wordBreak: "break-all",
              })}
            >
              {value}
            </span>
          )}
          {badge && (
            <span
              css={css({
                fontSize: "0.6rem",
                fontWeight: 800,
                textTransform: "uppercase",
                letterSpacing: "0.05em",
                color: "#FFFFFF",
                background: badgeColor || "#64748B",
                padding: "0.15rem 0.4rem",
                borderRadius: "4px",
              })}
            >
              {badge}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
