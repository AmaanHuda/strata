import React, { useEffect, useRef, useState } from "react";
import Map, { MapRef, NavigationControl, Source } from "react-map-gl/mapbox";
import type { MapMouseEvent } from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { useAreaStore } from "@/state/areaStore";
import { BuildingSidebar, BuildingInfo } from "@/components/panels/BuildingSidebar";
import { featureToInfo, pickBestFeature } from "@/three/classifyFeature";
import {
  pointLookup,
  getBuildingStructure,
  getBuildingGeometry,
} from "@/api/strataBackend";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

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
  const [selectedBuilding, setSelectedBuilding] = useState<BuildingInfo | null>(null);

  // Set Realistic Lighting and Fly to location
  useEffect(() => {
    if (isVisible && mapRef.current) {
      const map = mapRef.current.getMap();

      // Dynamic lighting for realistic shadows
      map.setLight({
        anchor: "viewport",
        color: "#fdf6e3",
        intensity: 0.4,
        position: [1.15, 210, 30],
      });

      if (center && center.length >= 2) {
        const lngCenter = (center[0].lng + center[1].lng) / 2;
        const latCenter = (center[0].lat + center[1].lat) / 2;

        map.flyTo({
          center: [lngCenter, latCenter],
          zoom: 16.5,
          pitch: 60,
          bearing: -17,
          duration: 3500,
        });

        setSelectedBuilding(null);
      }
    }
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
          dataSource: "STRATA Backend",
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

    // Clear previous backend data
    setBackendBuildingStructure(null);
    setBackendBuildingGeometry(null);

    // Show sidebar immediately with Mapbox info, then enrich with backend
    setSelectedBuildingDetail(mapboxInfo);
    setSelectedBuilding(mapboxInfo);
    setAppStep(2);
    setIsFetchingBackendBuilding(true);

    try {
      // 1. Point lookup: find what the backend knows at this coordinate
      const lookup = await pointLookup(lngLat.lat, lngLat.lng);

      if (lookup?.building) {
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
          name: structure?.building_name || mapboxInfo.name || "Building",
          height: geometry?.height_m ?? structure?.height_m ?? mapboxInfo.height,
          floors: structure?.floor_count ?? mapboxInfo.floors,
          // Flats = total units from backend; 0 means genuinely 0 or unavailable
          flats: structure?.floors.reduce((acc, f) => acc + f.units.length, 0) ?? 0,
          // These fields have no real backend equivalent — show "Not available" in UI
          occupancy: "Not available",
          energyRating: "N/A",
          area: geometry?.bounds
            ? 0  // area will be read from structure.footprint_area_sqm in sidebar
            : mapboxInfo.area,
          // Use real geometry from backend if available, else keep Mapbox geometry
          geometry: (geometry?.footprint_geojson as { type: string; coordinates: unknown } | null)
            ?? mapboxInfo.geometry,
          address: structure?.address ?? mapboxInfo.address,
          dataSource: structure?.provenance?.ml_derived
            ? `STRATA Backend · ML v${structure.provenance.ml_model_version || "unknown"}`
            : "STRATA Backend · PostGIS",
          isStructure: true,
          // Centroid from backend
          lat: geometry?.centroid?.lat ?? lngLat.lat,
          lng: geometry?.centroid?.lon ?? lngLat.lng,
        };

        setSelectedBuildingDetail(enriched);
        setSelectedBuilding(enriched);
      } else if (lookup?.parcel) {
        // Parcel found but no building in backend at this point
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
          dataSource: "STRATA Backend · PostGIS",
        };
        setSelectedBuildingDetail(enrichedParcel);
        setSelectedBuilding(enrichedParcel);
        setBackendBuildingStructure(null);
        setBackendBuildingGeometry(null);
      }
      // If lookup returns nothing: backend has no data at this point, keep Mapbox info
    } catch {
      // Backend unreachable — keep Mapbox info, don't fabricate backend data
      setBackendBuildingStructure(null);
      setBackendBuildingGeometry(null);
    } finally {
      setIsFetchingBackendBuilding(false);
    }
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
          if (center && center.length >= 2) {
            const lngCenter = (center[0].lng + center[1].lng) / 2;
            const latCenter = (center[0].lat + center[1].lat) / 2;
            if (Number.isFinite(lngCenter) && Number.isFinite(latCenter)) {
              map.jumpTo({
                center: [lngCenter, latCenter],
                zoom: 16.5,
                pitch: 60,
                bearing: -17,
              });
            }
          }
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
        <NavigationControl position="bottom-right" visualizePitch={true} />
      </Map>

      <BuildingSidebar
        info={selectedBuilding}
        onClose={() => {
          setSelectedBuilding(null);
          setSelectedBuildingDetail(null);
          setBackendBuildingStructure(null);
          setBackendBuildingGeometry(null);
          setAppStep(1);
        }}
      />
    </div>
  );
}
