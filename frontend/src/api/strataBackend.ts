/**
 * STRATA Backend API client.
 * All property/spatial/building/ULPIN data MUST come from this client only.
 * No mock data. No fabricated values. No Supabase for property records.
 */
import axios from "axios";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";

export const strataApi = axios.create({
  baseURL: `${BACKEND_URL}/api/v1`,
  timeout: 15000,
  headers: { "Content-Type": "application/json" },
});

// Attach Bearer token from localStorage on every request
strataApi.interceptors.request.use((config) => {
  const token = localStorage.getItem("strata_access_token");
  if (token) {
    config.headers["Authorization"] = `Bearer ${token}`;
  }
  return config;
});

// If the backend rejects our token, drop it and return to the sign-in gate.
// Without this the UI keeps silently falling back to Mapbox-only data and the
// user sees "No backend record found" with no explanation why.
strataApi.interceptors.response.use(
  (res) => res,
  (error) => {
    const status = error?.response?.status;
    const url: string = error?.config?.url || "";
    const hadToken = !!localStorage.getItem("strata_access_token");
    const isAuthCall = url.includes("/auth/login") || url.includes("/auth/refresh");
    if (status === 401 && hadToken && !isAuthCall) {
      console.warn("[STRATA] Session rejected by backend — signing out.");
      localStorage.removeItem("strata_access_token");
      localStorage.removeItem("strata_refresh_token");
      window.location.reload();
    }
    return Promise.reject(error);
  }
);

// --- Auth ---

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export async function loginUser(
  username: string,
  password: string
): Promise<TokenResponse> {
  const res = await strataApi.post<{ success: boolean; data: TokenResponse }>(
    "/auth/login",
    { username, password }
  );
  return res.data.data;
}

export async function refreshToken(refresh_token: string): Promise<TokenResponse> {
  const res = await strataApi.post<{ success: boolean; data: TokenResponse }>(
    "/auth/refresh",
    { refresh_token }
  );
  return res.data.data;
}

// --- Spatial ---

export interface SpatialEntityItem {
  id: string;
  entity_type: "parcel" | "building";
  identifier: string;
  official_ulpin: string | null;
  candidate_ulpin: string | null;
  status: string;
  area_sqm: number | null;
  height_m?: number | null;
  floor_count?: number | null;
  geometry_geojson: Record<string, unknown> | null;
  centroid: { lat: number; lon: number } | null;
  distance_m?: number | null;
  /** "inside" = click landed within the footprint; "nearest" = closest record within tolerance. */
  match_type?: "inside" | "nearest" | null;
}

export interface PointLookupResponse {
  lat: number;
  lon: number;
  parcel: SpatialEntityItem | null;
  building: SpatialEntityItem | null;
  floors_count: number;
  units_count: number;
  search_radius_m?: number | null;
}

/**
 * Point-in-polygon lookup: returns parcel + building at a lat/lon click.
 * `radiusM` widens the proximity tolerance so a click that lands just outside a
 * small footprint still resolves to that building (reported as match_type: "nearest").
 */
export async function pointLookup(
  lat: number,
  lon: number,
  radiusM = 400
): Promise<PointLookupResponse | null> {
  try {
    const res = await strataApi.get<{
      success: boolean;
      data: PointLookupResponse;
    }>("/spatial/search", { params: { lat, lon, radius_m: radiusM } });
    if (res.data.success) return res.data.data;
    return null;
  } catch (err) {
    console.error(
      `[STRATA] pointLookup failed for lat=${lat}, lon=${lon} (backend ${BACKEND_URL}). Returning no record.`,
      err
    );
    return null;
  }
}

export interface BBoxResponse {
  bbox: number[];
  layer: string;
  crs: string;
  count: number;
  results: SpatialEntityItem[];
}

export interface DataExtent {
  bbox: [number, number, number, number] | null;
  has_data: boolean;
  building_count: number;
  parcel_count: number;
  center_lon: number | null;
  center_lat: number | null;
  crs: string;
}

/**
 * Extent of the geometry actually stored in the backend.
 * The map uses this to open on the real data instead of a hard-coded city.
 */
