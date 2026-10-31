from flask import Flask, request, jsonify

app = Flask(__name__)

# In-memory warehouse store — resets on restart (intentional for challenge replayability)
WAREHOUSES = {
    "RYWYO": {"code": "RYWYO", "owner": "vendor-a", "name": "Main Warehouse"},
    "ABCDE": {"code": "ABCDE", "owner": "vendor-b", "name": "East Warehouse"},
    "XYZPQ": {"code": "XYZPQ", "owner": "vendor-c", "name": "West Warehouse"},
}


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/warehouses")
def list_warehouses():
    vendor_id = request.headers.get("X-Vendor-ID", "unknown")
    # IDOR: lists all warehouses regardless of who is asking — enables enumeration
    # Filter warehouses by owner to prevent unauthorized enumeration
    filtered = {k: v for k, v in WAREHOUSES.items() if v["owner"] == vendor_id}
    return jsonify(list(filtered.values()))


@app.route("/warehouses/<code>", methods=["GET"])
def get_warehouse(code):
    vendor_id = request.headers.get("X-Vendor-ID", "unknown")
    wh = WAREHOUSES.get(code)
    if not wh:
        return jsonify({"error": "not found"}), 404
    if vendor_id != wh["owner"]:
        return jsonify({"error": "unauthorized"}), 403
    return jsonify(wh)


@app.route("/warehouses/<code>", methods=["DELETE"])
def delete_warehouse(code):
    vendor_id = request.headers.get("X-Vendor-ID", "unknown")
    wh = WAREHOUSES.get(code)
    if not wh:
        return jsonify({"error": "not found"}), 404
    if vendor_id != wh["owner"]:
        return jsonify({"error": "unauthorized"}), 403
    del WAREHOUSES[code]
    return jsonify({"deleted": code, "by": vendor_id})


@app.route("/warehouses/<code>", methods=["PUT"])
def update_warehouse(code):
    vendor_id = request.headers.get("X-Vendor-ID", "unknown")
    wh = WAREHOUSES.get(code)
    if not wh:
        return jsonify({"error": "not found"}), 404
    if vendor_id != wh["owner"]:
        return jsonify({"error": "unauthorized"}), 403
    data = request.get_json() or {}
    wh.update(data)
    return jsonify(wh)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
