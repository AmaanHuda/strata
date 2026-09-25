"""Guard: the ingestion path must never mint or store an OFFICIAL ULPIN.

Only Survey of India / a gazetted government source may set ``official_ulpin``.
The on-demand ingestion pipeline (real OSM data + optional ML inference) is a
candidate-only path, so every ORM write of ``official_ulpin`` inside it must be
the literal ``None``.

This is a source-level guard because the rule matters even when the DB is not
available in the test environment (mirrors tests/unit/test_frontend_ulpin_honesty.py).
"""
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

INGEST_SOURCES = [
    REPO_ROOT / "app" / "services" / "on_demand_ingest.py",
    REPO_ROOT / "app" / "api" / "v1" / "ingest.py",
    REPO_ROOT / "app" / "services" / "cadastral_codes.py",
    REPO_ROOT / "app" / "integrations" / "osm" / "overpass.py",
]

# ORM entities that carry an official_ulpin column.
ORM_MODELS = ("Parcel", "Building", "Floor", "Unit", "ULPINRecord")


def _constructor_blocks(source: str):
    """Yield the text inside each `ModelName( ... )` call (paren-balanced)."""
    for model in ORM_MODELS:
        for match in re.finditer(rf"\b{model}\s*\(", source):
            start = match.end()
            depth = 1
            index = start
            while index < len(source) and depth > 0:
                char = source[index]
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1
                index += 1
            yield model, source[start : index - 1]


@pytest.mark.parametrize("path", INGEST_SOURCES, ids=lambda p: p.name)
def test_ingest_sources_exist(path):
    assert path.exists(), f"ingestion source missing: {path}"


def test_no_non_null_official_ulpin_is_written_by_ingestion():
    offenders = []
    for path in INGEST_SOURCES:
        source = path.read_text(encoding="utf-8")
        for model, block in _constructor_blocks(source):
            for assign in re.finditer(r"official_ulpin\s*=\s*([^,\n]+)", block):
                value = assign.group(1).strip()
                if value != "None":
                    offenders.append(f"{path.name}: {model}(...) official_ulpin={value}")
    assert not offenders, (
        "Ingestion must never write a non-null official_ulpin (government-only field). "
        f"Offenders: {offenders}"
    )


def test_ingestion_declares_the_candidate_disclaimer():
    source = (REPO_ROOT / "app" / "services" / "on_demand_ingest.py").read_text(encoding="utf-8")
    assert "NON-AUTHORITATIVE" in source
    assert "is_authoritative=False" in source


def test_ingestion_uses_the_parent_chain_for_candidate_ids():
    """Candidate building IDs must derive from the parcel ULPIN, not a raw UUID."""
    source = (REPO_ROOT / "app" / "services" / "on_demand_ingest.py").read_text(encoding="utf-8")
    assert "generate_parcel_ulpin" in source
    assert re.search(r'candidate_ulpin = f"\{parcel\.candidate_ulpin\}-B', source)
    # The internal entity UUID must never be formatted into an identifier.
    for line in source.splitlines():
        if "candidate_ulpin" not in line or "=" not in line.split("#")[0]:
            continue
        assert "str(building.id)" not in line, line
        assert "str(parcel.id)" not in line, line
        assert "{building.id}" not in line, line
        assert "{parcel.id}" not in line, line
