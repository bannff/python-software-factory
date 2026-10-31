"""AWS Aurora Serverless SQL adapter via Data API.

Implements SQLStore protocol using boto3 rds-data client.
"""

from __future__ import annotations

import re
import time
from typing import Any

from factory.storage.runtime.ports import SQLResult, StorageHealth

_SAFE_ARN = re.compile(r"^arn:aws:[\w\-:/]+$")
_SAFE_DB_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for Aurora Data API adapter"
        raise ImportError(msg)


def _validate_arn(value: str) -> str:
    if not _SAFE_ARN.match(value):
        raise ValueError(f"Invalid ARN: {value!r}")
    return value


class AuroraDataAPISQLStore:
    """Aurora Serverless Data API implementation of SQLStore port."""

    def __init__(
        self,
        cluster_arn: str,
        secret_arn: str,
        database: str = "postgres",
        region: str = "us-east-1",
    ) -> None:
        _require_boto3()
        import boto3

        self._cluster_arn = _validate_arn(cluster_arn)
        self._secret_arn = _validate_arn(secret_arn)
        if not _SAFE_DB_NAME.match(database):
            raise ValueError(f"Invalid database name: {database!r}")
        self._database = database
        self._region = region
        self._client = boto3.client("rds-data", region_name=region)

    def _exec(self, sql: str, params: list[dict] | None = None) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "resourceArn": self._cluster_arn,
            "secretArn": self._secret_arn,
            "database": self._database,
            "sql": sql,
            "includeResultMetadata": True,
        }
        if params:
            kwargs["parameters"] = params
        return self._client.execute_statement(**kwargs)

    @staticmethod
    def _to_params(d: dict[str, Any]) -> list[dict]:
        out = []
        for k, v in d.items():
            param: dict[str, Any] = {"name": k}
            if isinstance(v, int):
                param["value"] = {"longValue": v}
            elif isinstance(v, float):
                param["value"] = {"doubleValue": v}
            elif isinstance(v, bool):
                param["value"] = {"booleanValue": v}
            elif v is None:
                param["value"] = {"isNull": True}
            else:
                param["value"] = {"stringValue": str(v)}
            out.append(param)
        return out

    @staticmethod
    def _extract_value(field: dict[str, Any]) -> Any:
        if "isNull" in field and field["isNull"]:
            return None
        for key in ("longValue", "doubleValue", "stringValue", "booleanValue", "blobValue"):
            if key in field:
                return field[key]
        return None

    def _parse_result(self, resp: dict[str, Any]) -> SQLResult:
        meta = resp.get("columnMetadata", [])
        columns = [c.get("name", "") for c in meta]
        records = resp.get("records", [])
        rows = [
            {columns[i]: self._extract_value(f) for i, f in enumerate(rec)}
            for rec in records
        ]
        return SQLResult(rows=rows, row_count=resp.get("numberOfRecordsUpdated", len(rows)),
                         columns=columns)

    def execute(self, query: str, params: dict[str, Any] | None = None) -> SQLResult:
        api_params = self._to_params(params) if params else None
        resp = self._exec(query, api_params)
        return self._parse_result(resp)

    def execute_many(self, query: str, params_list: list[dict[str, Any]]) -> int:
        param_sets = [self._to_params(p) for p in params_list]
        resp = self._client.batch_execute_statement(
            resourceArn=self._cluster_arn,
            secretArn=self._secret_arn,
            database=self._database,
            sql=query,
            parameterSets=param_sets,
        )
        return len(resp.get("updateResults", []))

    def fetch_one(self, query: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        result = self.execute(query, params)
        return result.rows[0] if result.rows else None

    def fetch_all(self, query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        return self.execute(query, params).rows

    def table_exists(self, table_name: str) -> bool:
        result = self.fetch_one(
            "SELECT 1 FROM information_schema.tables WHERE table_name = :name",
            {"name": table_name},
        )
        return result is not None

    def health_check(self) -> StorageHealth:
        start = time.time()
        try:
            self.execute("SELECT 1")
            latency = (time.time() - start) * 1000
            return StorageHealth(healthy=True, backend="aurora-data-api", latency_ms=latency,
                                 details={"database": self._database, "region": self._region})
        except Exception as e:
            return StorageHealth(healthy=False, backend="aurora-data-api", message=str(e))

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "aurora-serverless",
            "construct": "ServerlessCluster",
            "props": {
                "engine": "aurora-postgresql",
                "enable_data_api": True,
                "default_database_name": self._database,
                "scaling": {"min_capacity": 2, "max_capacity": 16},
            },
        }
