# Payments

Payments exposes a 14-tool FastMCP surface: 7 deterministic tools, 3 operational tools, and 4 authoring tools. Every public tool preserves flat keyword arguments, validates ingress with a strict Payments-local Pydantic v2 DTO, and returns `ToolResult[OutputDTO]`. Callers check `result.ok` and read a successful typed payload from `result.data`; expected domain outcomes remain typed data, while only unexpected faults fail the envelope.

Public output is intentionally allowlisted: payment history excludes descriptions, customer identifiers, metadata, provider errors, raw webhook content, credentials, and client secrets. `api_key` and `public_key` are `SecretStr` inputs. Metadata, options, and webhook payloads are recursively bounded JSON and reject credential/card-like fields and PAN-like values.

`payments_process_webhook` parses and dispatches an unverified Stripe-shaped payload. It neither verifies a signature nor changes payment status. Its public output contains the processing flag, an optional server-generated correlation ID, and event type; unknown providers or invalid event types return `processed=false` with a safe error code.

Run focused tests with:

```sh
uv run pytest components/payments/test -q
```
