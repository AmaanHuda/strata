"""Unit tests for ULPIN generation logic."""
import uuid
from app.services.ulpin import _compute_ulpin


def test_ulpin_format():
    uid = uuid.uuid4()
    ulpin = _compute_ulpin("parcel", uid, "Mumbai", "Andheri", "Versova")
    assert len(ulpin) > 10
    assert ulpin[:2] == "IN"


def test_ulpin_deterministic():
    uid = uuid.uuid4()
    u1 = _compute_ulpin("building", uid)
    u2 = _compute_ulpin("building", uid)
    assert u1 == u2


def test_ulpin_different_entities():
    uid = uuid.uuid4()
    p = _compute_ulpin("parcel", uid)
    b = _compute_ulpin("building", uid)
    assert p != b
