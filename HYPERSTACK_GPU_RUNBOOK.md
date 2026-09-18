# Hyperstack GPU Setup for StreamMeCo Memory Construction

The Hyperstack GPU base is ready.

- **Instance:** `1042997` (`streammeco-a6000-20260914`)
- **IP:** `185.216.21.158`
- **GPU:** RTX A6000, 49,140 MiB VRAM
- **Environment:** `default-CANADA-1`
- **Disk:** 42 GB used, 56 GB free
- **Videos:** all 646 copied
- **Qwen:** load and inference smoke test passed
- **APIs:** Deepgram, OpenRouter, and 302.ai authentication passed
- **OpenRouter embedding:** 3,072 dimensions, 384 ms
- **Secrets:** `/opt/streammeco/secrets/runtime.env`, mode `600`

Connect with:

```bash
ssh -i '/Users/nijiachen/Downloads/njc_Hyperstack (1).txt' \
  ubuntu@185.216.21.158
```

The instance remains **ACTIVE**. The full Gemini versus Qwen comparison was not launched; the machine is prepared and preflight-verified for it.
This is the shortest reproducible path to a Hyperstack GPU that can run the
real first-clip comparison from `experiment_GPU_record.md`:

> Gemini 3.8 vs Qwen 3.5 4B first-clip comparison - 2026-09-14

It runs video decoding, Deepgram and MAI-Transcribe-2 ASR, CAM++ speaker
embedding, Buffalo-L face processing, local Qwen 3.5 4B, Gemini 3.8 Flash,
OpenRouter text embeddings, and VideoGraph construction.

This describes the September 14, 2026 historical comparison. New construction
selects exactly one ASR alias via `asr_provider` in `processing_config.json`;
Deepgram and MAI are alternatives, not co-required services. Use a fresh voice
graph and provider-bound caches when changing the selected ASR service.

## 1. Required Machine

Create a Hyperstack VM with:

- Ubuntu Server 22.04 LTS R550 CUDA 12.4
- One GPU with at least 24 GB VRAM; 48 GB is preferred
- At least 8 vCPUs and 32 GB RAM
- At least 40 GB free disk for the first-clip run; use 80 GB or more for growth
- SSH access and a public IP

Use Hyperstack's CUDA image. Do not replace its NVIDIA driver manually.

Hyperstack image reference:
<https://docs.hyperstack.cloud/docs/virtual-machines/images/>

## 2. Known-Good Dependency Versions

These versions were observed on the successful reference GPU:

| Dependency | Version |
| --- | --- |
| Python | 3.10.8 |
| PyTorch | 2.6.0+cu124 |
| torchvision | 0.21.0 |
| torchaudio | 2.6.0+cu124 |
| transformers | 5.17.0 |
| accelerate | 1.15.0 |
| ONNX Runtime GPU | 1.21.1 |
| InsightFace | 0.7.3 |
| OpenCV headless | 4.11.0.86 |
| NumPy | 1.26.4 |
| SciPy | 1.14.1 |
| MoviePy | 2.2.1 |
| OpenAI client | 1.109.1 |
| HTTPX | 0.28.1 |
| FLA core | 0.5.2 |

Required assets:

| Asset | Reference |
| --- | --- |
| Patched StreamMeCo source | Current local workspace; base commit alone is insufficient |
| Base source revision | `67c8e8c74c97e69f625890936754a9f934f3d35a` |
| 3D-Speaker revision | `065629c313eaf1a01c65c640c46d77e61e9607b4` |
| Qwen | `Qwen/Qwen3.5-4B`, about 8.8 GB |
| CAM++ | `campplus_cn_en_common.pt`, 192-dimensional embeddings |
| Face model | Complete InsightFace `buffalo_l` pack |
| Input clip | `DAY1_A1_JAKE_11094208.mp4`, 6,663,507 bytes |

The reference source tree contains extensive uncommitted adapter changes. Copy
the current workspace; cloning only the base revision will not reproduce the
run.

## 3. Install the Host and Python Dependencies

Connect to the new VM and run:

