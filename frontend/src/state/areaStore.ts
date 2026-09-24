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

  appendAreas: (areas: any[]) => void;
  setCenter: (center: any[]) => void;
  setAppStep: (step: number) => void;
  setSelectedBuildingDetail: (detail: BuildingInfo | null) => void;
  setBackendBuildingStructure: (structure: BuildingStructure | null) => void;
  setBackendBuildingGeometry: (geometry: BuildingGeometry | null) => void;
  setIsFetchingBackendBuilding: (val: boolean) => void;
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
  appendAreas: (areas) => set(() => ({ areas: [...areas] })),
  setCenter: (center) => set(() => ({ center: [...center] })),
  setAppStep: (step) => set(() => ({ appStep: step })),
  setSelectedBuildingDetail: (detail) => set(() => ({ selectedBuildingDetail: detail })),
  setBackendBuildingStructure: (structure) => set(() => ({ backendBuildingStructure: structure })),
  setBackendBuildingGeometry: (geometry) => set(() => ({ backendBuildingGeometry: geometry })),
  setIsFetchingBackendBuilding: (val) => set(() => ({ isFetchingBackendBuilding: val })),
}));
