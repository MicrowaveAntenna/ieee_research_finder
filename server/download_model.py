#!/usr/bin/env python3
"""Download Qwen3-Embedding-0.6B (~1.2 GB) into models/ next to this file.

Tries huggingface.co first and falls back to the hf-mirror.com mirror; an interrupted
download resumes when rerun. run_embed.bat / run_embed.sh call this automatically.

  python download_model.py
  set HF_ENDPOINT=https://hf-mirror.com  (then run it) to force one endpoint
"""

from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = "Qwen/Qwen3-Embedding-0.6B"
TARGET = HERE / "models" / "Qwen3-Embedding-0.6B"
ENDPOINTS = ["https://huggingface.co", "https://hf-mirror.com"]


def reachable(endpoint: str) -> bool:
    try:
        urllib.request.urlopen(f"{endpoint}/api/models/{REPO}", timeout=15).read(1)
        return True
    except Exception as exc:
        print(f"  {endpoint}: not reachable ({exc.__class__.__name__}: {exc})")
        return False


def main() -> int:
    if (TARGET / "model.safetensors").exists():
        print(f"Model already present: {TARGET}")
        return 0
    os.environ.pop("HF_HUB_OFFLINE", None)
    from huggingface_hub import snapshot_download

    endpoints = [os.environ["HF_ENDPOINT"]] if os.environ.get("HF_ENDPOINT") else ENDPOINTS
    for endpoint in endpoints:
        if not reachable(endpoint):
            continue
        print(f"Downloading {REPO} (~1.2 GB) from {endpoint}\n  -> {TARGET}")
        try:
            snapshot_download(REPO, local_dir=TARGET, endpoint=endpoint)
        except Exception as exc:
            print(f"  download from {endpoint} failed: {exc}")
            continue
        if (TARGET / "model.safetensors").exists():
            print("Model downloaded.")
            return 0
    print(
        "\nCould not download the model from any endpoint.\n"
        "Ask for a bundle that already contains it (pack_server_job.py --with-model)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
