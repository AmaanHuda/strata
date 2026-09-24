import type { BuildingInfo } from "@/components/panels/BuildingSidebar";

const M_PER_DEG_LAT = 110574;

function ringAreaSqm(ring: number[][], lat: number): number {
  const mPerDegLng = 111320 * Math.cos((lat * Math.PI) / 180);
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i++) {
    const [x1, y1] = ring[i];
    const [x2, y2] = ring[i + 1];
    sum +=
      x1 * mPerDegLng * (y2 * M_PER_DEG_LAT) - x2 * mPerDegLng * (y1 * M_PER_DEG_LAT);
  }
  return Math.abs(sum / 2);
}

/** Estimate footprint area in sq.ft from a feature geometry. */
export function estimateAreaSqFt(geometry: any, lat: number): number {
  try {
    if (!geometry) return 0;
    let ring: number[][] | null = null;
    if (geometry.type === "Polygon") ring = geometry.coordinates?.[0];
    if (geometry.type === "MultiPolygon") ring = geometry.coordinates?.[0]?.[0];
    if (!ring || ring.length < 4) return 0;
    return Math.round(ringAreaSqm(ring, lat) * 10.7639);
  } catch {
    return 0;
  }
}

type Category = {
  key: string;
  label: string;
  priority: number;
  isStructure: boolean;
};

const CATEGORIES: Record<string, Category> = {
  building: { key: "building", label: "Building", priority: 100, isStructure: true },
  poi: { key: "poi", label: "Point of Interest", priority: 95, isStructure: false },
  structure: { key: "structure", label: "Built Structure", priority: 80, isStructure: true },
  transit: { key: "transit", label: "Transit Infrastructure", priority: 75, isStructure: false },
  aeroway: { key: "aeroway", label: "Airport Area", priority: 70, isStructure: false },
  park: { key: "park", label: "Park / Green Space", priority: 70, isStructure: false },
  water: { key: "water", label: "Water Body", priority: 65, isStructure: false },
  road: { key: "road", label: "Road / Path", priority: 60, isStructure: false },
  place: { key: "place", label: "Place / Locality", priority: 50, isStructure: false },
  landuse: { key: "landuse", label: "Land Use Area", priority: 45, isStructure: false },
  parcel: { key: "parcel", label: "Land Parcel", priority: 40, isStructure: false },
  terrain: { key: "terrain", label: "Terrain", priority: 10, isStructure: false },
};

function categoryFor(layerId: string, sourceLayer: string, props: any): Category {
  const hay = `${layerId} ${sourceLayer}`.toLowerCase();
  const cls = String(props?.class || props?.type || "").toLowerCase();

  if (hay.includes("building") || cls.includes("building")) return CATEGORIES.building;
  if (hay.includes("poi") || props?.maki || props?.category_en) return CATEGORIES.poi;
  if (hay.includes("transit") || hay.includes("rail") || cls.includes("rail"))
    return CATEGORIES.transit;
  if (hay.includes("aeroway")) return CATEGORIES.aeroway;
  if (hay.includes("bridge") || hay.includes("tunnel") || hay.includes("structure"))
    return CATEGORIES.structure;
  if (
    hay.includes("park") ||
    hay.includes("green") ||
    hay.includes("grass") ||
    hay.includes("tree") ||
    hay.includes("vegetation") ||
    ["park", "grass", "scrub", "wood", "pitch", "garden"].includes(cls)
  )
    return CATEGORIES.park;
  if (hay.includes("water") || cls.includes("water") || cls === "river")
    return CATEGORIES.water;
  if (
    hay.includes("road") ||
    hay.includes("street") ||
    hay.includes("path") ||
    hay.includes("traffic")
  )
    return CATEGORIES.road;
  if (hay.includes("landuse") || hay.includes("land-use")) return CATEGORIES.landuse;
  if (hay.includes("place") || hay.includes("settlement") || hay.includes("label"))
    return CATEGORIES.place;
  if (hay.includes("hillshade") || hay.includes("terrain") || hay.includes("land"))
    return CATEGORIES.terrain;
  return CATEGORIES.parcel;
}

