# IEEE Transactions on Antennas and Propagation — metadata catalog

**Journal:** IEEE Transactions on Antennas and Propagation  
**Print ISSN:** 0018-926X  
**Electronic ISSN:** 1558-2221  
**IEEE Xplore punumber:** 8  
**Date range:** publication date 2021-01-01 through 2026-08-28 inclusive  
**Catalog generated:** 2026-09-24 (UTC)

## Totals

- **Papers in catalog:** 6359
- **With abstracts:** 6153 (96.8%)
- **With IEEE/author keywords:** 6268 (98.6%)
- **With volume/issue:** 6081 (95.6%)
- **Early Access (no volume/issue assigned):** 278
- **With DOI:** 6359
- **With IEEE Xplore URL:** 6359
- **Comments / replies / corrections / errata (by title prefix):** 41

## Counts by year (print/issued year)

- 2021: 974
- 2022: 1286
- 2023: 1036
- 2024: 986
- 2025: 1052
- 2026: 1025

## Counts by volume/issue

IEEE TAP is monthly. Volume 69 = 2021 … volume 74 = 2026.
Through the cutoff date, volume 74 includes issues 1–8 (January–August 2026).

- vol. 69 no. 1: 65
- vol. 69 no. 2: 66
- vol. 69 no. 3: 65
- vol. 69 no. 4: 66
- vol. 69 no. 5: 66
- vol. 69 no. 6: 67
- vol. 69 no. 7: 65
- vol. 69 no. 8: 103
- vol. 69 no. 9: 100
- vol. 69 no. 10: 100
- vol. 69 no. 11: 104
- vol. 69 no. 12: 107
- vol. 70 no. 1: 81
- vol. 70 no. 2: 83
- vol. 70 no. 3: 80
- vol. 70 no. 4: 86
- vol. 70 no. 5: 82
- vol. 70 no. 6: 98
- vol. 70 no. 7: 127
- vol. 70 no. 8: 131
- vol. 70 no. 9: 133
- vol. 70 no. 10: 132
- vol. 70 no. 11: 132
- vol. 70 no. 12: 121
- vol. 71 no. 1: 126
- vol. 71 no. 2: 95
- vol. 71 no. 3: 86
- vol. 71 no. 4: 87
- vol. 71 no. 5: 89
- vol. 71 no. 6: 90
- vol. 71 no. 7: 79
- vol. 71 no. 8: 72
- vol. 71 no. 9: 71
- vol. 71 no. 10: 76
- vol. 71 no. 11: 77
- vol. 71 no. 12: 88
- vol. 72 no. 1: 107
- vol. 72 no. 2: 101
- vol. 72 no. 3: 97
- vol. 72 no. 4: 87
- vol. 72 no. 5: 80
- vol. 72 no. 6: 80
- vol. 72 no. 7: 74
- vol. 72 no. 8: 75
- vol. 72 no. 9: 66
- vol. 72 no. 10: 70
- vol. 72 no. 11: 78
- vol. 72 no. 12: 70
- vol. 73 no. 1: 68
- vol. 73 no. 2: 60
- vol. 73 no. 3: 60
- vol. 73 no. 4: 70
- vol. 73 no. 5: 71
- vol. 73 no. 6: 72
- vol. 73 no. 7: 75
- vol. 73 no. 8: 120
- vol. 73 no. 9: 81
- vol. 73 no. 10: 120
- vol. 73 no. 11: 120
- vol. 73 no. 12: 119
- vol. 74 no. 1: 131
- vol. 74 no. 2: 90
- vol. 74 no. 3: 69
- vol. 74 no. 4: 80
- vol. 74 no. 5: 110
- vol. 74 no. 6: 102
- vol. 74 no. 7: 100
- vol. 74 no. 8: 82
- early access 2024: 1
- early access 2025: 16
- early access 2026: 261

## Data sources

