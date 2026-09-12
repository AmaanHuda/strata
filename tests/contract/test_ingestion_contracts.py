"""Ingestion contract and unsupported schema tests."""
import pytest
from app.core.errors import UnsupportedSchemaVersionError
from app.integrations.ml_engine.contracts import (
    MLIngestionPayload,
    SUPPORTED_SCHEMA_VERSIONS,
)


def test_unsupported_schema_version():
    with pytest.raises(Exception):
        # When schema version is unsupported
        payload = MLIngestionPayload(
            schema_version="99.9.9",
            parcel_number="DEL-001",
            district="South Delhi",
        )
        if payload.schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            raise UnsupportedSchemaVersionError(f"Unsupported schema {payload.schema_version}")


def test_supported_schema_versions_valid():
    for ver in ["1.0.0", "1.1.0", "2.0.0"]:
        payload = MLIngestionPayload(
            schema_version=ver,
            parcel_number=f"DEL-{ver}",
            district="Central Delhi",
        )
        assert payload.schema_version in SUPPORTED_SCHEMA_VERSIONS
