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
import json
import math
import os
import openai
import httpx
import cloud_http
from concurrent.futures import ThreadPoolExecutor
from time import sleep
import logging

# Configure logging
logger = logging.getLogger(__name__)

# Disable httpx logging
logging.getLogger("httpx").setLevel(logging.CRITICAL)
# Disable urllib3 logging (which httpx uses)
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
# Disable httpcore logging (which httpx uses)
logging.getLogger("httpcore").setLevel(logging.CRITICAL)

# api utils

processing_config = json.load(open("configs/processing_config.json"))
temp = processing_config["temperature"]

config = json.load(open("configs/api_config.json"))
client = {}
client_init_errors = {}

for model_name, model_cfg in config.items():
    if model_cfg.get("provider") == "deepgram":
        continue
    if (model_cfg.get("provider") == "openrouter"
            and model_cfg.get("capability") != "embeddings"):
        continue
    try:
        api_key = os.environ.get(model_cfg.get("api_key_env", "")) or model_cfg.get("api_key")
        azure_endpoint = model_cfg.get("azure_endpoint")
        api_version = model_cfg.get("api_version")
        base_url = model_cfg.get("base_url") or model_cfg.get("openai_base_url")

        if azure_endpoint:
            if not api_version:
                raise ValueError("Missing 'api_version' for Azure client")
            client[model_name] = openai.AzureOpenAI(
                azure_endpoint=azure_endpoint,
                api_version=api_version,
                api_key=api_key,
            )
        else:
            # OpenAI-compatible endpoint (or official OpenAI when base_url is empty)
            if base_url:
                client[model_name] = openai.OpenAI(api_key=api_key, base_url=base_url)
            else:
                client[model_name] = openai.OpenAI(api_key=api_key)
    except Exception as e:
        client_init_errors[model_name] = f"{type(e).__name__}: {e}"
        logger.error(f"Failed to initialize client for model '{model_name}': {e}")

def _get_client_or_raise(model):
    if model in client:
        return client[model]
    available = sorted(client.keys())
    init_err = client_init_errors.get(model)
    msg = (
        f"Model client '{model}' is not initialized. "
        f"Available model clients: {available}."
    )
    if init_err:
        msg += f" Init error for this model: {init_err}"
    raise KeyError(msg)

MAX_RETRIES = 5

def get_response(model, messages, timeout=30):
    if os.environ.get("EGOLIFE_GEMINI_ONLY") == "1" or os.environ.get("EGOLIFE_QWEN_ONLY") == "1":
        raise RuntimeError("Generic chat is forbidden; use audited Gemini runtime")
    """Get chat completion response from specified model.

    Args:
        model (str): Model identifier
        messages (list): List of message dictionaries

    Returns:
        tuple: (response content, total tokens used)
    """
    model_client = _get_client_or_raise(model)
    response = model_client.chat.completions.create(
        model=model, messages=messages, temperature=temp, timeout=timeout, max_tokens=8192
    )
    
    # return answer and number of tokens
    return response.choices[0].message.content, response.usage.total_tokens

def get_response_with_retry(model, messages, timeout=30):
    """Retry get_response up to MAX_RETRIES times with error handling.

    Args:
        model (str): Model identifier
        messages (list): List of message dictionaries

    Returns:
        tuple: (response content, total tokens used)
        
    Raises:
        Exception: If all retries fail
    """
    for i in range(MAX_RETRIES):
        try:
            return get_response(model, messages, timeout)
        except Exception as e:
            sleep(20)
            logger.warning(f"Retry {i} times, exception: {e} from message {messages}")
            continue
    raise Exception(f"Failed to get response after {MAX_RETRIES} retries")

def parallel_get_response(model, messages, timeout=30):
    """Process multiple messages in parallel using ThreadPoolExecutor.
    Messages are processed in batches, with each batch completing before starting the next.

    Args:
        model (str): Model identifier
        messages (list): List of message lists to process

    Returns:
        tuple: (list of responses, total tokens used)
    """
    batch_size = config[model]["qpm"]
    responses = []
    total_tokens = 0

    for i in range(0, len(messages), batch_size):
        batch = messages[i:i + batch_size]
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            batch_responses = list(executor.map(lambda msg: get_response_with_retry(model, msg, timeout), batch))
            
        # Extract answers and tokens from batch responses
        batch_answers = [response[0] for response in batch_responses]
        batch_tokens = [response[1] for response in batch_responses]
        
        responses.extend(batch_answers)
        total_tokens += sum(batch_tokens)

    return responses, total_tokens


