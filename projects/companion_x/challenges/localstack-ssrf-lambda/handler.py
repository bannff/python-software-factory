"""Intentionally vulnerable Lambda — SSRF via user-supplied URL.

DO NOT deploy to production. This Lambda fetches any URL the caller
provides, including internal AWS endpoints like SSM Parameter Store.
"""
import json
import urllib.request


def handler(event, context):
    url = event.get("url", "")
    if not url:
        return {"statusCode": 400, "body": "Missing 'url' parameter"}
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        return {"statusCode": 200, "body": body[:4000]}
    except Exception as e:
        return {"statusCode": 500, "body": str(e)}
