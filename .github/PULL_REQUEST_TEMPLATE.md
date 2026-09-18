# Pull request

## What this batch does

<!-- One logical batch per PR, please. -->

## Type

- [ ] `feat:` new capability
- [ ] `fix:` bug fix
- [ ] `docs:` documentation / hand-off only
- [ ] `test:` / `chore:` tests, tooling, housekeeping

## Checklist

- [ ] Ran `python scripts/embed_pages.py` and restarted the server (required after any change
      under `public/`).
- [ ] `python -m pytest -q` passes.
- [ ] With the server running, `python scripts/check_i18n.py` passes (required when an API
      response changed).
- [ ] If a route was added or changed: `src/api_docs.py` `ENDPOINTS`,
      `scripts/check_i18n.py` `CHECKS` and `public/sitemap.xml` updated in the same batch.
- [ ] Frontend-facing features read from **public** endpoints, never from the admin endpoints
      that return 403 in production.
- [ ] `CHANGELOG.md` updated; `HANDOFF.md` and both READMEs updated when behaviour or the API
      changed.
- [ ] No API key or token committed — secrets stay in environment variables.

## Notes for the reviewer

<!-- Anything that cannot be seen from the diff: decisions, trade-offs, follow-ups. -->
