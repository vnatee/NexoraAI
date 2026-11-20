from copy import deepcopy

import pytest

from mongo_table_connecters import knowledge_metadata_profiles as profiles
from prepdocslib.searchmanager import business_metadata_document, business_metadata_fields
from prepdocslib.textsplitter import SplitPage


class Cursor:
    def __init__(self, items):
        self.items = items

    def sort(self, key, direction):
        self.items.sort(key=lambda item: item.get(key, ""), reverse=direction < 0)
        return self

    def __iter__(self):
        return iter(self.items)


class MemoryCollection:
    def __init__(self):
        self.items = {}

    def create_index(self, *args, **kwargs):
        return None

    def insert_one(self, item):
        self.items[item["_id"]] = deepcopy(item)

    def find_one(self, query):
        return next(
            (deepcopy(item) for item in self.items.values() if all(item.get(key) == value for key, value in query.items())),
            None,
        )

    def find(self, query):
        return Cursor(
            [deepcopy(item) for item in self.items.values() if all(item.get(key) == value for key, value in query.items())]
        )


def test_product_profile_is_reusable_and_team_scoped(monkeypatch):
    collection = MemoryCollection()
    monkeypatch.setattr(profiles, "collection", collection)

    first = profiles.ensure_product_knowledge_profile("team-1", "admin-1")
    second = profiles.ensure_product_knowledge_profile("team-1", "admin-2")

    assert first["_id"] == second["_id"]
    assert first["version"] == 1
    assert {field["key"] for field in first["fields"]} >= {
        "product_family",
        "document_type",
        "language",
        "lifecycle_status",
    }
    assert len(profiles.list_metadata_profiles("team-1")) == 1
    assert profiles.list_metadata_profiles("team-2") == []


def test_document_metadata_is_validated_and_normalized():
    profile = {"fields": profiles._normalize_fields(profiles.PRODUCT_KNOWLEDGE_FIELDS)}
    values = {
        "product_family": "Industrial Meter",
        "document_type": "datasheet",
        "language": "th-en",
        "lifecycle_status": "active",
        "effective_date": "2026-10-12",
    }

    normalized, searchable_text, pairs = profiles.normalize_document_metadata(profile, values)

    assert normalized["product_family"] == "Industrial Meter"
    assert "Product family: Industrial Meter" in searchable_text
    assert "document_type=datasheet" in pairs

    with pytest.raises(profiles.MetadataProfileError, match="Product family is required"):
        profiles.normalize_document_metadata(
            profile,
            {
                "document_type": "datasheet",
                "language": "en",
                "lifecycle_status": "active",
            },
        )
    with pytest.raises(profiles.MetadataProfileError, match="unsupported value"):
        profiles.normalize_document_metadata(profile, {**values, "document_type": "secret"})
    with pytest.raises(profiles.MetadataProfileError, match="unsupported metadata fields"):
        profiles.normalize_document_metadata(profile, {**values, "audience": "external"})


def test_search_document_pins_profile_version_and_business_values():
    page = SplitPage(
        page_num=0,
        text="Calibration procedure",
        metadata={
            "metadata_profile_id": "profile-1",
            "metadata_profile_version": 3,
            "business_metadata_text": "Audience: external | Product family: Meter",
            "business_metadata": {"product_family": "Meter", "active": True},
        },
    )
    page.metadata.update(
        {
            "metadata_profile_id": "profile-1",
            "metadata_profile_version": 3,
            "business_metadata_text": "Audience: external | Product family: Meter",
            "business_metadata": {"product_family": "Meter", "active": True},
        }
    )

    document = business_metadata_document(page)

    assert document == {
        "metadataProfileId": "profile-1",
        "metadataProfileVersion": 3,
        "businessMetadataText": "Audience: external | Product family: Meter",
        "businessMetadata": ["active=true", "product_family=Meter"],
    }
    assert {field.name for field in business_metadata_fields()} == {
        "metadataProfileId",
        "metadataProfileVersion",
        "businessMetadataText",
        "businessMetadata",
    }
