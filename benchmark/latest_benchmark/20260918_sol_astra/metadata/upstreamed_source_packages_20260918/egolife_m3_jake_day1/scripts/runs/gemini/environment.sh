set -Eeuo pipefail
ROOT=/opt/streammeco/run
SMC=$ROOT/StreamMeCo
MANDOL=$ROOT/Mandol
RUN=$ROOT/egolife_10q_gemini
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
export EGOLIFE_GEMINI_ONLY=1
export EGOLIFE_ASR_MAX_ATTEMPTS=2
export EGOLIFE_EMBEDDING_MAX_ATTEMPTS=2
export EGOLIFE_RESULTS=$RESULTS
unset QWEN_MODEL_PATH
mkdir -p "$RESULTS" "$WORK"
cd "$SMC"
source /opt/streammeco/.venv/bin/activate
