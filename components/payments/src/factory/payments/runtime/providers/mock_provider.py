import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional, Any

from ..models import Money, Transaction, Customer, Invoice, PaymentStatus, InvoiceItem
from ..ports import PaymentGateway


class MockProvider(PaymentGateway):
    """
    In-memory mock provider for local development and testing.
    Determinstic behavior:
    - Amount ends in .00 -> SUCCEEDED
    - Amount ends in .99 -> FAILED
    """

    def __init__(self) -> None:
        self._transactions: Dict[str, Transaction] = {}
        self._customers: Dict[str, Customer] = {}
        self._invoices: Dict[str, Invoice] = {}

    @property
    def provider_id(self) -> str:
        return "mock"

    def health_check(self) -> bool:
        return True

    def create_payment_intent(
        self,
        amount: Money,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        # Deterministic simulation based on amount
        status = PaymentStatus.SUCCEEDED
        error_msg = None

        # Simulate decline for .99 cents
        if amount.amount % 1 == Decimal("0.99"):
            status = PaymentStatus.FAILED
            error_msg = "Simulated card decline"

        tid = f"txn_{uuid.uuid4().hex[:12]}"
        t = Transaction(
            transaction_id=tid,
            amount=amount,
            status=status,
            customer_id=customer_id,
            provider_id=self.provider_id,
            provider_ref=f"mock_intent_{tid}",
            metadata=metadata or {},
            error_message=error_msg,
        )
        self._transactions[tid] = t
        return t

    def get_transaction(self, provider_ref: str) -> Optional[Transaction]:
        # Search by provider_ref
        for t in self._transactions.values():
            if t.provider_ref == provider_ref:
                return t
        return None

    def refund_transaction(
        self, provider_ref: str, amount: Optional[Money] = None, reason: Optional[str] = None
    ) -> Transaction:
        txn = self.get_transaction(provider_ref)
        if not txn:
            raise ValueError(f"Transaction not found: {provider_ref}")

        # Mock logic: update status to refunded
        # In real world, we'd check amounts, etc.
        updated_txn = txn.model_copy(
            update={
                "status": PaymentStatus.REFUNDED,
                "updated_at": datetime.now(timezone.utc),
                "metadata": {**txn.metadata, "refund_reason": reason or "requested"},
            }
        )
        # Update in storage
        self._transactions[txn.transaction_id] = updated_txn
        return updated_txn

    def create_customer(
        self, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> Customer:
        cid = f"cus_{uuid.uuid4().hex[:12]}"
        c = Customer(
            customer_id=cid,
            email=email,
            name=name,
            provider_refs={self.provider_id: f"mock_cus_{cid}"},
            metadata=metadata or {},
        )
        self._customers[cid] = c
        return c

    def create_invoice(
        self, customer_id: str, amount: Money, description: str, due_date: Optional[str] = None
    ) -> Invoice:
        # Validate customer exists
        # In mock, we might skip strict check or look in self._customers

        iid = f"in_{uuid.uuid4().hex[:12]}"
        item = InvoiceItem(description=description, unit_price=amount)

        inv = Invoice(
            invoice_id=iid,
            customer_id=customer_id,
            items=[item],
            total=amount,
            status="open",
            due_date=datetime.fromisoformat(due_date) if due_date else None,
            provider_id=self.provider_id,
            provider_ref=f"mock_inv_{iid}",
            hosted_invoice_url=f"http://localhost/invoice/{iid}",
            metadata={},
        )
        self._invoices[iid] = inv
        return inv
