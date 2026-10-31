from typing import Dict, Any
import uuid
from datetime import datetime, timezone
from ..models import NotificationRequest, DeliveryStatus
from .base import NotificationBackend

try:
    from celery import Celery

    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False


class CeleryBackend(NotificationBackend):
    """
    Backend that delegates to a Celery worker.
    This is an Adapter around the off-the-shelf Celery library.
    """

    def __init__(self):
        self.app = None
        self.task_name = "notification.send"

    @property
    def name(self) -> str:
        return "celery"

    async def initialize(self, config: Dict[str, Any]) -> None:
        if not HAS_CELERY:
            raise ImportError(
                "Celery is not installed. Install with 'pip install celery'."
            )

        broker_url = config.get("broker_url", "redis://localhost:6379/0")
        self.task_name = config.get("task_name", "notification.send")

        # Initialize Celery app
        self.app = Celery("notification_module", broker=broker_url)
        self.app.conf.update(config.get("celery_config", {}))

    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        if not self.app:
            raise RuntimeError("Celery backend not initialized")

        # Prepare payload for the worker
        payload = request.dict()
        message_id = str(uuid.uuid4())

        # Enqueue the task
        # We use apply_async to get the task ID
        self.app.send_task(self.task_name, kwargs=payload, task_id=message_id)

        return DeliveryStatus(
            message_id=message_id,
            status="queued",  # Celery is async, so it's always 'queued' initially
            backend=self.name,
            timestamp=datetime.now(timezone.utc),
        )

    async def health_check(self) -> bool:
        if not self.app:
            return False
        try:
            with self.app.connection_or_acquire() as conn:
                return conn.default_channel.client.ensure_connection(max_retries=1)
        except Exception:
            return False
