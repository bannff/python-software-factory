"""AWS Lambda + SQS worker adapter.

Implements WorkerPort protocol using Lambda for task execution
and SQS for task queuing. Lambda is serverless so start() is a no-op.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ...core import TaskInfo, WorkerHealth
from . import QUEUE_URL_RE, require_boto3

logger = logging.getLogger(__name__)

_FUNC_RE = __import__("re").compile(r"^[A-Za-z0-9_-]{1,140}$")


class AWSWorkerAdapter:
    """Worker adapter using AWS Lambda + SQS."""

    def __init__(
        self,
        function_name: str,
        queue_url: str = "",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        require_boto3()
        if not _FUNC_RE.match(function_name):
            raise ValueError(f"Invalid function_name: {function_name!r}")
        if queue_url and not QUEUE_URL_RE.match(queue_url):
            raise ValueError(f"Invalid queue_url: {queue_url!r}")
        import boto3
        self._lambda = boto3.client("lambda", region_name=region)
        self._sqs = boto3.client("sqs", region_name=region) if queue_url else None
        self._function_name = function_name
        self._queue_url = queue_url
        self._region = region

    @property
    def backend_type(self) -> str:
        return "aws_lambda"

    def start(self, queues: list[str] | None = None) -> None:
        """No-op — Lambda is serverless, no worker process to start."""
        logger.info("AWS Lambda worker: no process to start (serverless)")

    def health_check(self) -> WorkerHealth:
        try:
            resp = self._lambda.get_function(FunctionName=self._function_name)
            state = resp.get("Configuration", {}).get("State", "Unknown")
            return WorkerHealth(
                healthy=state == "Active",
                backend="aws_lambda",
                queues=[self._queue_url] if self._queue_url else [],
            )
        except Exception as e:
            return WorkerHealth(
                healthy=False, backend="aws_lambda", error=str(e),
            )

    def list_tasks(self) -> list[TaskInfo]:
        """List recent SQS messages as pending tasks."""
        if not self._sqs or not self._queue_url:
            return []
        try:
            resp = self._sqs.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=0,
                AttributeNames=["All"],
            )
            tasks = []
            for msg in resp.get("Messages", []):
                body = json.loads(msg.get("Body", "{}"))
                tasks.append(TaskInfo(
                    name=body.get("task_name", "unknown"),
                    queue=self._queue_url.rsplit("/", 1)[-1],
                    state="PENDING",
                ))
            return tasks
        except Exception as e:
            logger.warning("Failed to list SQS tasks: %s", e)
            return []

    def send_task(
        self, name: str, args: tuple = (), kwargs: dict | None = None,
    ) -> Any:
        """Invoke Lambda function with task payload."""
        payload = json.dumps({
            "task_name": name, "args": list(args), "kwargs": kwargs or {},
        })
        resp = self._lambda.invoke(
            FunctionName=self._function_name,
            InvocationType="Event",
            Payload=payload.encode(),
        )
        return {
            "task_id": resp.get("ResponseMetadata", {}).get("RequestId", ""),
            "status": "dispatched",
            "status_code": resp.get("StatusCode"),
        }

    def infrastructure_spec(self) -> dict[str, Any]:
        resources: list[dict] = [{
            "type": "AWS::Lambda::Function",
            "properties": {
                "FunctionName": self._function_name,
                "Region": self._region,
            },
        }]
        if self._queue_url:
            resources.append({
                "type": "AWS::SQS::Queue",
                "properties": {"QueueUrl": self._queue_url},
            })
        return {"provider": "aws", "services": ["lambda", "sqs"], "resources": resources}
