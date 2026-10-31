# Recipe: Payments & Billing

Validates the payment processing, customer management, and invoice pipeline.

## Bricks Used
- `payments` - Payment processing with pluggable providers
- `events` - Event streaming for payment events
- `logger` - Audit logging for financial transactions

## Scenario

Create a customer, process a payment, handle a refund, create an invoice, and emit events for each financial operation.

## Prerequisites

- No AWS required
- Uses MockProvider (no Stripe API key needed)

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path
import yaml

# Payments - mock provider
tmpdir_pay = Path(tempfile.mkdtemp())
(tmpdir_pay / "settings.yaml").write_text(yaml.safe_dump({
    "provider": "mock",
}))
from factory.payments.runtime.runtime import Runtime as PaymentsRuntime
payments = PaymentsRuntime(config_dir=tmpdir_pay)

# Events
tmpdir_events = Path(tempfile.mkdtemp())
(tmpdir_events / "subscriptions").mkdir(parents=True, exist_ok=True)
from factory.events.runtime.runtime import EventsRuntime
events = EventsRuntime(config_dir=tmpdir_events)

# Logger
tmpdir_log = Path(tempfile.mkdtemp())
from factory.logger.runtime.runtime import LoggerRuntime
logger = LoggerRuntime(log_dir=str(tmpdir_log))
```

### Step 2: Health Checks

```python
provider = payments.active_provider
health = provider.health_check()
# Returns: True

available = payments.available_providers()
# Returns: ["mock", "stripe"]
```

### Step 3: Create Customer

```python
from factory.payments.core import Money

customer = provider.create_customer(
    email="customer@example.com",
    name="Test Customer",
    metadata={"plan": "pro", "source": "recipe-test"},
)
# Returns: Customer(id="...", email="customer@example.com", ...)
```

### Step 4: Process Payment

```python
amount = Money(amount=9999, currency="usd")  # $99.99

transaction = provider.create_payment_intent(
    amount=amount,
    customer_id=customer.id,
    metadata={"order_id": "ORD-001", "product": "annual-plan"},
)
# Returns: Transaction(id="...", status="succeeded", ...)
```

### Step 5: Emit Payment Event

```python
event = events.publish(
    event_type="payment.completed",
    payload={
        "transaction_id": transaction.id,
        "amount": amount.amount,
        "currency": amount.currency,
        "customer_id": customer.id,
    },
    source="payments-brick",
)
```

### Step 6: Log Transaction

```python
logger.info(
    f"Payment processed: {transaction.id}",
    source="payments",
    context={
        "amount": amount.amount,
        "currency": amount.currency,
        "customer_id": customer.id,
        "status": transaction.status,
    },
)
```

### Step 7: Get Transaction Details

```python
tx = provider.get_transaction(transaction.provider_ref)
# Returns: Transaction with full details
```

### Step 8: Process Refund

```python
refund_amount = Money(amount=2500, currency="usd")  # $25.00 partial refund
refund = provider.refund_transaction(
    provider_ref=transaction.provider_ref,
    amount=refund_amount,
    reason="Customer requested partial refund",
)
# Returns: Transaction with refund status
```

### Step 9: Create Invoice

```python
invoice_amount = Money(amount=4999, currency="usd")
invoice = provider.create_invoice(
    customer_id=customer.id,
    amount=invoice_amount,
    description="Monthly subscription - March 2025",
    due_date="2025-03-31",
)
# Returns: Invoice(id="...", status="...", ...)
```

### Step 10: Verify Audit Trail

```python
logs = logger.tail(n=5)
# Returns: list of payment-related log entries
```

## Success Criteria

- [x] Customer created
- [x] Payment intent processed successfully
- [x] Payment event emitted
- [x] Transaction retrievable by reference
- [x] Partial refund processed
- [x] Invoice created
- [x] All operations logged for audit

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| payments | `factory.payments.runtime.runtime.Runtime` | `active_provider`, `available_providers()` |
| payments | `factory.payments.core.Money` | `Money(amount=int, currency=str)` |
| payments ports | `factory.payments.runtime.ports.PaymentGateway` | `create_payment_intent()`, `refund_transaction()`, `create_invoice()` |
