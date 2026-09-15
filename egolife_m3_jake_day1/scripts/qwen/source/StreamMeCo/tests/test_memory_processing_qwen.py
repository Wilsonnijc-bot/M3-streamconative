import pytest

from mmagent.memory_processing_qwen import (
    _normalize_memory,
    _recover_memory_from_prose,
)


def test_normalize_memory_accepts_json_after_reasoning():
    response = """analysis first
</think>
{\"video_description\": [\"Jake opens the door.\"],
 \"high_level_conclusions\": [\"Jake is entering the room.\"]}
"""
    assert _normalize_memory(response) == {
        "video_description": ["Jake opens the door."],
        "high_level_conclusions": ["Jake is entering the room."],
    }


def test_recover_memory_from_explicit_prose_sections():
    response = """
**Video Description:**
- Jake walks into the kitchen.
- He places a cup on the counter.

**High-Level Conclusions:**
- Jake intends to prepare a drink.
"""
    assert _recover_memory_from_prose(response) == {
        "video_description": [
            "Jake walks into the kitchen.",
            "He places a cup on the counter.",
        ],
        "high_level_conclusions": ["Jake intends to prepare a drink."],
    }


def test_recover_memory_requires_both_sections():
    with pytest.raises(ValueError, match="both required memory sections"):
        _recover_memory_from_prose("Video Description:\n- Jake walks inside.")
