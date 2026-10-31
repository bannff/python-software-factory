"""Tests for Aurora Data API SQL store adapter."""

import pytest
from unittest.mock import MagicMock, patch

from factory.storage.runtime.ports import SQLResult, StorageHealth


@pytest.fixture
def mock_rds():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def sql_store(mock_rds):
    from factory.storage.runtime.adapters.aws_sql import AuroraDataAPISQLStore

    return AuroraDataAPISQLStore(
        cluster_arn="arn:aws:rds:us-east-1:123456789012:cluster:my-cluster",
        secret_arn="arn:aws:secretsmanager:us-east-1:123456789012:secret:my-secret",
        database="testdb",
    )


def test_sql_invalid_cluster_arn(mock_rds):
    from factory.storage.runtime.adapters.aws_sql import AuroraDataAPISQLStore

    with pytest.raises(ValueError, match="Invalid ARN"):
        AuroraDataAPISQLStore(
            cluster_arn="bad",
            secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:s",
        )


def test_sql_invalid_db_name(mock_rds):
    from factory.storage.runtime.adapters.aws_sql import AuroraDataAPISQLStore

    with pytest.raises(ValueError, match="Invalid database name"):
        AuroraDataAPISQLStore(
            cluster_arn="arn:aws:rds:us-east-1:123:cluster:c",
            secret_arn="arn:aws:secretsmanager:us-east-1:123:secret:s",
            database="123bad",
        )


def test_sql_execute(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [{"name": "id"}, {"name": "val"}],
        "records": [[{"longValue": 1}, {"stringValue": "hello"}]],
        "numberOfRecordsUpdated": 0,
    }
    result = sql_store.execute("SELECT * FROM t")
    assert isinstance(result, SQLResult)
    assert result.rows[0]["id"] == 1
    assert result.rows[0]["val"] == "hello"


def test_sql_execute_with_params(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [{"name": "n"}],
        "records": [[{"stringValue": "x"}]],
        "numberOfRecordsUpdated": 0,
    }
    result = sql_store.execute("SELECT :name", {"name": "x"})
    assert len(result.rows) == 1


def test_sql_fetch_one_found(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [{"name": "id"}],
        "records": [[{"longValue": 42}]],
        "numberOfRecordsUpdated": 0,
    }
    assert sql_store.fetch_one("SELECT 1") == {"id": 42}


def test_sql_fetch_one_empty(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [{"name": "id"}], "records": [],
        "numberOfRecordsUpdated": 0,
    }
    assert sql_store.fetch_one("SELECT 1 WHERE false") is None


def test_sql_execute_many(sql_store):
    sql_store._client.batch_execute_statement.return_value = {
        "updateResults": [{}, {}],
    }
    count = sql_store.execute_many(
        "INSERT INTO t VALUES(:v)", [{"v": 1}, {"v": 2}],
    )
    assert count == 2


def test_sql_table_exists_true(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [{"name": "?column?"}],
        "records": [[{"longValue": 1}]],
        "numberOfRecordsUpdated": 0,
    }
    assert sql_store.table_exists("my_table") is True


def test_sql_table_exists_false(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [], "records": [], "numberOfRecordsUpdated": 0,
    }
    assert sql_store.table_exists("nope") is False


def test_sql_health_check_ok(sql_store):
    sql_store._client.execute_statement.return_value = {
        "columnMetadata": [{"name": "?column?"}],
        "records": [[{"longValue": 1}]],
        "numberOfRecordsUpdated": 0,
    }
    h = sql_store.health_check()
    assert h.healthy is True
    assert h.backend == "aurora-data-api"


def test_sql_health_check_error(sql_store):
    sql_store._client.execute_statement.side_effect = Exception("conn fail")
    h = sql_store.health_check()
    assert h.healthy is False


def test_sql_extract_null():
    from factory.storage.runtime.adapters.aws_sql import AuroraDataAPISQLStore

    assert AuroraDataAPISQLStore._extract_value({"isNull": True}) is None


def test_sql_to_params():
    from factory.storage.runtime.adapters.aws_sql import AuroraDataAPISQLStore

    params = AuroraDataAPISQLStore._to_params(
        {"i": 1, "f": 2.5, "b": True, "n": None, "s": "hi"},
    )
    assert len(params) == 5


def test_sql_infrastructure_spec(sql_store):
    spec = sql_store.infrastructure_spec()
    assert spec["service"] == "aurora-serverless"
    assert spec["props"]["enable_data_api"] is True
