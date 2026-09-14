# Copyright (2025) Bytedance Ltd. and/or its affiliates

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import base64
import struct
import json
import os
import logging
import time
import torchaudio
import torch
from io import BytesIO
from speakerlab.process.processor import FBank
from speakerlab.models.campplus.DTDNN import CAMPPlus

from pydub import AudioSegment
from .utils.chat_api import merge_primary_transcriptions, transcribe_audio_with_retry
from .utils.general import normalize_embedding
import io

processing_config = json.load(open("configs/processing_config.json"))

MAX_RETRIES = processing_config["max_retries"]

embedding_model = None
feature_extractor = FBank(80, sample_rate=16000, mean_nor=True)


def _get_embedding_model():
    global embedding_model
    if embedding_model is None:
        checkpoint = os.environ.get(
            "CAMPLUS_CHECKPOINT",
            processing_config.get(
                "speaker_embedding_checkpoint",
                "models/camplus/campplus_cn_en_common.pt",
            ),
        )
        state = torch.load(checkpoint, map_location="cpu", weights_only=True)
        embedding_model = CAMPPlus(feat_dim=80, embedding_size=192)
        embedding_model.load_state_dict(state)
        embedding_model.to(torch.device("cuda"))
        embedding_model.eval()
    return embedding_model
def get_embedding(wav):

    def load_wav(wav_file, obj_fs=16000):
        wav, fs = torchaudio.load(wav_file)
        if fs != obj_fs:
            wav, fs = torchaudio.sox_effects.apply_effects_tensor(
                wav, fs, effects=[['rate', str(obj_fs)]]
            )
        if wav.shape[0] > 1:
            wav = wav[0, :].unsqueeze(0)
        return wav
    
    def compute_embedding(wav_file, save=True):
        wav = load_wav(wav_file)
        feat = feature_extractor(wav).unsqueeze(0).to(torch.device('cuda'))
        with torch.no_grad():
            embedding = _get_embedding_model()(feat).detach().squeeze(0).cpu().numpy()
        return embedding

    return compute_embedding(wav)

@torch.no_grad()
def generate(wav):
    wav = base64.b64decode(wav)
    wav_file = BytesIO(wav)
    emb = get_embedding(wav_file)
    return emb

@torch.no_grad()
def get_audio_embeddings(audio_segments):
    res = []
    for wav in audio_segments:
        completion = generate(wav.decode("utf-8"))
        bytes_data = struct.pack('f' * len(completion), *completion)
        res.append(bytes_data)
        
    return res


# Configure logging
logger = logging.getLogger(__name__)


