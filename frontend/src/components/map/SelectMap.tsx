import React, { useEffect, useRef, useState, useCallback } from "react";
import Map, { MapRef, Source, Layer } from "react-map-gl/mapbox";
import { css } from "@emotion/react";
import { Hand, SquareMousePointer, Trash2 } from "lucide-react";
import "mapbox-gl/dist/mapbox-gl.css";
import { INK, TEXT_PRIMARY } from "@/theme/color";

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
          onMouseDown={onMouseDown}
          onMouseMove={onMouseMove}
          onMouseUp={onMouseUp}
          onMove={onMove}
          interactiveLayerIds={[]}
          cursor={isDrag ? "grab" : "crosshair"}
        >
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
