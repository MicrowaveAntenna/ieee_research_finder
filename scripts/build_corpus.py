#!/usr/bin/env python3
"""Clean and merge all metadata-set catalogs into one search corpus.

Reads every ``IEEE * metadata sets/ieee-*-YYYY-YYYY.json`` catalog (never modifies
them) and writes ``index/corpus.jsonl`` plus ``index/corpus-stats.json``.

Cleaning steps:
  - classify each record: article / comment / correction / editorial / news
  - drop placeholder abstracts ("International audience", "See abstr. ...")
  - strip "Abstract—" prefixes and trailing copyright lines
  - flag IEEE's generic abstracts for non-research items ("Presents corrections to ...")
  - turn LaTeX fragments into plain text for search (display abstract keeps the original)
  - drop duplicate articles that share a normalized title + first author
  - OpenAlex keywords are NOT used for search (they contain entity-linking noise)
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ieee_metadata_harvester import PaperRecord  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CATALOG_GLOB = "IEEE * metadata sets/ieee-*-[0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].json"
JOURNAL_CODES = {"tap": "TAP", "awpl": "AWPL", "map": "APM"}

# --- document type -----------------------------------------------------------

# "Correction of beam direction ..." is a research title, so require "to/for/in", a colon, or a quote.
CORRECTION_TITLE = re.compile(
    r"^(corrections?|erratum|errata|corrigendum|addendum|retraction)\s*(to\b|for\b|in\b|on\b|:|-|—|–|\[|[\"“'‘]|$)"
    r"|\b(corrections?|erratum|errata)\s+(to|for|in)\s+[\"“'‘]|\[correction",
    re.I,
)
COMMENT_TITLE = re.compile(
    r"^(comments?\s+(on|to)\b|reply\b|replies\b|authors?['’]?\s+reply|response\s+to\b"
    r"|rebuttal|discussion\s+(of|on)\b|closure\s+to\b)",
    re.I,
)
EDITORIAL_TITLE = re.compile(
    r"^(guest\s+)?editorial|^editor['’]?s?\b|^preface\b|^foreword\b|^introduction\s+to\s+the\s+special"
    r"|^message\s+from|^president['’]?s?\s+(message|column|comments)|^(new\s+)?associate\s+editors?",
    re.I,
)
NEWS_TITLE = re.compile(
    r"in\s+memoriam|obituary|in\s+remembrance|call\s+for\s+(papers|nominations|contributions)"
    r"|^awards?\b|\baward\s+(announcement|winners|recipients)|^report\s+of\b|society\s+(news|information)"
    r"|^chapter\s|^meetings?\b|^book\s+reviews?|^calendar\b|^membership\b|^distinguished\s+lecturers?"
    r"|^(ieee\s+)?ap-?s\s+(news|administrative|adcom)|^table\s+of\s+contents|^information\s+for\s+authors",
    re.I,
)
GENERIC_ABSTRACT = [
    ("correction", re.compile(r"^presents corrections? to", re.I)),
    ("comment", re.compile(r"^presents letters sent to the editor", re.I)),
    ("editorial", re.compile(r"^presents the (introductory )?editorial", re.I)),
    (
        "news",
        re.compile(
            r"^(prospective authors are requested|provides society information|presents information on"
            r"|recounts the career|presents a biography|presents the recipients)",
            re.I,
        ),
    ),
]

# --- abstract cleaning -------------------------------------------------------

JUNK_ABSTRACT = re.compile(
    r"^(international audience|lema|archived web content|n/?a|no abstract( available)?)\.?$"
    r"|^(see abstr|for reference see)",
    re.I,
)
ABSTRACT_PREFIX = re.compile(r"^\s*abstract\s*[—–:\-.]*\s*", re.I)
COPYRIGHT_TAIL = re.compile(r"\s*(©|\(c\)|copyright)\s*(19|20)\d\d\b.*$", re.I)

LATEX_SYMBOLS = {
    "times": "×", "lambda": "λ", "mu": "μ", "pi": "π", "theta": "θ", "phi": "φ", "varphi": "φ",
    "epsilon": "ε", "varepsilon": "ε", "sigma": "σ", "omega": "ω", "Omega": "Ω", "alpha": "α",
    "beta": "β", "gamma": "γ", "Gamma": "Γ", "delta": "δ", "Delta": "Δ", "eta": "η", "tau": "τ",
    "rho": "ρ", "psi": "ψ", "sim": "~", "approx": "≈", "pm": "±", "leq": "≤", "le": "≤",
    "geq": "≥", "ge": "≥", "infty": "∞", "circ": "°", "cdot": "·", "degree": "°", "prime": "′",
    "rightarrow": "→", "to": "→", "ll": "≪", "gg": "≫", "neq": "≠", "propto": "∝",
}


def latex_to_text(text: str) -> str:
    """Flatten inline LaTeX ($1 \\times 8$, $\\lambda_{0}$, \\mathrm{dBi}) into plain text."""
    if "$" not in text and "\\" not in text:
        return text
    text = re.sub(r"\\(?:mathrm|text|textrm|mathbf|mathit|boldsymbol|operatorname)\s*\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\([A-Za-z]+)", lambda m: LATEX_SYMBOLS.get(m.group(1), m.group(1)), text)
    text = re.sub(r"[_^]\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"[_^](\w)", r"\1", text)
    text = text.replace("$", " ").replace("{", "").replace("}", "").replace("\\", "")
    return re.sub(r"\s+", " ", text).strip()


def clean_abstract(raw: str | None) -> tuple[str | None, str | None]:
    """Return (display abstract, generic doc type if the abstract is an IEEE placeholder)."""
    if not raw:
        return None, None
    text = re.sub(r"\s+", " ", raw).strip()
    text = ABSTRACT_PREFIX.sub("", text)
    text = COPYRIGHT_TAIL.sub("", text).strip()
    if len(text) < 25 or JUNK_ABSTRACT.search(text):
        return None, None
    for doc_type, pattern in GENERIC_ABSTRACT:
        if pattern.search(text) and len(text) < 400:
            return text, doc_type
    return text, None


def classify(title: str, generic_type: str | None) -> str:
    title = title.strip()
    if CORRECTION_TITLE.search(title):
        return "correction"
    if COMMENT_TITLE.search(title):
        return "comment"
    if EDITORIAL_TITLE.search(title):
        return "editorial"
    if NEWS_TITLE.search(title):
        return "news"
    return generic_type or "article"


def norm_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", latex_to_text(title).lower())


def citation_line(record: dict[str, Any]) -> str:
    paper = PaperRecord(**{k: record.get(k) for k in PaperRecord.__dataclass_fields__ if k in record})
    paper.abstract = None
    paper.keywords = None
    return paper.format_plain().split("  Abstract:")[0]


def build_doc(record: dict[str, Any], journal_code: str) -> dict[str, Any]:
    abstract, generic_type = clean_abstract(record.get("abstract"))
    title = re.sub(r"\s+", " ", record.get("title") or "").strip()
    doc_type = classify(title, generic_type)
    search_abstract = "" if (generic_type or not abstract) else latex_to_text(abstract)
    early = not record.get("volume") or record.get("pages") in ("1-1", "1")
    return {
        "id": (record.get("doi") or "").lower(),
        "journal_code": journal_code,
        "journal": record.get("journal"),
        "title": title,
        "authors": record.get("authors") or "",
        "year": record.get("year"),
        "month": record.get("month"),
        "volume": record.get("volume"),
        "issue": record.get("issue"),
        "pages": record.get("pages"),
        "doi": record.get("doi"),
        "arnumber": record.get("arnumber"),
        "url": record.get("url"),
        "doc_type": doc_type,
        "early_access": early,
        "abstract": abstract,
        "abstract_source": (record.get("sources") or {}).get("abstract") if abstract else None,
        "citation": citation_line(record),
        "search_text": (latex_to_text(title) + ". " + search_abstract).strip(),
    }


def dedupe(docs: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Drop repeated articles (same normalized title + first author), keeping the most complete."""

    def completeness(d: dict[str, Any]) -> tuple[int, int, int]:
        return (bool(d["abstract"]), not d["early_access"], len(d["abstract"] or ""))

    groups: dict[tuple[str, str], list[int]] = {}
    for i, d in enumerate(docs):
        if d["doc_type"] != "article":
            continue
        first_author = (d["authors"].split(",")[0] if d["authors"] else "").strip().lower()
        groups.setdefault((norm_title(d["title"]), first_author), []).append(i)
    drop: set[int] = set()
    for idxs in groups.values():
        if len(idxs) > 1:
            best = max(idxs, key=lambda i: completeness(docs[i]))
            drop.update(i for i in idxs if i != best)
    return [d for i, d in enumerate(docs) if i not in drop], len(drop)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Clean + merge metadata catalogs into index/corpus.jsonl")
    p.add_argument("--out-dir", type=Path, default=ROOT / "index")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    catalogs = sorted(ROOT.glob(CATALOG_GLOB))
    if not catalogs:
        print(f"No catalogs matched {CATALOG_GLOB}", file=sys.stderr)
        return 2

    docs: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_file: dict[str, int] = {}
    for path in catalogs:
        code = JOURNAL_CODES.get(path.stem.split("-")[1], path.stem.split("-")[1].upper())
        records = json.loads(path.read_text(encoding="utf-8"))
        per_file[path.name] = len(records)
        for record in records:
            doc = build_doc(record, code)
            if not doc["id"] or doc["id"] in seen:
                continue
            seen.add(doc["id"])
            docs.append(doc)

    docs, dup_dropped = dedupe(docs)
    docs.sort(key=lambda d: (d["journal_code"], d["year"] or 0, d["id"]))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    corpus_path = args.out_dir / "corpus.jsonl"
    with corpus_path.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    articles = [d for d in docs if d["doc_type"] == "article"]
    stats = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalogs": per_file,
        "docs": len(docs),
        "duplicates_dropped": dup_dropped,
        "by_type": dict(Counter(d["doc_type"] for d in docs)),
        "by_journal": dict(Counter(d["journal_code"] for d in docs)),
        "articles_with_abstract": sum(1 for d in articles if d["abstract"]),
        "articles_without_abstract": sum(1 for d in articles if not d["abstract"]),
        "early_access": sum(1 for d in docs if d["early_access"]),
        "year_range": [min(d["year"] for d in docs if d["year"]), max(d["year"] for d in docs if d["year"])],
    }
    (args.out_dir / "corpus-stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"Wrote {len(docs)} docs -> {corpus_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