def get_embedding(model, text, timeout=15):
    """Get embedding for text using specified model.

    Args:
        model (str): Model identifier
        text (str): Text to embed

    Returns:
        tuple: (embedding vector, total tokens used)
    """
    model_client = _get_client_or_raise(model)
    request_model = config[model].get("model", model)
    response = model_client.embeddings.create(
        input=text, model=request_model, timeout=timeout
    )
    return response.data[0].embedding, response.usage.total_tokens


def get_embeddings_batch(model, texts, timeout=120, metrics=None):
    return cloud_http.embed_batch(_get_client_or_raise(model), config[model].get('model',model),
        texts, timeout=timeout, attempts=int(os.environ.get('EGOLIFE_EMBEDDING_MAX_ATTEMPTS','2')),metrics=metrics)


def get_embedding_with_retry(model, text, timeout=15):
    attempts = int(os.environ.get('EGOLIFE_EMBEDDING_MAX_ATTEMPTS', '2')) if os.environ.get('EGOLIFE_RESULTS') else MAX_RETRIES
    last_exception = None
    for i in range(attempts):
        try:
            return get_embedding(model, text, timeout)
        except Exception as exc:
            last_exception = exc
            logger.warning("Embedding attempt %d/%d failed: %s", i + 1, attempts, exc)
            if i + 1 < attempts:
                sleep(min(2 ** (i + 1), 10) if os.environ.get('EGOLIFE_RESULTS') else 20)
    raise RuntimeError(
        f"Failed to get embedding after {attempts} retries for model '{model}'. "
        f"Last error: {type(last_exception).__name__}: {last_exception}"
    ) from last_exception


def parallel_get_embedding(model, texts, timeout=15):
    """Process multiple texts in parallel to get embeddings.

    Args:
        model (str): Model identifier
        texts (list): List of texts to embed

    Returns:
        tuple: (list of embeddings, total tokens used)
    """
    batch_size = config[model]["qpm"]
    embeddings = []
    total_tokens = 0
    
    # Process texts in batches
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        max_workers = len(batch)
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(lambda x: get_embedding_with_retry(model, x, timeout), batch))
            
        # Split batch results into embeddings and tokens
        batch_embeddings = [result[0] for result in results]
        batch_tokens = [result[1] for result in results]
        
        embeddings.extend(batch_embeddings)
        total_tokens += sum(batch_tokens)
        
    return embeddings, total_tokens

def _api_key(model):
    model_config = config[model]
    api_key = os.environ.get(model_config.get("api_key_env", "")) or model_config.get("api_key")
    if not api_key:
        raise ValueError(
            f"Missing API key for '{model}'. Set {model_config.get('api_key_env')} "
            "or configure api_key in configs/api_config.json."
        )
    return api_key


def _audio_content_type(audio_format):
    return {
        "mp3": "audio/mpeg",
        "m4a": "audio/mp4",
    }.get(audio_format, f"audio/{audio_format}")


def _timestamp(seconds, round_up=False):
    seconds = max(0, float(seconds or 0))
    total_seconds = math.ceil(seconds) if round_up else math.floor(seconds)
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def _segments_from_words(words):
    segments = []
    current = None
    for word in words or []:
        text = word.get("punctuated_word") or word.get("word") or word.get("text") or ""
        text = text.strip()
        if not text:
            continue
        speaker = word.get("speaker")
        start = float(word.get("start", 0))
        end = float(word.get("end", start))
        if current is None or (speaker is not None and speaker != current["speaker"]):
            if current is not None:
                segments.append(current)
            current = {"speaker": speaker, "start": start, "end": end, "words": [text]}
        else:
            current["end"] = end
            current["words"].append(text)
    if current is not None:
        segments.append(current)
    return [
        {
            "start_time": _timestamp(segment["start"]),
            "end_time": _timestamp(segment["end"], round_up=True),
            "asr": " ".join(segment["words"]),
            "speaker": segment["speaker"],
        }
        for segment in segments
    ]


