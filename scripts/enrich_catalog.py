#!/usr/bin/env python3
"""Batch-enrich an existing IEEE metadata catalog JSON file.

Uses OpenAlex DOI-batch lookups (keywords + abstracts) with optional Semantic
Scholar batch fallback. Writes updated .json, .txt, and refreshes summary stats.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

# Reuse formatting helpers from the single-record harvester.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from ieee_metadata_harvester import PaperRecord, decode_openalex_abstract  # noqa: E402

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "LiteratureFinderHelper/1.1 (mailto:research@example.com)",
        "Accept": "application/json",
    }
)

OPENALEX_BATCH = 100  # OpenAlex accepts up to 100 OR-values per filter
SS_BATCH = 100
CHECKPOINT_EVERY = 10


class OpenAlexUnavailable(RuntimeError):
    """OpenAlex kept failing (usually the daily credit budget is exhausted)."""


def normalize_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    return doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")


def format_catalog_line(record: dict[str, Any]) -> str:
    paper = PaperRecord(
        authors=record.get("authors") or "",
        title=record.get("title") or "",
        journal=record.get("journal") or "",
        volume=record.get("volume"),
        issue=record.get("issue"),
        pages=record.get("pages"),
        month=record.get("month"),
        year=record.get("year"),
        doi=record.get("doi"),
        abstract=record.get("abstract"),
        keywords=record.get("keywords"),
        url=record.get("url"),
        arnumber=record.get("arnumber"),
        isnumber=record.get("isnumber"),
        sources=dict(record.get("sources") or {}),
    )
    line = paper.format_plain()
    if not record.get("abstract"):
        line = line.replace("  Abstract:   ", "  Abstract: N/A  ", 1)
        line = line.replace("  Abstract:  ", "  Abstract: N/A  ", 1)
    if not record.get("keywords"):
        line = re.sub(r"keywords: \{[^}]*\}", "keywords: {N/A}", line)
    return line


def openalex_batch(dois: list[str]) -> dict[str, dict[str, Any]]:
    """Look up a DOI batch. Raises OpenAlexUnavailable instead of silently returning nothing."""
    if not dois:
        return {}
    filt = "doi:" + "|".join(dois)
    last = ""
    for attempt in range(4):
        try:
            resp = SESSION.get(
                "https://api.openalex.org/works",
                params={
                    "filter": filt,
                    "per-page": len(dois),
                    "select": "doi,abstract_inverted_index,keywords",
                },
                timeout=60,
            )
            if resp.status_code == 429:
                last = f"HTTP 429, remaining={resp.headers.get('X-RateLimit-Remaining')}"
                time.sleep(2.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            out: dict[str, dict[str, Any]] = {}
            for work in resp.json().get("results") or []:
                doi = normalize_doi((work.get("doi") or "").replace("https://doi.org/", ""))
                if doi:
                    out[doi] = work
            return out
        except requests.RequestException as exc:
            last = str(exc)
            print(f"  OpenAlex batch warning: {exc}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
    raise OpenAlexUnavailable(last)


def semanticscholar_batch(dois: list[str]) -> dict[str, str]:
    if not dois:
        return {}
    ids = [f"DOI:{d}" for d in dois]
    for attempt in range(5):
        try:
            resp = SESSION.post(
                "https://api.semanticscholar.org/graph/v1/paper/batch",
                params={"fields": "externalIds,abstract"},
                json={"ids": ids},
                timeout=60,
            )
            if resp.status_code == 429:
                time.sleep(3.0 * (attempt + 1))
                continue
            resp.raise_for_status()
            out: dict[str, str] = {}
            for paper in resp.json() or []:
                if not paper:
                    continue
                doi = normalize_doi((paper.get("externalIds") or {}).get("DOI"))
                abstract = (paper.get("abstract") or "").strip()
                if doi and abstract:
                    out[doi] = abstract
            return out
        except requests.RequestException as exc:
            print(f"  Semantic Scholar batch warning: {exc}", file=sys.stderr)
            time.sleep(2.0 * (attempt + 1))
    return {}


def apply_openalex(record: dict[str, Any], work: dict[str, Any]) -> None:
    sources = record.setdefault("sources", {})
    if not record.get("abstract"):
        abs_text = decode_openalex_abstract(work.get("abstract_inverted_index"))
        if abs_text:
            record["abstract"] = abs_text
            sources["abstract"] = "openalex"
    if not record.get("keywords") and work.get("keywords"):
        kws = [k.get("display_name") for k in work["keywords"] if k.get("display_name")]
        if kws:
            record["keywords"] = "; ".join(kws[:20])
            sources["keywords"] = "openalex"


def save_checkpoint(path: Path | None, records: list[dict[str, Any]], attempted: set[int]) -> None:
    if path:
        path.write_text(
            json.dumps({"attempted": sorted(attempted), "records": records}, ensure_ascii=False),
            encoding="utf-8",
        )


def enrich_records(
    records: list[dict[str, Any]],
    *,
    delay: float,
    use_ss_fallback: bool,
    checkpoint_path: Path | None,
    attempted: set[int] | None = None,
) -> tuple[int, int]:
    dois = [normalize_doi(r.get("doi")) for r in records]
    valid_indices = [i for i, d in enumerate(dois) if d]
    attempted = attempted if attempted is not None else set()
    # Only ask OpenAlex about records that still lack something and were not tried already.
    todo = [
        i
        for i in valid_indices
        if i not in attempted and not (records[i].get("abstract") and records[i].get("keywords"))
    ]
    kw_added = abs_added = 0
    print(f"  {len(todo)} records need OpenAlex lookup ({len(attempted)} already attempted)", file=sys.stderr)

    batches = [todo[i : i + OPENALEX_BATCH] for i in range(0, len(todo), OPENALEX_BATCH)]

    for batch_no, batch_idxs in enumerate(batches):
        batch_dois = [dois[i] for i in batch_idxs if dois[i]]
        try:
            works = openalex_batch(batch_dois)
        except OpenAlexUnavailable as exc:
            save_checkpoint(checkpoint_path, records, attempted)
            raise OpenAlexUnavailable(
                f"stopped at batch {batch_no + 1}/{len(batches)} ({exc}); "
                f"checkpoint saved, rerun with --resume later"
            ) from exc
        attempted.update(batch_idxs)
        for idx in batch_idxs:
            doi = dois[idx]
            if not doi:
                continue
            work = works.get(doi)
            if not work:
                continue
            before_kw = bool(records[idx].get("keywords"))
            before_abs = bool(records[idx].get("abstract"))
            apply_openalex(records[idx], work)
            if records[idx].get("keywords") and not before_kw:
                kw_added += 1
            if records[idx].get("abstract") and not before_abs:
                abs_added += 1

        if batch_no % 10 == 0 or batch_no == len(batches) - 1:
            print(
                f"  OpenAlex batch {batch_no + 1}/{len(batches)} · "
                f"+{kw_added} keywords · +{abs_added} abstracts",
                file=sys.stderr,
            )
        if (batch_no + 1) % CHECKPOINT_EVERY == 0:
            save_checkpoint(checkpoint_path, records, attempted)
        if delay:
            time.sleep(delay)

    if use_ss_fallback:
        missing_abs = [i for i in valid_indices if not records[i].get("abstract")]
        ss_batches = [
            missing_abs[i : i + SS_BATCH] for i in range(0, len(missing_abs), SS_BATCH)
        ]
        print(f"  Semantic Scholar fallback for {len(missing_abs)} missing abstracts", file=sys.stderr)
        for batch_no, batch_idxs in enumerate(ss_batches, start=1):
            batch_dois = [dois[i] for i in batch_idxs if dois[i]]
            found = semanticscholar_batch(batch_dois)
            for idx in batch_idxs:
                doi = dois[idx]
                if doi and doi in found and not records[idx].get("abstract"):
                    records[idx]["abstract"] = found[doi]
                    records[idx].setdefault("sources", {})["abstract"] = "semanticscholar"
                    abs_added += 1
            if batch_no % 5 == 0 or batch_no == len(ss_batches):
                print(
                    f"  SS batch {batch_no}/{len(ss_batches)} · total abstracts now "
                    f"{sum(1 for r in records if r.get('abstract'))}",
                    file=sys.stderr,
                )
            time.sleep(max(delay, 3.0))

    if checkpoint_path and checkpoint_path.exists():
        checkpoint_path.unlink(missing_ok=True)
    return kw_added, abs_added


def write_txt(records: list[dict[str, Any]], path: Path) -> None:
    path.write_text(
        "\n\n".join(format_catalog_line(r) for r in records) + "\n",
        encoding="utf-8",
    )


def patch_summary(summary_path: Path, records: list[dict[str, Any]], kw_added: int, abs_added: int) -> None:
    if not summary_path.exists():
        return
    text = summary_path.read_text(encoding="utf-8")
    n = len(records)
    with_abs = sum(1 for r in records if r.get("abstract"))
    with_kw = sum(1 for r in records if r.get("keywords"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d (UTC)")

    replacements = [
        (r"- \*\*With abstracts:\*\* \d+ \(\d+\.\d+%\)", f"- **With abstracts:** {with_abs} ({with_abs / n * 100:.1f}%)"),
        (r"- \*\*With IEEE/author keywords:\*\* \d+ \(\d+\.\d+%\)", f"- **With IEEE/author keywords:** {with_kw} ({with_kw / n * 100:.1f}%)"),
        (r"\*\*Catalog generated:\*\* .*", f"**Catalog generated:** {now}"),
    ]
    for pattern, repl in replacements:
        text, count = re.subn(pattern, repl, text, count=1)
        if count == 0 and "With OpenAlex topic keywords" not in text:
            pass

    note = (
        f"\n## Enrichment pass ({now})\n\n"
        f"- OpenAlex topic keywords added in this pass: **{kw_added}** (total with keywords: {with_kw})\n"
        f"- Abstracts added in this pass: **{abs_added}** (total with abstracts: {with_abs})\n"
        f"- Keywords are **OpenAlex inferred topics**, not IEEE Index Terms / author keywords.\n"
        f"- Records still without abstract: **{n - with_abs}** (not fabricated).\n"
    )
    if "## Enrichment pass" not in text:
        text = text.rstrip() + note
    else:
        text = re.sub(r"\n## Enrichment pass.*", note.rstrip(), text, flags=re.S)

    # Update keywords gap note if present
    text = re.sub(
        r"- \*\*Keywords:\*\* IEEE author keywords.*?`keywords: \{N/A\}`\.",
        (
            "- **Keywords:** OpenAlex topic keywords were added where available. "
            "IEEE author keywords / IEEE Thesaurus terms are generally not in Crossref/OpenAlex; "
            f"{with_kw} records now have OpenAlex topics, {n - with_kw} remain `keywords: {{N/A}}`."
        ),
        text,
        count=1,
    )
    summary_path.write_text(text, encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Batch-enrich an IEEE metadata catalog JSON file.")
    p.add_argument("json_path", type=Path, help="Path to catalog .json")
    p.add_argument("--delay", type=float, default=0.15, help="Delay between OpenAlex batches (seconds)")
    p.add_argument("--no-ss", action="store_true", help="Skip Semantic Scholar abstract fallback")
    p.add_argument("--checkpoint", type=Path, help="Checkpoint file path (default: alongside JSON)")
    p.add_argument("--resume", action="store_true", help="Resume from checkpoint if present")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    json_path = args.json_path.resolve()
    txt_path = json_path.with_suffix(".txt")
    summary_path = json_path.with_name(json_path.stem + "-summary.md")
    checkpoint = args.checkpoint or json_path.with_suffix(".enrich-checkpoint.json")

    records: list[dict[str, Any]]
    attempted: set[int] = set()
    if args.resume and checkpoint.exists():
        ck = json.loads(checkpoint.read_text(encoding="utf-8"))
        records = ck["records"]
        attempted = set(ck.get("attempted") or [])
        print(f"Resuming: {len(attempted)} records already attempted", file=sys.stderr)
    else:
        records = json.loads(json_path.read_text(encoding="utf-8"))

    print(f"Enriching {len(records)} records from {json_path.name}", file=sys.stderr)
    try:
        kw_added, abs_added = enrich_records(
            records,
            delay=args.delay,
            use_ss_fallback=not args.no_ss,
            checkpoint_path=checkpoint,
            attempted=attempted,
        )
    except OpenAlexUnavailable as exc:
        print(f"OpenAlex unavailable: {exc}", file=sys.stderr)
        return 3

    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_txt(records, txt_path)
    patch_summary(summary_path, records, kw_added, abs_added)

    with_kw = sum(1 for r in records if r.get("keywords"))
    with_abs = sum(1 for r in records if r.get("abstract"))
    print(
        f"Done. keywords: {with_kw}/{len(records)} · abstracts: {with_abs}/{len(records)}",
        file=sys.stderr,
    )
    print(f"Updated: {json_path}", file=sys.stderr)
    print(f"Updated: {txt_path}", file=sys.stderr)
    if summary_path.exists():
        print(f"Updated: {summary_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
