import { css } from "@emotion/react";
import type { Building } from "@/components/map/Processing";
import { Building2, Gauge, MapPinned } from "lucide-react";
import { type ReactNode } from "react";

export function StatsPanel({
  buildings,
  area,
  isVisible,
}: {
  buildings: Building[];
  area: { lat: number; lng: number }[] | null;
  isVisible: boolean;
}) {
  if (!isVisible) return null;

  const buildingCount = buildings.length;
  const areaLabel =
    area && area.length >= 2
      ? `${Math.abs(area[0].lat - area[1].lat).toFixed(3)} x ${Math.abs(
          area[0].lng - area[1].lng
        ).toFixed(3)}`
      : "N/A";

  const withHeightInfo = buildings.filter((b) => b.tags.height).length;

  return (
    <aside
      css={css({
        position: "fixed",
        left: "1rem",
        bottom: "1rem",
        zIndex: 9999,
        minWidth: "240px",
        padding: "0.95rem 1rem",
        borderRadius: "12px",
        background: "#FFFFFF",
        boxShadow: "3px 3px 0px #0F172A",
        color: "#0F172A",
        border: `2.5px solid #0F172A`,
      })}
    >
      <div
        css={css({
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          fontSize: "13px",
          fontWeight: 800,
          marginBottom: "0.75rem",
          color: "#0F172A",
          textTransform: "uppercase",
          letterSpacing: "0.02em",
        })}
      >
        <Gauge size={15} color="#2563EB" />
        Scene Stats
      </div>
      <StatRow icon={<Building2 size={12} />} label="Buildings" value={String(buildingCount)} />
      <StatRow icon={<MapPinned size={12} />} label="With height" value={String(withHeightInfo)} />
      <StatRow icon={<Gauge size={12} />} label="Area" value={areaLabel} />
    </aside>
  );
}

function StatRow({
  icon,
  label,
  value,
}: {
  icon: ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div
      css={css({
        display: "flex",
        justifyContent: "space-between",
        gap: "1rem",
        fontSize: "12px",
        padding: "0.45rem 0.55rem",
        borderRadius: "8px",
        backgroundColor: "#F1F5F9",
        border: `1.5px solid #0F172A`,
        marginBottom: "0.5rem",
      })}
    >
      <span
        css={css({
          color: "#434655",
          display: "inline-flex",
          alignItems: "center",
          gap: "0.4rem",
        })}
      >
        <span css={css({ color: "#2563EB" })}>{icon}</span>
        {label}
      </span>
      <span css={css({ fontWeight: 800, textAlign: "right", color: "#0F172A" })}>
        {value}
      </span>
    </div>
  );
}
