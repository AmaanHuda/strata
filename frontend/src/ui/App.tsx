import { css, keyframes } from "@emotion/react";
import { FullscreenModal } from "../components/FullscreenModal";
import { Title } from "@/components/text/Title";
import { Description } from "@/components/text/Description";
import { Column } from "@/components/flex/Column";
import { Row } from "@/components/flex/Row";
import { MapComponent } from "@/components/map/SelectMap";
import { SearchBar } from "@/components/map/SearchBar";
import { useState } from "react";
import {
  Button,
  NextButton,
  PrevButton,
} from "@/components/button/BottomButton";
import {
  ChevronRight,
  AlertTriangle,
  MousePointerClick,
} from "lucide-react";
import { NavButton } from "@/components/nav/TopNav";
import { useAreaStore } from "@/state/areaStore";
import { Modal } from "@/components/modal/Modal";
import { TopNav } from "@/components/nav/TopNav";
import { MapboxSpace } from "../three/MapboxSpace";
import { BuildingIsolateScene } from "@/components/scene/BuildingIsolateScene";
import { HeroSection } from "@/components/sections/HeroSection";
import { TeamSection } from "@/components/sections/TeamSection";
import { SiteFooter } from "@/components/sections/SiteFooter";

const IconSize = css({
  width: "14px",
  height: "14px",
  flexShrink: 0,
});

function App() {
  const [isNextButtonDisabled, setIsNextButtonDisabled] = useState(true);
  const [areaData, setAreaData] = useState<{ lat: number; lng: number }[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<{
    lat: number;
    lng: number;
  } | null>(null);

  const setCenter = useAreaStore((state) => state.setCenter);
  const appStep = useAreaStore((state) => state.appStep);
  const selectedBuildingId = useAreaStore((state) => state.selectedBuildingDetail?.id);
  const setAppStep = useAreaStore((state) => state.setAppStep);
  const [isWarnModal, setIsWarnModal] = useState(false);
  const [resetKey, setResetKey] = useState(0);

  const checkIsBig = (): boolean => {
    if (areaData.length < 2) return false;
    const a = areaData[0].lat - areaData[1].lat;
    const b = areaData[0].lng - areaData[1].lng;
    return a + b > 0.1;
  };

  const handleDone = (data: { lat: number; lng: number }[]) => {
    setAreaData(data);
    setCenter(data);
    setIsNextButtonDisabled(false);
  };

  const handleRemove = () => {
    setAreaData([]);
    setIsNextButtonDisabled(true);
  };

  const handleResetDemo = () => {
    handleRemove();
    setAppStep(0);
    setResetKey((k) => k + 1);
  };

  const handleClickNextStep = () => {
    if (appStep === 0 && checkIsBig()) {
      setIsWarnModal(true);
      return;
    }
    setAppStep(1);
  };

  const handleClickPrevStep = () => {
    setAppStep(0);
  };

  return (
    <div
      css={css({
        height: "100%",
        width: "100%",
        position: "relative",
        overflow: "hidden",
      })}
    >
      <TopNav />

      {/* Step 0: Map Selection */}
      <FullscreenModal isOpen={appStep === 0}>
        <HeroSection activeStep={0} />
        <div
          css={css({
            border: `3px solid #0F172A`,
            boxShadow: "6px 6px 0px #0F172A",
            borderRadius: "18px",
            overflow: "hidden",
            background: "#FFFFFF",
            flexShrink: 0,
          })}
        >
          {/* Search */}
          <div
            css={css({
              padding: "1.25rem 1.5rem",
              background: "#EAEDFF",
              borderBottom: `2.5px solid #0F172A`,
            })}
          >
            <SearchBar
              onLocationSelect={(lat, lng) => setSelectedLocation({ lat, lng })}
            />
          </div>

          {/* Map + telemetry drawer in shared frame */}
          <MapComponent
            onRemove={handleRemove}
            onDone={handleDone}
            flyTarget={selectedLocation}
            resetKey={resetKey}
            bare
          />
        </div>

        <div
          css={css({
            display: "flex",
            justifyContent: "flex-end",
            paddingTop: "0.5rem",
            marginTop: "0.5rem",
            paddingBottom: "0.5rem",
            flexShrink: 0,
          })}
        >
          <NextButton
            isShow={true}
            disabled={isNextButtonDisabled}
            onClick={handleClickNextStep}
          >
            View 3D <ChevronRight css={IconSize} />
          </NextButton>
        </div>
        <TeamSection />
        <SiteFooter />
      </FullscreenModal>

      {/* 3D View hint chip */}
      {appStep === 1 && (
        <div
          css={css({
            position: "absolute",
            zIndex: 9999,
            left: "50%",
            transform: "translateX(-50%)",
            bottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            background: "rgba(255, 255, 255, 0.95)",
            border: "2px solid #0F172A",
            boxShadow: "2px 2px 0px #0F172A",
            padding: "0.55rem 0.9rem",
            borderRadius: "12px",
            fontSize: "12px",
            fontWeight: 800,
            color: "#0F172A",
            pointerEvents: "none",
          })}
        >
          <MousePointerClick css={IconSize} /> Click a building to inspect it
        </div>
      )}

      {/* Warning Modal */}
      <Modal isOpen={isWarnModal} onClose={() => setIsWarnModal(false)}>
        <Column gap="0.85rem">
          <div
            css={css({
              display: "flex",
              alignItems: "center",
              gap: "0.65rem",
            })}
          >
            <div
              css={css({
                width: "2rem",
                height: "2rem",
                borderRadius: "10px",
                display: "grid",
                placeItems: "center",
                background: "#FEF3C7",
                border: `2px solid #0F172A`,
                boxShadow: "2px 2px 0px #0F172A",
                color: "#B45309",
              })}
            >
              <AlertTriangle size={14} strokeWidth={2.5} />
            </div>
            <Title>The area is too big</Title>
          </div>
          <Description>Do you want to proceed?</Description>
          <Button
            isShow={true}
            disabled={isNextButtonDisabled}
            onClick={() => {
              setAppStep(1);
              setIsWarnModal(false);
            }}
          >
            Continue <ChevronRight css={IconSize} />
          </Button>
        </Column>
      </Modal>

      {/* Photorealistic Mapbox 3D Scene */}
      <MapboxSpace isVisible={appStep === 1} />

      {/* Step 2: Isolated Building 3D Scene */}
      {appStep === 2 && <BuildingIsolateScene key={selectedBuildingId || "unselected"} />}
    </div>
  );
}

export default App;
