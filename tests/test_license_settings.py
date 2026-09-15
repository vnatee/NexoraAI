import base64
import json
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from mongo_table_connecters import license_settings


class _Result:
    def __init__(self, matched_count=0, upserted_id=None):
        self.matched_count = matched_count
        self.upserted_id = upserted_id


class _Collection:
    def __init__(self):
        self.documents = {}
        self.indexes = []

    def find_one(self, query):
        document = self.documents.get(query.get("_id"))
        if not document:
            return None
        for key, expected in query.items():
            if key == "_id":
                continue
            if isinstance(expected, dict) and "$exists" in expected:
                if (key in document) != expected["$exists"]:
                    return None
            elif document.get(key) != expected:
                return None
        return dict(document)

    def update_one(self, query, update, upsert=False):
        document = self.find_one(query)
        inserted = document is None and query.get("_id") not in self.documents
        if document is None:
            if not upsert or query.get("_id") in self.documents:
                return _Result()
            document = {"_id": query["_id"]}
        if inserted:
            document.update(update.get("$setOnInsert", {}))
        document.update(update.get("$set", {}))
        self.documents[document["_id"]] = document
        return _Result(matched_count=0 if inserted else 1, upserted_id=document["_id"] if inserted else None)

    def insert_one(self, document):
        self.documents[document["_id"]] = dict(document)

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))


def _signed_license(installation_id: str):
    private_key = Ed25519PrivateKey.generate()
    payload = {
        "schema_version": 1,
        "license_id": "license-001",
        "customer_id": "customer-001",
        "product": "nexoraai",
        "edition": "enterprise",
        "issuer": "nexora",
        "key_id": "vendor-2026",
        "not_before": "2026-09-01T00:00:00Z",
        "expires_at": "2027-09-01T00:00:00Z",
        "grace_days": 14,
        "features": {"mcp": True, "ocr": True},
        "capacities": {"users": 100, "teams": 10},
        "installation_id": installation_id,
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    ).rstrip(b"=").decode("ascii")
    signature = base64.urlsafe_b64encode(private_key.sign(encoded.encode("ascii"))).rstrip(b"=").decode("ascii")
    return f"NX1.{encoded}.{signature}", {"vendor-2026": private_key.public_key()}


def _configure(monkeypatch):
    settings = _Collection()
    audit = _Collection()
    monkeypatch.setattr(license_settings, "collection", settings)
    monkeypatch.setattr(license_settings, "audit_collection", audit)
    monkeypatch.setenv("APP_DATA_ENCRYPTION_KEY", Fernet.generate_key().decode("ascii"))
    return settings, audit


def test_installation_id_is_stable_and_trial_starts_only_once(monkeypatch):
    settings, audit = _configure(monkeypatch)
    first_id = license_settings.get_or_create_installation_id()
    assert license_settings.get_or_create_installation_id() == first_id

    start = datetime(2026, 9, 8, tzinfo=timezone.utc)
    first = license_settings.start_trial(actor_id="admin-1", now=start)
    second = license_settings.start_trial(actor_id="admin-2", now=start + timedelta(days=2))

    assert first["status"] == "active"
    assert first["trial"]["duration_days"] == 14
    assert second["trial"]["started_at"] == first["trial"]["started_at"]
    assert len([value for value in audit.documents.values() if value["action"] == "trial_started"]) == 1
    assert settings.documents[license_settings.INSTALLATION_ID]["installation_id"] == first_id


def test_trial_expires_without_being_reset(monkeypatch):
    _configure(monkeypatch)
    start = datetime(2026, 9, 8, tzinfo=timezone.utc)
    license_settings.start_trial(actor_id="admin-1", now=start)

    status = license_settings.get_license_status({}, now=start + timedelta(days=15))

    assert status["status"] == "expired"
    assert status["reason"] == "trial_expired"
    assert status["trial_available"] is False


def test_trial_status_accepts_pymongo_naive_utc_datetimes(monkeypatch):
    settings, _audit = _configure(monkeypatch)
    start = datetime(2026, 9, 8, tzinfo=timezone.utc)
    license_settings.start_trial(actor_id="admin-1", now=start)
    stored = settings.documents[license_settings.SETTINGS_ID]
    stored["trial_started_at"] = stored["trial_started_at"].replace(tzinfo=None)
    stored["trial_expires_at"] = stored["trial_expires_at"].replace(tzinfo=None)

    status = license_settings.get_license_status({}, now=start + timedelta(days=1))

    assert status["status"] == "active"
    assert status["trial"]["started_at"] == "2026-09-08T00:00:00+00:00"
    assert status["trial"]["expires_at"] == "2026-09-22T00:00:00+00:00"


def test_import_encrypts_raw_key_and_returns_only_safe_claims(monkeypatch):
    settings, audit = _configure(monkeypatch)
    installation_id = license_settings.get_or_create_installation_id()
    raw_license, public_keys = _signed_license(installation_id)

    imported = license_settings.import_license(
        raw_license,
        public_keys,
        actor_id="admin-1",
        now=datetime(2026, 9, 8, tzinfo=timezone.utc),
    )
    stored = settings.documents[license_settings.SETTINGS_ID]
    restored = license_settings.get_license_status(
        public_keys,
        now=datetime(2026, 9, 9, tzinfo=timezone.utc),
    )

    assert imported["status"] == "active"
    assert imported["license"]["features"] == {"mcp": True, "ocr": True}
    assert restored["license"]["license_id"] == "license-001"
    assert raw_license not in str(stored)
    assert "license_key" not in str(imported)
    assert next(iter(audit.documents.values()))["license_id"] == "license-001"


def test_license_for_another_installation_is_rejected(monkeypatch):
    _configure(monkeypatch)
    raw_license, public_keys = _signed_license("different-installation")

    try:
        license_settings.import_license(
            raw_license,
            public_keys,
            actor_id="admin-1",
            now=datetime(2026, 9, 8, tzinfo=timezone.utc),
        )
    except ValueError as error:
        assert "installation_mismatch" in str(error)
    else:
        raise AssertionError("installation mismatch should be rejected")


def test_missing_license_is_unlicensed_and_trial_is_available(monkeypatch):
    _configure(monkeypatch)

    status = license_settings.get_license_status({}, now=datetime(2026, 9, 8, tzinfo=timezone.utc))

    assert status["status"] == "unlicensed"
    assert status["trial_available"] is True
    assert status["audit_mode"] is True
