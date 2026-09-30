"""
Multi-source Evidence Fusion & Conflict Detection Engine.
SIH 2026 PS 26011 - ML Engine
"""
from typing import List, Dict, Any, Tuple, Optional



# Evidence fusion state constants
EVIDENCE_SUPPORTED = "SUPPORTED"
EVIDENCE_CONFLICTING = "CONFLICTING"
EVIDENCE_MISSING = "MISSING"
EVIDENCE_INFERRED = "INFERRED"


class EvidenceFusionEngine:
    """
    Fuses evidence from satellite, DEM, LiDAR, drone, BIM, and cadastral records with reliability weighting.
    Explicitly tracks evidence states (SUPPORTED, CONFLICTING, MISSING, INFERRED) and detects contradictory cues.
    """
    def __init__(self):
        self.source_weights = {
            "lidar": 0.95,
            "drone": 0.90,
            "bim": 0.95,
            "plan": 0.85,
            "cadastral": 0.90,
            "satellite": 0.75,
            "dem": 0.70,
            "dsm": 0.75,
            "dtm": 0.70,
            "gnss": 0.85,
            "osm": 0.40,
            "heuristic": 0.30
        }

    def fuse_evidence(
        self,
        evidence_list: List[Dict[str, Any]],
        height_observations: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        if not evidence_list:
            return {
                "combined_reliability": 0.0,
                "evidence_state": EVIDENCE_MISSING,
                "review_status": "INSUFFICIENT_EVIDENCE",
                "evidence_count": 0,
                "source_types": [],
                "conflicts": ["No evidence sources provided."]
            }

        total_weight = 0.0
        weighted_reliability = 0.0
        conflicts = []

        types = set()
        for ev in evidence_list:
            src_type = ev.get("type", "other").lower()
            rel = float(ev.get("reliability", 0.5))
            w = self.source_weights.get(src_type, 0.5)

            types.add(src_type)
            weighted_reliability += rel * w
            total_weight += w

        avg_reliability = (weighted_reliability / total_weight) if total_weight > 0 else 0.0

        # Check for cross-modal observation conflicts (e.g. conflicting height observations)
        if height_observations and len(height_observations) >= 2:
            heights = [h["height_m"] for h in height_observations if h.get("height_m") is not None]
            if len(heights) >= 2 and (max(heights) - min(heights) > 3.5):
                conflicts.append(
                    f"Height discrepancy across sources: min {min(heights):.1f}m vs max {max(heights):.1f}m (>3.5m difference)."
                )

        # Determine evidence state & review status
        if conflicts:
            evidence_state = EVIDENCE_CONFLICTING
            review_status = "SOURCE_CONFLICT"
        elif len(types) == 1 and ("heuristic" in types or "osm" in types):
            evidence_state = EVIDENCE_INFERRED
            review_status = "REVIEW_REQUIRED"
        elif len(types) >= 2 and avg_reliability >= 0.75:
            evidence_state = EVIDENCE_SUPPORTED
            review_status = "APPROVED"
        elif avg_reliability >= 0.50:
            evidence_state = EVIDENCE_SUPPORTED
            review_status = "REVIEW_REQUIRED"
        else:
            evidence_state = EVIDENCE_MISSING
            review_status = "LOW_CONFIDENCE"

        return {
            "combined_reliability": round(avg_reliability, 4),
            "evidence_state": evidence_state,
            "evidence_count": len(evidence_list),
            "source_types": sorted(list(types)),
            "review_status": review_status,
            "conflicts": conflicts
        }

