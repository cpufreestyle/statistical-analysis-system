# Asia-Pacific Statistical Analysis System

[![CI](https://github.com/cpufreestyle/statistical-analysis-system/actions/workflows/ci.yml/badge.svg)](https://github.com/cpufreestyle/statistical-analysis-system/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)

An open economic-statistics workbench for the Asia-Pacific region: **every figure comes from
official public data**, and the AI layer is only allowed to interpret those figures — never to
invent them.

- **Dashboard**: <https://qu-stat-system.vercel.app/app>
- **API reference**: <https://qu-stat-system.vercel.app/docs> (bilingual, server-rendered — 22 endpoint cards with parameters and `curl` examples)
- **Data**: World Bank Open Data · China National Bureau of Statistics (NBS) · China Customs
- **AI**: pluggable providers — InfiniSynapse Server API (`/api/ai/message` + `/api/ai/events` SSE, default) **or** any OpenAI-compatible `/chat/completions` endpoint (OpenAI / OpenRouter / Groq / DeepSeek / local Ollama · vLLM), Bearer-token auth
- **中文文档**: [README.zh-CN.md](README.zh-CN.md)

---

## Why it is different

Most "AI + data" demos let the model guess. This one is built the other way round:

| Principle | How it is enforced |
| --- | --- |
| Real official data only | The seed dataset is fetched from World Bank Open Data by `scripts/fetch_wb_data.py`; no synthetic or fabricated values ship in the app |
| Every number is traceable | Each row stores the source in its `note` field (e.g. `World Bank Open Data (NY.GDP.MKTP.CD, EAS)`), and the dashboard surfaces it under every KPI card |
| The AI cannot hallucinate figures | The locally retrieved statistics are injected into the prompt as the only allowed facts ("do not invent figures that are not given") |
| No cross-caliber arithmetic | Indicator functions first lock onto one region, then read only within that region — this fixed a real bug where YoY mixed two regions and produced a meaningless `+326%` |
| Bilingual, single source of truth | The identifier layer is localized **server-side** from `data/labels.csv`, so the REST API is bilingual too — not just the dashboard. `public/i18n.js` now only carries static UI copy |

## Screens

Five workbench tabs:

1. **AI Query** — ask in English or Chinese ("2024 GDP", "retail sales", "population of Japan").
   The engine resolves region / indicator / year, returns the real figures, and optionally hands
   them to the cloud AI for interpretation.
2. **Indicator Catalog** — searchable table of every stored series, filterable by region and
   category, with one-click hand-off to Custom Analysis and CSV export.
3. **Custom Analysis** — bind variables to any category / indicator / region, use
   `share` / `diff` / `ratio` / `sum` presets, and compute YoY. Expressions are evaluated in a
   restricted namespace (no arbitrary code execution).
4. **Bulletin** — generates a statistical bulletin for the selected year and region from real
   data, with an optional AI interpretation section.
5. **Charts** — hand-drawn SVG (no chart library): a multi-economy time-series line chart and a
   per-economy ranking bar chart, both carrying `role="img"` plus a text summary of the data for
   screen readers. Export the current indicator as CSV in one click.

The API itself is documented in-app at `/docs` (bilingual, server-rendered, no JavaScript).

## Data sources and caliber

| Dimension | Source | Notes |
| --- | --- | --- |
| Asia-Pacific (`EAS`) | World Bank Open Data | East Asia & Pacific, all income levels |
| Asia-Pacific, developing (`EAP`) | World Bank Open Data | East Asia & Pacific, excluding high income |
| China, Japan, Korea, India, Indonesia, Thailand, Viet Nam, Malaysia, Philippines, Singapore | World Bank Open Data | One dimension per economy for comparison (10 economies) |
| China, domestic detail | China NBS / China Customs (2024) | GDP and industry value added, retail sales, fixed asset investment, merchandise trade, resident population, per-capita disposable income |

Covered series per economy (World Bank codes):
`NY.GDP.MKTP.CD`, `NY.GDP.MKTP.KD.ZG`, `NY.GDP.PCAP.CD`, `FP.CPI.TOTL.ZG`,
`NV.IND.TOTL.CD`, `NE.EXP.GNFS.CD`, `NE.IMP.GNFS.CD`, `SP.POP.TOTL`, `SP.DYN.LE00.IN`,
`SL.UEM.TOTL.ZS` — six years, 2019-2024.

**Units.** Monetary World Bank series are converted to `USD 100M`; NBS series stay in
`CNY 100M`. The unit is always shown next to the value and never silently converted.

**Disclaimer.** Public data only — nothing internal or classified. Preliminary accounting
figures may be revised; where a number differs from the official final release, the official
release governs.

## Quick start

```bash
git clone https://github.com/cpufreestyle/statistical-analysis-system.git
cd statistical-analysis-system
python -m venv .venv
.venv/Scripts/Activate.ps1          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -e .
python -m src.cli web --port 5000   # open http://127.0.0.1:5000
```

The first start loads the real public dataset from the bundled seed files into SQLite
(`data/qu_stats.db`), so the dashboard works fully offline.

### Refresh the dataset from the source

```bash
.venv/Scripts/python.exe scripts/fetch_wb_data.py --from 2019 --to 2024
.venv/Scripts/python.exe scripts/embed_pages.py   # embed assets + seed CSVs for serverless
```

## CLI

```bash
python -m src.cli ask "2024 GDP"                    # local query, English output (default)
python -m src.cli ask "2024 GDP" --lang zh           # same query, Chinese identifiers
python -m src.cli ask "工业增加值" --cloud            # + InfiniSynapse interpretation
python -m src.cli report --year 2024                 # statistical bulletin (text)
python -m src.cli report --year 2024 --dimension 中国 --lang zh
python -m src.cli report --year 2024 --cloud         # bulletin + AI interpretation
python -m src.cli custom list --lang en              # declared custom analyses
python -m src.cli custom run "Trade Openness"        # English name works too
python -m src.cli collect --country EAS --indicators gdp,population
python -m src.cli collect --source global --indicators gdp --countries CHN,USA,JPN
python -m src.cli knowledge search --query "GDP 口径"
python -m src.cli db info
```

`--lang` (default `en`) selects the language of the data identifiers and of the knowledge-base
recall, and accepts the English name / slug anywhere a region or category is expected.

## Configuration

`config.yaml` holds the region defaults, the database URL, and the collector settings.

The InfiniSynapse API key is read from the environment first:

```bash
export INFINISYNAPSE_API_KEY="sk-..."     # preferred, especially on Vercel
export INFINISYNAPSE_SERVER="https://app.infinisynapse.cn"   # optional override
```

`config.yaml` is tracked by git, so **never commit a real key into it** — put the secret in the
environment and leave `infinisynapse.api_key` commented out.

### Switching the AI provider

Set `AI_PROVIDER` to choose a backend — `infinisynapse` (default) or `openai_compat`:

```bash
# Any OpenAI-compatible endpoint: OpenAI / OpenRouter / Groq / DeepSeek / local Ollama · vLLM
export AI_PROVIDER="openai_compat"
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"   # e.g. http://127.0.0.1:11434/v1 for Ollama
export OPENAI_MODEL="gpt-4o-mini"
```

Both providers return the same `{task_id, done, result}` shape, so `/api/ask?cloud=1` and the
statistical bulletin keep working unchanged. With no key configured the dashboard simply falls
back to local statistics and shows a note — it never errors out.

The frontend sends its current language as `lang`, which becomes the API `x-lang` header
(`en_US` / `zh_CN`), so the AI answers in the language the user is reading.

## API language contract

Indicator rows are stored with **Chinese canonical keys** (`category` / `indicator` so the data
files stay readable and match the official statistical terminology word-for-word). Handing those
to a non-Chinese consumer would leak `综合` / `GDP增长率` / `亿美元` straight through the API, so
localization happens in one place: `data/labels.csv` + `src/labels.py`.

Every data-bearing response carries three layers per identifier:

| Field | Meaning | Example |
| --- | --- | --- |
| `category` / `indicator` / `dimension` / `unit` | localized display value for the requested language | `National Accounts` / `GDP Growth` |
| `*_key` | the Chinese canonical key — stable across languages, use it as a join key | `综合` / `GDP增长率` |
| `*_slug` | stable ASCII identifier for programmatic use | `national_accounts` / `gdp_growth` |

Language resolution order: `?lang=` → `Accept-Language` header → `en`.

```bash
curl -s "http://127.0.0.1:5000/api/indicators?year=2024&dimension=China&lang=en"
curl -s "http://127.0.0.1:5000/api/report?format=json&year=2024&dimension=%E4%BA%9A%E5%A4%AA&lang=zh"
curl -s "http://127.0.0.1:5000/api/stats"        # public dataset-size counters
curl -s "http://127.0.0.1:5000/docs?lang=en"     # full reference
```

Admin endpoints (`/api/db`, `/api/reseed`, `/api/kv-status`, `/api/collect`) expose environment
details or mutate the store, so they require `X-Admin-Token` (or `?token=`) when
`QU_STAT_ADMIN_TOKEN` is set, and return **403 in production** when it is not. Everything a
visitor's page needs is served by public endpoints — `/api/stats` in particular exists so the
dashboard never depends on an admin route.

Input accepts all three layers, so `?dimension=China`, `?dimension=china` and `?dimension=中国`
are equivalent. Unregistered terms are returned as-is — never translated by guesswork, never
raising an error — so adding an indicator cannot break an existing call.

Run the contract check against a live server:

```bash
python scripts/check_i18n.py
```

It walks every data endpoint in both languages and fails if any display field still contains CJK
characters in English mode (or lost them in Chinese mode).

## Architecture

```text
public/                   frontend source (index.html, app.html, app.js, i18n.js, style.css)
data/ap_macro.csv         real World Bank Open Data seed (generated, committed)
data/nbs_cn.csv           real NBS / Customs seed for China domestic detail
data/labels.csv           identifier label pack: kind,key,slug,en (single source for i18n)
scripts/fetch_wb_data.py  fetch the World Bank dataset
scripts/embed_pages.py    embed public/ -> src/pages.py and data/ -> src/seed_data.py
scripts/check_i18n.py     contract check: no CJK leaks in English API responses
src/web.py                Flask app: pages, REST API, error pages, cold-start seeding
src/cli.py                argparse entry (ask / report / collect / custom / knowledge / db / web)
src/api_docs.py           /docs API reference (server-rendered, bilingual; endpoint registry)
src/error_pages.py        branded 404 / 405 / 500 pages (bilingual; JSON for /api/*)
src/loader.py             seed loading + user CSV/Excel import
src/collect.py            collection pipeline (pluggable sources, rate limited)
src/db.py                 SQLAlchemy Core over SQLite (indicators wide table + knowledge table)
src/labels.py             identifier localization: label / slug / key_of / localize_payload
src/stats/indicators.py   per-profession indicator functions (region-anchored)
src/stats/core.py         primitives: YoY, share, ranking, aggregation
src/stats/query.py        bilingual natural-language query engine (local rules)
src/stats/custom.py       custom-analysis engine over custom_analysis.yaml
src/knowledge.py          bilingual knowledge base + keyword retrieval (lightweight RAG)
src/report.py             bulletin builder (structured data + text renderer)
src/analyzer.py           pluggable AI providers: InfiniSynapse (SSE) + OpenAI-compatible
src/kv_store.py           optional Redis-compatible KV client (Upstash / Vercel KV)
src/kv_sync.py            persist and restore the SQLite snapshot through that KV store
src/pages.py              generated: frontend files inlined for serverless
src/seed_data.py          generated: seed CSVs inlined for serverless
api/index.py              Vercel serverless entry point
```

### Why assets are embedded

A Vercel serverless function cannot read `public/` or `data/` from the deployment bundle, so
`scripts/embed_pages.py` inlines the frontend files into `src/pages.py` and the seed CSVs into
`src/seed_data.py`. **After editing anything under `public/`, or after re-fetching the dataset,
re-run that script and restart the server** — otherwise you will be looking at stale assets.

## Deploying to Vercel

1. Push to the production branch; the Vercel project (`qu-stat-system`) redeploys automatically.
2. Set `INFINISYNAPSE_API_KEY` in the project's environment variables.
3. `vercel.json` routes every request to `api/index.py`; the SQLite database lives in `/tmp` and
   is rebuilt on cold start, optionally restored from a Redis-compatible KV store when the
   `KV_REST_API_URL` / `KV_REST_API_TOKEN` variables are present.
4. Optional: set `QU_STAT_BASE_URL` to your custom domain (it feeds `canonical`, `hreflang` and
   the `/docs` examples), and `QU_STAT_ADMIN_TOKEN` if you need to call the admin endpoints
   (re-seed / collect) in production.

## Windows / encoding pitfalls

These bit us, so they are documented rather than solved:

- The Windows console is GBK: printing Chinese from a diagnostic script can raise
  `UnicodeEncodeError`. Write results to a UTF-8 file and read it back instead of printing.
- Sending Chinese payloads to the GitHub API through PowerShell corrupts them into `?`
  (the command is written to a temporary `.ps1` and parsed as ANSI). Use a Python script with
  `json.dumps(..., ensure_ascii=False).encode("utf-8")` and verify by reading the response file.
- `Get-Content` shows UTF-8 Chinese as mojibake — that is a display artifact, the file is fine.

## Limitations

- The Asia-Pacific aggregate is a World Bank regional total: it is population-weighted and mixes
  economies of very different sizes, so compare growth rates rather than levels.
- Some NBS detail series are only published annually and thus exist for a single year in the
  dataset; YoY is shown as `—` when there is no prior-year row.
- Series that do not exist in a given region (for example retail sales for the Asia-Pacific
  aggregate) are reported as unavailable rather than estimated.

## License

Code is **MIT** — see [LICENSE](LICENSE).

The datasets under `data/` are public and keep their upstream terms: World Bank Open Data
(CC BY 4.0) and public releases from China NBS / China Customs. No internal or restricted
data is included anywhere in this repository.

| Looking for | Where |
| --- | --- |
| How to contribute | [CONTRIBUTING.md](CONTRIBUTING.md) · 中文：[CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md) |
| Reporting a vulnerability | [SECURITY.md](SECURITY.md) |
| What changed when | [CHANGELOG.md](CHANGELOG.md) |
| Citing this project | [CITATION.cff](CITATION.cff) |
| What the site collects | <https://qu-stat-system.vercel.app/privacy> |
| In-app API reference | <https://qu-stat-system.vercel.app/docs> |
