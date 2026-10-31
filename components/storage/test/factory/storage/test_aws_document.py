"""Tests for DynamoDB document store adapter."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from factory.storage.runtime.ports import Document, StorageHealth


@pytest.fixture
def mock_ddb():
    with patch("boto3.resource") as mr:
        table = MagicMock()
        mr.return_value.Table.return_value = table
        yield table


@pytest.fixture
def doc_store(mock_ddb):
    from factory.storage.runtime.adapters.aws_document import DynamoDBDocumentStore

    return DynamoDBDocumentStore(table_name="test-docs")


def test_doc_invalid_table_name():
    with patch("boto3.resource"):
        from factory.storage.runtime.adapters.aws_document import DynamoDBDocumentStore

        with pytest.raises(ValueError, match="Invalid table_name"):
            DynamoDBDocumentStore(table_name="bad name!!!")


def test_doc_insert(doc_store, mock_ddb):
    doc = doc_store.insert("users", {"name": "alice"}, doc_id="d1")
    assert doc.id == "d1"
    assert doc.collection == "users"
    mock_ddb.put_item.assert_called_once()


def test_doc_insert_generates_id(doc_store, mock_ddb):
    doc = doc_store.insert("users", {"name": "bob"})
    assert len(doc.id) > 0


def test_doc_get_found(doc_store, mock_ddb):
    mock_ddb.get_item.return_value = {"Item": {
        "pk": "users", "sk": "d1", "data": {"name": "alice"},
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }}
    doc = doc_store.get("users", "d1")
    assert doc is not None
    assert doc.data["name"] == "alice"


def test_doc_get_not_found(doc_store, mock_ddb):
    mock_ddb.get_item.return_value = {}
    assert doc_store.get("users", "d1") is None


def test_doc_update_found(doc_store, mock_ddb):
    mock_ddb.get_item.return_value = {"Item": {
        "pk": "users", "sk": "d1", "data": {"name": "alice"},
        "created_at": "2024-01-01T00:00:00+00:00",
        "updated_at": "2024-01-01T00:00:00+00:00",
    }}
    doc = doc_store.update("users", "d1", {"age": 30})
    assert doc is not None
    assert doc.data["age"] == 30
    assert doc.data["name"] == "alice"


def test_doc_update_not_found(doc_store, mock_ddb):
    mock_ddb.get_item.return_value = {}
    assert doc_store.update("users", "d1", {"age": 30}) is None


def test_doc_delete(doc_store, mock_ddb):
    assert doc_store.delete("users", "d1") is True
    mock_ddb.delete_item.assert_called_once()


def test_doc_find(doc_store, mock_ddb):
    mock_ddb.query.return_value = {"Items": [
        {"pk": "users", "sk": "d1", "data": {"name": "alice"},
         "created_at": "2024-01-01T00:00:00+00:00",
         "updated_at": "2024-01-01T00:00:00+00:00"},
    ]}
    with patch("boto3.dynamodb.conditions.Key") as mock_key:
        mock_key.return_value.eq.return_value = "pk = users"
        docs = doc_store.find("users", {})
    assert len(docs) == 1


def test_doc_find_with_query_filter(doc_store, mock_ddb):
    mock_ddb.query.return_value = {"Items": [
        {"pk": "users", "sk": "d1", "data": {"name": "alice"},
         "created_at": "2024-01-01T00:00:00+00:00",
         "updated_at": "2024-01-01T00:00:00+00:00"},
    ]}
    with patch("boto3.dynamodb.conditions.Key") as mock_key:
        mock_key.return_value.eq.return_value = "pk = users"
        docs = doc_store.find("users", {"name": "bob"})
    assert len(docs) == 0


def test_doc_list_collections(doc_store, mock_ddb):
    mock_ddb.scan.return_value = {"Items": [
        {"pk": "users"}, {"pk": "orders"}, {"pk": "users"},
    ]}
    cols = doc_store.list_collections()
    assert set(cols) == {"users", "orders"}


def test_doc_health_check_ok(doc_store, mock_ddb):
    type(mock_ddb).table_status = PropertyMock(return_value="ACTIVE")
    h = doc_store.health_check()
    assert h.healthy is True
    assert h.backend == "dynamodb"


def test_doc_health_check_error(doc_store, mock_ddb):
    type(mock_ddb).table_status = PropertyMock(side_effect=Exception("no table"))
    h = doc_store.health_check()
    assert h.healthy is False


def test_doc_invalid_collection(doc_store):
    with pytest.raises(ValueError, match="Invalid collection"):
        doc_store.insert("bad coll!!!", {"x": 1})


def test_doc_infrastructure_spec(doc_store):
    spec = doc_store.infrastructure_spec()
    assert spec["service"] == "dynamodb"
    assert spec["props"]["billing_mode"] == "PAY_PER_REQUEST"
