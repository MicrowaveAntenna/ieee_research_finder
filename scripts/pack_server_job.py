#!/usr/bin/env python3
"""Bundle the A100 embedding job into one zip to copy to the server.

  python scripts/pack_server_job.py                 # -> TEMPFILES/a100-embed-job.zip (~40 MB)
  python scripts/pack_server_job.py --with-model    # also bundle the 1.2 GB model (offline server)

Contents: the server/ files (README, check_env.py, download_model.py, run_embed.bat/.sh,
requirements-gpu.txt), scripts/litsearch.py, scripts/build_index.py and index/corpus.jsonl.
Without --with-model the server downloads the model itself (download_model.py).
"""

from __future__ import annotations

import argparse
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIX = "a100-embed-job"
DEFAULT_MODEL = "Qwen/Qwen3-Embedding-0.6B"


def model_snapshot(model_id: str) -> Path:
    from huggingface_hub import snapshot_download

    try:
        return Path(snapshot_download(model_id, local_files_only=True))
    except Exception:
        print(f"{model_id} not in local cache, downloading ...", file=sys.stderr)
        return Path(snapshot_download(model_id))


def add(zf: zipfile.ZipFile, src: Path, arcname: str, executable: bool = False) -> None:
    compress = zipfile.ZIP_STORED if src.suffix in {".safetensors", ".bin"} else zipfile.ZIP_DEFLATED
    info = zipfile.ZipInfo.from_file(src, f"{PREFIX}/{arcname}")
    info.compress_type = compress
    info.create_system = 3  # Unix, so unzip on the server applies the permission bits below
    info.external_attr = (0o100755 if executable else 0o100644) << 16
    data = src.read_bytes()
    if src.suffix == ".sh":
        data = data.replace(b"\r\n", b"\n")  # bash on Linux chokes on CRLF
    elif src.suffix == ".bat":
        data = data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")  # cmd labels/goto need CRLF
    zf.writestr(info, data)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Bundle the A100 embedding job")
    p.add_argument("--out", type=Path, default=ROOT / "TEMPFILES" / f"{PREFIX}.zip")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--with-model", action="store_true", help="Bundle the model from the local HF cache")
    args = p.parse_args(argv)

    corpus = ROOT / "index" / "corpus.jsonl"
    if not corpus.exists():
        print("index/corpus.jsonl missing: run scripts/build_corpus.py first", file=sys.stderr)
        return 2

    files: list[tuple[Path, str, bool]] = [
        (ROOT / "server" / "README.md", "README.md", False),
        (ROOT / "server" / "check_env.py", "check_env.py", False),
        (ROOT / "server" / "download_model.py", "download_model.py", False),
        (ROOT / "server" / "run_embed.bat", "run_embed.bat", False),
        (ROOT / "server" / "run_embed.sh", "run_embed.sh", True),
        (ROOT / "server" / "requirements-gpu.txt", "requirements-gpu.txt", False),
        (ROOT / "scripts" / "litsearch.py", "scripts/litsearch.py", False),
        (ROOT / "scripts" / "build_index.py", "scripts/build_index.py", False),
        (corpus, "index/corpus.jsonl", False),
    ]
    if args.with_model:
        snap = model_snapshot(args.model)
        target = "models/" + args.model.split("/")[-1]
        for f in sorted(snap.rglob("*")):
            if f.is_file() and not f.name.startswith("."):
                files.append((f, f"{target}/{f.relative_to(snap).as_posix()}", False))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", allowZip64=True) as zf:
        for src, arc, exe in files:
            add(zf, src, arc, exe)
            print(f"  + {arc}", file=sys.stderr)
    print(f"Wrote {args.out} ({args.out.stat().st_size / 1e6:.0f} MB, {len(files)} files)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