def process_voices(
    video_graph, base64_audio, base64_video, save_path, preprocessing=[], metrics=None
):
    """Diarize speech, compute CAM++ embeddings, and update voice nodes."""
    metrics = metrics if metrics is not None else {}
    total_started = time.perf_counter()
    metrics.update({
        "cache_hit": False,
        "asr_provider_ms": {},
        "asr_total_ms": None,
        "audio_segmentation_ms": None,
        "speech_embedding_ms": None,
        "graph_update_ms": None,
        "asr_segment_count": 0,
        "speech_embedding_count": 0,
        "voice_identity_count": 0,
    })

    def finish(value):
        metrics["total_ms"] = (time.perf_counter() - total_started) * 1000
        return value

    def get_audio_segments(audio_content, dialogs):
        audio_data = base64.b64decode(audio_content)
        audio = AudioSegment.from_wav(io.BytesIO(audio_data))
        audio_segments = []
        for start_time, end_time in dialogs:
            try:
                start_min, start_sec = map(int, start_time.split(':'))
                end_min, end_sec = map(int, end_time.split(':'))
            except ValueError:
                audio_segments.append(None)
                continue
            if ((start_min < 0 or start_sec < 0 or start_sec >= 60)
                    or (end_min < 0 or end_sec < 0 or end_sec >= 60)):
                audio_segments.append(None)
                continue
            start_msec = (start_min * 60 + start_sec) * 1000
            end_msec = (end_min * 60 + end_sec) * 1000
            if start_msec >= end_msec or end_msec > len(audio):
                audio_segments.append(None)
                continue
            segment = audio[start_msec:end_msec]
            with io.BytesIO() as segment_buffer:
                segment.export(segment_buffer, format='wav')
                audio_segments.append(base64.b64encode(segment_buffer.getvalue()))
        return audio_segments

    def diarize_audio(audio_content, filter=None):
        audio_data = base64.b64decode(audio_content)
        providers = processing_config.get(
            "asr_providers", ["deepgram-asr", "openrouter-mai-transcribe-2"]
        )
        if providers != ["deepgram-asr", "openrouter-mai-transcribe-2"]:
            raise RuntimeError(
                "ASR providers must be the mandatory ordered pair: "
                "deepgram-asr, openrouter-mai-transcribe-2"
            )
        provider_results = {}
        errors = []
        asr_started = time.perf_counter()
        for provider in providers:
            provider_started = time.perf_counter()
            try:
                provider_results[provider] = transcribe_audio_with_retry(
                    provider, audio_data, audio_format="wav"
                )
                logger.info("ASR/diarization completed with %s", provider)
            except Exception as exc:
                errors.append(f"{provider}: {type(exc).__name__}: {exc}")
            finally:
                metrics["asr_provider_ms"][provider] = (
                    time.perf_counter() - provider_started
                ) * 1000
        metrics["asr_total_ms"] = (time.perf_counter() - asr_started) * 1000
        if len(provider_results) != len(providers):
            raise RuntimeError(
                "Mandatory ASR/diarization provider failure: " + "; ".join(errors)
            )
        asrs = merge_primary_transcriptions(
            provider_results["deepgram-asr"],
            provider_results["openrouter-mai-transcribe-2"],
        )
        for asr in asrs:
            start_min, start_sec = map(int, asr["start_time"].split(':'))
            end_min, end_sec = map(int, asr["end_time"].split(':'))
            asr["duration"] = end_min * 60 + end_sec - start_min * 60 - start_sec
        return [asr for asr in asrs if filter(asr)]

    def filter_duration_based(audio):
        return audio["duration"] >= processing_config["min_duration_for_audio"]

    def update_videograph(audios):
        id2audios = {}
        for audio in audios:
            audio_info = {
                "embeddings": [audio["embedding"]],
                "contents": [audio["asr"]],
            }
            matched_nodes = video_graph.search_voice_nodes(audio_info)
            if matched_nodes:
                matched_node = matched_nodes[0][0]
                video_graph.update_node(matched_node, audio_info)
            else:
                matched_node = video_graph.add_voice_node(audio_info)
            audio["matched_node"] = matched_node
            id2audios.setdefault(matched_node, []).append(audio)
        return id2audios

    if not base64_audio:
        return finish({})

    try:
        cache_started = time.perf_counter()
        with open(save_path, "r") as handle:
            audios = json.load(handle)
        for audio in audios:
            audio["audio_segment"] = audio["audio_segment"].encode("utf-8")
        metrics["cache_hit"] = True
        metrics["cache_load_ms"] = (time.perf_counter() - cache_started) * 1000
    except Exception:
        metrics["cache_hit"] = False
        asrs = diarize_audio(base64_audio, filter=filter_duration_based)
        metrics["asr_segment_count"] = len(asrs)
        segment_started = time.perf_counter()
        dialogs = [(asr["start_time"], asr["end_time"]) for asr in asrs]
        audio_segments = get_audio_segments(base64_audio, dialogs)
        for asr, audio_segment in zip(asrs, audio_segments):
            asr["audio_segment"] = audio_segment
        audios = [audio for audio in asrs if audio["audio_segment"] is not None]
        metrics["audio_segmentation_ms"] = (
            time.perf_counter() - segment_started
        ) * 1000
        if audios:
            embedding_started = time.perf_counter()
            embeddings = get_audio_embeddings(
                [audio["audio_segment"] for audio in audios]
            )
            normed_embeddings = [normalize_embedding(value) for value in embeddings]
            for audio, embedding in zip(audios, normed_embeddings):
                audio["embedding"] = embedding
            metrics["speech_embedding_ms"] = (
                time.perf_counter() - embedding_started
            ) * 1000
            metrics["speech_embedding_count"] = len(embeddings)
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, "w") as handle:
            for audio in audios:
                audio["audio_segment"] = audio["audio_segment"].decode("utf-8")
            json.dump(audios, handle)
            for audio in audios:
                audio["audio_segment"] = audio["audio_segment"].encode("utf-8")
        logger.info("Write voice detection results to %s", save_path)

    metrics["asr_segment_count"] = len(audios)
    metrics["speech_embedding_count"] = len(audios)
    if "voice" in preprocessing or not audios:
        return finish({})
    graph_started = time.perf_counter()
    id2audios = update_videograph(audios)
    metrics["graph_update_ms"] = (time.perf_counter() - graph_started) * 1000
    metrics["voice_identity_count"] = len(id2audios)
    return finish(id2audios)

if __name__ == "__main__":
    pass
