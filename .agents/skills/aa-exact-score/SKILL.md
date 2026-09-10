---
name: aa-exact-score
description: Extract the EXACT (full-precision) Artificial Analysis Intelligence Index score and output-tokens-per-task for any model variant, straight from the payloads embedded in artificialanalysis.ai pages — the AA website UI rounds scores, this gets the raw value. Use whenever exact AA scores are needed: filling data/aa_tok_per_task.csv or data/pricing_extra.csv in the ai-work-per-dollar-index project, adding a new model to that index, or any time the user mentions AA scores, Intelligence Index precision, or "the AA website only shows rounded values".
---

# AA exact score extraction

Artificial Analysis computes its Intelligence Index at full precision (a weighted
blend of sub-benchmark fractions) and ships the raw value inside the React Server
Components payload of its pages. The rendered UI only shows a rounded display
value (AA even includes a `scoreRoundedDisplay` field). This skill reads the
payload, not the UI.

## Workflow

1. Run the bundled extractor with the model's AA slug (kebab-case, e.g.
   `deepseek-v4-1-flash` — visible in AA page URLs), from the project root:

   ```sh
   python3 .agents/skills/aa-exact-score/scripts/extract.py deepseek-v4-1-flash
   ```

   Add `--variant max` (or `medium`, `xhigh`…) to filter to one configuration
   when a model has several effort levels.

2. Interpret the JSON lines. Each line is one configuration:

   ```json
   {"shortName": "DeepSeek V4.1 Flash (max)", "slug": "deepseek-v4-1-flash", "effort": "max",
    "intelligenceIndex": 39.545442472527, "estimated": false, "tokPerTask": 88574, ...}
   ```

   - `intelligenceIndex` is the exact score — use it as-is, never round it.
   - `tokPerTask` is output tokens per task (reasoning + answer), already rounded
     to the nearest integer, matching the project's convention (e.g. GPT-5.6 Sol
     medium = 7874).
   - `estimated: true` means AA itself flags the value as an estimate; in the
     ai-work-per-dollar-index project such rows are normally excluded unless the
     user says otherwise.

3. If the script prints "no scored configuration found", AA has not published a
   score for that model/variant yet. Say so — do not guess, do not reuse another
   variant's or model's score.

4. Where to write the values depends on the target (ai-work-per-dollar-index
   project): `tokPerTask` goes to `data/aa_tok_per_task.csv` (columns
   `model,effort,tok_per_task`, slug + normalized effort), the exact score goes
   to `data/pricing_extra.csv` (`score` column, keyed by point `id` + `effort`).
   After editing those files, `fetch_pricing.py` must be re-run there.

## Notes

- The model detail page (`/models/<slug>`) is authoritative; the extractor falls
  back to the generic leaderboard page, where unscored models appear with a null
  score (the page lists configurations AA has not scored yet).
- Scores are snapshots of what AA serves right now. AA re-versions its index
  (e.g. v4.3), so values extracted at different dates are not directly comparable
  to older snapshots.