1. **Crossref REST API** (`https://api.crossref.org/journals/0018-926X/works`)  
   Filter: `from-pub-date:2021-01-01,until-pub-date:2026-08-28`.  
   Used for bibliographic metadata: authors, title, volume, issue, pages, publication date, DOI.  
   Crossref returned **6850** journal-article records. **0** of those records included abstracts or keywords (typical for IEEE deposits).

2. **Semantic Scholar Academic Graph API**  
   - Bulk search: venue = IEEE Transactions on Antennas and Propagation, years 2021–2026 (**6302** papers, **5756** with abstracts).  
   - Paper batch lookup by DOI for Crossref records still missing abstracts (**687** hits, **138** additional abstracts).  
   Abstracts are full text as returned by the API (median length ~1270 characters; none were ellipsis-truncated).

3. **OpenAlex API** was attempted (`filter=primary_location.source.issn:0018-926X,...`) but returned HTTP 429 / insufficient daily budget (`$0 remaining` under OpenAlex’s 2026 credit model). Not used.

4. **IEEE Xplore** public REST (`/rest/document/{arnumber}`) returned HTTP 418 (bot block). No PDFs were downloaded. IEEE Xplore stamp URLs use the real article number from Crossref `link` (the `arnumber=` in IEEE's PDF URL), e.g. DOI `10.1109/TAP.2020.3030907` → arnumber `9234023`. The DOI suffix is not the Xplore arnumber. Updated 2026-08-28 after the first build.

## Filtering (administrative items excluded)

From the 6850 Crossref records, items were dropped when they were clearly not research content:

- Table of contents, covers (pages C2–C4), publication information, information for authors, editorial boards, institutional listings
- Publisher ads (TechRxiv, IEEE Open Access, IEEE Collabratec)
- Special-issue banner pages, calls for papers, society award announcements, in-memoriam notes, and other single-page items with no authors
- Four Crossref “ghost” early-access records with pre-2020 DOIs and no volume (re-deposits of older papers)

Skipped counts from this build: {'old_ghost': 4, 'admin': 487}

## Known gaps

- **Abstracts:** 475 catalog papers have `Abstract: N/A` because neither Crossref nor Semantic Scholar provided an abstract. IEEE does not deposit TAP abstracts in Crossref. OpenAlex (which reconstructs inverted abstracts) was unavailable due to API budget.
- **Keywords:** IEEE author keywords / IEEE Thesaurus terms are **not deposited in Crossref** and are not available from Semantic Scholar. All records are marked `keywords: {N/A}` rather than substituting coarse S2 fields of study. Filling these would require IEEE Xplore (paywalled / bot-blocked).
- **Volume 74 issues 9–12 (Sep–Dec 2026)** are after the cutoff and are not included.
- **Early Access** papers (278) have Crossref pages `1-1` and no volume/issue yet; they are included because Crossref lists a publication date inside the window.
- Semantic Scholar bulk search listed 10 extra items with TechRxiv/arXiv DOIs (preprints). Those were **not** added as TAP papers; Crossref DOI is the catalog key.
- Month names for assigned issues use Crossref `published-print` when a month is present; otherwise the issue number of this monthly journal is mapped to the English month name (no. 1 = January, …).
- Author names are converted to IEEE initials + family name from Crossref given/family fields. Hyphenated given names become forms like `G.-Y. Deng`.

## Files

- `/workspace/ieee-tap-2021-2026.txt` — formatted catalog (one paper per block)
- `/workspace/ieee-tap-2021-2026.json` — structured JSON array
- `/workspace/ieee-tap-2021-2026-summary.md` — this summary

## Completeness check

- Crossref issue grid for vols 69–73 (12 issues) and vol 74 (issues 1–8): **complete**
- Missing issues: none
## Enrichment pass (2026-09-24 (UTC))

- OpenAlex topic keywords added in this pass: **6268** (total with keywords: 6268)
- Abstracts added in this pass: **269** (total with abstracts: 6153)
- Keywords are **OpenAlex inferred topics**, not IEEE Index Terms / author keywords.
- Records still without abstract: **206** (not fabricated).