export async function getDataExtent(): Promise<DataExtent | null> {
  try {
    const res = await strataApi.get<{ success: boolean; data: DataExtent }>(
      "/spatial/extent",
      { params: { layer: "all" } }
    );
    if (res.data.success) return res.data.data;
    return null;
  } catch (err) {
    console.error(`[STRATA] getDataExtent failed (backend ${BACKEND_URL}).`, err);
    return null;
  }
}

/** Viewport bounding box query for displaying buildings on the map. */
export async function queryBBox(
  minLon: number,
  minLat: number,
  maxLon: number,
  maxLat: number,
  layer: "building" | "parcel" | "all" = "building",
  limit = 100
): Promise<SpatialEntityItem[]> {
  try {
    const res = await strataApi.get<{ success: boolean; data: BBoxResponse }>(
      "/spatial/bbox",
      { params: { min_lon: minLon, min_lat: minLat, max_lon: maxLon, max_lat: maxLat, layer, limit } }
    );
    if (res.data.success) return res.data.data.results;
    return [];
  } catch (err) {
    console.error(
      `[STRATA] queryBBox failed for layer=${layer} (backend ${BACKEND_URL}). Returning empty layer.`,
      err
    );
    return [];
  }
}

// --- Buildings ---

export interface CentroidPoint { lat: number; lon: number; }

export interface UnitStructure {
  id: string;
  floor_id: string;
  unit_number: string;
  unit_type: string | null;
  area_sqm: number | null;
  volume_cum: number | null;
  is_occupied: boolean | null;
  official_ulpin: string | null;
  candidate_ulpin: string | null;
  status: string;
  is_verified: boolean;
}

export interface FloorStructure {
  id: string;
  building_id: string;
  floor_number: number;
  floor_label: string | null;
  floor_use: string | null;
  height_above_ground_m: number | null;
  ceiling_height_m: number | null;
  floor_area_sqm: number | null;
  volume_cum: number | null;
  official_ulpin: string | null;
  candidate_ulpin: string | null;
  status: string;
  is_verified: boolean;
  units: UnitStructure[];
}

export interface BuildingStructure {
  id: string;
  building_id: string;
  parcel_id: string;
  building_name: string | null;
  building_type: string | null;
  floor_count: number | null;
  height_m: number | null;
  footprint_area_sqm: number | null;
  official_ulpin: string | null;
  candidate_ulpin: string | null;
  status: string;
  is_verified: boolean;
  centroid: CentroidPoint | null;
  address: string | null;
  district: string | null;
  state: string | null;
  provenance: {
    ml_derived: boolean;
    ml_model_version: string | null;
    ml_confidence_score: number | null;
    version: number;
    created_at: string | null;
    updated_at: string | null;
  } | null;
  floors: FloorStructure[];
}

/** Fetch complete building hierarchy: floors, units, ULPIN, ML provenance. */
export async function getBuildingStructure(
  buildingId: string
): Promise<BuildingStructure | null> {
  try {
    const res = await strataApi.get<{
      success: boolean;
      data: BuildingStructure;
    }>(`/buildings/${buildingId}/structure`);
    if (res.data.success) return res.data.data;
    return null;
  } catch (err) {
    console.error(
      `[STRATA] getBuildingStructure failed for building ${buildingId} (backend ${BACKEND_URL}).`,
      err
    );
    return null;
  }
}

export interface BuildingGeometry {
  building_id: string;
  parcel_id: string;
  centroid: CentroidPoint | null;
  height_m: number | null;
  elevation_m: number | null;
  footprint_wkt: string | null;
  footprint_geojson: Record<string, unknown> | null;
  bounds: number[] | null;
  geometry_3d_lod2: Record<string, unknown> | null;
  source_crs: string;
  processing_crs: string;
}

// --- On-demand ingestion (real OpenStreetMap data for any Indian coordinate) ---

export interface IngestedUnit {
  id: string;
  unit_number: string;
  unit_type: string | null;
  area_sqm: number | null;
  candidate_ulpin: string | null;
  status: string;
  ml_derived: boolean;
}

