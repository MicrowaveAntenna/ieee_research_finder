#!/usr/bin/env python3
"""Fetch IEEE-style metadata records (citation + abstract + keywords + URL).

Primary sources (no IEEE login required):
  - CrossRef  — bibliographic fields, DOI, arnumber from IEEE URL
  - Semantic Scholar — abstracts
  - OpenAlex — keyword fallback when IEEE Index Terms are unavailable

IEEE Xplore blocks scripted HTTP (WAF returns 418). For IEEE-native keywords and
the exact "Cite This · Plain Text" block, use the in-browser harvester in
TEMPFILES/IEEE Literature Harvester.html while logged into ieeexplore.ieee.org.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "LiteratureFinderHelper/1.0 (mailto:research@example.com)",
        "Accept": "application/json",
    }
)


@dataclass
class PaperRecord:
    authors: str = ""
    title: str = ""
    journal: str = ""
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    month: str | None = None
    year: int | None = None
    doi: str | None = None
    abstract: str | None = None
    keywords: str | None = None
    url: str | None = None
    arnumber: str | None = None
    isnumber: str | None = None
    sources: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "authors": self.authors,
            "title": self.title,
            "journal": self.journal,
            "volume": self.volume,
            "issue": self.issue,
            "pages": self.pages,
            "month": self.month,
            "year": self.year,
            "doi": self.doi,
            "abstract": self.abstract,
            "keywords": self.keywords,
            "url": self.url,
            "arnumber": self.arnumber,
            "isnumber": self.isnumber,
            "sources": self.sources,
        }

    def format_plain(self) -> str:
        cite_parts: list[str] = []
        if self.authors:
            cite_parts.append(self.authors)
        if self.title:
            cite_parts.append(f'"{self.title},"')
        tail: list[str] = []
        if self.journal:
            tail.append(f"in {self.journal}")
        if self.volume:
            tail.append(f"vol. {self.volume}")
        if self.issue:
            tail.append(f"no. {self.issue}")
        if self.pages:
            tail.append(f"pp. {self.pages}")
        date_bits = [b for b in (self.month, str(self.year) if self.year else None) if b]
        if date_bits:
            tail.append(" ".join(date_bits))
        if self.doi:
            tail.append(f"doi: {self.doi.upper() if self.doi.lower().startswith('10.1109/') else self.doi}")
        citation = ", ".join([p for p in cite_parts if p])
        if tail:
            # Title already ends with a comma inside the quotes.
            citation += " " + ", ".join(tail)
        if not citation.endswith("."):
            citation += "."

        abstract = self.abstract or ""
        kw = self.keywords if self.keywords else "N/A"
        url = self.url or ""
        return (
            f"{citation}  Abstract: {abstract}  "
            f"keywords: {{{kw}}},  URL: {url}"
        )


def _get_json(
    url: str,
    params: dict[str, str] | None = None,
    timeout: int = 30,
    retries: int = 3,
) -> dict[str, Any] | None:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = SESSION.get(url, params=params, timeout=timeout)
            if resp.status_code == 404:
                return None
            if resp.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
                continue
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(0.8 * (attempt + 1))
    if last_error:
        print(f"  warning: {url} -> {last_error}", file=sys.stderr)
    return None


def abbreviate_author(given: str | None, family: str | None, fallback: str | None = None) -> str:
    if fallback and not (given or family):
        return fallback.strip()
    family = (family or "").strip()
    given = (given or "").strip()
    if not family and given:
        return given
    if not given:
        return family
    # Preserve hyphenated initials like Z.-B.
    chunks = re.split(r"([\s-]+)", given)
    initials: list[str] = []
    for chunk in chunks:
        if not chunk or re.fullmatch(r"[\s-]+", chunk):
            continue
        letter = chunk[0].upper()
        if initials and initials[-1].endswith("-") and len(chunk) == 1:
            initials[-1] += letter + "."
        else:
            initials.append(letter + ".")
    initials_str = "-".join(initials).replace(".-.", ".-")
    if "-" in given and len(initials) > 1:
        # e.g. Z-B -> Z.-B.
        initials_str = re.sub(r"\.-([A-Z])", r".-\1.", initials_str)
    return f"{initials_str} {family}".strip()


def format_authors_ieee(authors: list[dict[str, Any]]) -> str:
    names: list[str] = []
    for author in authors:
        if isinstance(author, str):
            names.append(author)
            continue
        given = author.get("given") or author.get("first")
        family = author.get("family") or author.get("last")
        literal = author.get("name") or author.get("literal") or author.get("preferredName")
        names.append(abbreviate_author(given, family, literal))
    names = [n for n in names if n]
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + ", and " + names[-1]


def parse_pages(message: dict[str, Any]) -> str | None:
    page = message.get("page")
    if page:
        return str(page).replace("--", "-")
    start = message.get("page-start") or message.get("pageStart")
    end = message.get("page-end") or message.get("pageEnd")
    if start and end:
        return f"{start}-{end}"
    if start:
        return str(start)
    return None


def parse_month_year(message: dict[str, Any]) -> tuple[str | None, int | None]:
    # Prefer print/issue date over online-first date for IEEE journals.
    for key in ("published-print", "issued", "published-online", "created"):
        part = message.get(key) or {}
        if not isinstance(part, dict):
            continue
        month_idx = part.get("month")
        year = part.get("year")
        if year:
            month_name = None
            if month_idx:
                try:
                    month_name = MONTHS[int(month_idx) - 1]
                except (ValueError, IndexError):
                    month_name = None
            return month_name, int(year)
    return None, None


def ieee_url_from_links(message: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    candidates: list[str] = []
    for link in message.get("link", []) or []:
        url = link.get("URL") or link.get("url") or ""
        if url:
            candidates.append(url)
    resource = message.get("resource") or {}
    primary = resource.get("primary") or {}
    if primary.get("URL"):
        candidates.append(primary["URL"])
    for url in candidates:
        if "ieeexplore.ieee.org" not in url:
            continue
        ar = re.search(r"arnumber=(\d+)", url, re.I) or re.search(r"/document/(\d+)", url, re.I)
        isnum = re.search(r"isnumber=(\d+)", url, re.I)
        arnumber = ar.group(1) if ar else None
        isnumber = isnum.group(1) if isnum else None
        if arnumber:
            stamp = f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}"
            if isnumber:
                stamp += f"&isnumber={isnumber}"
            return stamp, arnumber, isnumber
    return None, None, None


def strip_html(text: str | None) -> str | None:
    if not text:
        return None
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def decode_openalex_abstract(index: dict[str, list[int]] | None) -> str | None:
    if not index:
        return None
    max_pos = max(pos for positions in index.values() for pos in positions)
    words = [""] * (max_pos + 1)
    for word, positions in index.items():
        for pos in positions:
            words[pos] = word
    text = " ".join(words).strip()
    return text or None


def arnumber_from_landing(url: str | None) -> tuple[str | None, str | None]:
    if not url:
        return None, None
    ar = re.search(r"/document/(\d+)", url, re.I) or re.search(r"arnumber=(\d+)", url, re.I)
    isnum = re.search(r"isnumber=(\d+)", url, re.I)
    return (ar.group(1) if ar else None, isnum.group(1) if isnum else None)


def fetch_crossref(doi: str) -> PaperRecord | None:
    data = _get_json(f"https://api.crossref.org/works/{quote(doi, safe='')}")
    if not data:
        return None
    message = data.get("message") or {}
    month, year = parse_month_year(message)
    url, arnumber, isnumber = ieee_url_from_links(message)
    journal = ""
    for container in ("container-title", "short-container-title"):
        titles = message.get(container) or []
        if titles:
            journal = titles[0]
            break
    record = PaperRecord(
        authors=format_authors_ieee(message.get("author") or []),
        title=(message.get("title") or [""])[0],
        journal=journal,
        volume=str(message.get("volume")) if message.get("volume") else None,
        issue=str(message.get("issue")) if message.get("issue") else None,
        pages=parse_pages(message),
        month=month,
        year=year,
        doi=message.get("DOI") or doi,
        abstract=strip_html((message.get("abstract") or "")),
        url=url,
        arnumber=arnumber,
        isnumber=isnumber,
        sources={"biblio": "crossref"},
    )
    return record


def fetch_semanticscholar(doi: str) -> dict[str, Any] | None:
    return _get_json(
        "https://api.semanticscholar.org/graph/v1/paper/DOI:" + quote(doi, safe=""),
        params={"fields": "title,abstract,authors,year,journal,externalIds"},
    )


def fetch_openalex(doi: str) -> dict[str, Any] | None:
    return _get_json("https://api.openalex.org/works/https://doi.org/" + quote(doi, safe=""))


def merge_sources(record: PaperRecord, doi: str, with_keywords: bool = True) -> PaperRecord:
    ss = fetch_semanticscholar(doi)
    if ss:
        if not record.abstract and ss.get("abstract"):
            record.abstract = strip_html(ss["abstract"])
            record.sources["abstract"] = "semanticscholar"
        if not record.title and ss.get("title"):
            record.title = ss["title"]
        if not record.authors and ss.get("authors"):
            record.authors = format_authors_ieee(ss["authors"])
        journal = ss.get("journal") or {}
        if not record.volume and journal.get("volume"):
            record.volume = str(journal["volume"])
        if not record.pages and journal.get("pages"):
            record.pages = str(journal["pages"]).replace("--", "-")
        if not record.year and ss.get("year"):
            record.year = int(ss["year"])

    oa = fetch_openalex(doi) if (with_keywords or not record.abstract or not record.url) else None
    if oa:
        if not record.abstract:
            abs_text = decode_openalex_abstract(oa.get("abstract_inverted_index"))
            if abs_text:
                record.abstract = abs_text
                record.sources["abstract"] = record.sources.get("abstract") or "openalex"
        if not record.month or not record.year:
            pub_date = oa.get("publication_date") or ""
            if pub_date:
                try:
                    year_s, month_s, *_ = pub_date.split("-")
                    record.year = record.year or int(year_s)
                    record.month = record.month or MONTHS[int(month_s) - 1]
                except (ValueError, IndexError):
                    pass
        landing = ((oa.get("primary_location") or {}).get("landing_page_url")) or ""
        arnumber, isnumber = arnumber_from_landing(landing)
        if arnumber and not record.arnumber:
            record.arnumber = arnumber
            record.sources["arnumber"] = "openalex"
        if isnumber and not record.isnumber:
            record.isnumber = isnumber
        if with_keywords and not record.keywords and oa.get("keywords"):
            kws = [k.get("display_name") for k in oa["keywords"] if k.get("display_name")]
            if kws:
                record.keywords = "; ".join(kws[:20])
                record.sources["keywords"] = "openalex"

    if not record.url and record.arnumber:
        record.url = (
            "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber="
            + record.arnumber
        )
        if record.isnumber:
            record.url += "&isnumber=" + record.isnumber

    return record


def fetch_by_doi(doi: str, with_keywords: bool = True, delay: float = 0.0) -> PaperRecord | None:
    doi = doi.strip().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    record = fetch_crossref(doi)
    if not record:
        record = PaperRecord(doi=doi, sources={"biblio": None})
    record = merge_sources(record, doi, with_keywords=with_keywords)
    if delay:
        time.sleep(delay)
    return record


def fetch_by_arnumber(arnumber: str, with_keywords: bool = True, delay: float = 0.0) -> PaperRecord | None:
    # Resolve DOI via CrossRef query when possible.
    data = _get_json(
        "https://api.crossref.org/works",
        params={"filter": f"link.application:ieee,link.has-content-version:true", "rows": "1", "query": arnumber},
    )
    items = ((data or {}).get("message") or {}).get("items") or []
    for item in items:
        url, ar, _ = ieee_url_from_links(item)
        if ar == arnumber and item.get("DOI"):
            return fetch_by_doi(item["DOI"], with_keywords=with_keywords, delay=delay)
    record = PaperRecord(
        arnumber=arnumber,
        url=f"https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber={arnumber}",
        sources={"biblio": "arnumber-only"},
    )
    if delay:
        time.sleep(delay)
    return record


def load_seed_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
        return data if isinstance(data, list) else [data]
    # plain text: one record per blank line, or DOI/arnumber per line
    rows: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip()
        if not block:
            continue
        doi = re.search(r"doi:\s*(\S+)", block, re.I)
        ar = re.search(r"arnumber=(\d+)", block, re.I)
        if doi:
            rows.append({"doi": doi.group(1).rstrip(".,")})
        elif ar:
            rows.append({"arnumber": ar.group(1)})
        elif re.fullmatch(r"10\.\S+", block):
            rows.append({"doi": block})
        elif re.fullmatch(r"\d+", block):
            rows.append({"arnumber": block})
    return rows


def enrich_json_file(
    input_path: Path,
    output_json: Path | None,
    output_txt: Path | None,
    limit: int | None,
    delay: float,
    with_keywords: bool,
    only_missing_keywords: bool,
) -> list[PaperRecord]:
    seeds = load_seed_records(input_path)
    if limit:
        seeds = seeds[:limit]
    results: list[PaperRecord] = []
    total = len(seeds)

    for idx, seed in enumerate(seeds, start=1):
        if isinstance(seed, dict) and seed.get("title") and seed.get("doi"):
            record = PaperRecord(**{k: seed.get(k) for k in PaperRecord.__dataclass_fields__ if k in seed})
            record.sources = dict(seed.get("sources") or {})
            if only_missing_keywords and record.keywords:
                results.append(record)
                continue
            merged = merge_sources(record, record.doi or "", with_keywords=with_keywords)
            results.append(merged)
            print(f"[{idx}/{total}] enriched {record.doi}", file=sys.stderr)
        elif seed.get("doi"):
            print(f"[{idx}/{total}] DOI {seed['doi']}", file=sys.stderr)
            rec = fetch_by_doi(seed["doi"], with_keywords=with_keywords, delay=delay)
            if rec:
                results.append(rec)
        elif seed.get("arnumber"):
            print(f"[{idx}/{total}] arnumber {seed['arnumber']}", file=sys.stderr)
            rec = fetch_by_arnumber(seed["arnumber"], with_keywords=with_keywords, delay=delay)
            if rec:
                results.append(rec)
        if delay:
            time.sleep(delay)

    if output_json:
        output_json.write_text(
            json.dumps([r.to_dict() for r in results], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if output_txt:
        output_txt.write_text("\n\n".join(r.format_plain() for r in results) + "\n", encoding="utf-8")
    return results


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Harvest IEEE-style metadata (citation / abstract / keywords / URL)."
    )
    parser.add_argument("--doi", action="append", help="DOI to fetch (repeatable)")
    parser.add_argument("--arnumber", action="append", help="IEEE arnumber (repeatable)")
    parser.add_argument("--input", type=Path, help="Seed .json catalog or text file with DOIs")
    parser.add_argument("--output-json", type=Path, help="Write JSON array to this path")
    parser.add_argument("--output-txt", type=Path, help="Write plain-text catalog to this path")
    parser.add_argument("--limit", type=int, help="Process only the first N records from --input")
    parser.add_argument("--delay", type=float, default=0.2, help="Seconds between API calls")
    parser.add_argument(
        "--no-keywords",
        action="store_true",
        help="Skip OpenAlex keyword lookup",
    )
    parser.add_argument(
        "--only-missing-keywords",
        action="store_true",
        help="With --input JSON, only enrich records whose keywords are empty",
    )
    parser.add_argument("--print", dest="print_one", action="store_true", help="Print plain-text result to stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    records: list[PaperRecord] = []

    if args.input:
        out_json = args.output_json or args.input.with_suffix(".enriched.json")
        out_txt = args.output_txt or args.input.with_suffix(".enriched.txt")
        records = enrich_json_file(
            args.input,
            out_json,
            out_txt,
            args.limit,
            args.delay,
            with_keywords=not args.no_keywords,
            only_missing_keywords=args.only_missing_keywords,
        )
        print(f"Wrote {len(records)} records -> {out_json}", file=sys.stderr)
        if out_txt:
            print(f"Wrote plain text -> {out_txt}", file=sys.stderr)
    else:
        dois = args.doi or []
        ars = args.arnumber or []
        if not dois and not ars:
            print("Provide --doi, --arnumber, or --input", file=sys.stderr)
            return 2
        for doi in dois:
            rec = fetch_by_doi(doi, with_keywords=not args.no_keywords, delay=args.delay)
            if rec:
                records.append(rec)
        for ar in ars:
            rec = fetch_by_arnumber(ar, with_keywords=not args.no_keywords, delay=args.delay)
            if rec:
                records.append(rec)
        if args.output_json:
            args.output_json.write_text(
                json.dumps([r.to_dict() for r in records], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if args.output_txt:
            args.output_txt.write_text("\n\n".join(r.format_plain() for r in records) + "\n", encoding="utf-8")

    if args.print_one or (not args.output_json and not args.output_txt and not args.input):
        for rec in records:
            print(rec.format_plain())
            print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