```bash
set -Eeuo pipefail

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  build-essential ffmpeg git git-lfs libgl1 libglib2.0-0 libsndfile1 \
  python3.10 python3.10-dev python3.10-venv rsync tmux

sudo mkdir -p /opt/streammeco/{models,repos,run,data,secrets}
sudo chown -R "$USER":"$USER" /opt/streammeco

python3.10 -m venv /opt/streammeco/.venv
source /opt/streammeco/.venv/bin/activate
python -m pip install --upgrade pip setuptools wheel

python -m pip install \
  torch==2.6.0+cu124 \
  torchvision==0.21.0 \
  torchaudio==2.6.0+cu124 \
  --index-url https://download.pytorch.org/whl/cu124

python -m pip install \
  accelerate==1.15.0 \
  albumentations==2.0.8 \
  av==17.1.0 \
  easydict==1.13 \
  fla-core==0.5.2 \
  hdbscan==0.8.44 \
  httpx==0.28.1 \
  insightface==0.7.3 \
  matplotlib==3.10.9 \
  moviepy==2.2.1 \
  numpy==1.26.4 \
  onnx==1.17.0 \
  onnxruntime-gpu==1.21.1 \
  openai==1.109.1 \
  opencv-python-headless==4.11.0.86 \
  pillow==11.3.0 \
  pydub==0.25.1 \
  qwen-vl-utils==0.0.14 \
  requests==2.32.3 \
  scikit-image==0.25.2 \
  scikit-learn==1.6.1 \
  scipy==1.14.1 \
  soundfile==0.13.1 \
  transformers==5.17.0 \
  tqdm==4.67.1

git clone https://github.com/modelscope/3D-Speaker.git \
  /opt/streammeco/repos/3D-Speaker
git -C /opt/streammeco/repos/3D-Speaker checkout \
  065629c313eaf1a01c65c640c46d77e61e9607b4
```

`causal-conv1d` is optional. The reference GPU had an ABI-incompatible build,
so Transformers used its correct but slower PyTorch fallback. Do not block setup
on this extension.

## 4. Copy the Required Content

On the local workstation:

```bash
export HYPERSTACK_HOST='<new-vm-ip>'
export HYPERSTACK_KEY="$HOME/.ssh/<private-key>"
cd /Users/nijiachen/StreamMeCo

rsync -az \
  --exclude '.git/' \
  --exclude '.venv/' \
  --exclude '*.mp4' \
  --exclude '*.log' \
  --exclude '*.pkl' \
  --exclude 'qwen35_4b/' \
  -e "ssh -i $HYPERSTACK_KEY" \
  ./ ubuntu@"$HYPERSTACK_HOST":/opt/streammeco/run/

rsync -az --info=progress2 -e "ssh -i $HYPERSTACK_KEY" \
  qwen35_4b/ \
  ubuntu@"$HYPERSTACK_HOST":/opt/streammeco/models/Qwen3.5-4B/

rsync -az -e "ssh -i $HYPERSTACK_KEY" \
  egolife_day1/DAY1_A1_JAKE_11094208.mp4 \
  egolife_m3_jake_day1/EgoLifeQA_A1_JAKE.json \
  ubuntu@"$HYPERSTACK_HOST":/opt/streammeco/data/
```

Then download CAM++ and Buffalo-L on the VM:

```bash
source /opt/streammeco/.venv/bin/activate
python /opt/streammeco/run/gpu_setup/download_models.py \
  --root /opt/streammeco --only all
```

Important: blank hard-coded `api_key` values in
`StreamMeCo/configs/api_config.json` before transfer. Provide only these runtime
environment variables on the VM:

```text
DEEPGRAM_API_KEY
OPENROUTER_API_KEY
API_302_KEY
```

Store them in `/opt/streammeco/secrets/runtime.env` with mode `600`. Do not put
keys in this runbook, Git, logs, snapshots, or `experiment_GPU_record.md`.

## 5. Create the Runtime Layout

Run on the VM:

```bash
set -Eeuo pipefail
cd /opt/streammeco/run

mkdir -p models logs results work
ln -sfn /opt/streammeco/models/Qwen3.5-4B models/Qwen3.5-4B
ln -sfn /opt/streammeco/models/insightface models/insightface
ln -sfn /opt/streammeco/repos/3D-Speaker/speakerlab speakerlab

test "$(stat -c %s /opt/streammeco/data/DAY1_A1_JAKE_11094208.mp4)" = 6663507
test -s /opt/streammeco/data/EgoLifeQA_A1_JAKE.json
test -s /opt/streammeco/models/Qwen3.5-4B/model.safetensors.index.json
test -s /opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt
test -s /opt/streammeco/models/insightface/models/buffalo_l/det_10g.onnx
test -s /opt/streammeco/models/insightface/models/buffalo_l/w600k_r50.onnx
```

