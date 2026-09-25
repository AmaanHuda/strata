import React, { useEffect, useMemo, useRef, useState } from "react";
import Map, { Layer, MapRef, NavigationControl, Source } from "react-map-gl/mapbox";
import type { MapMouseEvent } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useAreaStore } from "@/state/areaStore";
import { BuildingSidebar, BuildingInfo } from "@/components/panels/BuildingSidebar";
import { featureToInfo, pickBestFeature } from "@/three/classifyFeature";
import {
  pointLookup,
  getBuildingStructure,
  getBuildingGeometry,
  getDataExtent,
  queryBBox,
} from "@/api/strataBackend";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN;

interface MapboxSpaceProps {
  isVisible: boolean;
}

export function MapboxSpace({ isVisible }: MapboxSpaceProps) {
  const mapRef = useRef<MapRef>(null);
  const center = useAreaStore((state) => state.center);
  const setAppStep = useAreaStore((state) => state.setAppStep);
  const setSelectedBuildingDetail = useAreaStore(
    (state) => state.setSelectedBuildingDetail
  );
  const setBackendBuildingStructure = useAreaStore(
    (state) => state.setBackendBuildingStructure
  );
  const setBackendBuildingGeometry = useAreaStore(
    (state) => state.setBackendBuildingGeometry
  );
  const setIsFetchingBackendBuilding = useAreaStore(
    (state) => state.setIsFetchingBackendBuilding
  );
  const setBackendLookupDone = useAreaStore(
    (state) => state.setBackendLookupDone
  );
  const setBackendFoundData = useAreaStore(
    (state) => state.setBackendFoundData
  );
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingInfo | null>(null);
  // Set when the currently selected entity is a real backend record, which is the
  // only case where we are allowed to draw our own 3D geometry over the basemap.
  const [isolatedBuilding, setIsolatedBuilding] = useState<{
    id: string;
    geometry: { type: string; coordinates: unknown };
    heightM: number;
    floors: number;
    label: string;
  } | null>(null);

  // Key of the area we have already framed, so the effect and onLoad cannot both
  // fly the camera while a genuinely new selection still re-frames it.
  const framedForRef = useRef<string | null>(null);

  /**
   * Frame the 3D camera on real data.
   *
   * The selection box is the user's area of interest, so if it actually contains
   * backend records we honour it. When it does not (or is the placeholder centre),
   * we frame the extent of the geometry really stored in PostGIS. Without this the
   * camera sat on a hard-coded city hundreds of metres from any record, so every
   * click resolved to "no backend record" even though the data existed.
   */
  const frameOnData = async () => {
    const map = mapRef.current?.getMap();
    if (!map) return;
    const key = JSON.stringify(center ?? null);
    if (framedForRef.current === key) return;
    framedForRef.current = key;

    map.setLight({
      anchor: "viewport",
      color: "#fdf6e3",
      intensity: 0.4,
      position: [1.15, 210, 30],
    });

    let bbox: [number, number, number, number] | null = null;

    // 1. Prefer the user's selected box, but only if the backend has records in it.
    if (center && center.length >= 2) {
      const lngs = center.map((c) => c.lng);
      const lats = center.map((c) => c.lat);
      const minLon = Math.min(...lngs);
      const maxLon = Math.max(...lngs);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      if ([minLon, maxLon, minLat, maxLat].every(Number.isFinite)) {
        const inBox = await queryBBox(minLon, minLat, maxLon, maxLat, "all", 1);
        if (inBox.length > 0) bbox = [minLon, minLat, maxLon, maxLat];
      }
    }

    // 2. Otherwise frame wherever the backend actually has data.
    if (!bbox) {
      const extent = await getDataExtent();
      if (extent?.has_data && extent.bbox) bbox = extent.bbox;
    }

    if (bbox) {
      map.fitBounds(
        [
          [bbox[0], bbox[1]],
          [bbox[2], bbox[3]],
        ],
        { padding: 90, maxZoom: 17.5, pitch: 60, bearing: -17, duration: 3500 }
      );
    } else if (center && center.length >= 2) {
      map.flyTo({
        center: [
          (center[0].lng + center[1].lng) / 2,
          (center[0].lat + center[1].lat) / 2,
        ],
        zoom: 16.5,
        pitch: 60,
        bearing: -17,
        duration: 3500,
      });
    }

    setSelectedBuilding(null);
  };

  // Set realistic lighting and frame the camera on real records.
  useEffect(() => {
    if (isVisible) void frameOnData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isVisible, center]);

  /**
   * On map click:
   * 1. Query Mapbox rendered features for geometry + base UI info.
   * 2. Query STRATA backend point lookup for the real building ID.
   * 3. If backend has a building at that point, fetch its real structure + geometry.
   * 4. All real data is stored in areaStore; fake fields are shown as "Not available".
   */
  const handleMapClick = async (e: MapMouseEvent) => {
    if (!mapRef.current) return;
    if (!Number.isFinite(e.point.x) || !Number.isFinite(e.point.y)) return;
    if (!Number.isFinite(e.lngLat.lng) || !Number.isFinite(e.lngLat.lat)) return;
    const map = mapRef.current.getMap();
    const lngLat = { lng: e.lngLat.lng, lat: e.lngLat.lat };

    // Query Mapbox rendered features for geometry
    const padding = 12;
    const bbox: [[number, number], [number, number]] = [
      [e.point.x - padding, e.point.y - padding],
      [e.point.x + padding, e.point.y + padding],
    ];
    const features = map.queryRenderedFeatures(bbox);
    const best = pickBestFeature(features as any[]);

    // Build a minimal BuildingInfo for immediate UI feedback (Mapbox data only)
    // Fields that require backend (flats, occupancy, energyRating) are set to sentinel "PENDING"
    // so BuildingSidebar/BuildingIsolateScene know to show "Not available" from backend
    const mapboxInfo: BuildingInfo = best
      ? featureToInfo(best, lngLat)
      : {
          id: `PARCEL-${lngLat.lng.toFixed(5)},${lngLat.lat.toFixed(5)}`,
          type: "parcel",
          name: "Land Parcel",
          category: "Land Parcel",
          height: 0,
          floors: 0,
          flats: 0,
          occupancy: "Not available",
          energyRating: "N/A",
          area: 0,
          lng: lngLat.lng,
          lat: lngLat.lat,
          dataSource: "Mapbox (preview only) — no backend record",
          isStructure: false,
          geometry: {
            type: "Polygon",
            coordinates: [[
              [lngLat.lng - 0.00004, lngLat.lat - 0.00004],
              [lngLat.lng + 0.00004, lngLat.lat - 0.00004],
              [lngLat.lng + 0.00004, lngLat.lat + 0.00004],
              [lngLat.lng - 0.00004, lngLat.lat + 0.00004],
              [lngLat.lng - 0.00004, lngLat.lat - 0.00004],
            ]],
          },
        };

    // Everything assembled above is Mapbox-derived. It is only relabelled
    // "STRATA Backend · PostGIS" once the backend returns an authoritative
    // record for this location — so the sidebar never claims Mapbox data is ours.
    mapboxInfo.dataSource = "Mapbox (preview only) — no backend record";

    // Clear previous backend data and reset lookup tracking flags
    setBackendBuildingStructure(null);
    setBackendBuildingGeometry(null);
    setBackendLookupDone(false);
    setBackendFoundData(false);

    // Show sidebar immediately with Mapbox info, then enrich with backend
    setSelectedBuildingDetail(mapboxInfo);
    setSelectedBuilding(mapboxInfo);
    setIsolatedBuilding(null);
    setAppStep(2);
    setIsFetchingBackendBuilding(true);

    try {
      // 1. Point lookup: find what the backend knows at this coordinate
      // 400 m tolerance: imported footprints are small relative to the map, so a
      // click just outside one should still resolve it (labelled "nearest match").
      const lookup = await pointLookup(lngLat.lat, lngLat.lng, 400);

      if (lookup?.building) {
        // Mark backend as having returned data before any async calls
        setBackendFoundData(true);
        const backendBuildingId = lookup.building.id;

        // 2. Fetch real structure (floors, units, ULPIN, ML provenance)
        const [structure, geometry] = await Promise.all([
          getBuildingStructure(backendBuildingId),
          getBuildingGeometry(backendBuildingId),
        ]);

        // 3. Store real backend data — UI will read from here
        setBackendBuildingStructure(structure);
        setBackendBuildingGeometry(geometry);

        // 4. Update BuildingInfo with real backend values where available
        const enriched: BuildingInfo = {
          ...mapboxInfo,
          // Use backend building ID as the canonical id
          id: backendBuildingId,
          name: structure?.building_name || lookup.building.identifier || mapboxInfo.name || "Building",
          height: geometry?.height_m ?? structure?.height_m ?? lookup.building.height_m ?? mapboxInfo.height,
          floors: structure?.floor_count ?? lookup.building.floor_count ?? mapboxInfo.floors,
          // Flats = total units from backend; 0 means genuinely 0 or unavailable
          flats: structure?.floors
            ? structure.floors.reduce((acc, f) => acc + f.units.length, 0)
            : (lookup.units_count ?? 0),
          // These fields have no real backend equivalent — show "Not available" in UI
          occupancy: "Not available",
          energyRating: "N/A",
          area: structure?.footprint_area_sqm
            ? Number(structure.footprint_area_sqm)
            : lookup.building.area_sqm
              ? Number(lookup.building.area_sqm)
              : mapboxInfo.area,
          // Use real geometry from backend if available, else keep Mapbox geometry
          geometry: (geometry?.footprint_geojson as { type: string; coordinates: unknown } | null)
            ?? (lookup.building.geometry_geojson as { type: string; coordinates: unknown } | null)
            ?? mapboxInfo.geometry,
          address: structure?.address ?? mapboxInfo.address,
          dataSource: (() => {
            const base = structure?.provenance?.ml_derived
              ? `STRATA Backend · ML v${structure.provenance.ml_model_version || "unknown"}`
              : "STRATA Backend · PostGIS";
            const how = lookup.building?.match_type;
            const away = lookup.building?.distance_m;
            if (how === "nearest") {
              return `${base} · nearest match${away != null ? ` (${away} m from click)` : ""}`;
            }
            return base;
          })(),
          isStructure: true,
          // Centroid from backend
          lat: geometry?.centroid?.lat ?? lookup.building.centroid?.lat ?? lngLat.lat,
          lng: geometry?.centroid?.lon ?? lookup.building.centroid?.lon ?? lngLat.lng,
        };

        setSelectedBuildingDetail(enriched);
        setSelectedBuilding(enriched);

        // 5. Isolate exactly this building in 3D using the REAL backend footprint.
        //    Only genuine PostGIS geometry is extruded here — never a synthesised
        //    box — and its height is the stored height. If the backend has no
        //    height, nothing is extruded (the sidebar states that instead).
        const realGeometry =
          (enriched.geometry as { type: string; coordinates: unknown } | null) ?? null;
        if (realGeometry?.coordinates && (enriched.floors ?? 0) > 0) {
          const geometry = realGeometry as { type: string; coordinates: unknown };
          const heightM = Number(enriched.height ?? 0) > 0 ? Number(enriched.height) : 0;
          if (heightM > 0) {
            setIsolatedBuilding({
              id: backendBuildingId,
              geometry,
              heightM,
              floors: Number(enriched.floors ?? 1),
              label: enriched.name ?? "Selected building",
            });
            const focus = lookup.building.centroid
              ?? (geometry.coordinates ? centroidOf(geometry.coordinates) : null);
            if (focus) {
              map.flyTo({
                center: [focus.lon, focus.lat],
                zoom: 18.2,
                pitch: 62,
                bearing: -22,
                duration: 1800,
              });
            }
          }
        }
      } else if (lookup?.parcel) {
        setIsolatedBuilding(null);
        // Parcel found but no building in backend at this point
        setBackendFoundData(true);
        const enrichedParcel: BuildingInfo = {
          ...mapboxInfo,
          id: lookup.parcel.id,
          name: lookup.parcel.identifier || "Land Parcel",
          category: "Land Parcel",
          type: "parcel",
          isStructure: false,
          floors: 0,
          flats: 0,
          height: 0,
          occupancy: "Not available",
          energyRating: "N/A",
          area: lookup.parcel.area_sqm ? Number(lookup.parcel.area_sqm) : mapboxInfo.area,
          geometry: (lookup.parcel.geometry_geojson as { type: string; coordinates: unknown } | null) ?? mapboxInfo.geometry,
          lat: lookup.parcel.centroid?.lat ?? lngLat.lat,
          lng: lookup.parcel.centroid?.lon ?? lngLat.lng,
          dataSource: "STRATA Backend · PostGIS",
        };
        setSelectedBuildingDetail(enrichedParcel);
        setSelectedBuilding(enrichedParcel);
        setBackendBuildingStructure(null);
        setBackendBuildingGeometry(null);
      }
      // lookup returned null or empty: backend has no spatial record at this point.
      // Keep Mapbox info but mark lookup as done with no data found.
    } catch {
      // Backend unreachable — keep Mapbox info, don't fabricate backend data
      setSelectedBuildingDetail({
        ...mapboxInfo,
        dataSource: "Mapbox (preview only) — backend unreachable",
      });
      setBackendBuildingStructure(null);
      setBackendBuildingGeometry(null);
    } finally {
      setIsFetchingBackendBuilding(false);
      setBackendLookupDone(true);
    }
  };

  /** Walk a (Multi)Polygon coordinate tree and return its centre point. */
  const centroidOf = (coordinates: unknown): { lat: number; lon: number } | null => {
    const points: [number, number][] = [];
    const walk = (value: unknown) => {
      if (!Array.isArray(value)) return;
      if (typeof value[0] === "number" && typeof value[1] === "number") {
        points.push([value[0] as number, value[1] as number]);
        return;
      }
      value.forEach(walk);
    };
    walk(coordinates);
    if (!points.length) return null;
    const lons = points.map((p) => p[0]);
    const lats = points.map((p) => p[1]);
    return {
      lon: (Math.min(...lons) + Math.max(...lons)) / 2,
      lat: (Math.min(...lats) + Math.max(...lats)) / 2,
    };
  };

  const handleMouseEnter = () => {
    if (mapRef.current) {
      mapRef.current.getMap().getCanvas().style.cursor = "pointer";
    }
  };

  const handleMouseLeave = () => {
    if (mapRef.current) {
      mapRef.current.getMap().getCanvas().style.cursor = "";
    }
  };

  /** GeoJSON for the isolated building only — real backend footprint. */
  const isolatedGeoJSON = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: isolatedBuilding
        ? [
            {
              type: "Feature" as const,
              properties: { label: isolatedBuilding.label },
              geometry: isolatedBuilding.geometry,
            },
          ]
        : [],
    }),
    [isolatedBuilding]
  );

  if (!MAPBOX_TOKEN) {
    return (
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#F8FAFC",
          color: "#BA1A1A",
          zIndex: 0,
          padding: "2rem",
          textAlign: "center",
          flexDirection: "column",
        }}
      >
        <h2>Missing Mapbox Token</h2>
        <p>
          Please add <b>VITE_MAPBOX_TOKEN</b> to your .env file to view the 3D Map.
        </p>
      </div>
    );
  }

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        zIndex: 0,
        opacity: isVisible ? 1 : 0.0,
        pointerEvents: isVisible ? "auto" : "none",
        transition: "opacity 0.8s ease-in-out",
      }}
    >
      <Map
        ref={mapRef}
        mapboxAccessToken={MAPBOX_TOKEN}
        initialViewState={{
          longitude: 77.209,
          latitude: 28.6139,
          zoom: 16,
          pitch: 60,
          bearing: -17,
        }}
        mapStyle="mapbox://styles/mapbox/standard"
        onClick={(e) => void handleMapClick(e)}
        terrain={{ source: "mapbox-dem", exaggeration: 1.5 }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onLoad={(e) => {
          const map = e.target;
          if (map.setConfigProperty) {
            map.setConfigProperty("basemap", "lightPreset", "dusk");
            map.setConfigProperty("basemap", "showPointOfInterestLabels", true);
            map.setConfigProperty("basemap", "showTransitLabels", true);
          }
          void frameOnData();
        }}
      >
        {/* Terrain DEM source — standard Mapbox 3D terrain */}
        <Source
          id="mapbox-dem"
          type="raster-dem"
          url="mapbox://mapbox.mapbox-terrain-dem-v1"
          tileSize={512}
          maxzoom={14}
        />
        {/*
          NOTE: The Mapbox Standard style already renders 3D buildings from OSM.
          We do NOT add custom ULPIN GeoJSON overlays here because that would be
          fabricated data. Real building geometry comes from the backend after a
          click and is rendered in BuildingIsolateScene via IsolatedMapboxObject.
        */}
        {/*
          3D isolation of the selected backend record.
          This is REAL PostGIS geometry (the stored footprint) extruded to the
          stored height, drawn above the basemap's own generic extrusions so the
          selected property is unmistakable. When the backend has no record (or no
          height) this source is empty and nothing is drawn — we never invent a
          block to highlight.
        */}
        {isolatedBuilding && (
          <Source id="strata-isolated-building" type="geojson" data={isolatedGeoJSON as any}>
            <Layer
              id="strata-isolated-building-extrusion"
              type="fill-extrusion"
              slot="top"
              paint={{
                "fill-extrusion-color": "#F59E0B",
                "fill-extrusion-height": isolatedBuilding.heightM,
                "fill-extrusion-base": 0,
                "fill-extrusion-opacity": 0.92,
                "fill-extrusion-vertical-gradient": true,
              }}
            />
            <Layer
              id="strata-isolated-building-outline"
              type="line"
              slot="top"
              paint={{ "line-color": "#B45309", "line-width": 2.5 }}
            />
          </Source>
        )}

        <NavigationControl position="bottom-right" visualizePitch={true} />
      </Map>

      <BuildingSidebar
        info={selectedBuilding}
        onClose={() => {
          setSelectedBuilding(null);
          setSelectedBuildingDetail(null);
          setBackendBuildingStructure(null);
          setBackendBuildingGeometry(null);
          setIsolatedBuilding(null);
          setAppStep(1);
        }}
      />

      {/* Isolation badge — makes it explicit that the amber block is a real record. */}
      {isolatedBuilding && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            transform: "translateX(-50%)",
            bottom: "1.5rem",
            background: "rgba(255,255,255,0.96)",
            border: "2px solid #0F172A",
            boxShadow: "2px 2px 0px #0F172A",
            borderRadius: "12px",
            padding: "0.5rem 0.85rem",
            fontSize: "12px",
            fontWeight: 800,
            color: "#0F172A",
            zIndex: 10,
            pointerEvents: "none",
            maxWidth: "80%",
          }}
        >
          3D isolation · {isolatedBuilding.label} · {isolatedBuilding.heightM.toFixed(1)} m ·{" "}
          {isolatedBuilding.floors} floors · real PostGIS record
        </div>
      )}
    </div>
  );
}
