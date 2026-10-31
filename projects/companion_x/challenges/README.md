# Vulnerable App Targets

Intentionally vulnerable apps for red team agent benchmarking.
Each target runs as a Docker container on port 5050.

## Quick Start

```bash
# Start a target (pick one):
docker compose --profile warehouse up -d vuln-idor-warehouse
docker compose --profile vampi up -d vuln-vampi
docker compose --profile crapi up -d vuln-crapi
docker compose --profile juiceshop up -d vuln-juice-shop

# Verify it's running:
curl http://localhost:5050/health

# Stop:
docker compose --profile <profile> down
```

## Targets

| Target | Profile | Port | GT Findings | Vuln Classes |
|--------|---------|------|-------------|--------------|
| IDOR Warehouse | `warehouse` | 5050 | 3 | IDOR |
| VAmPI | `vampi` | 5050 | 6 | IDOR, SQLi, Mass Assignment |
| crAPI | `crapi` | 5050 | ~20 | IDOR, BOLA, SSRF, SQLi |
| Juice Shop | `juiceshop` | 5050 | ~100 | XSS, SQLi, IDOR, Auth |

## GT Entries

Each target has a `gt_entries.json` with known vulnerabilities.
Format matches the canonical ground-truth schema consumed by the security tooling.
