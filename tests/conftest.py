"""Shared test fixtures."""
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pytest
import pytest_asyncio

# Set required env vars BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_db")
os.environ.setdefault("SECRET_KEY", "test_secret_key_at_least_32_chars_long_here")

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.models.job import AsyncJob
from app.db.session import get_db


class MockQueryResult:
    def __init__(self, items: Optional[List[Any]] = None):
        self._items = items if items is not None else []

    def first(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._items[0] if self._items else None

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar_one(self):
        return self._items[0] if self._items else 0

    def scalars(self):
        return self

    def all(self):
        return list(self._items)

    def __iter__(self):
        return iter(self._items)


class MockDbStore:
    def __init__(self):
        self.entities: Dict[uuid.UUID, Any] = {}

    def get(self, model, ident):
        try:
            u_ident = uuid.UUID(str(ident))
            return self.entities.get(u_ident)
        except Exception:
            return self.entities.get(ident)

    def save(self, instance):
        if not hasattr(instance, "id") or getattr(instance, "id", None) is None:
            instance.id = uuid.uuid4()
        if hasattr(instance, "created_at") and getattr(instance, "created_at", None) is None:
            instance.created_at = datetime.now(timezone.utc)
        if hasattr(instance, "updated_at") and getattr(instance, "updated_at", None) is None:
            instance.updated_at = datetime.now(timezone.utc)
        if hasattr(instance, "retry_count") and getattr(instance, "retry_count", None) is None:
            instance.retry_count = 0
        if hasattr(instance, "max_retries") and getattr(instance, "max_retries", None) is None:
            instance.max_retries = 3
        if hasattr(instance, "progress") and getattr(instance, "progress", None) is None:
            instance.progress = 0.0
        self.entities[instance.id] = instance
        return instance


_global_test_store = MockDbStore()


class MockAsyncSession:
    def __init__(self, store: MockDbStore):
        self._store = store

    async def execute(self, statement, *args, **kwargs):
        stmt_str = str(statement).lower()
        if "from async_jobs" in stmt_str:
            jobs = [v for v in self._store.entities.values() if isinstance(v, AsyncJob)]
            # Check by ID
            if "async_jobs.id =" in stmt_str or "async_jobs.id ==" in stmt_str:
                target_id = None
                if hasattr(statement, "compile"):
                    for val in statement.compile().params.values():
                        try:
                            target_id = uuid.UUID(str(val))
                            break
                        except Exception:
                            pass
                if target_id and target_id in self._store.entities:
                    return MockQueryResult([self._store.entities[target_id]])
                return MockQueryResult([])

            # Check by idempotency_key
            if "idempotency_key" in stmt_str:
                target_key = None
                if hasattr(statement, "compile"):
                    for val in statement.compile().params.values():
                        if isinstance(val, str) and len(val) > 0:
                            target_key = val
                            break
                if target_key:
                    matching = [j for j in jobs if getattr(j, "idempotency_key", None) == target_key]
                    return MockQueryResult(matching)
                return MockQueryResult([])

            # Check status filter
            if "status =" in stmt_str or "status ==" in stmt_str:
                target_status = None
                if hasattr(statement, "compile"):
                    for val in statement.compile().params.values():
                        if str(val).upper() in ["QUEUED", "PROCESSING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]:
                            target_status = str(val).upper()
                            break
                if target_status:
                    matching = [j for j in jobs if getattr(j, "status", None) == target_status]
                    return MockQueryResult(matching)

            return MockQueryResult(jobs)
        if "from parcels" in stmt_str:
            from app.db.models.property import Parcel
            if "parcels.id =" in stmt_str or "parcels.id ==" in stmt_str:
                target_id = None
                if hasattr(statement, "compile"):
                    for val in statement.compile().params.values():
                        try:
                            target_id = uuid.UUID(str(val))
                            break
                        except Exception:
                            pass
                if target_id and target_id in self._store.entities:
                    return MockQueryResult([self._store.entities[target_id]])
                return MockQueryResult([])
            return MockQueryResult([])

        if "from buildings" in stmt_str:
            from app.db.models.property import Building
            bldgs = [v for v in self._store.entities.values() if isinstance(v, Building)]
            if "buildings.id =" in stmt_str or "buildings.id ==" in stmt_str:
                target_id = None
                if hasattr(statement, "compile"):
                    for val in statement.compile().params.values():
                        try:
                            target_id = uuid.UUID(str(val))
                            break
                        except Exception:
                            pass
                if target_id and target_id in self._store.entities:
                    return MockQueryResult([self._store.entities[target_id]])
                return MockQueryResult([])
            return MockQueryResult(bldgs)
        if "from ulpin_records" in stmt_str:
            from app.db.models.ulpin import ULPINRecord
            records = [v for v in self._store.entities.values() if isinstance(v, ULPINRecord)]
            target_val = None
            if hasattr(statement, "compile"):
                for val in statement.compile().params.values():
                    if isinstance(val, str) and len(val) > 0:
                        target_val = val
                        break
            if target_val:
                matching = [
                    r for r in records
                    if getattr(r, "official_ulpin", None) == target_val
                    or getattr(r, "candidate_ulpin", None) == target_val
                ]
                return MockQueryResult(matching)
            return MockQueryResult(records)

        if "count(" in stmt_str:
            return MockQueryResult([len(self._store.entities)])
        return MockQueryResult([])


    def begin_nested(self):
        class MockNested:
            async def __aenter__(self_nested):
                return self_nested
            async def __aexit__(self_nested, exc_type, exc_val, exc_tb):
                pass
        return MockNested()

    async def get(self, entity, ident):
        return self._store.get(entity, ident)

    def add(self, instance):
        self._store.save(instance)

    async def flush(self):
        pass

    async def refresh(self, instance):
        self._store.save(instance)

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def delete(self, instance):
        if hasattr(instance, "id") and instance.id in self._store.entities:
            del self._store.entities[instance.id]

    async def close(self):
        pass



@pytest.fixture(autouse=True)
def mock_db_override():
    """Overrides get_db with in-memory MockAsyncSession for all tests."""
    _global_test_store.entities.clear()
    async def _override_get_db():
        session = MockAsyncSession(_global_test_store)
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    _global_test_store.entities.clear()



@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def client_with_auth():
    """
    AsyncClient for the endpoint suites that used to need a signed-in user.

    Sign-in was removed from STRATA, so endpoints no longer authenticate. This is
    now a plain client, keeping the name so those suites stay untouched.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest.fixture
def auth_headers():
    """
    Was an Authorization header plus an auth dependency override. With sign-in
    removed the endpoints read no header, so tests can keep passing this along.
    """
    yield {}