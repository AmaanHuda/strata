import React, { useEffect, useRef, useState, useCallback } from "react";
import Map, { MapRef, Source, Layer } from "react-map-gl/mapbox";
import { css } from "@emotion/react";
import { Hand, SquareMousePointer, Trash2 } from "lucide-react";
import "mapbox-gl/dist/mapbox-gl.css";
import { INK, TEXT_PRIMARY } from "@/theme/color";
import {
  queryBBox,
  getDataExtent,
  ingestLocation,
  type SpatialEntityItem,
} from "@/api/strataBackend";

/** Approximate metres per degree of longitude at a given latitude. */
function metresPerDegree(lat: number) {
  const latRad = (lat * Math.PI) / 180;
  return { lon: 111320 * Math.cos(latRad), lat: 110540 };
}

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

const IconSize = css({
  width: "14px",
  height: "14px",
});

function SelectBox() {
  return (
    <>
      <SquareMousePointer css={IconSize} />
    </>
  );
}

export function MapComponent({
  onRemove,
  onDone,
  flyTarget,
  resetKey,
  bare = false,
}: {
  onDone: (e: { lat: number; lng: number }[]) => void;
  onRemove: () => void;
  flyTarget: { lat: number; lng: number } | null;
  resetKey?: number;
  bare?: boolean;
}) {
  const mapRef = useRef<MapRef>(null);
  
  const [isDrag, setIsDrag] = useState(true);
  const [startPoint, setStartPoint] = useState<{lat: number, lng: number} | null>(null);
  const [endPoint, setEndPoint] = useState<{lat: number, lng: number} | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [center, setCenter] = useState<{ lat: number; lng: number }>({ lat: 18.9220, lng: 72.8347 });

  // On-demand ingestion controls (real OpenStreetMap source data).
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestMessage, setIngestMessage] = useState<string | null>(null);
  const [ingestError, setIngestError] = useState(false);
  // Cadastral context is operator-supplied: the ULPIN code segments come from
  // real administrative names, and OSM usually carries no addr:state tag.
  const [ingestState, setIngestState] = useState("");
  const [ingestDistrict, setIngestDistrict] = useState("");

  // Real geometry pulled from the backend for the current viewport.
  const [backendFeatures, setBackendFeatures] = useState<any | null>(null);
  const [backendCount, setBackendCount] = useState(0);
  const [backendLoaded, setBackendLoaded] = useState(false);
  // Mapbox must finish loading before fitBounds / getBounds mean anything.
  // Calling them on mount silently used the stale default viewport (a city
  // centre unrelated to the data), which is why the map opened on empty ground.
  const [mapReady, setMapReady] = useState(false);

  /**
   * Load the real parcels/buildings for the viewport from PostGIS and draw them.
   * Without this the map is just a basemap, so there is no way to see where the
   * backend's data actually is before drawing a box over empty ground.
   */
  const loadBackendData = useCallback(async () => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const bounds = map.getBounds();
    if (!bounds) return;

    const items = await queryBBox(
      bounds.getWest(),
      bounds.getSouth(),
      bounds.getEast(),
      bounds.getNorth(),
      "all",
      200
    );
    setBackendCount(items.length);

    const features = items
      .filter((i: SpatialEntityItem) => Boolean(i.geometry_geojson))
      .map((i: SpatialEntityItem) => ({
        type: "Feature" as const,
        properties: {
          id: i.id,
          kind: i.entity_type,
          name: i.identifier,
          ulpin: i.candidate_ulpin || i.official_ulpin || null,
          height_m: i.height_m ?? null,
          floor_count: i.floor_count ?? null,
          area_sqm: i.area_sqm ?? null,
        },
        geometry: i.geometry_geojson,
      }));

    setBackendFeatures({ type: "FeatureCollection", features });
    setBackendLoaded(true);
  }, []);

  // Open on the extent of the data that actually exists, then draw it.
  useEffect(() => {
    if (!mapReady) return;
    let cancelled = false;
    void (async () => {
      const extent = await getDataExtent();
      if (cancelled) return;
      if (extent?.has_data && extent.bbox && mapRef.current) {
        const [minLon, minLat, maxLon, maxLat] = extent.bbox;
        mapRef.current.fitBounds(
          [
            [minLon, minLat],
            [maxLon, maxLat],
          ],
          { padding: 70, maxZoom: 16, duration: 0 }
        );
      }
      await loadBackendData();
    })();
    return () => {
      cancelled = true;
    };
  }, [mapReady, loadBackendData]);

  /**
   * Fetch real OSM footprints for the drawn box (or the current map centre) and
   * reload the drawn backend layer. Nothing is fabricated: if OpenStreetMap has
   * no building there, the message says so and the database stays unchanged.
   */
  const handleIngest = useCallback(async () => {
    let target = center;
    let radiusM = 300;
    if (startPoint && endPoint) {
      const lat = (startPoint.lat + endPoint.lat) / 2;
      const lng = (startPoint.lng + endPoint.lng) / 2;
      const perDeg = metresPerDegree(lat);
      const widthM = Math.abs(endPoint.lng - startPoint.lng) * perDeg.lon;
      const heightM = Math.abs(endPoint.lat - startPoint.lat) * perDeg.lat;
      // Cover the drawn area, clamped to the API's accepted 10 m - 2000 m range.
      radiusM = Math.min(2000, Math.max(10, Math.round(Math.max(widthM, heightM) / 2)));
      target = { lat, lng };
    }

    setIsIngesting(true);
    setIngestError(false);
    setIngestMessage("Fetching real footprints from OpenStreetMap…");
    try {
      const result = await ingestLocation({
        lat: target.lat,
        lon: target.lng,
        radiusM,
        state: ingestState.trim() || undefined,
        district: ingestDistrict.trim() || undefined,
        maxBuildings: 10,
      });
      if (!result) {
        setIngestError(true);
        setIngestMessage("Ingestion failed. See the console for the backend response.");
        return;
      }
      if (result.buildings_ingested === 0) {
        setIngestError(true);
        setIngestMessage(
          result.skipped_reasons[0]
            ?? `OpenStreetMap returned ${result.buildings_found} footprint(s); nothing new was stored.`
        );
        return;
      }
      const source = result.buildings[0];
      const provenanceBits = [
        source?.height_source ? `height: ${source.height_source}` : null,
        source?.floor_source ? `floors: ${source.floor_source}` : null,
        source?.ml_used ? `ML ${source.ml_model_version ?? ""}`.trim() : "no ML",
      ].filter(Boolean);
      setIngestMessage(
        `Stored ${result.buildings_ingested} real record(s) · ${result.floors_created} floors · ` +
          `${result.units_created} candidate units · e.g. ${
            result.candidate_ulpins[0] ?? "no candidate ULPIN"
          } (NON-AUTHORITATIVE) · ${provenanceBits.join(" · ")}`
      );
      await loadBackendData();
    } finally {
      setIsIngesting(false);
    }
  }, [center, startPoint, endPoint, ingestState, ingestDistrict, loadBackendData]);

  const handleClickSwitchDrag = () => {
    setIsDrag(!isDrag);
  };

  const handleClickRemoveBox = () => {
    onRemove();
    setStartPoint(null);
    setEndPoint(null);
    setIsDrag(true);
  };

  useEffect(() => {
    if (typeof resetKey !== "undefined") {
      setStartPoint(null);
      setEndPoint(null);
      setIsDrag(true);
    }
  }, [resetKey]);

  useEffect(() => {
    if (flyTarget && mapRef.current) {
      mapRef.current.flyTo({
        center: [flyTarget.lng, flyTarget.lat],
        zoom: 12,
        duration: 1500
      });
    }
  }, [flyTarget]);

  const onMouseDown = useCallback((e: any) => {
    if (isDrag) return;
    setIsDrawing(true);
    setStartPoint({ lat: e.lngLat.lat, lng: e.lngLat.lng });
    setEndPoint({ lat: e.lngLat.lat, lng: e.lngLat.lng });
  }, [isDrag]);

  const onMouseMove = useCallback((e: any) => {
    if (!isDrawing || isDrag) return;
    setEndPoint({ lat: e.lngLat.lat, lng: e.lngLat.lng });
  }, [isDrawing, isDrag]);

  const onMouseUp = useCallback((e: any) => {
    if (!isDrawing || isDrag) return;
    setIsDrawing(false);
    
    if (startPoint && endPoint) {
      const ne = {
        lat: Math.max(startPoint.lat, endPoint.lat),
        lng: Math.max(startPoint.lng, endPoint.lng)
      };
      const sw = {
        lat: Math.min(startPoint.lat, endPoint.lat),
        lng: Math.min(startPoint.lng, endPoint.lng)
      };
      onDone([ne, sw]);
    }
  }, [isDrawing, isDrag, startPoint, endPoint, onDone]);

  const onMove = useCallback((e: any) => {
    setCenter({ lat: e.viewState.latitude, lng: e.viewState.longitude });
  }, []);

  const geoJsonData = React.useMemo(() => {
    if (!startPoint || !endPoint) return null;
    
    const minLng = Math.min(startPoint.lng, endPoint.lng);
    const maxLng = Math.max(startPoint.lng, endPoint.lng);
    const minLat = Math.min(startPoint.lat, endPoint.lat);
    const maxLat = Math.max(startPoint.lat, endPoint.lat);

    return {
      type: "FeatureCollection",
      features: [
        {
          type: "Feature",
          properties: {},
          geometry: {
            type: "Polygon",
            coordinates: [
              [
                [minLng, minLat],
                [maxLng, minLat],
                [maxLng, maxLat],
                [minLng, maxLat],
                [minLng, minLat],
              ]
            ]
          }
        }
      ]
    };
  }, [startPoint, endPoint]);

  return (
    <div
      css={css({
        position: "relative",
        borderRadius: bare ? "0" : "18px",
        overflow: "hidden",
        border: bare ? "none" : `3px solid ${INK}`,
        boxShadow: bare ? "none" : "6px 6px 0px #0F172A",
        background: "#FFFFFF",
      })}
    >
      <div
        css={css({
          position: "absolute",
          zIndex: 9,
          right: "1rem",
          top: "1rem",
          display: "flex",
          justifyContent: "flex-end",
          gap: "0.5rem",
          flexWrap: "wrap",
        })}
      >
        <button
          css={css({
            color: "#ffffff",
            backgroundColor: isIngesting ? "#64748B" : "#047857",
            border: `2px solid ${INK}`,
            padding: "0.6rem 0.95rem",
            borderRadius: "12px",
            cursor: isIngesting ? "wait" : "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            fontWeight: 800,
            fontSize: "12px",
            boxShadow: "2px 2px 0px #0F172A",
            ":hover": { transform: "translate(-1px, -1px)", boxShadow: "3px 3px 0px #0F172A" },
            ":active": { transform: "translate(2px, 2px)", boxShadow: "0px 0px 0px #0F172A" },
          })}
          disabled={isIngesting}
          onClick={() => void handleIngest()}
          title="Fetch real building footprints from OpenStreetMap for this area and store them as CANDIDATE records"
        >
          {isIngesting ? "Fetching real data…" : "Fetch real data here"}
        </button>

        <button
          css={css({
            display: (startPoint == null) || isDrag ? "none" : "inline-flex",
            color: "#ffffff",
            backgroundColor: "#BA1A1A",
            border: `2px solid ${INK}`,
            padding: "0.6rem 0.95rem",
            borderRadius: "12px",
            cursor: "pointer",
            transition:
              "transform 0.16s ease, box-shadow 0.16s ease, background-color 0.16s ease",
            alignItems: "center",
            gap: "0.5rem",
            fontWeight: 700,
            fontSize: "12px",
            boxShadow: "2px 2px 0px #0F172A",
            ":hover": {
              backgroundColor: "#93000A",
              transform: "translate(-1px, -1px)",
              boxShadow: "3px 3px 0px #0F172A",
            },
            ":active": {
              transform: "translate(2px, 2px)",
              boxShadow: "0px 0px 0px #0F172A",
            },
          })}
          onClick={handleClickRemoveBox}
        >
          <Trash2 css={IconSize} /> Remove Box
        </button>

        <button
          css={css({
            color: isDrag ? "#ffffff" : TEXT_PRIMARY,
            backgroundColor: isDrag ? "#2563EB" : "#FFFFFF",
            border: `2px solid ${INK}`,
            padding: "0.6rem 0.95rem",
            borderRadius: "12px",
            cursor: "pointer",
            transition:
              "transform 0.16s ease, box-shadow 0.16s ease, background-color 0.16s ease",
            display: "inline-flex",
            alignItems: "center",
            gap: "0.5rem",
            fontWeight: 800,
            fontSize: "12px",
            boxShadow: "2px 2px 0px #0F172A",
            ":hover": {
              transform: "translate(-1px, -1px)",
              boxShadow: "3px 3px 0px #0F172A",
            },
            ":active": {
              transform: "translate(2px, 2px)",
              boxShadow: "0px 0px 0px #0F172A",
            },
          })}
          onClick={handleClickSwitchDrag}
        >
          {isDrag ? <SelectBox /> : <Hand css={IconSize} />}
          <span>{isDrag ? "Draw Box" : "Back to Drag"}</span>
        </button>
      </div>

      <div style={{ height: "60vh", minHeight: "400px", width: "100%" }}>
        <Map
          ref={mapRef}
          mapboxAccessToken={MAPBOX_TOKEN}
          initialViewState={{
            longitude: 72.8347,
            latitude: 18.9220,
            zoom: 12
          }}
          mapStyle="mapbox://styles/mapbox/streets-v12"
          dragPan={isDrag}
          onLoad={() => setMapReady(true)}
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMove={onMove}
          onMoveEnd={loadBackendData}
          interactiveLayerIds={[]}
          cursor={isDrag ? "grab" : "crosshair"}
        >
          {backendFeatures && (
            <Source id="strata-backend" type="geojson" data={backendFeatures}>
              <Layer
                id="strata-backend-parcels-line"
                type="line"
                filter={["==", ["get", "kind"], "parcel"]}
                paint={{
                  "line-color": "rgba(37, 99, 235, 0.9)",
                  "line-width": 1.8,
                  "line-dasharray": [2, 1.5],
                }}
              />
              <Layer
                id="strata-backend-buildings-fill"
                type="fill"
                filter={["==", ["get", "kind"], "building"]}
                paint={{
                  "fill-color": "rgba(16, 185, 129, 0.38)",
                  "fill-outline-color": "rgba(5, 150, 105, 0.95)",
                }}
              />
              <Layer
                id="strata-backend-buildings-line"
                type="line"
                filter={["==", ["get", "kind"], "building"]}
                paint={{ "line-color": "rgba(5, 150, 105, 1)", "line-width": 2 }}
              />
            </Source>
          )}

          {geoJsonData && (
            <Source type="geojson" data={geoJsonData as any}>
              <Layer
                id="selection-box-fill"
                type="fill"
                paint={{
                  "fill-color": "rgba(37, 99, 235, 0.14)",
                }}
              />
              <Layer
                id="selection-box-line"
                type="line"
                paint={{
                  "line-color": "rgba(37, 99, 235, 0.95)",
                  "line-width": 2.5,
                }}
              />
            </Source>
          )}
        </Map>
      </div>

      {/* Backend data indicator — proves whether real records are in view */}
      <div
        css={css({
          position: "absolute",
          zIndex: 9,
          left: "1rem",
          top: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "0.4rem",
          maxWidth: "60%",
        })}
      >
        <div
          css={css({
            background: "rgba(255, 255, 255, 0.96)",
            border: `2px solid ${INK}`,
            boxShadow: "2px 2px 0px #0F172A",
            padding: "0.4rem 0.7rem",
            borderRadius: "10px",
            fontSize: "0.72rem",
            fontWeight: 800,
            color: backendCount > 0 ? "#047857" : TEXT_PRIMARY,
            pointerEvents: "none",
            width: "fit-content",
          })}
        >
          {backendLoaded
            ? `${backendCount} backend record${backendCount === 1 ? "" : "s"} in view`
            : "Loading backend data…"}
        </div>

        {/* Optional cadastral context: the ULPIN code segments come from these
            real administrative names. OSM rarely carries addr:state. */}
        <div
          css={css({
            display: "flex",
            gap: "0.3rem",
            background: "rgba(255, 255, 255, 0.96)",
            border: `2px solid ${INK}`,
            boxShadow: "2px 2px 0px #0F172A",
            padding: "0.3rem 0.4rem",
            borderRadius: "10px",
            width: "fit-content",
          })}
        >
          <input
            value={ingestState}
            onChange={(e) => setIngestState(e.target.value)}
            placeholder="State (e.g. Maharashtra)"
            css={css({
              border: "1.5px solid #CBD5E1",
              borderRadius: "7px",
              padding: "0.28rem 0.45rem",
              fontSize: "0.7rem",
              fontWeight: 700,
              width: "150px",
              outline: "none",
            })}
          />
          <input
            value={ingestDistrict}
            onChange={(e) => setIngestDistrict(e.target.value)}
            placeholder="District (e.g. Mumbai)"
            css={css({
              border: "1.5px solid #CBD5E1",
              borderRadius: "7px",
              padding: "0.28rem 0.45rem",
              fontSize: "0.7rem",
              fontWeight: 700,
              width: "140px",
              outline: "none",
            })}
          />
        </div>

        {ingestMessage ? (
          <div
            css={css({
              background: ingestError ? "#FEF2F2" : "#ECFDF5",
              border: `2px solid ${ingestError ? "#FCA5A5" : "#6EE7B7"}`,
              color: ingestError ? "#991B1B" : "#065F46",
              borderRadius: "10px",
              padding: "0.4rem 0.7rem",
              fontSize: "0.7rem",
              fontWeight: 700,
              lineHeight: 1.45,
              maxWidth: "420px",
            })}
          >
            {ingestMessage}
          </div>
        ) : null}
      </div>

      <div
        css={css({
          position: "absolute",
          zIndex: 9,
          left: "1rem",
          bottom: "1rem",
          background: "rgba(255, 255, 255, 0.95)",
          border: `2px solid ${INK}`,
          boxShadow: "2px 2px 0px #0F172A",
          padding: "0.4rem 0.7rem",
          borderRadius: "10px",
          fontSize: "0.75rem",
          fontWeight: 700,
          fontFamily: "monospace",
          color: TEXT_PRIMARY,
          pointerEvents: "none",
        })}
      >
        {center.lat.toFixed(5)}, {center.lng.toFixed(5)}
      </div>
    </div>
  );
}
