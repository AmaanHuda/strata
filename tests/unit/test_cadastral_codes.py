"""Unit tests for candidate-ULPIN code segment assignment (DB-free)."""
import pytest

from app.services.cadastral_codes import assign_cadastral_codes, state_code_for
from app.services.ulpin import ULPINService


class TestStateCodes:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Maharashtra", "MH"),
            ("Mumbai", "MH"),
            ("Delhi", "DL"),
            ("Karnataka", "KA"),
            ("Tamil Nadu", "TN"),
            ("West Bengal", "WB"),
        ],
    )
    def test_real_iso_codes(self, name, expected):
        assert state_code_for(name) == expected

    def test_supplied_code_wins(self):
        assert state_code_for("Maharashtra", supplied="mh-42") == "MH"

    def test_unknown_name_falls_back_to_initials(self):
        assert state_code_for("Some Place") == "SP"

    def test_missing_name_is_never_crashy(self):
        assert state_code_for(None) == "IN"


class TestCodeAssignment:
    def test_supplied_numeric_codes_are_used_verbatim(self):
        codes = assign_cadastral_codes(
            state="Maharashtra",
            district="Mumbai",
            taluk="Andheri",
            village="Village",
            district_code="12",
            taluk_code="345",
            village_code="678901",
        )
        assert (codes.district_code, codes.taluk_code, codes.village_code) == ("12", "345", "678901")
        assert codes.code_basis == "supplied_lgd"

    def test_derived_codes_have_the_right_widths(self):
        codes = assign_cadastral_codes(
            state="Maharashtra", district="Mumbai", taluk="Andheri", village="Bandra"
        )
        assert codes.state_code == "MH"
        assert len(codes.district_code) == 2
        assert len(codes.taluk_code) == 3
        assert len(codes.village_code) == 6
        assert codes.code_basis == "name_hash"
        assert all(c.isdigit() for c in (
            codes.district_code, codes.taluk_code, codes.village_code
        ))

    def test_derivation_is_deterministic(self):
        first = assign_cadastral_codes(state="Maharashtra", district="Mumbai", taluk="A", village="B")
        second = assign_cadastral_codes(state="Maharashtra", district="Mumbai", taluk="A", village="B")
        assert first == second

    def test_different_names_produce_different_codes(self):
        first = assign_cadastral_codes(state="Maharashtra", district="Mumbai", taluk="A", village="B")
        second = assign_cadastral_codes(state="Maharashtra", district="Pune", taluk="A", village="B")
        assert first.district_code != second.district_code

    def test_metadata_records_the_basis_and_the_caveat(self):
        meta = assign_cadastral_codes(
            state="Maharashtra", district="Mumbai", taluk="A", village="B"
        ).as_metadata()
        assert meta["code_basis"] == "name_hash"
        assert "CANDIDATE" in meta["note"]

    def test_missing_context_is_handled_without_inventing_a_real_code(self):
        codes = assign_cadastral_codes(state=None, district=None, taluk=None, village=None)
        assert codes.district_name == "UNSPECIFIED"
        assert codes.code_basis == "name_hash"


class TestGeneratedUlpinShape:
    """The generated parcel ULPIN must satisfy the candidate format the API validates."""

    def test_candidate_ulpin_matches_the_service_regex(self):
        codes = assign_cadastral_codes(
            state="Maharashtra", district="Mumbai", taluk="Mumbai", village="400001"
        )
        parcel_ulpin = ULPINService.generate_parcel_ulpin(
            state=codes.state_code,
            district=codes.district_code,
            taluk=codes.taluk_code,
            village=codes.village_code,
            survey_number="OSM-W28846517",
        )
        assert ULPINService.is_candidate_format(parcel_ulpin)
        # Never mistakable for a 14-character official Bhu-Aadhaar identifier.
        assert not ULPINService.is_official_format(parcel_ulpin)
        assert ULPINService.is_candidate_format(f"{parcel_ulpin}-B1")
        assert ULPINService.is_candidate_format(f"{parcel_ulpin}-B1-F0")

    def test_legacy_string_slicing_would_have_produced_an_invalid_identifier(self):
        """Pins the import-path regression: raw slicing yields letters where digits are required."""
        legacy = ULPINService.generate_parcel_ulpin(
            state="MH", district="MU", taluk="Andheri", village="Kurla",
            survey_number="PARCEL-MU-00006",
        )
        assert legacy.startswith("MH-MU-")
        assert not ULPINService.is_candidate_format(legacy)

    def test_import_path_codes_now_produce_a_valid_candidate_ulpin(self):
        """Same real inputs the GeoJSON importer receives for Mumbai."""
        codes = assign_cadastral_codes(
            state="Maharashtra", district="Mumbai", taluk="Andheri", village="Kurla"
        )
        ulpin = ULPINService.generate_parcel_ulpin(
            state=codes.state_code,
            district=codes.district_code,
            taluk=codes.taluk_code,
            village=codes.village_code,
            survey_number="PARCEL-MU-00006",
        )
        assert ULPINService.is_candidate_format(ulpin)
        assert not ULPINService.is_official_format(ulpin)
