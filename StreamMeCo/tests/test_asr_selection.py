import hashlib
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "asr_selection", Path(__file__).parents[1] / "mmagent/utils/asr_selection.py"
)
selection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(selection)


@pytest.fixture
def providers():
    return {
        "deepgram-asr": {"provider": "deepgram", "model": "nova-3", "base_url": "https://deepgram"},
        "mai-asr": {"provider": "openrouter", "model": "mai", "base_url": "https://openrouter"},
        "other-asr": {"provider": "openrouter", "model": "other", "base_url": "https://openrouter"},
        "embedding": {"provider": "openrouter", "capability": "embeddings", "model": "text", "base_url": "https://openrouter"},
    }


@pytest.mark.parametrize("name", ["deepgram-asr", "mai-asr", "other-asr"])
def test_selects_exactly_one_configured_transcription_adapter(providers, name):
    assert selection.selected_asr_provider({"asr_provider": name}, providers) == name


@pytest.mark.parametrize(
    "settings",
    [
        {},
        {"asr_provider": ["deepgram-asr", "mai-asr"]},
        {"asr_provider": "mai-asr", "asr_providers": ["deepgram-asr"]},
        {"asr_provider": "embedding"},
        {"asr_provider": "unknown"},
    ],
)
def test_rejects_ambiguous_or_non_asr_configuration(providers, settings):
    with pytest.raises(ValueError):
        selection.selected_asr_provider(settings, providers)


def test_invokes_only_selected_provider_and_preserves_its_segments():
    calls = []
    original = [{"asr": "hello", "speaker": 3}]

    def request(name):
        calls.append(name)
        return original

    results, errors, times, total = selection.run_selected_asr("mai-asr", request)
    assert calls == ["mai-asr"]
    assert not errors and set(times) == {"mai-asr"} and total >= 0
    assert selection.selected_segments("mai-asr", results) == [
        {"asr": "hello", "speaker": 3, "asr_provider": "mai-asr", "asr_sources": ["mai-asr"]}
    ]
    assert "asr_sources" not in original[0]
    with pytest.raises(ValueError, match="selected provider"):
        selection.selected_segments("deepgram-asr", results)
    with pytest.raises(ValueError, match="fused sources"):
        selection.selected_segments("mai-asr", {"mai-asr": [
            {"asr": "mixed", "asr_sources": ["deepgram-asr", "mai-asr"]}
        ]})


def test_selected_provider_failure_never_uses_another_provider():
    calls = []

    def request(name):
        calls.append(name)
        raise RuntimeError("offline")

    results, errors, timings, _ = selection.run_selected_asr("mai-asr", request)
    assert calls == ["mai-asr"]
    assert results == {} and "offline" in errors[0] and set(timings) == {"mai-asr"}


def test_voice_cache_binds_provider_audio_and_single_source(tmp_path):
    path = tmp_path / "clip_1_voices.json"
    audio = b"recording"
    rows = [{"asr": "hello", "asr_provider": "mai-asr", "asr_sources": ["mai-asr"], "audio_segment": "YQ=="}]
    path.write_text(json.dumps(rows))
    assert selection.cached_voice_segments(path, "mai-asr", audio) is None
    meta = {"asr_provider": "mai-asr", "audio_sha256": hashlib.sha256(audio).hexdigest()}
    (tmp_path / "clip_1_voices.json.provider.json").write_text(json.dumps(meta))
    assert selection.cached_voice_segments(path, "mai-asr", audio) == rows
    assert selection.cached_voice_segments(path, "deepgram-asr", audio) is None
    assert selection.cached_voice_segments(path, "mai-asr", b"other") is None
    rows[0]["asr_sources"].append("deepgram-asr")
    path.write_text(json.dumps(rows))
    assert selection.cached_voice_segments(path, "mai-asr", audio) is None
    path.write_text("[]")
    assert selection.cached_voice_segments(path, "mai-asr", audio) == []
