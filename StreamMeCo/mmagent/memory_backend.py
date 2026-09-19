"""Select the native memory-construction implementation explicitly."""
import os

if os.environ.get('M3_MEMORY_BACKEND')=='terra':
    from .memory_processing_terra import generate_memories, process_memories
elif os.environ.get('EGOLIFE_GEMINI_ONLY')=='1':
    from .memory_processing_gemini import generate_memories, process_memories
else:
    from .memory_processing_qwen import generate_memories, process_memories
