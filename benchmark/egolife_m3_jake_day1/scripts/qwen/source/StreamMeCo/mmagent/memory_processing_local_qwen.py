"""Qwen-only memory generation, retaining the existing M3 graph update code."""
import time
from benchmarks import qwen_runtime as runtime
from .memory_processing_qwen import generate_video_context, process_memories, _normalize_memory
from .utils.chat_gemini import generate_messages
from .prompts import prompt_generate_memory_with_ids_sft
from .qwen_memory_prompt import IDENTITY_SYSTEM_PROMPT

def generate_memories(base64_frames, faces_list, voices_list, video_path, model_type='sft', metrics=None):
    metrics = metrics if metrics is not None else {}
    started = time.perf_counter()
    context = generate_video_context(base64_frames, faces_list, voices_list, video_path)
    messages, media = generate_messages([{'type':'text','content':prompt_generate_memory_with_ids_sft + '\nReturn one complete JSON object with video_description and high_level_conclusions arrays. Be concise and avoid duplicate events.'}] + context, fps=float(__import__('os').environ.get('QWEN_VLM_FPS','2')))
    messages.insert(0, {'role':'system', 'content':IDENTITY_SYSTEM_PROMPT})
    metrics['identity_system_prompt'] = IDENTITY_SYSTEM_PROMPT
    metrics['supplied_voice_ids'] = [f'<voice_{i}>' for i,v in voices_list.items() if v]
    metrics['context_preparation_ms'] = (time.perf_counter()-started)*1000
    event = runtime.call(messages, 'memory_construction', media=media)
    memory = _normalize_memory(event['response'])
    metrics.update(vlm_ms=event['latency_ms'], raw_response=event['response'], valid_memory_json=True,
                   generated_memory=memory, media=media, attempts=[event],
                   episodic_memory_count=len(memory['video_description']),
                   semantic_memory_count=len(memory['high_level_conclusions']))
    return memory['video_description'], memory['high_level_conclusions']
