from types import SimpleNamespace

from mongo_table_connecters import agents


class _Collection:
    def __init__(self, deleted=0):
        self.deleted = deleted
        self.deleted_queries = []
        self.updated = []
        self.inserted = []

    def delete_many(self, query):
        self.deleted_queries.append(query)
        return SimpleNamespace(deleted_count=self.deleted)

    def delete_one(self, query):
        self.deleted_queries.append(query)
        return SimpleNamespace(deleted_count=self.deleted)

    def update_many(self, query, update):
        self.updated.append((query, update))
        return SimpleNamespace(modified_count=1)

    def insert_one(self, document):
        self.inserted.append(document)
        return SimpleNamespace(inserted_id=document["_id"])


class _Database:
    def __init__(self):
        self.collections = {
            name: _Collection(deleted=1)
            for name in (*agents.AGENT_BINDING_COLLECTIONS, "teams", "agents", "agent_lifecycle_audit")
        }

    def __getitem__(self, name):
        return self.collections[name]


def test_delete_agent_cascade_removes_bindings_team_reference_and_records_metadata(monkeypatch):
    database = _Database()
    monkeypatch.setattr(agents, "db", database)
    monkeypatch.setattr(agents, "agents_collection", database["agents"])

    counts = agents.delete_agent_cascade(
        "draft-1",
        reason="draft_expired",
        actor_id=None,
    )

    assert counts["agents"] == 1
    assert all(
        collection.deleted_queries == [{"agent_id": "draft-1"}]
        for name, collection in database.collections.items()
        if name in agents.AGENT_BINDING_COLLECTIONS
    )
    assert database["teams"].updated == [
        ({"agent_id": "draft-1"}, {"$pull": {"agent_id": "draft-1"}})
    ]
    event = database["agent_lifecycle_audit"].inserted[0]
    assert event["event_type"] == "agent_deleted"
    assert event["reason"] == "draft_expired"
    assert "prompt" not in event


def test_legacy_agent_without_lifecycle_status_remains_active():
    assert agents.is_active_agent({"_id": "legacy-1"}) is True
    assert agents.is_active_agent({"_id": "draft-1", "lifecycle_status": "draft"}) is False
