"""Frontend guard: the UI must never mint a ULPIN.

Official ULPINs (14-character Bhu-Aadhaar identifiers) are assigned by the
government, and candidate identifiers are produced by the backend pipeline. The
frontend's only job is to display what the API returns, so any client-side ULPIN
construction is a fabrication risk - exactly what ``utils/ulpin.ts`` and
``api/supabase.ts`` used to do by deriving a 14-digit identifier from lat/lng.

The scans run here (rather than in a JS runner) because this repo's test
toolchain is pytest; the target is frontend TypeScript source, not Python.
"""
import re
from pathlib import Path

import pytest

FRONTEND_SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"

# 1. Client-side ULPIN minting, by function/call name (e.g. generateBaseUlpin).
_GENERATOR = re.compile(r"generate\w*ulpin", re.IGNORECASE)
# 2. Official 14-character Bhu-Aadhaar format expressed as a regex, e.g. [A-Z0-9]{14}.
_OFFICIAL_FORMAT_REGEX = re.compile(r"\[\s*A-Z0-9\s*\]\s*\{\s*14\s*\}")
# 3. Padding a value out to 14 characters, i.e. building the official shape.
_PAD_TO_14 = re.compile(r"padStart\(\s*14\b")
# 4. A hardcoded 14-character uppercase alphanumeric literal on a ULPIN line.
_ULPIN_LITERAL_14 = re.compile(r"['\"][A-Z0-9]{14}['\"]")

# (rule name, pattern, needs_ulpin_on_the_line). The generator pattern already
# names ulpin itself; the others are only suspicious on a ULPIN-handling line.
_RULES = (
    ("client-side ULPIN generator", _GENERATOR, False),
    ("official 14-char format regex", _OFFICIAL_FORMAT_REGEX, True),
    ("padStart(14) - builds the official shape", _PAD_TO_14, True),
    ("hardcoded 14-char ULPIN literal", _ULPIN_LITERAL_14, True),
)


def _scan(text: str):
    """Returns (line number, rule name, line) for each offending line."""
    offenders = []
    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.lstrip()
        if stripped.startswith(("//", "*", "/*")):
            continue  # comments may legitimately discuss the rule
        for name, pattern, needs_ulpin_on_the_line in _RULES:
            if not pattern.search(line):
                continue
            if not needs_ulpin_on_the_line or "ulpin" in line.lower():
                offenders.append((lineno, name, line.strip()))
    return offenders


def _frontend_sources():
    if not FRONTEND_SRC.is_dir():
        pytest.skip("frontend sources are not part of this revision")
    return sorted(
        p for p in FRONTEND_SRC.rglob("*") if p.suffix in {".ts", ".tsx"} and p.is_file()
    )


def test_scanner_catches_the_deleted_fabrication_code():
    """Positive control, so a passing suite cannot mean a broken scanner."""
    legacy = (
        'export function generateBaseUlpin(lat: number, lng: number): string {\n'
        '  const latPart = Math.round((lat + 90) * 100000).toString().padStart(7, "0");\n'
        '  const lngPart = Math.round((lng + 180) * 100000).toString().padStart(7, "0");\n'
        '  return `${latPart}${lngPart}`;\n'
        '}\n'
        'const OFFICIAL_ULPIN = /^[A-Z0-9]{14}$/;\n'
        'const officialUlpin = "1234567890ABCD";\n'
    )
    caught = {name for _, name, _ in _scan(legacy)}
    assert "client-side ULPIN generator" in caught
    assert "official 14-char format regex" in caught
    assert "hardcoded 14-char ULPIN literal" in caught


def test_no_frontend_file_mints_a_ulpin():
    offenders = []
    for path in _frontend_sources():
        for lineno, rule, line in _scan(path.read_text(encoding="utf-8")):
            offenders.append(f"{path.relative_to(FRONTEND_SRC.parent.parent)}:{lineno}: [{rule}] {line}")
    assert not offenders, (
        "Frontend mints a ULPIN - official ULPINs must come from the government record and "
        "candidate ULPINs from the backend:\n" + "\n".join(offenders)
    )


def test_frontend_ulpin_fabrication_modules_stay_deleted():
    """Regression pin: these two modules derived ULPINs from coordinates client-side."""
    for rel in ("utils/ulpin.ts", "api/supabase.ts"):
        target = FRONTEND_SRC / rel
        assert not target.exists(), (
            f"{rel} was deleted because it fabricated ULPINs client-side; "
            "do not reintroduce it (ULPINs must come from the backend)."
        )
