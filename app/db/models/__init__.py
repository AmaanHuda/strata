# Import all models so Alembic can detect them
from app.db.models.user import User
from app.db.models.property import Parcel, Building, Floor, Unit
from app.db.models.ulpin import ULPINRecord
from app.db.models.audit import AuditLog
from app.db.models.job import AsyncJob
from app.db.models.dataset import DatasetRegistry
from app.db.models.provenance import ProvenanceRecord
