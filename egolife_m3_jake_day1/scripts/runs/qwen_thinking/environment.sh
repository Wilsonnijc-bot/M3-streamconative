set -Eeuo pipefail
ROOT=/opt/streammeco/run
SMC=$ROOT/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full/code/StreamMeCo
MANDOL=$ROOT/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full/code/Mandol
RUN=$ROOT/egolife_10q_qwen35_4b_fps2_thinking_ids_v2_full
RESULTS=$RUN/results
WORK=$RUN/work
QA=/opt/streammeco/data/EgoLifeQA_A1_JAKE.json
CLIPS=/opt/streammeco/data/egolife_day1
source /opt/streammeco/secrets/runtime.env
export STREAMMECO_ROOT=$SMC
export PYTHONPATH="$SMC:/opt/streammeco/repos/3D-Speaker"
export CAMPLUS_CHECKPOINT=/opt/streammeco/models/camplus/v1.0.0/campplus_cn_en_common.pt
export INSIGHTFACE_MODEL_ROOT=/opt/streammeco/models/insightface
export TOKENIZERS_PARALLELISM=false
unset EGOLIFE_GEMINI_ONLY
export EGOLIFE_QWEN_ONLY=1
export QWEN_VLM_FPS=2
export QWEN_RUN=$RUN
export QWEN_URL=http://127.0.0.1:8766/generate
export EGOLIFE_ASR_MAX_ATTEMPTS=2
export EGOLIFE_EMBEDDING_MAX_ATTEMPTS=2
export EGOLIFE_RESULTS=$RESULTS
export QWEN_MODEL_PATH=/opt/streammeco/models/Qwen3.5-4B
unset QWEN_MAX_NEW_TOKENS
mkdir -p "$RESULTS" "$WORK"
cd "$SMC"
source /opt/streammeco/.venv/bin/activate