export interface IngestedFloor {
  id: string;
  floor_number: number;
  floor_label: string | null;
  floor_use: string | null;
  height_above_ground_m: number | null;
  ceiling_height_m: number | null;
  floor_area_sqm: number | null;
  candidate_ulpin: string | null;
  status: string;
  floor_source: string | null;
  units: IngestedUnit[];
}

export interface IngestedBuilding {
  building_id: string;
  parcel_id: string;
  parcel_number: string;
  building_name: string | null;
  building_type: string | null;
  osm_type: string;
  osm_id: number;
  source_url: string;
  osm_tags: Record<string, unknown>;
  height_m: number | null;
  height_source: string | null;
  floor_count: number | null;
  floor_source: string | null;
  footprint_area_sqm: number | null;
  footprint_geojson: Record<string, unknown> | null;
  centroid: { lat: number; lon: number } | null;
  official_ulpin: string | null;
  candidate_ulpin: string | null;
  status: string;
  ml_used: boolean;
  ml_model_version: string | null;
  ml_confidence: number | null;
  ml_data_status: string | null;
  ml_review_status: string | null;
  ml_validation: Record<string, unknown> | null;
  floors: IngestedFloor[];
  units_created: number;
  already_existed: boolean;
}

export interface IngestLocationResult {
  query_lat: number;
  query_lon: number;
  radius_m: number;
  source: string;
  buildings_found: number;
  buildings_ingested: number;
  buildings_skipped: number;
  parcels_created: number;
  parcels_reused: number;
  floors_created: number;
  units_created: number;
  candidate_ulpins: string[];
  buildings: IngestedBuilding[];
  skipped_reasons: string[];
  authoritative: boolean;
  disclaimers: string[];
}

/**
 * Fetch real OSM footprints for a coordinate and persist them as CANDIDATE records.
 * Nothing is fabricated: geometry and tags come from OpenStreetMap, and any
 * height/floor value the source does not carry is left null or tagged ML-derived.
 */
export async function ingestLocation(params: {
  lat: number;
  lon: number;
  radiusM?: number;
  nameContains?: string;
  state?: string;
  district?: string;
  maxBuildings?: number;
  runMl?: boolean;
}): Promise<IngestLocationResult | null> {
  try {
    const res = await strataApi.post<{ success: boolean; data: IngestLocationResult }>(
      "/ingest/location",
      {
        lat: params.lat,
        lon: params.lon,
        radius_m: params.radiusM ?? 200,
        name_contains: params.nameContains ?? null,
        state: params.state ?? null,
        district: params.district ?? null,
        max_buildings: params.maxBuildings ?? 10,
        run_ml: params.runMl ?? true,
      },
      { timeout: 180000 } // Overpass + ML inference is slower than a plain read
    );
    if (res.data.success) return res.data.data;
    return null;
  } catch (err) {
    console.error(
      `[STRATA] ingestLocation failed for lat=${params.lat}, lon=${params.lon} (backend ${BACKEND_URL}).`,
      err
    );
    return null;
  }
}

/** Persisted row counts, so coverage is observable rather than assumed. */
export async function getIngestCoverage(): Promise<Record<string, number> | null> {
  try {
    const res = await strataApi.get<{ success: boolean; data: Record<string, number> }>(
      "/ingest/coverage"
    );
    if (res.data.success) return res.data.data;
    return null;
  } catch (err) {
    console.error("[STRATA] getIngestCoverage failed.", err);
    return null;
  }
}

/** Fetch real GeoJSON geometry for 3D rendering. */
export async function getBuildingGeometry(
  buildingId: string
): Promise<BuildingGeometry | null> {
  try {
    const res = await strataApi.get<{
      success: boolean;
      data: BuildingGeometry;
    }>(`/buildings/${buildingId}/geometry`);
    if (res.data.success) return res.data.data;
    return null;
  } catch (err) {
    console.error(
      `[STRATA] getBuildingGeometry failed for building ${buildingId} (backend ${BACKEND_URL}). Falling back to Mapbox geometry.`,
      err
    );
    return null;
  }
}
