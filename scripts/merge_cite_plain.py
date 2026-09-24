#!/usr/bin/env python3
"""Merge IEEE Cite This plain-text blocks back into the catalog JSON/TXT files."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from enrich_catalog import format_catalog_line  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = [
    ROOT / "IEEE TAP metadata sets" / "ieee-tap-1960-1999.json",
    ROOT / "IEEE TAP metadata sets" / "ieee-tap-2000-2020.json",
    ROOT / "IEEE TAP metadata sets" / "ieee-tap-2021-2026.json",
    ROOT / "IEEE AWPL metadata sets" / "ieee-awpl-2002-2026.json",
    ROOT / "IEEE APM metadata sets" / "ieee-map-1990-2026.json",
]


def parse_blocks(text: str) -> dict[str, dict[str, str]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    blocks: list[str] = []
    buf: list[str] = []
    for line in text.split("\n"):
        buf.append(line)
        if re.search(r"^\s*URL:\s*http", line, re.I):
            blocks.append("\n".join(buf).strip())
            buf = []
    if "".join(buf).strip():
        blocks.append("\n".join(buf).strip())

    out: dict[str, dict[str, str]] = {}
    for blk in blocks:
        if not blk:
            continue
        ar = (re.search(r"arnumber=(\d+)", blk, re.I) or re.search(r"/document/(\d+)", blk)) 
        if not ar:
            continue
        i_abs = re.search(r"\bAbstract:\s*", blk, re.I)
        i_kw = re.search(r"\bkeywords:\s*", blk, re.I)
        i_url = re.search(r"\bURL:\s*http", blk, re.I)
        abstract = ""
        keywords = ""
        if i_abs:
            start = i_abs.end()
            end = len(blk)
            for marker in (i_kw, i_url):
                if marker and marker.start() > i_abs.start():
                    end = min(end, marker.start())
            abstract = re.sub(r"\s+", " ", blk[start:end]).strip()
        if i_kw:
            start = i_kw.end()
            end = i_url.start() if i_url and i_url.start() > i_kw.start() else len(blk)
            keywords = blk[start:end].strip()
            keywords = re.sub(r"^\{|\},?\s*$", "", keywords).strip()
            keywords = re.sub(r"\s+", " ", keywords)
            if keywords.upper() in {"N/A", "NA", ""}:
                keywords = ""
        out[ar.group(1)] = {"abstract": abstract, "keywords": keywords, "raw": blk}
    return out


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/merge_cite_plain.py FILE.txt [MORE.txt ...]", file=sys.stderr)
        return 2
    merged: dict[str, dict[str, str]] = {}
    for arg in sys.argv[1:]:
        text = Path(arg).read_text(encoding="utf-8")
        merged.update(parse_blocks(text))
    print(f"Parsed {len(merged)} citation blocks", file=sys.stderr)
    filled = 0
    for path in CATALOGS:
        records = json.loads(path.read_text(encoding="utf-8"))
        changed = 0
        for record in records:
            ar = str(record.get("arnumber") or "")
            hit = merged.get(ar)
            if not hit:
                continue
            sources = record.setdefault("sources", {})
            if hit["abstract"] and not record.get("abstract"):
                record["abstract"] = hit["abstract"]
                sources["abstract"] = "ieee-cite"
                changed += 1
            if hit["keywords"] and not record.get("keywords"):
                record["keywords"] = hit["keywords"].replace(";", "; ")
                sources["keywords"] = "ieee-cite"
        if changed:
            path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            path.with_suffix(".txt").write_text(
                "\n\n".join(format_catalog_line(r) for r in records) + "\n",
                encoding="utf-8",
            )
            filled += changed
            print(f"{path.name}: filled {changed} abstracts", file=sys.stderr)
    print(f"Total abstracts filled: {filled}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
