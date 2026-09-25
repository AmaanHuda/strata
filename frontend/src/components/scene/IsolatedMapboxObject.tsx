import { useEffect, useMemo, useRef, useState } from "react";
import Map, { Layer, MapRef, Source } from "react-map-gl/mapbox";
import type { BuildingInfo } from "@/components/panels/BuildingSidebar";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

type IsolatedFloorRef = {
  id: string;
  floor_number: number;
  label?: string | null;
};

type IsolatedMapboxObjectProps = {
  info: BuildingInfo;
  extractedFloor: number;
  /** Real backend floors, ordered bottom-up, so a clicked extrusion maps to a floor id. */
  floors?: IsolatedFloorRef[];
  /** Index into `floors` of the currently selected floor (-1 for none). */
  selectedFloorIndex?: number;
  /** Called with the clicked floor id, or null when empty space is clicked. */
  onSelectFloor?: (floorId: string | null) => void;
};

function collectCoordinates(value: unknown, output: [number, number][]) {
  if (!Array.isArray(value)) return;
  if (
    value.length >= 2 &&
    typeof value[0] === "number" &&
    typeof value[1] === "number" &&
    Number.isFinite(value[0]) &&
    Number.isFinite(value[1])
  ) {
    output.push([value[0], value[1]]);
    return;
  }
  value.forEach((item) => collectCoordinates(item, output));
}

function getBounds(geometry: BuildingInfo["geometry"]) {
  const coordinates: [number, number][] = [];
  collectCoordinates(geometry?.coordinates, coordinates);
  if (!coordinates.length) return null;

  let minLng = coordinates[0][0];
  let minLat = coordinates[0][1];
  let maxLng = minLng;
  let maxLat = minLat;
  coordinates.forEach(([lng, lat]) => {
    minLng = Math.min(minLng, lng);
    minLat = Math.min(minLat, lat);
    maxLng = Math.max(maxLng, lng);
    maxLat = Math.max(maxLat, lat);
  });
  return [[minLng, minLat], [maxLng, maxLat]] as [[number, number], [number, number]];
}

