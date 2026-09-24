#!/usr/bin/env bash
# Encode index/corpus.jsonl with Qwen3-Embedding-0.6B on the GPU.
# Run inside the unzipped a100-embed-job folder:
#   bash run_embed.sh
# Optional environment variables:
#   PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple   (pip mirror, read by pip itself)
#   TORCH_INDEX=https://download.pytorch.org/whl/cu121        (torch build matching an older driver)
#   VENV=/path/to/venv                                        (default: ./.venv)
#   BATCH=128
set -euo pipefail
cd "$(dirname "$0")"

VENV=${VENV:-.venv}
BATCH=${BATCH:-128}

if [ ! -d "$VENV" ]; then
  python3 -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip

if ! python -c "import torch" 2>/dev/null; then
  if [ -n "${TORCH_INDEX:-}" ]; then
    pip install torch --index-url "$TORCH_INDEX"
  else
    pip install torch
  fi
fi
pip install -r requirements-gpu.txt

python - <<'EOF'
import torch
assert torch.cuda.is_available(), "CUDA is not available: check nvidia-smi and the torch build (README step 2)"
print("torch", torch.__version__, "| GPU:", torch.cuda.get_device_name(0))
EOF

if [ ! -f models/Qwen3-Embedding-0.6B/model.safetensors ]; then
  python download_model.py
fi
export HF_HUB_OFFLINE=1
python scripts/build_index.py --no-bm25 \
  --model Qwen/Qwen3-Embedding-0.6B \
  --model-path models/Qwen3-Embedding-0.6B \
  --device cuda --batch-size "$BATCH"

ls -la index/emb.npy index/emb-meta.json
echo "Done. Copy index/emb.npy and index/emb-meta.json back to the local index/ folder."