def _normalize_transcription(response):
    utterances = response.get("results", {}).get("utterances", [])
    if utterances:
        return [
            {
                "start_time": _timestamp(item.get("start")),
                "end_time": _timestamp(item.get("end"), round_up=True),
                "asr": (item.get("transcript") or item.get("text") or "").strip(),
                "speaker": item.get("speaker"),
            }
            for item in utterances
            if (item.get("transcript") or item.get("text") or "").strip()
        ]

    segments = response.get("segments", [])
    if segments:
        return [
            {
                "start_time": _timestamp(item.get("start")),
                "end_time": _timestamp(item.get("end"), round_up=True),
                "asr": (item.get("text") or item.get("transcript") or "").strip(),
                "speaker": item.get("speaker"),
            }
            for item in segments
            if (item.get("text") or item.get("transcript") or "").strip()
        ]

    words = response.get("words", [])
    if not words:
        channels = response.get("results", {}).get("channels", [])
        if channels:
            alternatives = channels[0].get("alternatives", [])
            if alternatives:
                words = alternatives[0].get("words", [])
    word_segments = _segments_from_words(words)
    if word_segments:
        return word_segments

    text = (response.get("text") or "").strip()
    if text:
        duration = response.get("duration") or response.get("usage", {}).get("seconds") or 0
        return [{"start_time": "00:00", "end_time": _timestamp(duration, round_up=True), "asr": text}]
    return []


def _seconds(timestamp):
    minutes, seconds = timestamp.split(":", 1)
    return int(minutes) * 60 + int(seconds)


def merge_primary_transcriptions(deepgram_segments, mai_segments):
    """Fuse both primary transcripts while preferring MAI diarization boundaries."""
    if not deepgram_segments and not mai_segments:
        return []
    if not mai_segments:
        return [dict(segment, asr_sources=["deepgram-asr", "openrouter-mai-transcribe-2"]) for segment in deepgram_segments]

    merged = []
    used_deepgram = set()
    for mai in mai_segments:
        mai_start = _seconds(mai["start_time"])
        mai_end = _seconds(mai["end_time"])
        overlapping = []
        for index, deepgram in enumerate(deepgram_segments):
            dg_start = _seconds(deepgram["start_time"])
            dg_end = _seconds(deepgram["end_time"])
            if min(mai_end, dg_end) > max(mai_start, dg_start):
                overlapping.append(deepgram["asr"])
                used_deepgram.add(index)
        dg_text = " ".join(overlapping).strip()
        mai_text = mai["asr"].strip()
        parts = []
        if dg_text:
            parts.append(f"Deepgram: {dg_text}")
        if mai_text:
            parts.append(f"MAI: {mai_text}")
        if parts:
            merged.append(
                {
                    "start_time": mai["start_time"],
                    "end_time": mai["end_time"],
                    "asr": " | ".join(parts),
                    "speaker": mai.get("speaker"),
                    "asr_sources": ["deepgram-asr", "openrouter-mai-transcribe-2"],
                }
            )
    for index, deepgram in enumerate(deepgram_segments):
        if index not in used_deepgram:
            merged.append(dict(deepgram, asr=f"Deepgram: {deepgram['asr']}", asr_sources=["deepgram-asr", "openrouter-mai-transcribe-2"]))
    merged.sort(key=lambda segment: _seconds(segment["start_time"]))
    return merged
def transcribe_audio(model, audio_data, audio_format="wav", timeout=180):
    """Return timestamped diarized segments from a configured ASR provider."""
    model_config = config[model]
    provider = model_config.get("provider")
    base_url = model_config["base_url"].rstrip("/")

    if provider == "deepgram":
        params = {
            "model": model_config.get("model", "nova-3"),
            "smart_format": "true",
            "utterances": "true",
            "language": model_config.get("language", "multi"),
            "diarize_model": model_config.get("diarize_model", "latest"),
        }
        response = cloud_http.post(
            f"{base_url}/v1/listen",
            params=params,
            headers={
                "Authorization": f"Token {_api_key(model)}",
                "Content-Type": _audio_content_type(audio_format),
            },
            content=audio_data,
            timeout=timeout,
        )
    elif provider == "openrouter":
        payload = {
            "model": model_config.get("model", "microsoft/mai-transcribe-2"),
            "input_audio": {"data": base64.b64encode(audio_data).decode("ascii"), "format": audio_format},
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
            "provider": {
                "only": [model_config.get("upstream_provider", "azure")],
                "options": {"azure": {"diarization": {"enabled": True}}},
            },
        }
        response = cloud_http.post(
            f"{base_url}/audio/transcriptions",
            headers={
                "Authorization": f"Bearer {_api_key(model)}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Celina-love-sweet/StreamMeCo",
                "X-Title": "StreamMeCo",
            },
            json=payload,
            timeout=timeout,
        )
    else:
        raise ValueError(f"Unsupported transcription provider for '{model}': {provider}")

    if response.is_error:
        from .asr_resilience import ASRHTTPError
        raise ASRHTTPError(provider, response.status_code, response.text, response.headers.get("Retry-After"))
    return _normalize_transcription(response.json())