function nameFrom(props: any): string | undefined {
  const candidates = [
    props?.name,
    props?.name_en,
    props?.buildingName,
    props?.ulpinId,
    props?.ref,
    props?.category_en,
  ];
  const found = candidates.find(
    (c) => typeof c === "string" && c.trim().length > 0
  );
  return found ? String(found) : undefined;
}

function titleCase(s: string) {
  return s
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

/** Stable pseudo-random from a string so repeat clicks show identical numbers. */
function seeded(seed: string, min: number, max: number): number {
  let h = 2166136261;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const r = Math.abs(h % 10000) / 10000;
  return Math.round(min + r * (max - min));
}

/** Turn any rendered Mapbox feature into a selectable property object. */
export function featureToInfo(
  feature: any,
  lngLat: { lng: number; lat: number }
): BuildingInfo {
  const props = (feature?.properties || {}) as any;
  const layerId = String(feature?.layer?.id || "");
  const sourceLayer = String(feature?.sourceLayer || "");
  const cat = categoryFor(layerId, sourceLayer, props);

  const rawHeight = Number(
    props.height ?? props.trueHeight ?? props.render_height ?? 0
  );
  const baseHeight = Math.max(
    0,
    Number(props.min_height ?? props.base_height ?? props.render_min_height ?? 0)
  );
  const height = cat.isStructure
    ? rawHeight > baseHeight
      ? rawHeight
      : seeded(layerId + String(feature?.id ?? ""), 12, 48)
    : 0;

  const measuredArea = estimateAreaSqFt(feature?.geometry, lngLat.lat);
  const area =
    measuredArea > 0 ? measuredArea : seeded(sourceLayer + layerId, 900, 12000);

  const floors = cat.isStructure ? Math.max(1, Math.round(height / 3.2)) : 1;
  const flats = cat.isStructure
    ? floors * seeded(String(feature?.id ?? layerId), 2, 6)
    : 0;

  const classLabel = props.class || props.type;
  const name =
    nameFrom(props) ||
    `${cat.label}${classLabel ? ` · ${titleCase(String(classLabel))}` : ""}`;

  const address = [props.address, props.locality, props.place, props.district]
    .filter((v) => typeof v === "string" && v.trim())
    .join(", ");

  const id = String(
    props.ulpinId ??
      feature?.id ??
      `${layerId || "object"}-${lngLat.lng.toFixed(5)},${lngLat.lat.toFixed(5)}`
  );

  return {
    id,
    type: classLabel ? String(classLabel) : cat.key,
    name,
    category: cat.label,
    height,
    floors,
    flats,
    occupancy: cat.isStructure ? `${seeded(id, 62, 98)}%` : "N/A",
    energyRating: cat.isStructure ? ["A+", "A", "B", "C"][seeded(id, 0, 3)] : "—",
    area,
    lng: lngLat.lng,
    lat: lngLat.lat,
    address: address || undefined,
    dataSource: props.source
      ? String(props.source)
      : props.ulpinId
        ? "ULPIN Registry"
        : `Mapbox Standard · ${sourceLayer || layerId || "basemap"}`,
    isStructure: cat.isStructure,
    baseHeight,
    geometry: feature?.geometry
      ? {
          type: String(feature.geometry.type),
          coordinates: feature.geometry.coordinates,
        }
      : undefined,
    mapColor: typeof props.color === "string" ? props.color : undefined,
  };
}

/** Pick the most meaningful feature from a query result. */
export function pickBestFeature(features: any[]): any | null {
  if (!features?.length) return null;
  const scored = features.map((f, idx) => {
    const cat = categoryFor(
      String(f?.layer?.id || ""),
      String(f?.sourceLayer || ""),
      f?.properties || {}
    );
    const hasName = nameFrom(f?.properties || {}) ? 8 : 0;
    return { f, score: cat.priority + hasName - idx * 0.01 };
  });
  scored.sort((a, b) => b.score - a.score);
  return scored[0].f;
}
