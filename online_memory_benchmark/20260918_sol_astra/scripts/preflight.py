"""Fail-closed online benchmark readiness check; never runs benchmark inference."""
import json
import os
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

import torch

root = Path(__file__).resolve().parents[1]
request = json.loads((root / "configs/run_request.json").read_text())
blockers = []

def require(condition, message):
    if not condition:
        blockers.append(message)

require(torch.cuda.is_available(), "CUDA is unavailable")
cuda_ok = False
if torch.cuda.is_available():
    cuda_ok = torch.arange(8, device="cuda").square().sum().item() == 140
require(cuda_ok, "CUDA tensor arithmetic failed")
require(bool(shutil.which("tmux")), "tmux is unavailable")
require((root / "scripts/online_benchmark.py").is_file(),
        "Integrated online C1-C4 benchmark entrypoint is absent")

media = Path("/opt/streammeco/aea_6h")
manifest_path = media / "aea_6h_manifest.json"
manifest = json.loads(manifest_path.read_text()) if manifest_path.is_file() else {"recordings": []}
missing = [r["video_path"] for r in manifest["recordings"]
           if not (media / r["video_path"]).is_file()]
require(len(manifest["recordings"]) == 109 and not missing,
        "AEA recording manifest or media is incomplete")
require(Path("/opt/streammeco/data/EgoLifeQA_A1_JAKE.json").is_file(),
        "Jake source annotations are unavailable")
for dataset, expected in (("jake", 10), ("aea", 1994)):
    path = root / "configs" / f"{dataset}_questions.json"
    count = len(json.loads(path.read_text())["questions"]) if path.is_file() else 0
    require(count == expected, f"Normalized {dataset} questions missing/incomplete ({count}/{expected})")
    path = root / "configs" / f"tst_{dataset}.json"
    if not path.is_file():
        blockers.append(f"Verified TST enrollment and independent threshold calibration absent for {dataset}")
    else:
        tst = json.loads(path.read_text())
        for field in ("enrollment", "calibration", "encoder_checkpoint"):
            value = tst.get(field)
            require(bool(value) and Path(value).is_file(), f"TST {dataset} {field} unavailable")
        require(isinstance(tst.get("threshold"), (int, float)),
                f"TST {dataset} calibrated threshold unavailable")

free_bytes = shutil.disk_usage(root).free
key = os.environ.get("OPENAI_API_KEY")
require(bool(key), "Official OpenAI API key missing from private runtime environment")
model_access = False
if key:
    model_id = request["primary_backend"]["model_id"]
    req = urllib.request.Request("https://api.openai.com/v1/models/" + model_id,
                                 headers={"Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            model_access = json.load(response).get("id") == model_id
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        blockers.append(f"Official Sol model access check failed: {type(error).__name__}")
    require(model_access, "Official Sol model ID is not accessible")

report = {"status": "ready" if not blockers else "blocked",
          "benchmark_started": False, "instance_id": request["instance_id"],
          "primary_backend": request["primary_backend"]["model_id"],
          "primary_reasoning_effort": request["primary_backend"]["reasoning_effort"],
          "consolidation_backend": request["consolidation_backend"]["model"],
          "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
          "torch": torch.__version__, "cuda_tensor_check": cuda_ok,
          "disk_free_bytes": free_bytes,
          "storage_note": "Measure peak working and artifact bytes on a short prefix before full execution",
          "aea_recordings": len(manifest["recordings"]),
          "aea_missing_media": missing, "model_access": model_access,
          "blockers": blockers}
(root / "metadata/readiness.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2), flush=True)
sys.exit(0 if not blockers else 2)
