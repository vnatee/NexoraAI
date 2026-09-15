from io import BytesIO

import azure.core.exceptions
import azure.storage.filedatalake
import azure.storage.filedatalake.aio
import pytest
from azure.search.documents.aio import SearchClient
from azure.storage.filedatalake.aio import DataLakeDirectoryClient, DataLakeFileClient
from quart.datastructures import FileStorage

import app as app_module


# parameterize for directory existing or not
@pytest.mark.asyncio
@pytest.mark.parametrize("directory_exists", [True, False])
async def test_upload_file(auth_client, monkeypatch, mock_data_lake_service_client, directory_exists):

    async def mock_get_directory_properties(self, *args, **kwargs):
        if directory_exists:
            return None
        else:
            raise azure.core.exceptions.ResourceNotFoundError()

    monkeypatch.setattr(DataLakeDirectoryClient, "get_directory_properties", mock_get_directory_properties)

    directory_created = [False]

    async def mock_create_directory(self, *args, **kwargs):
        directory_created[0] = True

    monkeypatch.setattr(DataLakeDirectoryClient, "create_directory", mock_create_directory)

    async def mock_directory_set_access_control(self, *args, **kwargs):
        assert kwargs.get("owner") == "OID_X"
        return None

    monkeypatch.setattr(DataLakeDirectoryClient, "set_access_control", mock_directory_set_access_control)

    def mock_directory_get_file_client(self, *args, **kwargs):
        return azure.storage.filedatalake.aio.DataLakeFileClient(
            account_url="https://test.blob.core.windows.net/", file_system_name="user-content", file_path=args[0]
        )

    monkeypatch.setattr(DataLakeDirectoryClient, "get_file_client", mock_directory_get_file_client)

    async def mock_upload_file(self, *args, **kwargs):
        assert kwargs.get("overwrite") is True
        assert kwargs.get("metadata") == {"UploadedBy": "OID_X"}
        return None

    monkeypatch.setattr(DataLakeFileClient, "upload_data", mock_upload_file)

    created_jobs = []
    scheduled_jobs = []
    monkeypatch.setattr(
        app_module,
        "_resolve_upload_route",
        lambda filename, routing_context: {"status": "fallback", "source": "system_fallback"},
    )

    def mock_create_job(**kwargs):
        created_jobs.append(kwargs)
        return {"_id": "job-1"}

    monkeypatch.setattr(app_module, "create_ingestion_job", mock_create_job)
    monkeypatch.setattr(app_module, "serialize_ingestion_job", lambda job: job)
    monkeypatch.setattr(app_module, "_schedule_ingestion_job", scheduled_jobs.append)

    response = await auth_client.post(
        "/upload",
        headers={"Authorization": "Bearer test"},
        files={"file": FileStorage(BytesIO(b"foo;bar"), filename="a.txt")},
    )
    payload = await response.get_json()
    assert payload == {"message": "Upload accepted for processing", "jobs": [{"_id": "job-1"}]}
    assert response.status_code == 202
    assert created_jobs[0]["owner_id"] == "OID_X"
    assert created_jobs[0]["scope"] == "personal"
    assert created_jobs[0]["storage_path"] == "OID_X/a.txt"
    assert created_jobs[0]["routing_context"]["scope"] == "personal"
    assert scheduled_jobs == ["job-1"]
    assert directory_created[0] == (not directory_exists)


