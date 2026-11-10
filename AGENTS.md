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
python3 work_per_dollar.py --max-price 20                   # hide results costing more than $20/month
python3 work_per_dollar.py --min-tasks 50000 --min-score 42 # combine filters
python3 work_per_dollar.py --no-chart                       # table only, no value bars
python3 work_per_dollar.py --chart-width 8                  # narrower value bars
python3 fetch_pricing.py                                    # refresh data/pricing_gen.csv from source
```

After editing `data/pricing_extra.csv` or `data/aa_tok_per_task.csv`, re-run
`fetch_pricing.py` so the changes flow into `pricing_gen.csv`.

## Files

| File | Role |
|---|---|
| `data/aa_tok_per_task.csv` | **Hand-maintained.** The AA activation table: Intelligence Index score **and** output tokens per task (answer + reasoning) per model slug + effort. It is the authoritative AA snapshot for the index — repo scores are only used to discover which efforts a point exposes |
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
| `score` | AA Intelligence Index for this model at this effort (taken from `aa_tok_per_task.csv`, not from the repo) |
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
- **Inclusion rule (data-driven)** — a row is emitted only when its
  (`model`, `effort`) exists in `data/aa_tok_per_task.csv`. There is no hardcoded
  model list: adding a row there makes every plan carrying that model + effort
  appear on the next fetch. That table also supplies the `score` and
  `tok_per_task` written for the row, so the repo's own scores are only used to
  discover which efforts a point exposes (and, for models the repo cannot score
  at all, the table itself drives that discovery).
- `VARIANT_PREFERENCE` — canonical vs dated snapshot benchmark rows (DeepSeek V4
  Flash / V4 Pro use the newer `0731` / `0813` snapshots). Dated variants of other
  models are dropped. This only affects effort discovery now; the score always
  comes from `aa_tok_per_task.csv`.
- `SCORE_OVERRIDES` — fallback score for models the repo has no score for
  (currently `qwen3.8-flash: 40`), so their points reach the AA-table join.
- Metered (pay-per-token) API rows are skipped — no monthly fee.
- Finally `pricing_extra.csv` is merged in: rows sharing (`id`, `effort`)
  **overwrite** the fetched row, the rest are **appended**.

DeepSeek V4.1 Flash is served under an untimestamped point id
(`opencode_go::deepseek-v4.1-flash`), but every upstream point for it is mapped to
the AA configuration `DeepSeek V4.1 Flash 1017 (max)` — upstream's
`highest_archived_reference` selection, and the only configuration AA still
publishes. The index therefore measures the 1017 snapshot; the repo score
(45.0965) is superseded by the AA table's live value (32.5896, 138,962 tok/task).

### `data/aa_tok_per_task.csv` (manual)

Columns: `model` (slug, e.g. `gpt-6-luna`), `effort` (`none` for models without
an effort selector), `score` (exact AA Intelligence Index), `tok_per_task`
(output tokens = answer + reasoning per AA benchmark task). Fill it for the models
and thinking levels you care about — unfilled combinations simply don't produce
results.

This file is the AA basis of the whole table: all rows in `pricing_gen.csv` take
their `score` and `tok_per_task` from here, so keep values from a single AA
index revision. AA re-versions its index (scores and task lengths move together),
which is why the repo's own 4-dp scores are ignored once a row exists here.

To get exact values for a model, use the project skill
`.agents/skills/aa-exact-score/`: it extracts the full-precision AA Intelligence
Index and tokens-per-task straight from the payloads embedded in
artificialanalysis.ai pages (the site UI rounds scores). Usage:

```sh
python3 .agents/skills/aa-exact-score/scripts/extract.py deepseek-v4-1-flash --variant max
```

AA's model page only embeds the default (highest) variant; fetch the effort pages
directly for the others, e.g. `claude-opus-5-5-high`, `gpt-6-1-sol-medium`,
`grok-4-7-high`.

### `data/pricing_extra.csv` (manual)

Merge rule (applied by `fetch_pricing.py` when writing `pricing_gen.csv`): a row
whose (`id`, `effort`) matches a fetched row **overwrites** it; any other row is
**appended**. Extras should stay **additive**: when the fetched data already
carries the same (`id`, `effort`), the fetch should report `0 rows overwritten`.
If it does not, either fix the value upstream or drop the extra row. Current
contents:

- **International GLM Coding plans.** Upstream only has the CNY-billed
  `glm_coding_*_cn_*` points, which the currency filter drops before the merge;
  the international ids (`glm_coding_max_new_mid::glm-5.3`, etc.) do not exist
  upstream, so these rows are purely additive: Max $168, Pro $80, Lite $18 (real
  international USD prices, not a CNY conversion), plus yearly variants at
  $117.6 / $56 / $12.6.
- **MiMo Token Plans.** Same pattern: upstream uses these exact ids
  (`mimo_token_lite_day::mimo-v2.6-pro`, …) but bills them in CNY, so the
  currency filter removes them before the merge and nothing is overwritten. Our
  rows keep the USD prices ($6 / $16 / $50 / $100) with the plan's real monthly
  token allowance, which is why `real_usd_per_mtok` differs from the upstream CNY
  conversion (Lite Day 0.01609 vs 0.01893). Lite / Standard / Pro / Max ×
  Day / Night 0.8x.
- **Muse Code plans.** No upstream point at all; low-confidence quota estimates
  documented in `data/pricing_estimates.md` ($5 / $15 / $50, `(estimated)` in the
  plan label).

Cursor, SuperGrok and ChatGPT Plus are deliberately absent: upstream covers them
in USD, including the Cursor/SuperGrok yearly variants that used to live here.

When adding rows here, `score` and `tok_per_task` must be copied from the
corresponding model + effort row of `data/aa_tok_per_task.csv` (that table is the
AA basis, not the repo).
