#!/usr/bin/env python3
"""Hybrid (BM25 + dense embedding) search over index/corpus.jsonl.

Shared by build_index.py (building), search.py (CLI) and mcp_server.py (Claude Code tool).

Index files in index/:
  corpus.jsonl      cleaned docs from build_corpus.py
  bm25.npz          BM25 weight matrix (docs x terms, CSC)
  bm25-vocab.json   term list for the matrix columns
  emb.npy           L2-normalised float16 document embeddings (optional)
  emb-meta.json     model name, doc ids and text hashes for emb.npy
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import scipy.sparse as sp
import snowballstemmer

ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = ROOT / "index"
DEFAULT_MODEL = "BAAI/bge-small-en-v1.5"
RRF_K = 60
BM25_K1 = 1.2
BM25_B = 0.75
TITLE_WEIGHT = 2  # title tokens are counted this many times

# Kept small on purpose: BM25 idf already discounts common words, and
# domain tokens such as "me" (magneto-electric) must survive.
STOPWORDS = frozenset(
    "a an and are as at be been by for from has have in into is it its of on or that the "
    "their these this those to was were with which we our can also".split()
)
DEFAULT_TYPES = ("article",)
ALL_TYPES = ("article", "comment", "correction", "editorial", "news")

QWEN3_TASK = (
    "Given an antenna, microwave or electromagnetics design question, retrieve abstracts of "
    "IEEE papers that describe relevant designs, techniques or analyses"
)
BGE_EN_QUERY = "Represent this sentence for searching relevant passages: "

_stemmer = snowballstemmer.stemmer("english")
_stem_cache: dict[str, str] = {}


def _stem(token: str) -> str:
    out = _stem_cache.get(token)
    if out is None:
        out = _stemmer.stemWord(token)
        _stem_cache[token] = out
    return out


def tokenize(text: str) -> list[str]:
    """Lowercase, split, stem. Hyphenated compounds also emit the joined form
    (magneto-electric -> magneto, electr, magnetoelectr) so either spelling matches."""
    text = text.lower().replace("–", "-").replace("—", "-").replace("‐", "-")
    tokens: list[str] = []
    for chunk in re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text):
        parts = chunk.split("-")
        for part in parts:
            if part and part not in STOPWORDS:
                tokens.append(_stem(part))
        if len(parts) > 1:
            tokens.append(_stem("".join(parts)))
    return tokens


def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def load_corpus(index_dir: Path = INDEX_DIR) -> list[dict[str, Any]]:
    with (index_dir / "corpus.jsonl").open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


# --- BM25 ---------------------------------------------------------------------


def build_bm25(docs: list[dict[str, Any]]) -> tuple[sp.csc_matrix, list[str]]:
    vocab: dict[str, int] = {}
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    doc_len = np.zeros(len(docs), dtype=np.float32)
    for i, doc in enumerate(docs):
        title = doc.get("title") or ""
        body = doc["search_text"][len(title):] if doc["search_text"].startswith(title) else doc["search_text"]
        tokens = tokenize(title) * TITLE_WEIGHT + tokenize(body)
        doc_len[i] = len(tokens)
        for term, tf in Counter(tokens).items():
            rows.append(i)
            cols.append(vocab.setdefault(term, len(vocab)))
            vals.append(tf)
    n_docs, n_terms = len(docs), len(vocab)
    tf = sp.csr_matrix((np.array(vals, dtype=np.float32), (rows, cols)), shape=(n_docs, n_terms))
    df = np.bincount(np.array(cols), minlength=n_terms)
    idf = np.log1p((n_docs - df + 0.5) / (df + 0.5)).astype(np.float32)
    norm = BM25_K1 * (1 - BM25_B + BM25_B * doc_len / max(doc_len.mean(), 1.0))
    row_of_nnz = np.repeat(np.arange(n_docs), np.diff(tf.indptr))
    data = tf.data
    tf.data = idf[tf.indices] * data * (BM25_K1 + 1) / (data + norm[row_of_nnz])
    terms = [""] * n_terms
    for term, j in vocab.items():
        terms[j] = term
    return tf.tocsc(), terms


def save_bm25(matrix: sp.csc_matrix, terms: list[str], index_dir: Path = INDEX_DIR) -> None:
    sp.save_npz(index_dir / "bm25.npz", matrix)
    (index_dir / "bm25-vocab.json").write_text(json.dumps(terms, ensure_ascii=False), encoding="utf-8")


# --- dense ----------------------------------------------------------------------


def load_model(name: str, device: str | None = None):
    from sentence_transformers import SentenceTransformer  # heavy import, keep lazy

    return SentenceTransformer(name, device=device)


def query_encode_kwargs(model, name: str) -> dict[str, Any]:
    lname = name.lower()
    if "qwen3-embedding" in lname:
        return {"prompt": f"Instruct: {QWEN3_TASK}\nQuery:"}
    if "query" in (getattr(model, "prompts", None) or {}):
        return {"prompt_name": "query"}
    if "bge-" in lname and "-en" in lname:
        return {"prompt": BGE_EN_QUERY}
    return {}


# --- search ---------------------------------------------------------------------


class LitIndex:
    def __init__(self, index_dir: Path = INDEX_DIR, device: str | None = "cpu"):
        self.index_dir = index_dir
        self.device = device
        self.docs = load_corpus(index_dir)
        self.by_id = {d["id"]: i for i, d in enumerate(self.docs)}
        self.by_arnumber = {str(d["arnumber"]): i for i, d in enumerate(self.docs) if d.get("arnumber")}
        self.bm25 = sp.load_npz(index_dir / "bm25.npz").tocsc()
        terms = json.loads((index_dir / "bm25-vocab.json").read_text(encoding="utf-8"))
        self.term_ids = {t: j for j, t in enumerate(terms)}
        self.journal = np.array([d["journal_code"] for d in self.docs])
        self.year = np.array([d.get("year") or 0 for d in self.docs])
        self.doc_type = np.array([d["doc_type"] for d in self.docs])

        self.emb: np.ndarray | None = None
        self.model_name: str | None = None
        self._model = None
        self._model_lock = threading.Lock()  # warm-up thread and first query must not both load it
        emb_path, meta_path = index_dir / "emb.npy", index_dir / "emb-meta.json"
        if emb_path.exists() and meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("ids") == [d["id"] for d in self.docs]:
                self.emb = np.load(emb_path).astype(np.float32)
                self.model_name = meta["model"]

    @property
    def has_dense(self) -> bool:
        return self.emb is not None

    def _model_obj(self):
        with self._model_lock:
            if self._model is None:
                self._model = load_model(self.model_name, self.device)
            return self._model

    def encode_query(self, query: str) -> np.ndarray:
        model = self._model_obj()
        vec = model.encode(
            [query], normalize_embeddings=True, **query_encode_kwargs(model, self.model_name)
        )[0]
        return vec.astype(np.float32)

    def bm25_scores(self, text: str) -> np.ndarray:
        ids = sorted({self.term_ids[t] for t in tokenize(text) if t in self.term_ids})
        if not ids:
            return np.zeros(len(self.docs), dtype=np.float32)
        return np.asarray(self.bm25[:, ids].sum(axis=1)).ravel()

    def mask(
        self,
        journals: Iterable[str] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        types: Iterable[str] | None = DEFAULT_TYPES,
    ) -> np.ndarray:
        keep = np.ones(len(self.docs), dtype=bool)
        if journals:
            keep &= np.isin(self.journal, [j.upper() for j in journals])
        if year_from:
            keep &= self.year >= year_from
        if year_to:
            keep &= self.year <= year_to
        if types:
            keep &= np.isin(self.doc_type, list(types))
        return keep

    @staticmethod
    def _ranked(scores: np.ndarray, keep: np.ndarray, limit: int, positive_only: bool) -> list[int]:
        valid = keep & (scores > 0) if positive_only else keep.copy()
        idx = np.flatnonzero(valid)
        if idx.size == 0:
            return []
        if idx.size > limit:
            idx = idx[np.argpartition(-scores[idx], limit - 1)[:limit]]
        return idx[np.argsort(-scores[idx], kind="stable")].tolist()

    def _fuse(
        self, bm: np.ndarray | None, dense: np.ndarray | None, keep: np.ndarray, top_k: int, pool: int
    ) -> list[dict[str, Any]]:
        fused: dict[int, float] = {}
        ranks: dict[int, dict[str, int]] = {}
        for name, scores, positive in (("bm25", bm, True), ("dense", dense, False)):
            if scores is None:
                continue
            for rank, i in enumerate(self._ranked(scores, keep, pool, positive), start=1):
                fused[i] = fused.get(i, 0.0) + 1.0 / (RRF_K + rank)
                ranks.setdefault(i, {})[name] = rank
        order = sorted(fused, key=lambda i: -fused[i])[:top_k]
        return [{"doc": self.docs[i], "score": fused[i], "ranks": ranks[i]} for i in order]

    def search(
        self,
        query: str,
        top_k: int = 10,
        journals: Iterable[str] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        types: Iterable[str] | None = DEFAULT_TYPES,
        mode: str = "hybrid",
        pool: int = 200,
    ) -> list[dict[str, Any]]:
        keep = self.mask(journals, year_from, year_to, types)
        use_dense = mode in ("hybrid", "dense") and self.has_dense
        bm = self.bm25_scores(query) if mode in ("hybrid", "bm25") or not use_dense else None
        dense = self.emb @ self.encode_query(query) if use_dense else None
        return self._fuse(bm, dense, keep, top_k, pool)

    def lookup(self, key: str) -> dict[str, Any] | None:
        key = key.strip().lower().removeprefix("https://doi.org/").removeprefix("doi:").strip()
        m = re.search(r"arnumber=(\d+)|/document/(\d+)", key)
        if m:
            key = m.group(1) or m.group(2)
        i = self.by_id.get(key)
        if i is None:
            i = self.by_arnumber.get(key)
        return self.docs[i] if i is not None else None

    def similar(
        self,
        key: str,
        top_k: int = 10,
        journals: Iterable[str] | None = None,
        year_from: int | None = None,
        year_to: int | None = None,
        types: Iterable[str] | None = DEFAULT_TYPES,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        doc = self.lookup(key)
        if doc is None:
            return None, []
        i = self.by_id[doc["id"]]
        keep = self.mask(journals, year_from, year_to, types)
        keep[i] = False
        bm = self.bm25_scores(doc["search_text"])
        dense = self.emb @ self.emb[i] if self.has_dense else None
        return doc, self._fuse(bm, dense, keep, top_k, 200)


def format_hit(n: int, hit: dict[str, Any], abstract_chars: int | None = None) -> str:
    doc = hit["doc"]
    ranks = " · ".join(f"{k} #{v}" for k, v in sorted(hit.get("ranks", {}).items()))
    tags = [doc["journal_code"], str(doc.get("year") or "")]
    if doc["doc_type"] != "article":
        tags.append(doc["doc_type"])
    if doc.get("early_access"):
        tags.append("early access")
    abstract = doc.get("abstract") or "N/A"
    if abstract_chars and len(abstract) > abstract_chars:
        abstract = abstract[:abstract_chars].rsplit(" ", 1)[0] + " …"
    head = f"[{n}] {' '.join(t for t in tags if t)}" + (f"  ({ranks})" if ranks else "")
    return f"{head}\n{doc['citation']}\nURL: {doc.get('url') or ''}\nAbstract: {abstract}"
