#!/usr/bin/env python3
"""Build the BM25 + dense search index from index/corpus.jsonl.

Dense encoding is incremental: embeddings of docs whose id and search_text are unchanged
are reused (from emb.npy or an interrupted run's emb-partial.npz), so monthly updates and
restarts only encode what is new. The same script runs on CPU or on the A100 (--device cuda).

  python scripts/build_index.py                                   # BM25 + bge-small on CPU
  python scripts/build_index.py --model Qwen/Qwen3-Embedding-0.6B --device cuda --batch-size 128
  python scripts/build_index.py --model Qwen/Qwen3-Embedding-0.6B --model-path models/Qwen3-Embedding-0.6B --device cuda
  python scripts/build_index.py --no-dense                        # BM25 only (seconds)
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from litsearch import (  # noqa: E402
    DEFAULT_MODEL,
    INDEX_DIR,
    build_bm25,
    load_corpus,
    load_model,
    save_bm25,
    text_hash,
)

CHUNK = 1024  # docs per encode() call; progress is saved after each chunk


def load_cached(index_dir: Path, model: str) -> dict[tuple[str, str], np.ndarray]:
    """Map (doc id, text hash) -> embedding from a finished or interrupted run of the same model."""
    cache: dict[tuple[str, str], np.ndarray] = {}
    meta_path, emb_path = index_dir / "emb-meta.json", index_dir / "emb.npy"
    if meta_path.exists() and emb_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("model") == model:
            emb = np.load(emb_path)
            cache.update({(i, h): emb[k] for k, (i, h) in enumerate(zip(meta["ids"], meta["hashes"]))})
    partial = index_dir / "emb-partial.npz"
    if partial.exists():
        data = np.load(partial, allow_pickle=False)
        if str(data["model"]) == model:
            cache.update({(i, h): v for i, h, v in zip(data["ids"], data["hashes"], data["emb"])})
    return cache


def build_dense(docs: list[dict], index_dir: Path, args: argparse.Namespace) -> None:
    ids = [d["id"] for d in docs]
    texts = [d["search_text"] for d in docs]
    hashes = [text_hash(t) for t in texts]
    cache = load_cached(index_dir, args.model)
    todo = [k for k, key in enumerate(zip(ids, hashes)) if key not in cache]
    print(f"Dense: {len(docs) - len(todo)} cached, {len(todo)} to encode with {args.model}", file=sys.stderr)

    if todo:
        if args.threads:
            import torch

            torch.set_num_threads(args.threads)
        model = load_model(str(args.model_path or args.model), args.device)
        model.max_seq_length = args.max_seq_length
        done_ids: list[str] = []
        done_hashes: list[str] = []
        done_vecs: list[np.ndarray] = []
        start = time.time()
        for c in range(0, len(todo), CHUNK):
            chunk = todo[c : c + CHUNK]
            vecs = model.encode(
                [texts[k] for k in chunk],
                batch_size=args.batch_size,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            ).astype(np.float16)
            for k, v in zip(chunk, vecs):
                cache[(ids[k], hashes[k])] = v
                done_ids.append(ids[k])
                done_hashes.append(hashes[k])
                done_vecs.append(v)
            np.savez(
                index_dir / "emb-partial.npz",
                model=np.array(args.model),
                ids=np.array(done_ids),
                hashes=np.array(done_hashes),
                emb=np.stack(done_vecs),
            )
            n = min(c + CHUNK, len(todo))
            rate = n / (time.time() - start)
            print(f"  encoded {n}/{len(todo)} · {rate:.1f} docs/s · ETA {(len(todo) - n) / rate / 60:.1f} min", file=sys.stderr)

    emb = np.stack([cache[(i, h)] for i, h in zip(ids, hashes)]).astype(np.float16)
    np.save(index_dir / "emb.npy", emb)
    meta = {
        "model": args.model,
        "dim": int(emb.shape[1]),
        "max_seq_length": args.max_seq_length,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ids": ids,
        "hashes": hashes,
    }
    (index_dir / "emb-meta.json").write_text(json.dumps(meta), encoding="utf-8")
    (index_dir / "emb-partial.npz").unlink(missing_ok=True)
    print(f"Dense: wrote {emb.shape} -> {index_dir / 'emb.npy'}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Build BM25 + dense index from index/corpus.jsonl")
    p.add_argument("--index-dir", type=Path, default=INDEX_DIR)
    p.add_argument("--model", default=DEFAULT_MODEL, help=f"sentence-transformers model id (default {DEFAULT_MODEL})")
    p.add_argument(
        "--model-path",
        type=Path,
        help="Load the model from this local folder (offline server); emb-meta.json still records --model",
    )
    p.add_argument("--device", default=None, help="cpu / cuda (default: auto)")
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--max-seq-length", type=int, default=512)
    p.add_argument("--threads", type=int, help="Limit CPU threads for encoding (cooler / quieter, slower)")
    p.add_argument("--no-dense", action="store_true", help="Only rebuild BM25")
    p.add_argument("--no-bm25", action="store_true", help="Only rebuild dense embeddings")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    docs = load_corpus(args.index_dir)
    print(f"Corpus: {len(docs)} docs", file=sys.stderr)
    if not args.no_bm25:
        t = time.time()
        matrix, terms = build_bm25(docs)
        save_bm25(matrix, terms, args.index_dir)
        print(f"BM25: {matrix.shape[1]} terms, {matrix.nnz} postings ({time.time() - t:.1f}s)", file=sys.stderr)
    if not args.no_dense:
        build_dense(docs, args.index_dir, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