## 6. Preflight

Run on the VM:

```bash
set -Eeuo pipefail
cd /opt/streammeco/run/StreamMeCo
source /opt/streammeco/.venv/bin/activate
source /opt/streammeco/secrets/runtime.env

export PYTHONPATH="$PWD:/opt/streammeco/repos/3D-Speaker"
export QWEN_MODEL_PATH=/opt/streammeco/models/Qwen3.5-4B
export CAMPLUS_CHECKPOINT=/opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt
export INSIGHTFACE_MODEL_ROOT=/opt/streammeco/models/insightface

python - <<'PY'
import os
import torch
import onnxruntime as ort

assert torch.__version__ == '2.6.0+cu124'
assert torch.cuda.is_available()
assert torch.cuda.get_device_properties(0).total_memory >= 23 * 1024**3
assert torch.arange(8, device='cuda').square().sum().item() == 140
assert 'CUDAExecutionProvider' in ort.get_available_providers()
for name in ('DEEPGRAM_API_KEY', 'OPENROUTER_API_KEY', 'API_302_KEY'):
    assert os.environ.get(name), f'{name} is missing'
print('GPU_PREFLIGHT_OK', torch.cuda.get_device_name(0))
PY

python -m py_compile benchmarks/compare_first_clip_vlms.py
python -c 'import benchmarks.compare_first_clip_vlms; print("IMPORT_OK")'
```

Do not launch until all checks pass.

## 7. Run Real Memory Construction

Run on the VM:

```bash
set -Eeuo pipefail

RUN_ID="first-clip-vlm-compare-$(date -u +%Y%m%dT%H%M%SZ)"
RESULTS="/opt/streammeco/run/results/$RUN_ID"
WORK="/opt/streammeco/run/work/$RUN_ID"
LOG="/opt/streammeco/run/logs/$RUN_ID.log"
mkdir -p "$RESULTS" "$WORK" "$(dirname "$LOG")"

tmux new-session -d -s "$RUN_ID" \
  "bash -lc 'set -Eeuo pipefail
  cd /opt/streammeco/run/StreamMeCo
  source /opt/streammeco/.venv/bin/activate
  source /opt/streammeco/secrets/runtime.env
  export PYTHONPATH=\"\$PWD:/opt/streammeco/repos/3D-Speaker\"
  export QWEN_MODEL_PATH=/opt/streammeco/models/Qwen3.5-4B
  export CAMPLUS_CHECKPOINT=/opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt
  export INSIGHTFACE_MODEL_ROOT=/opt/streammeco/models/insightface
  python benchmarks/compare_first_clip_vlms.py \
    --clip /opt/streammeco/data/DAY1_A1_JAKE_11094208.mp4 \
    --results \"$RESULTS\" \
    --work \"$WORK\" \
    2>&1 | tee \"$LOG\"
  rc=\${PIPESTATUS[0]}
  printf \"\\nEXIT_STATUS=%s\\n\" \"\$rc\" >> \"$LOG\"
  exit \"\$rc\"'"

printf 'RUN_ID=%s\nRESULTS=%s\nWORK=%s\nLOG=%s\n' \
  "$RUN_ID" "$RESULTS" "$WORK" "$LOG"
```

Monitor with:

```bash
export RUN_ID='first-clip-vlm-compare-<timestamp-from-launch>'
tmux attach -t "$RUN_ID"
# Or without attaching:
tail -f "/opt/streammeco/run/logs/$RUN_ID.log"
```

## 8. Verify Completion

After the tmux session exits:

```bash
export RUN_ID='first-clip-vlm-compare-<timestamp-from-launch>'
RESULTS="/opt/streammeco/run/results/$RUN_ID"
LOG="/opt/streammeco/run/logs/$RUN_ID.log"

grep -q '^EXIT_STATUS=0$' "$LOG"
test -s "$RESULTS/shared_preprocessing.json"
test -s "$RESULTS/qwen3_5_4b.json"
test -s "$RESULTS/qwen3_5_4b_graph.pkl"
test -s "$RESULTS/gemini_3_8_flash.json"
test -s "$RESULTS/gemini_3_8_flash_graph.pkl"
test -s "$RESULTS/comparison.md"
