from copy import deepcopy

import pytest

from mongo_table_connecters import data_group


class _Result:
    def __init__(self, modified_count=0):
        self.modified_count = modified_count


class _Collection:
    def __init__(self, document):
        self.document = deepcopy(document)

    def find_one(self, query):
        if self.document.get("_id") != query.get("_id"):
            return None
        if (
            query.get("delete_at") is None
            and self.document.get("delete_at") is not None
        ):
            return None
        return deepcopy(self.document)

    def update_one(self, query, update):
        if self.document.get("_id") != query.get("_id"):
            return _Result()
        self.document.update(deepcopy(update.get("$set") or {}))
        push = (update.get("$push") or {}).get("publication_history") or {}
        events = deepcopy(push.get("$each") or [])
        history = [*(self.document.get("publication_history") or []), *events]
        self.document["publication_history"] = history[
            int(push.get("$slice") or -100) :
        ]
        return _Result(1)


def _document():
    return {
        "_id": "group-1",
        "delete_at": None,
        "name": "Customer product knowledge",
        "access_mode": "team",
        "user_id": [],
        "exposure": "external",
        "publication_status": "draft",
        "publication_version": 0,
        "publication_history": [],
    }


def test_external_publication_increments_version_and_retire_removes_access(
    monkeypatch,
):
    collection = _Collection(_document())
    monkeypatch.setattr(data_group, "data_groups_collection", collection)

    assert data_group.update_data_group_publication(
        "group-1",
        exposure="external",
        publication_status="published",
        actor_id="admin-1",
    )
    assert collection.document["publication_status"] == "published"
    assert collection.document["publication_version"] == 1
    assert collection.document["published_by"] == "admin-1"
    assert len(collection.document["publication_history"]) == 1

    assert data_group.update_data_group_publication(
        "group-1",
        exposure="external",
        publication_status="retired",
        actor_id="admin-1",
    )
    assert collection.document["publication_status"] == "retired"
    assert collection.document["published_at"] is None
    assert collection.document["published_by"] is None
    assert len(collection.document["publication_history"]) == 2


def test_external_publication_rejects_unknown_status(monkeypatch):
    monkeypatch.setattr(
        data_group, "data_groups_collection", _Collection(_document())
    )

    with pytest.raises(ValueError, match="publication status"):
        data_group.update_data_group_publication(
            "group-1",
            exposure="external",
            publication_status="approved_without_review",
            actor_id="admin-1",
        )
