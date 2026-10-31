from typing import Optional, Dict, Any, Protocol
from .models import Money, Transaction, Customer, Invoice


class PaymentGateway(Protocol):
    """
    Abstract Port for Payment Providers.
    Implementations (Adapters) must adhere to this interface using Domain Models.
    """

    @property
    def provider_id(self) -> str:
        """Unique identifier for the provider (e.g. 'stripe', 'mock')"""
        ...

    def health_check(self) -> bool:
        """Returns True if the upstream API is reachable"""
        ...

    def create_payment_intent(
        self,
        amount: Money,
        customer_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Transaction:
        """Initiates a payment intent/transaction"""
        ...

    def get_transaction(self, provider_ref: str) -> Optional[Transaction]:
        """Retrieves transaction details by provider reference"""
        ...

    def refund_transaction(
        self, provider_ref: str, amount: Optional[Money] = None, reason: Optional[str] = None
    ) -> Transaction:
        """Refunds a transaction (full or partial)"""
        ...

    def create_customer(
        self, email: str, name: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None
    ) -> Customer:
        """Creates a customer record in the provider"""
        ...

    def create_invoice(
        self, customer_id: str, amount: Money, description: str, due_date: Optional[str] = None
    ) -> Invoice:
        """Creates a simple invoice (v1 simplified)"""
        ...