export function IsolatedMapboxObject({
  info,
  extractedFloor,
  floors,
  selectedFloorIndex = -1,
  onSelectFloor,
}: IsolatedMapboxObjectProps) {
  const mapRef = useRef<MapRef>(null);
  const [isModelReady, setIsModelReady] = useState(false);
  const validLng = typeof info.lng === "number" && Number.isFinite(info.lng);
  const validLat = typeof info.lat === "number" && Number.isFinite(info.lat);
  const hasExtrudableGeometry =
    info.geometry?.type === "Polygon" || info.geometry?.type === "MultiPolygon";
  const bounds = useMemo(
    () => hasExtrudableGeometry ? getBounds(info.geometry) : null,
    [hasExtrudableGeometry, info.geometry]
  );
  const center = bounds
    ? {
        longitude: (bounds[0][0] + bounds[1][0]) / 2,
        latitude: (bounds[0][1] + bounds[1][1]) / 2,
      }
    : {
        longitude: validLng ? info.lng as number : 77.209,
        latitude: validLat ? info.lat as number : 28.6139,
      };

  const floorCount = info.isStructure === false ? 1 : Math.max(1, info.floors);
  const objectHeight = info.isStructure === false ? 0.6 : Math.max(3, info.height);
  const floorHeight = objectHeight / floorCount;
  const extractionGap = 2.5;
  const geojson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: hasExtrudableGeometry && info.geometry
        ? [{ type: "Feature" as const, properties: {}, geometry: info.geometry }]
        : [],
    }),
    [hasExtrudableGeometry, info.geometry]
  );

  useEffect(() => {
    const map = mapRef.current?.getMap();
    if (!map || !bounds) return;
    map.fitBounds(bounds, {
      padding: 150,
      pitch: 64,
      bearing: -25,
      duration: 700,
      maxZoom: 19.5,
    });
  }, [bounds, info.id]);

  if (!MAPBOX_TOKEN || !hasExtrudableGeometry || !bounds) {
    return (
      <div className="map-object-unavailable">
        Mapbox did not provide an extrudable footprint for this object.
      </div>
    );
  }

  return (
    <div style={{ position: "relative", width: "100%", height: "100%" }}>
      <Map
      key={info.id}
      ref={mapRef}
      mapboxAccessToken={MAPBOX_TOKEN}
      initialViewState={{
        ...center,
        zoom: 18,
        pitch: 64,
        bearing: -25,
      }}
      mapStyle="mapbox://styles/mapbox/standard"
      style={{ width: "100%", height: "100%" }}
      terrain={{ source: "isolate-dem", exaggeration: 1 }}
      onClick={(event) => {
        if (!onSelectFloor) return;
        const map = mapRef.current?.getMap();
        if (!map) return;
        // Query by prefix rather than by layer name: asking for a layer that has
        // not been created yet would throw. This keeps the fallback safe.
        const hits = map.queryRenderedFeatures(event.point);
        const hit = hits.find((f) => String(f.layer?.id || "").startsWith("selected-floor-"));
        if (!hit) {
          onSelectFloor(null);
          return;
        }
        const match = String(hit.layer?.id || "").match(/selected-floor-(\d+)/);
        const index = match ? Number(match[1]) : -1;
        const floor = index >= 0 ? floors?.[index] : undefined;
        // No backend floor at that index (e.g. floors are unknown) -> clear instead
        // of inventing an identifier.
        onSelectFloor(floor ? floor.id : null);
      }}
      minPitch={20}
      maxPitch={85}
      attributionControl={false}
      onSourceData={(event) => {
        if (
          event.sourceId === "selected-mapbox-object" &&
          event.isSourceLoaded
        ) {
          setIsModelReady(true);
        }
      }}
      onLoad={(event) => {
        const map = event.target;
        if (map.setConfigProperty) {
          map.setConfigProperty("basemap", "lightPreset", "dusk");
          map.setConfigProperty("basemap", "show3dObjects", false);
          map.setConfigProperty("basemap", "showPointOfInterestLabels", false);
          map.setConfigProperty("basemap", "showTransitLabels", false);
        }
        if (bounds) {
          map.fitBounds(bounds, {
            padding: 150,
            pitch: 64,
            bearing: -25,
            duration: 0,
            maxZoom: 19.5,
          });
        }
      }}
    >
      <Source
        id="isolate-dem"
        type="raster-dem"
        url="mapbox://mapbox.mapbox-terrain-dem-v1"
        tileSize={512}
        maxzoom={14}
      />
      <Source id="selected-mapbox-object" type="geojson" data={geojson}>
        {Array.from({ length: floorCount }, (_, index) => {
          const firstExtractedFloor = floorCount - extractedFloor;
          const isExtracted = extractedFloor > 0 && index >= firstExtractedFloor;
          const isSelected = index === selectedFloorIndex;
          // Smooth, additive lift: extracted floors keep their gap, and the clicked
          // floor is nudged out so it stays part of the building but is isolated.
          const lifted = isExtracted
            ? (index - firstExtractedFloor + 1) * extractionGap
            : isSelected
              ? 1.5
              : 0;
          const base = index * floorHeight + lifted;
          return (
            <Layer
              key={`${info.id}-floor-${index}`}
              id={`selected-floor-${index}`}
              type="fill-extrusion"
              slot="top"
              paint={{
                "fill-extrusion-color": isSelected
                  ? "#F59E0B"
                  : isExtracted
                    ? "#93C5FD"
                    : info.mapColor || "#CBD5E1",
                "fill-extrusion-base": base,
                "fill-extrusion-height": base + Math.max(0.12, floorHeight - 0.08),
                "fill-extrusion-opacity": isSelected ? 1 : 0.9,
                "fill-extrusion-vertical-gradient": true,
              }}
            />
          );
        })}
      </Source>
      </Map>
      {!isModelReady ? (
        <div className="map-object-loading">Loading building model...</div>
      ) : null}
    </div>
  );
}