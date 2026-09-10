# AI Work-per-Dollar Index

Ranks AI subscription plans (model × thinking level × plan) by
**intelligence-weighted benchmark work per dollar** — how many Artificial
Analysis Intelligence Index-equivalent tasks your monthly fee buys, weighted
by the score the model actually achieves at that thinking level.

```
monthly tokens = price_usd / real_usd_per_mtok * 1e6
tasks/month    = monthly tokens / tok_per_task
value          = AA intelligence score * tasks/month / price_usd
```

The headline metric captures two effects a naive `score / price` ratio misses:

- higher thinking levels burn far more tokens per task (max effort is rarely
  worth it), and
- models differ wildly in how verbose they are per task.

## Usage

```sh
python3 fetch_pricing.py    # refresh data/pricing_gen.csv from the source repo
python3 work_per_dollar.py  # print the ranking
```

Filter the results, e.g. serious plans only:

```sh
python3 work_per_dollar.py --min-tasks 50000 --min-score 42
```

## Data

Pricing points come from the excellent open project
[FeiZhuLulu/real-api-pricing](https://github.com/FeiZhuLulu/real-api-pricing)
(AA Intelligence Index board). Tokens-per-task values come from Artificial
Analysis measurements, curated by hand in `data/aa_tok_per_task.csv`.

See [AGENTS.md](AGENTS.md) for the full pipeline documentation: file schemas,
curation rules, and how to add a model or plan.
