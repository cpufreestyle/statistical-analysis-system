# Changelog

All notable changes are recorded here.

Versioning follows semver: `pyproject.toml` carries the latest released version and every
independent batch gets its **own tag + release** (batches are never merged into one release).
Older entries keep their original date + batch grouping.

Format follows [Keep a Changelog](https://keepachangelog.com/); tags are `Added`, `Changed`,
`Fixed`, `Security` and `Docs`.

## [Unreleased]

Nothing yet.

## v1.4.0 — 2026-09-18 — UI polish (`a9d2c37`)

### Changed

- 指标卡与 Quick Start 网格从固定 4 列改为 `repeat(auto-fit, minmax(220px/200px, 1fr))`，
  解决 3 张或 5 张卡时右侧/下方出现空列的问题；响应式断点不再显式覆盖网格列数。
- 顶栏品牌隐藏重复的英文副标题，标题更干净。
- 工作台标签 active 状态加蓝色背景与 3px 下划线，标签图标放大，状态更醒目。
- 图表容器升级为白底卡片 + 阴影 + 更大圆角/内边距；
  折线图增大画布、左外边距与字号，新增 Y 轴线，网格线改用深色也可见的 `--gray-200`；
  排名条图标签区与条形略放大、圆角加大。
- 区块徽章由灰阶改为蓝色系，提高识别度。

## v1.3.0 — 2026-09-18 — Open-source readiness (`130e793`, `c70ce1b`)

### Added

- **`LICENSE` (MIT).** The READMEs claimed MIT while the repository contained no licence file,
  which legally means “all rights reserved”. Fixed, and `pyproject.toml` now declares it.
- `CONTRIBUTING.md` + `CONTRIBUTING.zh-CN.md` — the six hard rules, the “changing an endpoint
  means touching four places” checklist, and the test/PR conventions.
- `SECURITY.md` — private reporting channel, in/out of scope, admin-token and `/tmp` SQLite
  notes, and an explicit “no third-party audit yet”.
- `CHANGELOG.md` (this file) and `CITATION.cff` (CFF 1.2.0, points at the GitHub mirror).
- `.github/PULL_REQUEST_TEMPLATE.md` and bug-report / feature-request issue templates.
- `GET /privacy` — bilingual privacy & data statement rendered server-side (`src/privacy_page.py`,
  reuses `api_docs.SHARED_CSS`). It answers the three questions people actually ask: what is
  stored (the `qu_lang_v2` key in `localStorage`), under which licence the data is used
  (World Bank CC BY 4.0), and whether AI is on (off by default). Linked from the landing-page
  footer, `/docs` and the error pages; listed in `sitemap.xml`.
- New tests for the privacy page (placeholder substitution, both languages, the three
  answers, reachability, sitemap). Suite grows 106 → 111.

### Changed

- `.markdownlint-cli2.jsonc` now owns the ignore list (`data/`, `node_modules/`, `.venv/`,
  assistant memory directories). Running `markdownlint-cli2 "**/*.md"` locally used to report
  3083 issues, all of them outside the project; the CI job now reuses the same config.

### Docs

- Both READMEs: CI / licence / Python badges, the `## License` section now separates code
  (MIT) from data terms, and a navigation table for CONTRIBUTING / SECURITY / CHANGELOG /
  CITATION / privacy / docs.
- `HANDOFF.md` §0, §5, §6.7 and §9 refreshed.

## v1.2.0 — 2026-09-18 — Usability & quality (`202f428`)

### Added

- `GET /docs` — bilingual API reference rendered server-side (no JavaScript): 22 endpoint
  cards covering all 23 routes, parameter tables, `curl` examples and the shared conventions
  (`src/api_docs.py`). Entry points on both pages and in `sitemap.xml`.
- Branded bilingual error pages for 404 / 405 / 500 (`src/error_pages.py`); `/api/*` paths
  still answer with JSON.
- `hreflang` alternates (`en`, `zh-CN`, `x-default`) on `/`, `/app` and `/docs`, each pointing
  at its own URL.
- Chart accessibility: chart SVGs carry `role="img"` + `aria-label` + a `<desc>` data summary,
  the legend is `aria-hidden`, containers are `aria-live="polite"`.
- `tests/test_stats_core.py` — 17 tests for `yoy` / `share` / `rank_items` / `fmt_pct`
  boundaries and for `report.build_bulletin_data()`. Suite grows 74 → 106.
- A test that compares `app.url_map` against `src/api_docs.py`'s `ENDPOINTS` in both
  directions, so a new route cannot ship without documentation.

### Fixed

- **Admin-endpoint regression**: the landing page and dashboard sidebar were reading
  `/api/db`, which returns 403 in production — the counters silently showed “—”. Added the
  public read-only `GET /api/stats` and pointed both pages at it.
- `/api/collect` returning 403 on the hosted build now shows an explanatory message instead of
  failing silently.

### Changed

- Chart series colours moved from hard-coded hex values to `--ch-1…--ch-14` tokens, with a
  brighter palette in dark mode (the old values fell below 3:1 contrast on white).
- `config.yaml`: `infinisynapse.prefer_language` `zh_CN` → `en_US` (matches the product
  default). `.gitignore` now covers `.python-version`.

### Docs

- Both READMEs updated (API reference link, `/api/stats`, admin-endpoint 403 behaviour,
  `QU_STAT_BASE_URL` / `QU_STAT_ADMIN_TOKEN`, new modules in the architecture map) and
  corrected where they had drifted: the data-source table still listed Australia and the
  United States, and the panel count and ranking size were stale.
- `HANDOFF.md` refreshed end to end; the rule set grows from five to six.

## 2026-09-18 — Performance, hardening, UX & SEO batch (`7d3faab`)

### Added

- Security response headers (`nosniff`, `X-Frame-Options`, `Referrer-Policy`,
  `Permissions-Policy`, CSP locked to `'self'`; HSTS over HTTPS).
- Admin-endpoint token auth (`QU_STAT_ADMIN_TOKEN` → `X-Admin-Token` or `?token=`); 403 in
  production when unset, open in local development.
- Content-hash long caching for static assets (`?v=<sha256[:12]>`), `no-store` for HTML and
  APIs; dark mode via `prefers-color-scheme`; skip links, `:focus-visible`,
  `prefers-reduced-motion`; JSON-LD structured data on both pages.

### Changed

- Removed the Google Fonts dependency — the UI uses a system font stack, so the project now
  has **zero external CDN dependencies**.
- Share card switched from SVG to a 1200×630 PNG generated by `scripts/make_og_image.py` and
  embedded as base64.

## 2026-09-17 — Asia-Pacific caliber (`d8915f2`, `40e3784`)

### Fixed

- Dropped the United States and Australia dimensions: they are not Asia-Pacific economies.
  `ap_macro.csv` goes from 837 rows / 14 dimensions to 720 rows / 12; the label pack and the
  collector's default indicator list were cleaned up too so they cannot come back.

## 2026-09-17 — Tests and CI baseline (`7f2d4f2`)

### Added

- `tests/` with 66 unit tests (label contract, analyzer dispatch, web routes, embed
  regression) and a `conftest` that isolates the test database. `.github/workflows/ci.yml`
  runs pytest, boots the server for `check_i18n.py`, then an optional markdownlint pass.

## 2026-09-17 — Pluggable AI provider (`458cc56`)

### Added

- `src/analyzer.py` supports `infinisynapse` (default, auditable SSE) and `openai_compat`
  (any OpenAI-compatible `/chat/completions`: OpenAI / OpenRouter / Groq / DeepSeek / local
  Ollama · vLLM). Selected with `AI_PROVIDER`; without a key the app degrades to local
  statistics instead of erroring.

## 2026-09-17 — SEO baseline (`b25f754`)

### Added

- `robots.txt`, `sitemap.xml`, `og:image`, and `<html lang>` that follows `?lang=` /
  `Accept-Language` instead of being hard-coded.

## 2026-09-16 — Export, share links and charts (`fc269b4`, `ea6f615`)

### Added

- `GET /api/export.csv` plus “export” buttons in the indicator and chart panels, and a share
  link that preserves the current filter state through `history.replaceState`.
- Hand-drawn SVG line and ranking charts (no chart library), fulfilling the visualisation P0.

## 2026-09-16 — Server-side identifier localization (`f0d63b1`)

### Changed

- Data identifiers are localized server-side from `data/labels.csv`, so the REST API is
  bilingual rather than only the dashboard. Every record exposes the display value plus
  `*_key` (canonical Chinese key) and `*_slug` (stable ASCII key).

## 2026-09-16 — Public data, English-first, bilingual READMEs (`3895850`)

### Changed

- The dataset moved to real public sources (World Bank Open Data, China NBS, China Customs);
  all synthetic sample data was removed. English became the default language and both READMEs
  were published.

## 2026-09-07 → 2026-09-13 — Bilingual UI

### Added

- Chinese / English toggle persisted in `localStorage`, English copies for static UI strings,
  and a fix for the “switched back to Chinese but still English” bug.

## 2026-07-27 → 2026-07-31 — Early batches

### Added

- Web dashboard and CLI, user-defined custom analyses over `custom_analysis.yaml`, collection
  from World Bank Open Data, Vercel deployment with optional KV snapshot restore, direct
  InfiniSynapse Server API integration replacing the `agent_infini` binary.

### Changed

- Data layer consolidated on SQLAlchemy Core; all internal-organization wording removed so
  the project reads as a neutral public tool.