def transcribe_audio_with_retry(model, audio_data, audio_format="wav", timeout=180, context=None):
    from .asr_resilience import transcribe_resilient
    root = os.environ.get("EGOLIFE_RESULTS")
    return transcribe_resilient(
        model, audio_data, audio_format, config[model],
        lambda: transcribe_audio(model, audio_data, audio_format=audio_format, timeout=timeout),
        retries=int(os.environ.get("EGOLIFE_ASR_MAX_ATTEMPTS", "2")) if root else config[model].get("retries", 2), root=root, context=context,
    )


def parallel_transcribe_audio_files(model, file_paths):
    def transcribe_file(path):
        with open(path, "rb") as audio_file:
            audio_data = audio_file.read()
        return transcribe_audio_with_retry(
            model,
            audio_data,
            audio_format=os.path.splitext(path)[1].lstrip(".").lower(),
        )

    batch_size = config[model]["qpm"]
    responses = []
    for i in range(0, len(file_paths), batch_size):
        batch = file_paths[i:i + batch_size]
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            batch_responses = list(executor.map(transcribe_file, batch))
        responses.extend(batch_responses)
    return responses

def generate_messages(inputs):
    """Generate message list for chat completion from mixed inputs.

    Args:
        inputs (list): List of input dictionaries with 'type' and 'content' keys
        type can be:
            "text" - text content
            "image/jpeg", "image/png" - base64 encoded images
            "video/mp4", "video/webm" - base64 encoded videos
            "video_url" - video URL
            "audio/mp3", "audio/wav" - base64 encoded audio
        content should be a string for text,
        a list of base64 encoded media for images/video/audio,
        or a string (url) for video_url
        inputs are like: 
        [
            {
                "type": "video_base64/mp4",
                "content": <base64>
            },
            {
                "type": "text",
                "content": "Describe the video content."
            },
            ...
        ]

    Returns:
        list: Formatted messages for chat completion
    """
    messages = []
    messages.append(
        {"role": "system", "content": "You are an expert in video understanding."}
    )
    content = []
    for input in inputs:
        if not input["content"]:
            logger.warning("empty content, skip")
            continue
        if input["type"] == "text":
            content.append({"type": "text", "text": input["content"]})
        elif input["type"] in ["images/jpeg", "images/png"]:
            img_format = input["type"].split("/")[1]
            if isinstance(input["content"][0], str):
                content.extend(
                    [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{img_format};base64,{img}",
                                "detail": "high",
                            },
                        }
                        for img in input["content"]
                    ]
                )
            else:
                for img in input["content"]:
                    content.append({
                        "type": "text",
                        "text": img[0],
                    })
                    content.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/{img_format};base64,{img[1]}",
                            "detail": "high",
                        },
                    })
        elif input["type"] == "video_url":
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": input["content"]},
                }
            )
        elif input["type"] in ["video_base64/mp4", "video_base64/webm"]:
            video_format = input["type"].split("/")[1]
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:video/{video_format};base64,{input['content']}"},
                }
            )
        elif input["type"] in ["audio_base64/mp3", "audio_base64/wav"]:
            audio_format = input["type"].split("/")[1]
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:audio/{audio_format};base64,{input['content']}"
                    },
                }
            )
        else:
            raise ValueError(f"Invalid input type: {input['type']}")
    messages.append({"role": "user", "content": content})
    return messages

def print_messages(messages):
    for message in messages:
        if message["role"] == "user":
            for item in message["content"]:
                if item["type"] == "text":
                    logger.debug(item['text'])
