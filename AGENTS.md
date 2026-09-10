# AI Work-per-Dollar Index

Ranks curated subscription rows (model × thinking level × plan) by
intelligence-weighted benchmark work per dollar:

```
monthly tokens = price_usd / real_usd_per_mtok * 1e6
tasks/month    = monthly tokens / tok_per_task
value          = AA intelligence score * tasks/month / price_usd
```

```sh
python3 work_per_dollar.py                                  # full ranking
python3 work_per_dollar.py --min-tasks 50000                # hide results below 50k tasks/month
python3 work_per_dollar.py --min-score 42                   # hide results scoring below 42
python3 work_per_dollar.py --min-tasks 50000 --min-score 42 # combine both filters
python3 fetch_pricing.py                                    # refresh data/pricing_gen.csv from source
```

After editing `data/pricing_extra.csv` or `data/aa_tok_per_task.csv`, re-run
`fetch_pricing.py` so the changes flow into `pricing_gen.csv`.

## Files

| File | Role |
|---|---|
| `data/aa_tok_per_task.csv` | **Hand-maintained.** AA output tokens per Intelligence Index task (answer + reasoning), keyed by model slug + effort. Independent of the pricing repo |
| `data/pricing_gen.csv` | **Generated** by `fetch_pricing.py`: curated repo data with `pricing_extra.csv` already merged in. The single input of `work_per_dollar.py` — do not hand-edit |
| `data/pricing_extra.csv` | **Hand-maintained.** Overrides (same `id`+`effort` as a fetched row) and extra plans (yearly), same schema as `pricing_gen.csv` |
| `fetch_pricing.py` | Fetches + curates repo data, merges `pricing_extra.csv`, writes `pricing_gen.csv`; owns all curation rules |
| `work_per_dollar.py` | The ranking script — a pure calculator over `pricing_gen.csv` |

## Schema: `pricing_gen.csv` / `pricing_extra.csv`

Both files share the same columns:

| Column | Meaning |
|---|---|
| `id` | `plan::model` point id from the source repo (e.g. `cursor_pro::grok-4.6`); yearly extras use `<plan>_yearly::<model>` |
| `model` | Display name (repo `model_display`, e.g. `GPT 5.6 Luna`) |
| `effort` | Thinking level: `medium`/`high`/`xhigh`/`max`, or `none` when the provider exposes no effort selector |
| `plan` | Display-ready plan name (English, `Midpoint` marker stripped) |
| `price_usd` | Effective monthly price in USD |
| `real_usd_per_mtok` | Effective USD per million tokens (monthly tokens are derived from this) |
| `score` | AA Intelligence Index for this model at this effort |
| `tok_per_task` | Output tokens (answer + reasoning) per AA benchmark task |

## Data sources & curation

### `fetch_pricing.py` (repo → `pricing_gen.csv`)

Downloads from **https://github.com/FeiZhuLulu/real-api-pricing** (branch `main`):
`derived/points.csv` (pricing per plan × model), `derived/benchmark-points.csv`
(all benchmark configurations per point; we use `board = aa_intelligence_index`),
and `data/adopted.csv` (native billing currency per point). That board is the same
data the published site ([real-api-pricing.vercel.app](https://real-api-pricing.vercel.app))
plots on its AA Intelligence Index board.

Curation applied at fetch time (config tables at the top of the script):

- **Currency filter** — only points billed in USD or EUR are kept (`KEEP_CURRENCIES`).
  Plans whose `price_usd` is just a currency conversion (GLM/Zhipu, Kimi, MiniMax,
  Aliyun CN plans, all CNY) are excluded — their real international prices come
  from `pricing_extra.csv` instead.
- `EFFORT_WHITELIST` — per model, the only thinking levels kept.
- `VARIANT_PREFERENCE` — canonical vs dated snapshot benchmark rows (DeepSeek V4
  Flash / V4 Pro use the newer `0731` / `0813` snapshots). Dated variants of other
  models are dropped.
- `SCORE_OVERRIDES` — manually verified scores for models the repo has no score
  for (currently `qwen3.8-flash: 40`).
- Metered (pay-per-token) API rows are skipped — no monthly fee.
- Rows whose (model, effort) has no entry in `data/aa_tok_per_task.csv` are
  omitted: no tokens-per-task value ⇒ no result.
- Finally `pricing_extra.csv` is merged in: rows sharing (`id`, `effort`)
  **overwrite** the fetched row, the rest are **appended**.

Known gap: the repo replaced OpenCode Go's `deepseek-v4-flash` with
`deepseek-v4.1-flash`; add it to `EFFORT_WHITELIST` and `data/aa_tok_per_task.csv`
when AA data for it is available.

### `data/aa_tok_per_task.csv` (manual)

Columns: `model` (slug, e.g. `gpt-5.6-luna`), `effort` (`none` for models without
an effort selector), `tok_per_task` (output tokens = answer + reasoning per AA
benchmark task). Fill it for the models and thinking levels you care about —
unfilled combinations simply don't produce results.

To get exact values for a model, use the project skill
`.agents/skills/aa-exact-score/`: it extracts the full-precision AA Intelligence
Index and tokens-per-task straight from the payloads embedded in
artificialanalysis.ai pages (the site UI rounds scores). Usage:

```sh
python3 .agents/skills/aa-exact-score/scripts/extract.py deepseek-v4-1-flash --variant max
```

### `data/pricing_extra.csv` (manual)

Merge rule (applied by `fetch_pricing.py` when writing `pricing_gen.csv`): a row
whose (`id`, `effort`) matches a fetched row **overwrites** it; any other row is
**appended**. Current contents:

- **International GLM Coding plans.** Zhipu's own repo plans are CNY-billed and
  filtered out, so these rows are the only source for them — their ids drop the
  repo's `_cn` marker accordingly (`glm_coding_max_new_mid::glm-5.3`, etc.):
  Max $168, Pro $80, Lite $18 (real international USD prices, not a CNY
  conversion).
- **Yearly plans** (`<plan>_yearly::<model>` ids, `(yearly)` in plan name,
  effective monthly price under annual billing): Cursor Pro $16, Cursor Pro+ $48,
  SuperGrok $25, SuperGrok Plus $83.33, GLM Coding Max $117.6, Pro $56, Lite $12.6.

When adding rows here, `score` and `tok_per_task` must match the corresponding
model + effort values (score from the repo/AA, tok_per_task from
`data/aa_tok_per_task.csv`).
