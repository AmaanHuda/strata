/** VPMS design tokens — Neo-Material Geospatial
 * Neo-brutalist structure (2.5px ink borders, hard offset shadows)
 * fused with Material 3 pastel surfaces & systematic hierarchy.
 */

// Ink (structural outline color — replaces pure black)
export const INK = "#0F172A";

// Backgrounds
export const BG_PRIMARY = "#F8FAFC"; // Slate-50 soft tinted canvas
export const BG_SURFACE = "#FFFFFF"; // Surface container
export const BG_TINT = "#EFF6FF"; // Primary pastel tint
export const BG_PANEL = "#F1F5F9"; // Subtle UI panels / tool docks
export const BG_GLASS = "#FFFFFF";
export const BG_GLASS_HOVER = "#F8FAFC";
export const BG_GLASS_ACTIVE = "#FFFFFF";
export const BG_OVERLAY = "rgba(15, 23, 42, 0.5)";

// Pastel chip containers (data callouts)
export const CHIP_MINT = "#ECFDF5";
export const CHIP_AMBER = "#FEF3C7";
export const CHIP_BLUE = "#EFF6FF";

// Borders
export const BORDER_COLOR = INK; // structural 2–2.5px ink boundaries
export const BORDER_HAIRLINE = "#C3C6D7"; // 1–1.5px subtle slate lines
export const BORDER_ACTIVE = "#2563EB";
export const BORDER_SUBTLE = "#C3C6D7";

// Text
export const TEXT_PRIMARY = "#0F172A";
export const TEXT_SECONDARY = "#434655";
export const TEXT_MUTED = "#64748B";
export const SUBTITLE_COLOR = TEXT_PRIMARY;
export const DESC_COLOR = TEXT_SECONDARY;
export const ACTION_ICON_COLOR = TEXT_SECONDARY;

// Accents
export const ACCENT_BLUE = "#2563EB"; // Electric Royal Blue — primary
export const ACCENT_TEAL = "#10B981"; // Geospatial Mint — secondary
export const ACCENT_ORANGE = "#F59E0B"; // Amber Terrain — tertiary
export const ACCENT_RED = "#BA1A1A";
export const ACCENT_GREEN = "#10B981";
export const ACCENT_INDIGO = "#4F46E5";

// Soft accent containers
export const BLUE_SOFT = "#EFF6FF";
export const MINT_SOFT = "#ECFDF5";
export const AMBER_SOFT = "#FEF3C7";
export const ERROR_SOFT = "#FFDAD6";

// Elevation — tactile hard offsets (no blur)
export const SHADOW_XS = "1px 1px 0px #0F172A";
export const SHADOW_SM = "2px 2px 0px #0F172A";
export const SHADOW_MD = "3px 3px 0px #0F172A";
export const SHADOW_LG = "4px 4px 0px #0F172A";
export const SHADOW_XL = "6px 6px 0px #0F172A";
export const SHADOW_PRESS = "1px 1px 0px #0F172A";

// Glass effects (kept for compatibility; hard shadows now take over)
export const BLUR_GLASS = "blur(8px)";
export const SHADOW_GLASS = SHADOW_MD;
export const SHADOW_GLOW_BLUE = SHADOW_LG;

// Radii (Material 3 curves inside ink containment)
export const RADIUS_SM = "8px";
export const RADIUS_MD = "12px";
export const RADIUS_LG = "16px";

// Shared tactile press/hover interaction (physical switch feel)
export const pressable = {
  transition:
    "transform 0.16s ease, box-shadow 0.16s ease, background-color 0.16s ease, color 0.16s ease",
  ":hover": {
    transform: "translate(-1px, -1px)",
    boxShadow: SHADOW_LG,
  },
  ":active": {
    transform: "translate(2px, 2px)",
    boxShadow: SHADOW_PRESS,
  },
} as const;
