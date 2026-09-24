#!/usr/bin/env python3
"""Search the IEEE antenna literature index from the command line.

  python scripts/search.py "wideband circularly polarized ME dipole array" -k 8
  python scripts/search.py "metasurface RCS reduction" --journal TAP --from 2018
  python scripts/search.py --similar 10.1109/TAP.2020.3030907
  python scripts/search.py --get 9234023
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litsearch import ALL_TYPES, DEFAULT_TYPES, LitIndex, format_hit  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Hybrid BM25 + embedding search over IEEE TAP/AWPL/APM")
    p.add_argument("query", nargs="?", help="Search query (English technical terms work best)")
    p.add_argument("-k", "--top-k", type=int, default=10)
    p.add_argument("--journal", action="append", choices=["TAP", "AWPL", "APM"], help="Repeatable")
    p.add_argument("--from", dest="year_from", type=int)
    p.add_argument("--to", dest="year_to", type=int)
    p.add_argument("--types", nargs="+", default=list(DEFAULT_TYPES), choices=ALL_TYPES)
    p.add_argument("--mode", choices=["hybrid", "bm25", "dense"], default="hybrid")
    p.add_argument("--similar", metavar="DOI_OR_ARNUMBER", help="Find papers similar to this one")
    p.add_argument("--get", metavar="DOI_OR_ARNUMBER", help="Print one paper")
    p.add_argument("--abstract-chars", type=int, default=600, help="Truncate abstracts (0 = full)")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (args.query or args.similar or args.get):
        build_parser().print_help()
        return 2
    index = LitIndex()
    filters = dict(journals=args.journal, year_from=args.year_from, year_to=args.year_to, types=args.types)

    if args.get:
        doc = index.lookup(args.get)
        if not doc:
            print(f"Not found: {args.get}", file=sys.stderr)
            return 1
        hits = [{"doc": doc, "ranks": {}}]
    elif args.similar:
        doc, hits = index.similar(args.similar, top_k=args.top_k, **filters)
        if not doc:
            print(f"Not found: {args.similar}", file=sys.stderr)
            return 1
        print(f"Similar to: {doc['citation']}\n", file=sys.stderr)
    else:
        hits = index.search(args.query, top_k=args.top_k, mode=args.mode, **filters)
        if not index.has_dense and args.mode != "bm25":
            print("(dense index not built or out of date: BM25 only)\n", file=sys.stderr)

    if args.json:
        print(json.dumps([{**h["doc"], "ranks": h.get("ranks", {})} for h in hits], ensure_ascii=False, indent=2))
    else:
        chars = args.abstract_chars or None
        print("\n\n".join(format_hit(n, h, chars) for n, h in enumerate(hits, 1)) or "No results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
