# Asia-Pacific Statistical Analysis System

An open economic-statistics workbench for the Asia-Pacific region: **every figure comes from
official public data**, and the AI layer is only allowed to interpret those figures — never to
invent them.

- **Dashboard**: <https://qu-stat-system.vercel.app/app>
- **Data**: World Bank Open Data · China National Bureau of Statistics (NBS) · China Customs
- **AI**: InfiniSynapse Server API (`/api/ai/message` + `/api/ai/events` SSE), Bearer-token auth
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
| Bilingual, single source of truth | One dictionary (`public/i18n.js`) drives the whole UI; the English view has no leftover Chinese labels |

## Screens

Four panels — three workbenches plus a bulletin generator:

1. **AI Query** — ask in English or Chinese ("2024 GDP", "retail sales", "population of Japan").
   The engine resolves region / indicator / year, returns the real figures, and optionally hands
   them to the cloud AI for interpretation.
2. **Indicator Catalog** — searchable table of every stored series, filterable by region and
   category, with one-click hand-off to Custom Analysis.
3. **Custom Analysis** — bind variables to any category / indicator / region, use
   `share` / `diff` / `ratio` / `sum` presets, and compute YoY. Expressions are evaluated in a
   restricted namespace (no arbitrary code execution).
4. **Bulletin** — generates a statistical bulletin for the selected year and region from real
   data, with an optional AI interpretation section.
5. **Cross-economy ranking** — industry answers append a ranking of the 12 non-aggregate
   economies by industrial value added (top 10 shown), which replaced the previous fabricated
   town ranking.

## Data sources and caliber

| Dimension | Source | Notes |
| --- | --- | --- |
| Asia-Pacific (`EAS`) | World Bank Open Data | East Asia & Pacific, all income levels |
| Asia-Pacific, developing (`EAP`) | World Bank Open Data | East Asia & Pacific, excluding high income |
| China, Japan, Korea, India, Indonesia, Thailand, Viet Nam, Malaysia, Philippines, Singapore, Australia, United States | World Bank Open Data | One dimension per economy for comparison |
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
python -m src.cli ask "2024 GDP"                    # local natural-language query (EN/中文)
python -m src.cli ask "工业增加值" --cloud            # + InfiniSynapse interpretation
python -m src.cli report --year 2024                 # statistical bulletin (text)
python -m src.cli report --year 2024 --cloud         # bulletin + AI interpretation
python -m src.cli custom list                        # declared custom analyses
python -m src.cli custom run "贸易依存度"
python -m src.cli collect --country EAS --indicators gdp,population
python -m src.cli collect --source global --indicators gdp --countries CHN,USA,JPN
python -m src.cli knowledge search --query "GDP 口径"
python -m src.cli db info
```

## Configuration

`config.yaml` holds the region defaults, the database URL, and the collector settings.

The InfiniSynapse API key is read from the environment first:

```bash
export INFINISYNAPSE_API_KEY="sk-..."     # preferred, especially on Vercel
export INFINISYNAPSE_SERVER="https://app.infinisynapse.cn"   # optional override
```

`config.yaml` is tracked by git, so **never commit a real key into it** — put the secret in the
environment and leave `infinisynapse.api_key` commented out.

The frontend sends its current language as `lang`, which becomes the API `x-lang` header
(`en_US` / `zh_CN`), so the AI answers in the language the user is reading.

## Architecture

```text
public/                   frontend source (index.html, app.html, app.js, i18n.js, style.css)
data/ap_macro.csv         real World Bank Open Data seed (generated, committed)
data/nbs_cn.csv           real NBS / Customs seed for China domestic detail
scripts/fetch_wb_data.py  fetch the World Bank dataset
scripts/embed_pages.py    embed public/ -> src/pages.py and data/ -> src/seed_data.py
src/web.py                Flask app: pages, REST API, cold-start seeding
src/cli.py                argparse entry (ask / report / collect / custom / knowledge / db / web)
src/loader.py             seed loading + user CSV/Excel import
src/collect.py            collection pipeline (pluggable sources, rate limited)
src/db.py                 SQLAlchemy Core over SQLite (indicators wide table + knowledge table)
src/stats/indicators.py   per-profession indicator functions (region-anchored)
src/stats/core.py         primitives: YoY, share, ranking, aggregation
src/stats/query.py        bilingual natural-language query engine (local rules)
src/stats/custom.py       custom-analysis engine over custom_analysis.yaml
src/knowledge.py          bilingual knowledge base + keyword retrieval (lightweight RAG)
src/report.py             bulletin builder (structured data + text renderer)
src/analyzer.py           InfiniSynapse Server API client (SSE streaming)
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

MIT
