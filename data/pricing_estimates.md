# Muse Code subscription estimates

Added 2026-10-01. These are low-confidence, workload-specific estimates, not
published token entitlements. Their plan labels include `(estimated)` so this
qualification appears in the ranking.

## Evidence

- [Meta's product page](https://dev.meta.ai/products/muse-code) lists Everyday
  at $5/month, High at $15/month with 5x Everyday usage, and Power at $50/month
  with 20x Everyday usage. Older reports use 3x/10x; those are not used here.
- [Everyday user report](https://www.reddit.com/r/MetaAI/comments/1wftsrp/muse_code_is_a_scam_just_use_the_contributor_api/):
  50.2M input tokens (including 49M cached), 355K output tokens, and 35% of the
  weekly allowance consumed. The report also lists 5.66M subagent tokens;
  whether these are included in the totals is unclear.
- [Quota implementation documentation](https://github.com/steipete/CodexBar/blob/main/docs/muse.md)
  describes five-hour and weekly weighted limits, rather than a flat raw-token
  allowance.
- [Artificial Analysis](https://artificialanalysis.ai/models/muse-spark-1-3):
  Muse Spark 1.3 max score `48.0923107719685`, output tokens per task `60200`,
  extracted with the project's aa-exact-score skill on 2026-10-01.

## Calculation

Assume the reported session consumed 35 percentage points of a weekly quota,
the subagent tokens are already included, and the same workload can exhaust
the weekly allowance despite the five-hour limit. Use the project's four-week
month convention:

```text
Everyday monthly MTok = (50.2 + 0.355) / 0.35 * 4
                     = 577.7714285714286
High monthly MTok    = Everyday * 5  = 2888.857142857143
Power monthly MTok   = Everyday * 20 = 11555.42857142857
real_usd_per_mtok    = monthly subscription price / monthly MTok
```

The same raw-token estimate is paired with the existing Muse Spark 1.3 `max`
benchmark configuration. This assumes the sample's effective allowance also
applies to that model/configuration; the report does not establish its effort
setting or how Standard and Contributor modes consume quota. High and Power
are extrapolations, not independent measurements. Cache mix, output mix,
reasoning, subagent accounting, and model choice may change attainable tokens.
The raw sample has not been normalized to the upstream standard workload.

Rows use `muse_code_everyday::muse-spark-1.3`,
`muse_code_high::muse-spark-1.3`, and `muse_code_power::muse-spark-1.3`.
Replace these estimates when direct quota measurements or official allowances
become available.
