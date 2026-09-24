#!/usr/bin/env python3
"""MCP server exposing the IEEE antenna literature index to Claude Code (stdio transport).

Register once (user scope, usable from any project):
  claude mcp add --scope user ieee-literature -- <repo>/.venv/Scripts/python.exe <repo>/scripts/mcp_server.py
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litsearch import ALL_TYPES, DEFAULT_TYPES, INDEX_DIR, LitIndex, format_hit  # noqa: E402

from mcp.server.mcpserver import MCPServer  # noqa: E402

INSTRUCTIONS = """\
Local search engine over IEEE antenna literature: IEEE Transactions on Antennas and Propagation
(TAP, 1960-2026), IEEE Antennas and Wireless Propagation Letters (AWPL, 2002-2026) and IEEE
Antennas and Propagation Magazine (APM, 1990-2026), ~41k papers with abstracts.

Use it when the user is designing an antenna / microwave / EM structure and wants prior art,
design approaches, or references. Guidance:
- English technical queries work best, e.g. "wideband dual-polarized magneto-electric dipole
  array 28 GHz"; the semantic index also understands Chinese, but English is more precise.
- Avoid negations ("without phase shifters" matches phase-shifter papers). Name the wanted
  mechanism instead: "frequency-scanning leaky-wave antenna", "parasitic reconfigurable beam steering".
- For a design question, run 2-4 searches that cover different angles (structure, technique,
  band/application, performance goal), then synthesize the approaches with citations.
- Use similar_papers on a strong hit to expand around it; get_paper for a full record.
- Only cite papers returned by these tools, with their IEEE Xplore URL. Abstracts marked N/A
  are genuinely missing; do not invent their content.
"""

JournalCode = Literal["TAP", "AWPL", "APM"]

server = MCPServer("ieee-literature", instructions=INSTRUCTIONS)
_index: LitIndex | None = None
_lock = threading.Lock()


def index() -> LitIndex:
    global _index
    with _lock:
        if _index is None:
            _index = LitIndex(INDEX_DIR, device="cpu")
        return _index


def _types(include_non_research: bool) -> tuple[str, ...]:
    return ALL_TYPES if include_non_research else DEFAULT_TYPES


def _render(hits: list[dict], abstract_chars: int) -> str:
    if not hits:
        return "No results."
    return "\n\n".join(format_hit(n, h, abstract_chars or None) for n, h in enumerate(hits, 1))


@server.tool()
def search_papers(
    query: Annotated[str, Field(description="English technical query, e.g. 'low-profile wideband circularly polarized metasurface antenna'")],
    top_k: Annotated[int, Field(ge=1, le=30, description="Number of papers to return")] = 8,
    journals: Annotated[list[JournalCode] | None, Field(description="Restrict to these journals")] = None,
    year_from: Annotated[int | None, Field(description="Earliest publication year (inclusive)")] = None,
    year_to: Annotated[int | None, Field(description="Latest publication year (inclusive)")] = None,
    include_non_research: Annotated[bool, Field(description="Also return comments, corrections, editorials, news")] = False,
    abstract_chars: Annotated[int, Field(ge=0, description="Truncate abstracts to this many characters (0 = full)")] = 0,
) -> str:
    """Hybrid keyword + semantic search over IEEE TAP / AWPL / APM paper titles and abstracts.
    Returns IEEE citations, IEEE Xplore URLs and abstracts, best match first."""
    idx = index()
    hits = idx.search(
        query,
        top_k=top_k,
        journals=journals,
        year_from=year_from,
        year_to=year_to,
        types=_types(include_non_research),
    )
    note = "" if idx.has_dense else "(semantic index unavailable: keyword-only results)\n\n"
    return note + _render(hits, abstract_chars)


@server.tool()
def similar_papers(
    paper: Annotated[str, Field(description="DOI, IEEE arnumber, or IEEE Xplore URL of a paper in the index")],
    top_k: Annotated[int, Field(ge=1, le=30)] = 8,
    journals: Annotated[list[JournalCode] | None, Field(description="Restrict to these journals")] = None,
    year_from: Annotated[int | None, Field(description="Earliest publication year (inclusive)")] = None,
    year_to: Annotated[int | None, Field(description="Latest publication year (inclusive)")] = None,
    abstract_chars: Annotated[int, Field(ge=0, description="Truncate abstracts (0 = full)")] = 0,
) -> str:
    """Find papers most similar to a given paper (more-like-this), e.g. to expand around a strong hit."""
    doc, hits = index().similar(paper, top_k=top_k, journals=journals, year_from=year_from, year_to=year_to)
    if doc is None:
        return f"Paper not found in index: {paper}"
    return f"Similar to: {doc['citation']}\n\n" + _render(hits, abstract_chars)


@server.tool()
def get_paper(
    paper: Annotated[str, Field(description="DOI, IEEE arnumber, or IEEE Xplore URL")],
) -> str:
    """Return the full record (citation, URL, full abstract) of one paper."""
    doc = index().lookup(paper)
    if doc is None:
        return f"Paper not found in index: {paper}"
    return format_hit(1, {"doc": doc, "ranks": {}})


@server.tool()
def index_info() -> str:
    """Corpus coverage (journals, years, counts) and which embedding model the index uses."""
    idx = index()
    stats_path = INDEX_DIR / "corpus-stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else {}
    stats["dense_model"] = idx.model_name if idx.has_dense else None
    return json.dumps(stats, ensure_ascii=False, indent=2)


def _warm_up() -> None:
    """Load the index and embedding model in the background so the first query is fast."""
    try:
        idx = index()
        if idx.has_dense:
            idx.encode_query("warm up")
    except Exception as exc:  # the tools will surface real errors on first call
        print(f"warm-up failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    threading.Thread(target=_warm_up, daemon=True).start()
    server.run("stdio")
