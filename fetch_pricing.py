#!/usr/bin/env python3
"""Fetch and curate pricing points from the public real-api-pricing project
into data/pricing_gen.csv.

Source: https://github.com/FeiZhuLulu/real-api-pricing
  * derived/points.csv          one row per subscription plan x model
  * derived/benchmark-points.csv  one row per point x benchmark configuration
  * data/adopted.csv            native billing currency per point

All curation happens here, so work_per_dollar.py stays a pure calculator:
  * only points billed in USD or EUR are kept
  * only models / thinking levels in EFFORT_WHITELIST are kept
  * VARIANT_PREFERENCE picks canonical vs dated snapshot benchmark rows
  * estimated scores are dropped; SCORE_OVERRIDES fills missing scores
  * rows are joined with data/aa_tok_per_task.csv; a row without a
    tokens-per-task value there is omitted entirely
  * data/pricing_extra.csv is merged in last (rows sharing an id+effort
    overwrite the fetched row, the rest are appended), so work_per_dollar.py
    has this single CSV to read
"""

from __future__ import annotations

import csv
import io
import re
import sys
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
AA_TOKENS_CSV = DATA_DIR / "aa_tok_per_task.csv"
PRICING_EXTRA_CSV = DATA_DIR / "pricing_extra.csv"
OUTPUT_CSV = DATA_DIR / "pricing_gen.csv"

REPO_RAW = "https://raw.githubusercontent.com/FeiZhuLulu/real-api-pricing/main/derived"
REPO_DATA_RAW = "https://raw.githubusercontent.com/FeiZhuLulu/real-api-pricing/main/data"
POINTS_URL = f"{REPO_RAW}/points.csv"
BENCHMARK_URL = f"{REPO_RAW}/benchmark-points.csv"
ADOPTED_URL = f"{REPO_DATA_RAW}/adopted.csv"
BOARD = "aa_intelligence_index"

# Points billed in any other currency are skipped (their price_usd is a
# currency conversion, not a real international price).
KEEP_CURRENCIES = {"USD", "EUR"}

OUTPUT_COLUMNS = ["id", "model", "effort", "plan", "price_usd", "real_usd_per_mtok", "score", "tok_per_task"]

# (id, effort) identifies one benchmark row.
KEY_FIELDS = ("id", "effort")

# ---------------------------------------------------------------------------
# Curation config — edit here when new models / benchmark data arrive.
# ---------------------------------------------------------------------------

# Allowed thinking levels per model (normalized: lowercase slug, "none" when
# the provider exposes no effort selector). Anything else is dropped.
EFFORT_WHITELIST: dict[str, set[str]] = {
    "gpt-5.6-luna": {"max"},
    "gpt-5.6-sol": {"medium", "high", "xhigh"},
    "grok-4.6": {"medium", "high", "xhigh"},
    "deepseek-v4-flash": {"max"},
    "deepseek-v4-pro": {"max"},
    "glm-5.3": {"max"},
    "glm-5.3-flash": {"none"},
    "qwen3.8-flash": {"none"},
}

# Manually verified AA intelligence scores for models the repo has no score
# for (the repo never invents scores; neither do we beyond this table).
SCORE_OVERRIDES: dict[str, float] = {
    "qwen3.8-flash": 40.0,
}

# Dated snapshot benchmarks, e.g. "DeepSeek V4 Flash 0731 (max)".
DATED_VARIANT_RE = re.compile(r"\b\d{4}\b")

# Which benchmark variant to use per model. Default is the canonical row;
# "dated" prefers the newer dated snapshot (higher score, same quota).
VARIANT_PREFERENCE: dict[str, str] = {
    "deepseek-v4-flash": "dated",
    "deepseek-v4-pro": "dated",
}

# English plan-label map from the source project's web front-end
# (web/src/domain.ts, displayPlan).
GLM_RENAMES = (("老客", "v2"), ("新客", "v3"))
EN_WORDS = {
    "Kimi 会员 ": "Kimi CN CNY ",
    "阿里云百炼": "Alibaba Cloud CN",
    "新客": "New",
    "老客": "Existing",
    "闲时": "Off-peak",
    "中间值": "Midpoint",
    "忙时": "Peak",
}

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def norm_model(raw: str) -> str:
    """'GPT 5.6 Luna' / 'GPT_5.6 luna' -> 'gpt-5.6-luna'."""
    s = raw.strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"[^a-z0-9.-]", "", s)


def norm_effort(raw: str | None) -> str:
    s = (raw or "").strip().lower()
    return "none" if s in {"", "none", "non-reasoning", "non_reasoning", "default"} else s


def display_plan(plan: str) -> str:
    """Reproduce the source web app's English plan label, minus the
    peak/mid/off-peak 'Midpoint' marker we do not display."""
    if plan.startswith("GLM "):
        for src, dst in GLM_RENAMES:
            plan = plan.replace(src, dst)
    for src, dst in EN_WORDS.items():
        plan = plan.replace(src, dst)
    return re.sub(r"\s+Midpoint(?=\s*\(|$)", "", plan).strip()


# ---------------------------------------------------------------------------
# Fetch + curate
# ---------------------------------------------------------------------------


