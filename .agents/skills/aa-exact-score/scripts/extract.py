#!/usr/bin/env python3
"""Extract exact Artificial Analysis intelligence metrics for one model.

Fetches the model's public page(s) on artificialanalysis.ai, joins the Next.js
RSC payload chunks embedded in the HTML, and prints every configuration object
that carries an intelligenceIndex for the requested model — at full precision.
The AA website UI rounds these values (see the `scoreRoundedDisplay` field AA
ships alongside the raw number); this script reports the raw one.

Usage:
    python3 extract.py deepseek-v4-1-flash
    python3 extract.py gpt-5-6-sol --variant medium

Output: one JSON line per configuration found, with:
    intelligenceIndex   exact index (use as-is, do not round)
    tokPerTask          output tokens per task = reasoning + answer, rounded
                        to the nearest integer (project convention)
    estimated           AA's own flag; estimated configurations are marked
"""

import argparse
import json
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
PUSH_RE = re.compile(r'self\.__next_f\.push\(\[1,("(?:[^"\\]|\\.)*")\]\)')


def payload_of(url: str) -> str:
    req = urllib.request.Request(url, headers=UA)
    html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    return "".join(json.loads(chunk) for chunk in PUSH_RE.findall(html))


def objects_containing(payload: str, needle: str) -> list[dict]:
    """Innermost `{...}` objects whose raw text contains `needle`.

    Single string-aware pass building a brace stack; at each needle hit the
    innermost enclosing object start is recorded, then brace-walked forward.
    """
    hits: list[int] = []
    stack: list[int] = []
    in_str = esc = False
    i = 0
    n = len(payload)
    while i < n:
        ch = payload[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            stack.append(i)
        elif ch == "}":
            start = stack.pop() if stack else None
            if start is not None and needle in payload[start:i + 1]:
                hits.append(start)
        i += 1

    out = []
    for start in hits:
        depth = 0
        j = start
        in_str = esc = False
        while j < n:
            ch = payload[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        try:
            obj = json.loads(payload[start:j + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            out.append(obj)
    return out


def summarize(obj: dict) -> dict | None:
    if obj.get("intelligenceIndex") is None:
        return None
    toks = obj.get("intelligenceIndexOutputTokensPerTask") or {}
    reasoning, answer = toks.get("reasoning"), toks.get("answer")
    effort = obj.get("effort")
    return {
        "shortName": obj.get("shortName"),
        "slug": obj.get("slug"),
        "effort": effort.get("label") if isinstance(effort, dict) else effort,
        "intelligenceIndex": obj.get("intelligenceIndex"),
        "estimated": obj.get("intelligenceIndexIsEstimated"),
        "tokPerTask": round(reasoning + answer) if reasoning is not None and answer is not None else None,
        "costPerTaskUsd": obj.get("costPerTaskUsd"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", help="AA model slug, e.g. deepseek-v4-1-flash")
    parser.add_argument("--variant", default=None,
                        help="only show configurations whose slug/shortName contains this (e.g. max)")
    args = parser.parse_args()

    urls = [f"https://artificialanalysis.ai/models/{args.model}",
            "https://artificialanalysis.ai/leaderboards/models"]
    seen, found = set(), []
    for url in urls:
        try:
            payload = payload_of(url)
        except Exception as exc:  # noqa: BLE001 - report and try next page
            print(f"warning: {url} failed: {exc}", file=sys.stderr)
            continue
        for needle in (args.model, f'"{args.model}"'):
            for obj in objects_containing(payload, needle):
                s = summarize(obj)
                if s is None:
                    continue
                key = json.dumps(s, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                if args.variant:
                    slug = s["slug"] or ""
                    # configuration slugs are "<model-slug>[-<variant>]"; this
                    # keeps gpt-5-6-sol-medium when filtering gpt-5-6-sol while
                    # excluding unrelated models that share the effort name
                    on_target = slug == args.model or slug.startswith(args.model + "-")
                    if args.variant.lower() not in (slug + (s["shortName"] or "")).lower() or not on_target:
                        continue
                found.append(s)
        if found:
            break  # model page is authoritative; skip the generic leaderboard

    if not found:
        print("no scored configuration found for this model — "
              "AA may not have published a score yet", file=sys.stderr)
        return 1
    for s in found:
        print(json.dumps(s))
    return 0


if __name__ == "__main__":
    sys.exit(main())
