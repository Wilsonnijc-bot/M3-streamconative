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
import json
import logging
import os
import re
import torch
from transformers import AutoModelForMultimodalLM, AutoProcessor

# Configure logging
logger = logging.getLogger(__name__)

processing_config = json.load(open("configs/processing_config.json"))
temp = processing_config["temperature"]
MAX_RETRIES = processing_config["max_retries"]
processor, model = None, None

def strip_thinking(response):
    """Remove Qwen's private reasoning block before downstream parsing."""
    if "</think>" in response:
        response = response.rsplit("</think>", 1)[1]
    return re.sub(r"^\s*<think>.*?</think>\s*", "", response, flags=re.DOTALL).strip()


def get_response(messages, enable_thinking=None, max_new_tokens=None, return_details=False):
    """Generate one local Qwen 3.5 multimodal response on the GPU."""
    if os.environ.get("EGOLIFE_GEMINI_ONLY") == "1":
        raise RuntimeError("Local Qwen is forbidden in this Gemini-only experiment")
    global model, processor
    if enable_thinking is None:
        enable_thinking = processing_config.get("qwen_enable_thinking", True)
    if model is None:
        model_path = os.environ.get(
            "QWEN_MODEL_PATH",
            processing_config.get("qwen_model_path", processing_config["ckpt"]),
        )
        model = AutoModelForMultimodalLM.from_pretrained(
            model_path,
            torch_dtype="auto",
            device_map="auto",
            attn_implementation=os.environ.get("QWEN_ATTN_IMPLEMENTATION", "sdpa"),
        )
        model.eval()
        processor = AutoProcessor.from_pretrained(model_path)

    inputs = processor.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=enable_thinking,
        processor_kwargs={
            "videos_kwargs": {
                "cap_pixels_per_frame": processing_config.get(
                    "qwen_cap_pixels_per_frame", True
                )
            }
        },
        return_dict=True,
        return_tensors="pt",
    )
    inputs = inputs.to(model.device)

    with torch.no_grad():
        configured_max_tokens = (
            processing_config.get("qwen_thinking_max_new_tokens", 1536)
            if enable_thinking
            else processing_config.get("qwen_max_new_tokens", 512)
        )
        generation_kwargs = {
            "max_new_tokens": int(
                os.environ.get(
                    "QWEN_MAX_NEW_TOKENS",
                    max_new_tokens or configured_max_tokens,
                )
            ),
            "do_sample": temp > 1e-5,
        }
        if generation_kwargs["do_sample"]:
            generation_kwargs["temperature"] = temp
        generation = model.generate(**inputs, **generation_kwargs)
        generate_ids = generation[:, inputs.input_ids.size(1):]
        response = processor.batch_decode(
            generate_ids,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )[0]
        output_token_count = generate_ids.shape[1]
        token_count = len(generation[0])
    raw_response = response
    response = strip_thinking(raw_response)
    details = {
        "raw_response": raw_response, "response": response,
        "output_tokens": output_token_count,
        "max_new_tokens": generation_kwargs["max_new_tokens"],
        "hit_max_new_tokens": output_token_count >= generation_kwargs["max_new_tokens"],
        "thinking_started": "<think>" in raw_response,
        "thinking_completed": "</think>" in raw_response,
    }

    del generation
    del generate_ids
    del inputs
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    if return_details:
        return response, token_count, details
    return response, token_count
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
                            "type": "image",
                            "image": f"data:image;base64,{img}",
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
                        "type": "image",
                        "image": f"data:image;base64,{img[1]}"
                    })
        elif input["type"] in ["video_url", "video_base64/mp4", "video_base64/webm"]:
            content.append(
                {
                    "type": "video",
                    "video": input["content"],
                    "fps": processing_config.get("qwen_video_fps", 2),
                    "max_pixels": processing_config.get(
                        "qwen_video_max_pixels", 151200
                    ),
                }
            )
        else:
            raise ValueError(f"Invalid input type: {input['type']}")
    messages.append({"role": "user", "content": content})
    return messages