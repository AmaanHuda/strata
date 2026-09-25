"""
Cadastral code segments for candidate (non-authoritative) ULPINs.

The candidate ULPIN format consumed by :class:`~app.services.ulpin.ULPINService`
is ``<STATE(2)><-><DISTRICT(2 digits)><-><TALUK(3 digits)><-><VILLAGE(6 digits)>
<-P-><SEQ(8)>``. Official LGD/SoI code tables are not bundled with this
repository, so this module does two honest things:

1. Uses the real ISO 3166-2:IN state code for the state segment.
2. When the caller has not supplied real numeric LGD codes, DERIVES a stable
   numeric segment from the real administrative *name* using SHA-256, and
   labels it as an application-internal code assignment.

A derivable code is a routing key, not a legal identifier. Every ULPIN that
uses one remains CANDIDATE / ``is_authoritative=False``, and the assignment
basis is recorded in the entity metadata for audit.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

# ISO 3166-2:IN subdivision codes (real codes, used for the 2-letter segment).
ISO_3166_2_IN_STATE_CODES: Dict[str, str] = {
    "andhra pradesh": "AP",
    "arunachal pradesh": "AR",
    "assam": "AS",
    "bihar": "BR",
    "chhattisgarh": "CG",
    "goa": "GA",
    "gujarat": "GJ",
    "haryana": "HR",
    "himachal pradesh": "HP",
    "jharkhand": "JH",
    "karnataka": "KA",
    "kerala": "KL",
    "madhya pradesh": "MP",
    "maharashtra": "MH",
    "manipur": "MN",
    "meghalaya": "ML",
    "mizoram": "MZ",
    "nagaland": "NL",
    "odisha": "OD",
    "punjab": "PB",
    "rajasthan": "RJ",
    "sikkim": "SK",
    "tamil nadu": "TN",
    "telangana": "TG",
    "tripura": "TR",
    "uttar pradesh": "UP",
    "uttarakhand": "UK",
    "west bengal": "WB",
    "andaman and nicobar islands": "AN",
    "chandigarh": "CH",
    "dadra and nagar haveli and daman and diu": "DH",
    "delhi": "DL",
    "jammu and kashmir": "JK",
    "ladakh": "LA",
    "lakshadweep": "LD",
    "puducherry": "PY",
}

# Common OSM spellings / abbreviations for the same subdivisions.
_STATE_ALIASES: Dict[str, str] = {
    "bombay": "MH",
    "mumbai": "MH",
    "mh": "MH",
    "new delhi": "DL",
    "ncr": "DL",
    "orissa": "OD",
    "uttaranchal": "UK",
    "pondicherry": "PY",
    "bangalore": "KA",
    "bengaluru": "KA",
    "chennai": "TN",
    "kolkata": "WB",
    "hyderabad": "TG",
}


@dataclass(frozen=True)
class CadastralCodes:
    """The four code segments of a candidate parcel ULPIN plus their basis."""

    state_code: str
    district_code: str
    taluk_code: str
    village_code: str
    code_basis: str  # supplied_lgd | iso3166_2_name_hash | name_hash
    district_name: str
    taluk_name: str
    village_name: str
    state_name: str

    def as_metadata(self) -> Dict[str, Any]:
        data = asdict(self)
        data["note"] = (
            "Numeric segments are application-internal code assignments derived from "
            "real administrative names, not gazetted LGD codes. The resulting ULPIN is "
            "a CANDIDATE identifier and carries no legal standing."
        )
        return data


def _hash_segment(value: str, digits: int) -> str:
    """Deterministic numeric segment of `digits` length from a real name."""
    if not value or not value.strip():
        return "0" * digits
    digest = hashlib.sha256(f"strata:cadastral:{value.strip().lower()}".encode("utf-8")).hexdigest()
    number = int(digest[:16], 16) % (10 ** digits)
    return str(number).zfill(digits)


def state_code_for(state_name: Optional[str], supplied: Optional[str] = None) -> str:
    """Resolve a 2-letter state segment, preferring any caller-supplied code."""
    if supplied:
        clean = "".join(ch for ch in supplied.upper() if ch.isalpha())
        if len(clean) >= 2:
            return clean[:2]
    if state_name:
        key = state_name.strip().lower()
        if key in _STATE_ALIASES:
            return _STATE_ALIASES[key]
        if key in ISO_3166_2_IN_STATE_CODES:
            return ISO_3166_2_IN_STATE_CODES[key]
        initials = "".join(w[0] for w in key.split() if w)
        if len(initials) >= 2:
            return initials[:2].upper()
    return "IN"


def assign_cadastral_codes(
    *,
    state: Optional[str],
    district: Optional[str],
    taluk: Optional[str],
    village: Optional[str],
    district_code: Optional[str] = None,
    taluk_code: Optional[str] = None,
    village_code: Optional[str] = None,
) -> CadastralCodes:
    """
    Produce the four candidate ULPIN segments.

    Real numeric codes passed by the caller always win; otherwise the segments
    are deterministically derived from the real names and explicitly labelled.
    """
    supplied_any = any(v is not None for v in (district_code, taluk_code, village_code))
    district_name = (district or "UNSPECIFIED").strip() or "UNSPECIFIED"
    taluk_name = (taluk or "UNSPECIFIED").strip() or "UNSPECIFIED"
    village_name = (village or "UNSPECIFIED").strip() or "UNSPECIFIED"
    state_name = (state or "INDIA").strip() or "INDIA"

    def _numeric(value: Optional[str], name: str, digits: int) -> str:
        if value:
            digits_only = "".join(ch for ch in str(value) if ch.isdigit())
            if digits_only:
                return digits_only.zfill(digits)[-digits:]
        return _hash_segment(name, digits)

    return CadastralCodes(
        state_code=state_code_for(state_name),
        district_code=_numeric(district_code, district_name, 2),
        taluk_code=_numeric(taluk_code, taluk_name, 3),
        village_code=_numeric(village_code, village_name, 6),
        code_basis="supplied_lgd" if supplied_any else "name_hash",
        district_name=district_name,
        taluk_name=taluk_name,
        village_name=village_name,
        state_name=state_name,
    )
