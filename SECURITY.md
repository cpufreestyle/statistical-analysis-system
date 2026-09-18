# Security Policy

## Supported versions

This project is maintained on the `master` branch. Fixes land there and are not backported to
old tags — please verify against the latest `master` before reporting.

| Version | Supported |
| --- | --- |
| `master` (latest) | ✅ |
| `v1.0.0` and older tags | ❌ (far behind; see `HANDOFF.md` §6) |

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Use one of these instead:

- GitHub: *Security → Report a vulnerability* (private advisory) on the GitHub mirror, or
- Gitee: a private message to the maintainer account.

Include what you can: the affected endpoint or file, reproduction steps, and the impact you
believe it has. You should get an acknowledgement within a few days; this is a spare-time
project, so please allow reasonable time for a fix, and tell us if the issue is being
disclosed elsewhere so we can coordinate.

## What is in scope

- Authentication and authorization of the **admin endpoints** (`/api/db`, `/api/reseed`,
  `/api/kv-status`, `/api/collect`) — they must stay behind `QU_STAT_ADMIN_TOKEN` and return
  403 in production when no token is configured.
- Secret handling: API keys are read from environment variables only and must never be
  committed to `config.yaml` or any tracked file.
- Anything that could turn the AI layer into a data-exfiltration or prompt-injection path.
- Dependency issues in `requirements.txt`.

## What is out of scope

- The dataset: everything under `data/` is **public** (World Bank Open Data, China NBS, China
  Customs). There is no personal, internal or classified data in this repository, so a
  “data leak” report here would be a misunderstanding.
- Reports that require an account on a third-party service we do not control.
- Denial of service against the hosted demo (Vercel free tier).

## Security-relevant design notes

- Admin endpoints are gated by `@admin_required` + `_admin_denied()`: with
  `QU_STAT_ADMIN_TOKEN` set, requests must carry `X-Admin-Token` or `?token=`; when it is
  unset they are open locally but **403 on Vercel**.
- Every response carries `X-Content-Type-Options`, `X-Frame-Options: SAMEORIGIN`,
  `Referrer-Policy`, a restrictive `Permissions-Policy` and a CSP limited to `'self'`; HSTS is
  added over HTTPS.
- No external CDN: fonts use the system stack, so there is no third-party script or style to
  compromise.
- On Vercel the SQLite file lives in `/tmp` and is rebuilt on cold start; the app stores no
  user accounts and no user-submitted data beyond what you type into the query box for that
  request.

## Status

This project has **not** undergone a third-party security audit. Treat the hosted deployment
as a demo, not as a system of record.
