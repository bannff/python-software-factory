"""AWS Marketplace Metering adapter for payments.

Implements PaymentGateway protocol using AWS Marketplace Metering
for usage-based billing. Marketplace manages customers and invoicing
via AWS accounts, so those operations are handled locally or return
not-supported.
"""

from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..models import (
    Currency,
    Customer,
    Invoice,
    InvoiceItem,
    Money,
    PaymentStatus,
    Transaction,
)
from ..ports import PaymentGateway

_SAFE_PRODUCT_CODE = re.compile(r"^[A-Za-z0-9_\-]{1,255}$")
_SAFE_DIMENSION = re.compile(r"^[A-Za-z0-9_\-]{1,255}$")


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for AWS Marketplace adapter"
        raise ImportError(msg)


class AWSMarketplaceProvider(PaymentGateway):
    """AWS Marketplace Metering provider for PaymentGateway port."""

    def __init__(self, product_code: str, region: str = "us-east-1") -> None:
        _require_boto3()
        import boto3

        if not _SAFE_PRODUCT_CODE.match(product_code):
            raise ValueError(f"Invalid product_code: {product_code!r}")
        self._product_code = product_code
        self._region = region
        self._client = boto3.client("meteringmarketplace", region_name=region)
        self._customers: Dict[str, Customer] = {}
        self._transactions: Dict[str, Transaction] = {}

    @property
    def provider_id(self) -> str:
        return "aws-marketplace"

    def health_check(self) -> bool:
        try:
            self._client.meter_usage(
                ProductCode=self._product_code,
                Timestamp=datetime.now(timezone.utc),
                UsageDimension="health_check",
                UsageQuantity=0,
                DryRun=True,
            )
            return True
        except Exception:
            return False

    def create_payment_intent(
        self,
        amount: Money,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        tid = f"txn_{uuid.uuid4().hex[:12]}"
        dimension = (metadata or {}).get("usage_dimension", "api_calls")
        if not _SAFE_DIMENSION.match(dimension):
            raise ValueError(f"Invalid usage_dimension: {dimension!r}")
        quantity = int(amount.amount)
        try:
            resp = self._client.meter_usage(
                ProductCode=self._product_code,
                Timestamp=datetime.now(timezone.utc),
                UsageDimension=dimension,
                UsageQuantity=quantity,
            )
            txn = Transaction(
                transaction_id=tid,
                amount=amount,
                status=PaymentStatus.COMPLETED,
                customer_id=customer_id,
                provider_id=self.provider_id,
                provider_ref=resp.get("MeteringRecordId", tid),
                metadata=metadata or {},
            )
        except Exception as e:
            txn = Transaction(
                transaction_id=tid,
                amount=amount,
                status=PaymentStatus.FAILED,
                customer_id=customer_id,
                provider_id=self.provider_id,
                provider_ref="",
                error_message=str(e),
                metadata=metadata or {},
            )
        self._transactions[tid] = txn
        return txn

    def get_transaction(self, provider_ref: str) -> Optional[Transaction]:
        for t in self._transactions.values():
            if t.provider_ref == provider_ref:
                return t
        return None

    def refund_transaction(
        self,
        provider_ref: str,
        amount: Optional[Money] = None,
        reason: Optional[str] = None,
    ) -> Transaction:
        txn = self.get_transaction(provider_ref)
        if not txn:
            raise ValueError(f"Transaction not found: {provider_ref}")
        return txn.model_copy(update={
            "status": PaymentStatus.FAILED,
            "error_message": "Refunds not supported via AWS Marketplace Metering",
        })

    def create_customer(
        self,
        email: str,
        name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Customer:
        cid = f"cus_{uuid.uuid4().hex[:12]}"
        c = Customer(
            customer_id=cid,
            email=email,
            name=name,
            provider_refs={self.provider_id: cid},
            metadata=metadata or {},
        )
        self._customers[cid] = c
        return c

    def create_invoice(
        self,
        customer_id: str,
        amount: Money,
        description: str,
        due_date: Optional[str] = None,
    ) -> Invoice:
        iid = f"inv_{uuid.uuid4().hex[:12]}"
        return Invoice(
            invoice_id=iid,
            customer_id=customer_id,
            items=[InvoiceItem(description=description, unit_price=amount)],
            total=amount,
            status="not_supported",
            provider_id=self.provider_id,
            provider_ref="",
            metadata={"note": "AWS Marketplace handles billing directly"},
        )

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "marketplace-metering",
            "construct": "MeteringUsage",
            "props": {
                "product_code": self._product_code,
                "region": self._region,
            },
        }
