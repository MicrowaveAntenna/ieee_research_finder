#!/usr/bin/env python3
"""Check that the current Python environment can run the GPU embedding job.

Run with the python of your own virtual environment (nothing is installed or changed):
  python check_env.py
Prints what is missing and the exact pip commands to fix it. Exit code 0 = ready.
"""

from __future__ import annotations

import importlib
import re
from importlib import metadata
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
NEEDED = [  # module, pip name, minimum version
    ("numpy", "numpy", "1.24"),
    ("scipy", "scipy", "1.10"),
    ("snowballstemmer", "snowballstemmer", "2.2"),
    ("transformers", "transformers", "4.51"),
    ("sentence_transformers", "sentence-transformers", "3.0"),
]


def vtuple(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3])


def driver_cuda() -> str | None:
    try:
        out = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = re.search(r"CUDA Version:\s*([\d.]+)", out)
    return m.group(1) if m else None


def torch_index(cuda: str | None) -> str:
    v = vtuple(cuda or "0")
    for tag, need in (("cu128", (12, 8)), ("cu126", (12, 6)), ("cu124", (12, 4)), ("cu121", (12, 1)), ("cu118", (11, 8))):
        if v >= need:
            return f"https://download.pytorch.org/whl/{tag}"
    return "https://download.pytorch.org/whl/cu118"


def main() -> int:
    ok = True
    print(f"Python {sys.version.split()[0]}  ({sys.executable})")
    if sys.version_info < (3, 9):
        print("  [X] Python 3.9 or newer is required")
        ok = False

    cuda = driver_cuda()
    print(f"NVIDIA driver CUDA version: {cuda or 'nvidia-smi not found'}")
    index_url = torch_index(cuda)

    try:
        import torch

        built = torch.version.cuda
        print(f"torch {torch.__version__} (CUDA build: {built or 'none, CPU-only'})")
        if torch.cuda.is_available():
            print(f"  [OK] GPU: {torch.cuda.get_device_name(0)}")
        else:
            ok = False
            print("  [X] torch cannot see the GPU.")
            if not built:
                print("      This venv has the CPU-only torch (the default from pip on Windows).")
                print("      Replacing it changes torch for everything in this venv:")
                print(f"      python -m pip install --force-reinstall torch --index-url {index_url}")
    except ImportError:
        ok = False
        print("  [X] torch is not installed. Install the CUDA build:")
        print(f"      python -m pip install torch --index-url {index_url}")

    missing = []
    for module, pip_name, minimum in NEEDED:
        try:
            importlib.import_module(module)
            try:
                version = metadata.version(pip_name)  # some packages have no __version__
            except metadata.PackageNotFoundError:
                version = "0"
            if vtuple(version) < vtuple(minimum):
                missing.append(pip_name)
                print(f"  [X] {pip_name} {version} < {minimum}")
            else:
                print(f"  [OK] {pip_name} {version}")
        except ImportError:
            missing.append(pip_name)
            print(f"  [X] {pip_name} not installed")
    if missing:
        ok = False
        print("\n  Preview what pip would change first (nothing is installed):")
        print("      python -m pip install --dry-run -r requirements-gpu.txt")
        print("  then, if that is fine for your other projects:")
        print("      python -m pip install -r requirements-gpu.txt")
        print("  (add  -i https://pypi.tuna.tsinghua.edu.cn/simple  for the Tsinghua mirror)")

    if not (HERE / "index" / "corpus.jsonl").exists():
        ok = False
        print("  [X] missing index/corpus.jsonl: unzip the whole a100-embed-job.zip")
    if (HERE / "models" / "Qwen3-Embedding-0.6B" / "model.safetensors").exists():
        print("  [OK] model files present")
    else:
        print("  [..] model not downloaded yet: run_embed.bat downloads it first (~1.2 GB)")

    print("\nREADY: run run_embed.bat" if ok else "\nNOT READY: fix the [X] items above")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