def fetch_csv(url: str) -> list[dict]:
    with urllib.request.urlopen(url) as resp:
        text = resp.read().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text)))


def read_local_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_currencies() -> dict[str, str]:
    """Point id -> native billing currency, from the repo's adopted table."""
    return {
        f"{row['plan_id']}::{row['served_model']}": row["currency"].strip().upper()
        for row in fetch_csv(ADOPTED_URL)
    }


def load_tok_per_task() -> dict[tuple[str, str], int]:
    return {
        (norm_model(row["model"]), norm_effort(row["effort"])): int(row["tok_per_task"])
        for row in read_local_csv(AA_TOKENS_CSV)
    }


def merge_extra(gen: list[dict], extra: list[dict]) -> tuple[list[dict], int, int]:
    """Rows from `extra` overwrite gen rows sharing the same (id, effort);
    the rest are appended (e.g. yearly plans).
    Returns (merged rows, appended count, overwritten count)."""
    extra_by_key: dict[tuple[str, ...], list[dict]] = {}
    for row in extra:
        extra_by_key.setdefault(tuple(row[k] for k in KEY_FIELDS), []).append(row)
    merged, overwritten = [], 0
    for row in gen:
        replacements = extra_by_key.pop(tuple(row[k] for k in KEY_FIELDS), None)
        if replacements:
            merged.extend(replacements)
            overwritten += 1
        else:
            merged.append(row)
    appended = sum(len(rows) for rows in extra_by_key.values())
    for leftover in extra_by_key.values():
        merged.extend(leftover)
    return merged, appended, overwritten


def benchmark_rows_for_board(bench: list[dict]) -> dict[str, list[dict]]:
    by_point: dict[str, list[dict]] = {}
    for row in bench:
        if row["board"] == BOARD:
            by_point.setdefault(row["point_id"], []).append(row)
    return by_point


def curate_point(point: dict, bench_rows: list[dict] | None) -> list[tuple[str, float]]:
    """Return the (effort, score) candidates kept for one point."""
    slug = norm_model(point["model"])
    allowed = EFFORT_WHITELIST.get(slug)
    if allowed is None:
        return []

    kept: list[tuple[str, float]] = []
    prefer_dated = VARIANT_PREFERENCE.get(slug) == "dated"
    for row in bench_rows or []:
        is_dated = bool(DATED_VARIANT_RE.search(row["variant"]))
        if is_dated != prefer_dated:
            continue
        effort = norm_effort(row["reasoning_effort"])
        if effort not in allowed:
            continue
        if row["score_is_estimated"].strip().lower() == "true":
            continue
        score_raw = row["score"].strip()
        score = float(score_raw) if score_raw else SCORE_OVERRIDES.get(slug)
        if score is not None:
            kept.append((effort, score))

    if not bench_rows and "none" in allowed:
        # Point never scored on this board (no effort selector, no score yet).
        score_raw = (point.get("aa_intelligence_index__score") or "").strip()
        score = float(score_raw) if score_raw else SCORE_OVERRIDES.get(slug)
        if score is not None:
            kept.append(("none", score))
    return kept


def main() -> int:
    points = fetch_csv(POINTS_URL)
    bench_by_point = benchmark_rows_for_board(fetch_csv(BENCHMARK_URL))
    currencies = load_currencies()
    tok_per_task = load_tok_per_task()

    rows = []
    stats = {"non_usd_eur": 0, "outside_whitelist": 0, "metered": 0, "no_tok_per_task": 0}
    for point in points:
        if currencies.get(point["id"]) not in KEEP_CURRENCIES:
            stats["non_usd_eur"] += 1
            continue
        if not point["price_usd"].strip():
            stats["metered"] += 1  # pay-per-token API rows have no monthly fee
            continue
        candidates = curate_point(point, bench_by_point.get(point["id"]))
        if not candidates:
            stats["outside_whitelist"] += 1
            continue
        for effort, score in candidates:
            tpt = tok_per_task.get((norm_model(point["model"]), effort))
            if tpt is None:
                stats["no_tok_per_task"] += 1
                continue
            rows.append({
                "id": point["id"],
                "model": point["model_display"],
                "effort": effort,
                "plan": display_plan(point["plan"]),
                "price_usd": f"{float(point['price_usd']):g}",
                "real_usd_per_mtok": point["real_usd_per_mtok"],
                "score": f"{score:g}",
                "tok_per_task": tpt,
            })

    rows, appended, overridden = merge_extra(rows, read_local_csv(PRICING_EXTRA_CSV))

    rows.sort(key=lambda r: (r["id"], r["effort"]))
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(points)} points scanned from the repo")
    print(f"{len(rows)} rows written to {OUTPUT_CSV.relative_to(BASE_DIR)}")
    print(f"pricing_extra merged: {appended} rows appended, {overridden} rows overwritten")
    print(f"skipped: {stats['non_usd_eur']} points not billed in USD/EUR, "
          f"{stats['outside_whitelist']} points outside EFFORT_WHITELIST, "
          f"{stats['metered']} metered (no monthly fee), "
          f"{stats['no_tok_per_task']} rows without a tok_per_task value")
    return 0


if __name__ == "__main__":
    sys.exit(main())
