# WebGoat — OWASP Vulnerable Java App

Java Spring Boot app with 30+ intentional vulnerability lessons.
Source: https://github.com/WebGoat/WebGoat

## Quick Start

```bash
docker compose --profile webgoat up -d vuln-webgoat
# Wait ~30s for startup
curl http://localhost:5050/WebGoat/login
```

## Auth

Default: register a new user at `/WebGoat/register.mvc`
IDOR lessons require authenticating as `tom` (password: `tom`).

## IDOR Lessons (3 GT entries)

| GT ID | Endpoint | Method | Vuln |
|-------|----------|--------|------|
| webgoat-idor-view-001 | /IDOR/profile/{userId} | GET | View other user's profile |
| webgoat-idor-edit-002 | /IDOR/profile/{userId} | PUT | Edit other user's profile + role |
| webgoat-idor-viewown-003 | /IDOR/profile/alt-path | GET | URL pattern discovery |

## Source Code for SAST

Clone for SAST scanning:
```bash
git clone --depth 1 https://github.com/WebGoat/WebGoat.git
```

IDOR lesson files:
- `src/main/java/org/owasp/webgoat/lessons/idor/IDORViewOtherProfile.java`
- `src/main/java/org/owasp/webgoat/lessons/idor/IDOREditOtherProfile.java`
- `src/main/java/org/owasp/webgoat/lessons/idor/IDORViewOwnProfileAltUrl.java`
- `src/main/java/org/owasp/webgoat/lessons/idor/IDORLogin.java`
- `src/main/java/org/owasp/webgoat/lessons/idor/UserProfile.java`

## Future GT Expansion

Additional vuln classes available: SQLi, XSS, CSRF, SSRF,
Path Traversal, XXE, JWT, Deserialization, Session Hijack.
