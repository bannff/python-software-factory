"""ECS Fargate + SQS long-poll worker adapter.

Implements WorkerPort protocol for Fargate tasks that consume SQS
messages and execute MCP tools or Strands swarm workflows in-process.
Unlike the Lambda adapter, start() runs a blocking poll loop.
"""

from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any

from ...core import TaskInfo, WorkerHealth
from . import QUEUE_URL_RE, require_boto3

logger = logging.getLogger(__name__)


class FargateSQSAdapter:
    """Worker adapter: SQS long-poll → in-process MCP tool execution.

    Designed for ECS Fargate tasks running companion-x in worker mode.
    Consumes messages, dispatches to the MCP bridge, deletes on success.
    """

    def __init__(
        self,
        queue_url: str,
        region: str = "us-east-1",
        wait_seconds: int = 20,
        visibility_timeout: int = 300,
        max_messages: int = 1,
        **kwargs: Any,
    ) -> None:
        require_boto3()
        if not QUEUE_URL_RE.match(queue_url):
            raise ValueError(f"Invalid queue_url: {queue_url!r}")
        import boto3

        self._sqs = boto3.client("sqs", region_name=region)
        self._queue_url = queue_url
        self._region = region
        self._wait_seconds = min(wait_seconds, 20)
        self._visibility_timeout = visibility_timeout
        self._max_messages = min(max_messages, 10)
        self._running = False
        self._processed = 0
        self._errors = 0

    @property
    def backend_type(self) -> str:
        return "fargate_sqs"

    def start(self, queues: list[str] | None = None) -> None:
        """Blocking SQS long-poll loop. Runs until SIGTERM/SIGINT."""
        self._running = True
        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)
        logger.info("Fargate SQS worker started, polling %s", self._queue_url)

        while self._running:
            try:
                self._poll_once()
            except Exception:
                logger.exception("Poll cycle error")
                time.sleep(5)

        logger.info("Fargate SQS worker stopped (%d processed, %d errors)",
                     self._processed, self._errors)

    def _shutdown(self, signum: int, frame: Any) -> None:
        logger.info("Received signal %d, shutting down gracefully", signum)
        self._running = False

    def _poll_once(self) -> None:
        """Single SQS receive + dispatch cycle."""
        resp = self._sqs.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=self._max_messages,
            WaitTimeSeconds=self._wait_seconds,
            VisibilityTimeout=self._visibility_timeout,
            AttributeNames=["All"],
        )
        for msg in resp.get("Messages", []):
            try:
                self._process_message(msg)
                self._sqs.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=msg["ReceiptHandle"],
                )
                self._processed += 1
            except Exception:
                logger.exception("Failed to process message %s", msg.get("MessageId"))
                self._errors += 1

    def _process_message(self, msg: dict[str, Any]) -> Any:
        """Parse SQS message and dispatch to MCP bridge."""
        from ..bridge import execute_mcp_tool

        body = json.loads(msg.get("Body", "{}"))
        action = body.get("action", "tool")

        if action == "swarm":
            return execute_mcp_tool(
                "agent_invoke_swarm",
                {"swarm_id": body["swarm_id"], "task": body["task"]},
            )
        # Default: direct MCP tool call. Preserve legacy positional task args
        # while the bridge maps them through the public MCP schema.
        positional_args = body.get("args")
        if positional_args:
            return execute_mcp_tool(
                body["tool_name"],
                body.get("arguments", {}),
                positional_args=positional_args,
            )
        return execute_mcp_tool(body["tool_name"], body.get("arguments", {}))

    def health_check(self) -> WorkerHealth:
        """Check SQS queue accessibility."""
        try:
            attrs = self._sqs.get_queue_attributes(
                QueueUrl=self._queue_url,
                AttributeNames=["ApproximateNumberOfMessages"],
            )
            pending = int(attrs["Attributes"].get("ApproximateNumberOfMessages", 0))
            return WorkerHealth(
                healthy=True,
                backend="fargate_sqs",
                active_tasks=pending,
                queues=[self._queue_url.rsplit("/", 1)[-1]],
            )
        except Exception as e:
            return WorkerHealth(healthy=False, backend="fargate_sqs", error=str(e))

    def list_tasks(self) -> list[TaskInfo]:
        """Peek at SQS messages without consuming them."""
        try:
            resp = self._sqs.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=0,
                VisibilityTimeout=0,
            )
            return [
                TaskInfo(
                    name=json.loads(m.get("Body", "{}")).get("tool_name", "unknown"),
                    queue=self._queue_url.rsplit("/", 1)[-1],
                    state="PENDING",
                )
                for m in resp.get("Messages", [])
            ]
        except Exception as e:
            logger.warning("Failed to list SQS tasks: %s", e)
            return []

    def send_task(
        self, name: str, args: tuple = (), kwargs: dict | None = None,
    ) -> Any:
        """Enqueue a task message onto SQS."""
        payload = json.dumps({
            "action": "tool",
            "tool_name": name,
            "args": list(args),
            "arguments": kwargs or {},
        })
        resp = self._sqs.send_message(QueueUrl=self._queue_url, MessageBody=payload)
        return {
            "task_id": resp.get("MessageId", ""),
            "status": "queued",
            "queue": self._queue_url.rsplit("/", 1)[-1],
        }

    def infrastructure_spec(self) -> dict[str, Any]:
        """Return structured resource requirements for CDK generation."""
        return {
            "provider": "aws",
            "services": ["ecs", "sqs"],
            "resources": [
                {
                    "type": "AWS::ECS::Service",
                    "properties": {"LaunchType": "FARGATE", "Region": self._region},
                },
                {
                    "type": "AWS::SQS::Queue",
                    "properties": {"QueueUrl": self._queue_url},
                },
            ],
        }
