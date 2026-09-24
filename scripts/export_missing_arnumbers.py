#!/usr/bin/env python3
"""Write IEEE arnumbers whose catalog records have no abstract."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGS = [
    ROOT / "IEEE TAP metadata sets" / "ieee-tap-1960-1999.json",
    ROOT / "IEEE TAP metadata sets" / "ieee-tap-2000-2020.json",
    ROOT / "IEEE TAP metadata sets" / "ieee-tap-2021-2026.json",
    ROOT / "IEEE AWPL metadata sets" / "ieee-awpl-2002-2026.json",
    ROOT / "IEEE APM metadata sets" / "ieee-map-1990-2026.json",
]
OUT = ROOT / "TEMPFILES" / "missing-abstract-arnumbers.txt"


def main() -> None:
    seen: set[str] = set()
    ordered: list[str] = []
    per_file: list[str] = []
    for path in CATALOGS:
        records = json.loads(path.read_text(encoding="utf-8"))
        missing = 0
        for record in records:
            if record.get("abstract"):
                continue
            ar = str(record.get("arnumber") or "").strip()
            if not ar:
                continue
            missing += 1
            if ar not in seen:
                seen.add(ar)
                ordered.append(ar)
        per_file.append(f"{path.name}: {missing} missing abstracts")
    OUT.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    print(f"Wrote {len(ordered)} arnumbers -> {OUT}")
    for line in per_file:
        print(" ", line)


if __name__ == "__main__":
    main()