@pytest.mark.asyncio
async def test_list_uploaded(auth_client, monkeypatch, mock_data_lake_service_client):
    monkeypatch.setattr(
        app_module,
        "latest_indexed_times",
        lambda scope, paths, **kwargs: {"OID_X/a.txt": "2026-08-20T13:40:04+00:00"},
    )
    response = await auth_client.get("/list_uploaded", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert (await response.get_json()) == [
        ["a.txt", 1, "2026-08-20T13:40:04+00:00"],
        ["b.txt", 1, None],
        ["c.txt", 1, None],
    ]


@pytest.mark.asyncio
async def test_list_uploaded_nopaths(auth_client, monkeypatch, mock_data_lake_service_client):
    monkeypatch.setattr(app_module, "latest_indexed_times", lambda *args, **kwargs: {})
    class MockResponse:
        def __init__(self):
            self.reason = "No path found"
            self.status_code = 404

    class MockAsyncIteratorError:
        def __aiter__(self):
            return self

        async def __anext__(self):
            raise azure.core.exceptions.ResourceNotFoundError(
                response=azure.core.exceptions.HttpResponseError(response=MockResponse())
            )

    def mock_get_paths(self, *args, **kwargs):
        return MockAsyncIteratorError()

    monkeypatch.setattr(azure.storage.filedatalake.aio.FileSystemClient, "get_paths", mock_get_paths)

    response = await auth_client.get("/list_uploaded", headers={"Authorization": "Bearer test"})
    assert response.status_code == 200
    assert (await response.get_json()) == []


@pytest.mark.asyncio
async def test_delete_uploaded(auth_client, monkeypatch, mock_data_lake_service_client):

    async def mock_delete_file(self):
        return None

    monkeypatch.setattr(DataLakeFileClient, "delete_file", mock_delete_file)

    def mock_directory_get_file_client(self, *args, **kwargs):
        return azure.storage.filedatalake.aio.DataLakeFileClient(
            account_url="https://test.blob.core.windows.net/", file_system_name="user-content", file_path=args[0]
        )

    monkeypatch.setattr(DataLakeDirectoryClient, "get_file_client", mock_directory_get_file_client)

    class AsyncSearchResultsIterator:
        def __init__(self):
            self.results = [
                {
                    "sourcepage": "a's doc.txt",
                    "sourcefile": "a's doc.txt",
                    "content": "This is a test document.",
                    "embedding": [],
                    "category": None,
                    "id": "file-a_txt-7465737420646F63756D656E742E706466",
                    "oids": ["OID_X"],
                    "@search.score": 0.03279569745063782,
                    "@search.reranker_score": 3.4577205181121826,
                },
                {
                    "sourcepage": "a's doc.txt",
                    "sourcefile": "a's doc.txt",
                    "content": "This is a test document.",
                    "embedding": [],
                    "category": None,
                    "id": "file-a_txt-7465737420646F63756D656E742E706422",
                    "oids": [],
                    "@search.score": 0.03279569745063782,
                    "@search.reranker_score": 3.4577205181121826,
                },
                {
                    "sourcepage": "a's doc.txt",
                    "sourcefile": "a's doc.txt",
                    "content": "This is a test document.",
                    "embedding": [],
                    "category": None,
                    "id": "file-a_txt-7465737420646F63756D656E742E706433",
                    "oids": ["OID_X", "OID_Y"],
                    "@search.score": 0.03279569745063782,
                    "@search.reranker_score": 3.4577205181121826,
                },
            ]

        def __aiter__(self):
            return self

        async def __anext__(self):
            if len(self.results) == 0:
                raise StopAsyncIteration
            return self.results.pop()

        async def get_count(self):
            return len(self.results)

    search_results = AsyncSearchResultsIterator()

    searched_filters = []

    async def mock_search(self, *args, **kwargs):
        self.filter = kwargs.get("filter")
        searched_filters.append(self.filter)
        return search_results

    monkeypatch.setattr(SearchClient, "search", mock_search)

    deleted_documents = []

    async def mock_delete_documents(self, documents):
        deleted_documents.extend(documents)
        return documents

    monkeypatch.setattr(SearchClient, "delete_documents", mock_delete_documents)

    response = await auth_client.post(
        "/delete_uploaded", headers={"Authorization": "Bearer test"}, json={"filename": "a's doc.txt"}
    )
    assert response.status_code == 200
    assert len(searched_filters) == 2, "It should have searched twice (with no results on second try)"
    assert searched_filters[0] == "sourcefile eq 'a''s doc.txt'"
    assert len(deleted_documents) == 1, "It should have only deleted the document solely owned by OID_X"
    assert deleted_documents[0]["id"] == "file-a_txt-7465737420646F63756D656E742E706466"
