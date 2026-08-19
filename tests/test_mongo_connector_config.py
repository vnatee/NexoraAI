from mongo_table_connecters.mongo_connector import DB_NAME, MONGO_URI, get_database


def test_mongo_connector_accepts_standard_local_uri():
    assert MONGO_URI == "mongodb://localhost:27017"
    assert DB_NAME == "nexora_test"
    assert get_database().name == "nexora_test"
