import copy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongo_table_connecters.agents as agents_module


def _matches(document, query):
    for key, expected in query.items():
        present = key in document
        actual = document.get(key)
        if isinstance(expected, dict):
            if "$gt" in expected and not (actual and actual > expected["$gt"]):
                return False
            if "$exists" in expected and present is not expected["$exists"]:
                return False
            if "$in" in expected and actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class FakeCollection:
    def __init__(self, documents=None):
        self.documents = [copy.deepcopy(item) for item in (documents or [])]

    def find_one(self, query):
        item = next((item for item in self.documents if _matches(item, query)), None)
        return copy.deepcopy(item) if item else None

    def find(self, query):
        return [copy.deepcopy(item) for item in self.documents if _matches(item, query)]

    def insert_one(self, document):
        self.documents.append(copy.deepcopy(document))
        return SimpleNamespace(inserted_id=document.get("_id"))

    def insert_many(self, documents):
        self.documents.extend(copy.deepcopy(list(documents)))

    def update_one(self, query, update):
        for item in self.documents:
            if not _matches(item, query):
                continue
            before = copy.deepcopy(item)
            item.update(copy.deepcopy(update.get("$set") or {}))
            for key in update.get("$unset") or {}:
                item.pop(key, None)
            return SimpleNamespace(modified_count=int(item != before), matched_count=1)
        return SimpleNamespace(modified_count=0, matched_count=0)

    def delete_one(self, query):
        for index, item in enumerate(self.documents):
            if _matches(item, query):
                self.documents.pop(index)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)

    def delete_many(self, query):
        retained = [item for item in self.documents if not _matches(item, query)]
        deleted = len(self.documents) - len(retained)
        self.documents = retained
        return SimpleNamespace(deleted_count=deleted)


def test_agent_revision_clones_and_atomically_promotes_agent_and_bindings(monkeypatch):
    updated_at = datetime.utcnow()
    active = {
        "_id": "active-1",
        "agent_name": "Active",
        "prompt": {"task": "old"},
        "config": {"runtime": "langgraph", "temperature": 0.2},
        "lifecycle_status": "active",
        "delete_at": None,
        "update_at": updated_at,
    }
    collections = {
        "agents": FakeCollection([active]),
        **{
            name: FakeCollection(
                [{"_id": f"{name}-old", "agent_id": "active-1", "delete_at": None, "enabled": True}]
            )
            for name in agents_module.AGENT_BINDING_COLLECTIONS
        },
    }
    monkeypatch.setattr(agents_module, "db", collections)
    monkeypatch.setattr(agents_module, "agents_collection", collections["agents"])

    revision, created = agents_module.create_or_resume_agent_revision(
        active,
        created_by="manager-1",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
    )

    assert created is True
    assert revision["revision_of"] == "active-1"
    for name in agents_module.AGENT_BINDING_COLLECTIONS:
        cloned = collections[name].find({"agent_id": revision["_id"]})
        assert len(cloned) == 1
        assert cloned[0]["_id"] != f"{name}-old"

    revision["agent_name"] = "Revised"
    revision["prompt"] = {"task": "new"}
    revision["config"] = {"runtime": "langgraph", "temperature": 0.7}
    first_collection = collections[agents_module.AGENT_BINDING_COLLECTIONS[0]]
    first_collection.delete_many({"agent_id": revision["_id"]})

    published = agents_module.publish_agent_revision(revision, active)

    assert published["_id"] == "active-1"
    assert published["agent_name"] == "Revised"
    assert published["prompt"] == {"task": "new"}
    assert published["config"]["temperature"] == 0.7
    assert collections["agents"].find_one({"_id": revision["_id"]}) is None
    assert first_collection.find({"agent_id": "active-1"}) == []
    for name in agents_module.AGENT_BINDING_COLLECTIONS[1:]:
        promoted = collections[name].find({"agent_id": "active-1"})
        assert len(promoted) == 1
        assert collections[name].find({"agent_id": revision["_id"]}) == []


def test_agent_revision_publish_rejects_stale_active_agent(monkeypatch):
    active = {
        "_id": "active-1",
        "lifecycle_status": "active",
        "delete_at": None,
        "update_at": datetime.utcnow(),
    }
    revision = {
        "_id": "revision-1",
        "revision_of": "active-1",
        "revision_base_updated_at": datetime.utcnow() - timedelta(minutes=1),
    }
    collections = {
        "agents": FakeCollection([active, revision]),
        **{name: FakeCollection() for name in agents_module.AGENT_BINDING_COLLECTIONS},
    }
    monkeypatch.setattr(agents_module, "db", collections)
    monkeypatch.setattr(agents_module, "agents_collection", collections["agents"])

    try:
        agents_module.publish_agent_revision(revision, active)
    except ValueError as error:
        assert "changed after this revision" in str(error)
    else:
        raise AssertionError("stale revision should not publish")


def test_agent_revision_publish_rolls_back_bindings_when_final_update_fails(monkeypatch):
    updated_at = datetime.utcnow()
    active = {
        "_id": "active-1",
        "lifecycle_status": "active",
        "delete_at": None,
        "update_at": updated_at,
    }
    revision = {
        "_id": "revision-1",
        "revision_of": "active-1",
        "revision_base_updated_at": updated_at,
        "agent_name": "Revised",
        "prompt": {},
        "config": {},
    }

    class LostLockCollection(FakeCollection):
        failed_final_update = False

        def update_one(self, query, update):
            if isinstance(query.get("publish_lock"), str) and not self.failed_final_update:
                self.failed_final_update = True
                return SimpleNamespace(modified_count=0, matched_count=0)
            return super().update_one(query, update)

    agent_collection = LostLockCollection([active, revision])
    collections = {
        "agents": agent_collection,
        **{
            name: FakeCollection(
                [
                    {"_id": f"{name}-active", "agent_id": "active-1"},
                    {"_id": f"{name}-revision", "agent_id": "revision-1"},
                ]
            )
            for name in agents_module.AGENT_BINDING_COLLECTIONS
        },
    }
    monkeypatch.setattr(agents_module, "db", collections)
    monkeypatch.setattr(agents_module, "agents_collection", agent_collection)

    try:
        agents_module.publish_agent_revision(revision, active)
    except RuntimeError as error:
        assert "publish lock was lost" in str(error)
    else:
        raise AssertionError("lost publish lock should roll back")

    assert "publish_lock" not in agent_collection.find_one({"_id": "active-1"})
    for name in agents_module.AGENT_BINDING_COLLECTIONS:
        assert [item["_id"] for item in collections[name].find({"agent_id": "active-1"})] == [
            f"{name}-active"
        ]
        assert [item["_id"] for item in collections[name].find({"agent_id": "revision-1"})] == [
            f"{name}-revision"
        ]
