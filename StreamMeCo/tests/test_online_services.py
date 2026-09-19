import base64
import json
from types import SimpleNamespace

from mmagent import asr_cache
from mmagent.asr_cache import PreparedASRCache
from mmagent.consolidation_evidence import export_consolidation_evidence


def test_prepared_asr_cache_calls_provider_once(tmp_path, monkeypatch):
    calls = []

    def run(provider, request):
        calls.append(provider)
        return (
            {
                provider: [
                    {
                        "start_time": "00:00",
                        "end_time": "00:02",
                        "asr": "hello",
                        "asr_provider": provider,
                        "asr_sources": [provider],
                    }
                ]
            },
            [],
            {provider: 12.0},
            12.0,
        )

    monkeypatch.setattr(asr_cache, "run_selected_asr", run)
    cache = PreparedASRCache(
        tmp_path / "asr",
        "test-asr",
        {"provider": "deepgram", "model": "test", "api_key": "excluded"},
        display_root=tmp_path,
    )
    audio = base64.b64encode(b"audio")
    first, first_context = cache.get(audio)
    second, second_context = cache.get(audio)
    assert len(calls) == 1
    assert first_context["cache_hit"] is False
    assert second_context["cache_hit"] is True
    assert second[0] == first[0]
    assert second[2] == {"test-asr": None}
    assert "excluded" not in next((tmp_path / "asr").glob("*.json")).name


def test_evidence_export_uses_recorded_provider_and_mapper(tmp_path):
    directory = tmp_path / "method"
    audit_dir = directory / "audits"
    audit_dir.mkdir(parents=True)
    audit = {
        "voice_observations": [
            {
                "voice_node_id": 4,
                "source_row_index": 0,
                "start_time": "00:00",
                "end_time": "00:02",
                "asr": "hello",
                "asr_provider": "custom-asr",
                "assignment_scores": {
                    "method": "TST",
                    "method_id": "ecapa",
                    "candidates": [],
                    "threshold": 0.6,
                    "created_new_identity": True,
                },
            }
        ]
    }
    (audit_dir / "clip_1_audit.json").write_text(json.dumps(audit))
    graph = SimpleNamespace(
        nodes={}, edges={}, segment_times={1: (0.0, 2.0)}, asr_provider="custom-asr"
    )
    snapshot = SimpleNamespace(
        graph=graph, cutoff_clip_id=1, cutoff_timestamp=2.0, graph_version="v1"
    )
    plan = [
        {
            "clip_id": 1,
            "start_s": 0.0,
            "end_s": 2.0,
            "gap": None,
            "source": {
                "path": "/recording.wav",
                "start_s": 0.0,
                "source_offset_s": 0.0,
            },
        }
    ]
    exported = export_consolidation_evidence(snapshot, directory, "session", plan)
    observation = exported["replay"]["observations"][0]
    assert observation["transcripts"] == {"custom-asr": "hello"}
    assert "clip_1_voices.tst.json" in observation["audio_ref"]
    assignment = json.loads(exported["assignment_jsonl"].read_text().strip())
    assert assignment["method"] == "TST"
    assert assignment["decision"] == "new_voice"
