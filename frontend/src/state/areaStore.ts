import { create } from "zustand";
import { BuildingInfo } from "../components/panels/BuildingSidebar";
import { BuildingStructure, BuildingGeometry } from "@/api/strataBackend";

type AreaStore = {
  areas: any;
  center: {
    lat: number;
    lng: number;
  }[];
  appStep: number;
  selectedBuildingDetail: BuildingInfo | null;
  /** Real backend building structure — floors, units, ULPIN, ML provenance. Null when none selected or backend returned nothing. */
  backendBuildingStructure: BuildingStructure | null;
  /** Real backend building geometry — real GeoJSON footprint + height. */
  backendBuildingGeometry: BuildingGeometry | null;
  /** True while fetching backend building data after a map click. */
  isFetchingBackendBuilding: boolean;
  /**
   * True once the backend point-lookup has completed (regardless of whether
   * it found anything). Reset to false on every new map click so the "No
   * backend record" disclaimer never shows while a lookup is pending.
   */
  backendLookupDone: boolean;
  /**
   * True if the backend lookup returned at least a parcel OR a building for
   * the clicked coordinate. Used to suppress the false-positive disclaimer.
   */
  backendFoundData: boolean;

  appendAreas: (areas: any[]) => void;
  setCenter: (center: any[]) => void;
  setAppStep: (step: number) => void;
  setSelectedBuildingDetail: (detail: BuildingInfo | null) => void;
  setBackendBuildingStructure: (structure: BuildingStructure | null) => void;
  setBackendBuildingGeometry: (geometry: BuildingGeometry | null) => void;
  setIsFetchingBackendBuilding: (val: boolean) => void;
  setBackendLookupDone: (val: boolean) => void;
  setBackendFoundData: (val: boolean) => void;
};

export const useAreaStore = create<AreaStore>((set) => ({
  areas: [],
  center: [
    {
      lat: 18.9250,
      lng: 72.8370,
    },
    {
      lat: 18.9200,
      lng: 72.8320,
    },
  ],
  appStep: 0,
  selectedBuildingDetail: null,
  backendBuildingStructure: null,
  backendBuildingGeometry: null,
  isFetchingBackendBuilding: false,
  backendLookupDone: false,
  backendFoundData: false,
  appendAreas: (areas) => set(() => ({ areas: [...areas] })),
  setCenter: (center) => set(() => ({ center: [...center] })),
  setAppStep: (step) => set(() => ({ appStep: step })),
  setSelectedBuildingDetail: (detail) => set(() => ({ selectedBuildingDetail: detail })),
  setBackendBuildingStructure: (structure) => set(() => ({ backendBuildingStructure: structure })),
  setBackendBuildingGeometry: (geometry) => set(() => ({ backendBuildingGeometry: geometry })),
  setIsFetchingBackendBuilding: (val) => set(() => ({ isFetchingBackendBuilding: val })),
  setBackendLookupDone: (val) => set(() => ({ backendLookupDone: val })),
  setBackendFoundData: (val) => set(() => ({ backendFoundData: val })),
}));

