"""IDOR Warehouse Lambda — intentionally vulnerable.

Same 3 IDOR vulns as the Flask app but running as Lambda behind API Gateway.
GET/DELETE/PUT /warehouses/{code} — no ownership check on X-Vendor-ID header.
"""
import json

WAREHOUSES = {
    "RYWYO": {"code": "RYWYO", "owner": "vendor-a", "name": "Main Warehouse"},
    "ABCDE": {"code": "ABCDE", "owner": "vendor-b", "name": "East Warehouse"},
    "XYZPQ": {"code": "XYZPQ", "owner": "vendor-c", "name": "West Warehouse"},
}


def handler(event, context):
    method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    headers = event.get("headers") or {}
    vendor_id = headers.get("X-Vendor-ID", headers.get("x-vendor-id", "unknown"))
    body_str = event.get("body") or "{}"

    if path == "/health":
        return _resp(200, {"status": "ok"})
    if path == "/warehouses" and method == "GET":
        return _resp(200, list(WAREHOUSES.values()))

    # /warehouses/{code}
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[0] == "warehouses":
        code = parts[1]
        wh = WAREHOUSES.get(code)
        if not wh:
            return _resp(404, {"error": "not found"})
        if method == "GET":
            # IDOR: returns data without checking vendor_id == owner
            return _resp(200, wh)
        if method == "DELETE":
            # IDOR: deletes without ownership check
            del WAREHOUSES[code]
            return _resp(200, {"deleted": code, "by": vendor_id})
        if method == "PUT":
            # IDOR: updates without ownership check
            data = json.loads(body_str) if body_str else {}
            wh.update(data)
            return _resp(200, wh)

    return _resp(404, {"error": "not found"})


def _resp(code, body):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"},
            "body": json.dumps(body)}
