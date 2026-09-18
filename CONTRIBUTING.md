# Contributing

Thanks for taking the time. This project is small on purpose: **no build step, no frontend
framework, no cloud dependency at runtime**. Contributions that keep it that way are much
easier to merge.

> 中文版见 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md)

## Get it running

```bash
python -m venv .venv

# Windows
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m src.cli web --port 5000

# macOS / Linux
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m src.cli web --port 5000
```

- Landing page: <http://127.0.0.1:5000/>
- Dashboard: <http://127.0.0.1:5000/app>
- API reference: <http://127.0.0.1:5000/docs>

Cold start seeds the SQLite database from `data/*.csv` — fully offline, no API key required.

## Six rules that will silently bite you

These are the project's non-negotiable rules; the full rationale lives in `HANDOFF.md` §4.

1. **After editing anything under `public/`, run `python scripts/embed_pages.py` and restart
   the server.** Serverless bundles cannot read `public/`, so pages are served from the
   inlined `src/pages.py`. Skip it and you will debug stale assets.
2. **Identifiers are stored as Chinese canonical keys**; localization happens in exactly one
   place (`data/labels.csv` + `src/labels.py`). The frontend must not translate data —
   `public/i18n.js` only carries static UI copy.
3. **Unregistered terms pass through** instead of raising or silently falling back to a
   default. New data must never break an existing call.
4. **Secrets live in environment variables**, never in the tracked `config.yaml`.
5. **One batch = one tag + one release.** Do not merge unrelated batches into one.
6. **Frontend-facing data must come from public endpoints.** The admin endpoints
   (`/api/db`, `/api/reseed`, `/api/kv-status`, `/api/collect`) return 403 in production;
   `/api/stats` exists so no page depends on them.

## Adding or changing an endpoint

Four places move together — miss one and CI or the docs will tell you:

| Where | What |
| --- | --- |
| `src/web.py` | the route itself |
| `src/api_docs.py` | `ENDPOINTS` — a test compares it against `app.url_map` in both directions |
| `scripts/check_i18n.py` | `CHECKS` — the bilingual contract |
| `public/sitemap.xml` | if it is a page rather than an API |

## Tests and checks

```bash
.venv/Scripts/python.exe -m pytest -q            # unit tests
.venv/Scripts/python.exe scripts/embed_pages.py  # regenerate inlined assets
python scripts/check_i18n.py                     # bilingual contract (server must be running)
```

Markdown is linted with `markdownlint-cli2` in CI (non-blocking); configuration lives in
`.markdownlint.json`.

## Pull requests

- Commit messages are written in Chinese with a conventional prefix:
  `feat:` / `fix:` / `docs:` / `test:` / `chore:` plus a short Chinese summary.
- One logical batch per PR. When behaviour or the API changes, update `CHANGELOG.md`,
  `HANDOFF.md` and both READMEs in the same batch.
- Fill in the pull-request template checklist (embed / tests / i18n / docs).

## Reporting bugs and security issues

Use the issue templates in `.github/ISSUE_TEMPLATE/`. For anything that could expose data or
credentials, follow `SECURITY.md` instead of opening a public issue.

## License

By contributing you agree that your contribution is released under the MIT License
(see `LICENSE`). The public datasets under `data/` keep their own upstream licenses.
