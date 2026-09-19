"""Export a committed M3 prefix for the consolidation service."""

import json
from pathlib import Path



def _seconds(timestamp):
    minutes, seconds = map(float, timestamp.split(":"))
    return minutes * 60 + seconds


def _write_jsonl(path, records):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    )
    temporary.replace(path)


def export_consolidation_evidence(snapshot, directory, session, plan):
    from .clip_audit import graph_view

    directory = Path(directory)
    observations = []
    segments = []
    gaps = []
    assignments = []
    for event in plan:
        if event["clip_id"] > snapshot.cutoff_clip_id:
            break
        clip_id = event["clip_id"]
        source = event.get("source")
        segments.append(
            {
                "segment_id": clip_id,
                "absolute_start_seconds": event["start_s"],
                "absolute_end_seconds": event["end_s"],
                "gap": event["gap"],
                "source": source["path"] if source else None,
                "start_seconds_in_source": (
                    event["start_s"]
                    - source["start_s"]
                    + source.get("source_offset_s", 0)
                    if source
                    else 0
                ),
            }
        )
        if event["gap"]:
            gaps.append(
                {
                    "clip_id": clip_id,
                    "reason": event["gap"],
                    "start_s": event["start_s"],
                    "end_s": event["end_s"],
                }
            )
            continue
        audit_path = directory / "audits" / f"clip_{clip_id}_audit.json"
        audit = json.loads(audit_path.read_text())
        for row in audit["voice_observations"]:
            start = round(event["start_s"] + _seconds(row["start_time"]), 6)
            end = round(event["start_s"] + _seconds(row["end_time"]), 6)
            if end > event["end_s"] + 1e-6 or end <= start:
                raise ValueError("ASR observation exceeds committed interval")
            utterance_id = (
                f'{session}/utt_{clip_id:06d}_{row["source_row_index"]:04d}'
            )
            mapping = row.get("assignment_scores")
            if mapping is None:
                raise ValueError("voice audit lacks recorded pre-mutation scores")
            threshold = mapping["threshold"]
            candidates = mapping.get("candidates")
            if candidates is None:
                candidates = [
                    {
                        "candidate_id": candidate_id,
                        "score": score,
                        "eligible": score >= threshold,
                        "rejection_reason": (
                            None if score >= threshold else "below_threshold"
                        ),
                    }
                    for candidate_id, score in mapping["candidate_scores"].items()
                ]
            method = mapping.get("method", "TST")
            created = mapping["created_new_identity"]
            assignments.append(
                {
                    "evidence_id": "assignment/" + utterance_id,
                    "kind": "historical_assignment",
                    "session_id": session,
                    "utterance_id": utterance_id,
                    "available_at": end,
                    "method": method,
                    "candidates": candidates,
                    "threshold": threshold,
                    "selected_candidate": (
                        None if created else f'voice_{row["voice_node_id"]}'
                    ),
                    "decision": "new_voice" if created else "match",
                    "score_origin": "historical_pre_mutation",
                    "model_version": mapping.get("method_id", method),
                    "source_audit": str(audit_path),
                }
            )
            provider = row.get("asr_provider") or getattr(
                snapshot.graph, "asr_provider", "asr"
            )
            suffix = ".tst.json" if method == "TST" else ".json"
            observations.append(
                {
                    "utterance_id": utterance_id,
                    "session_id": session,
                    "clip_id": clip_id,
                    "start_time": start,
                    "end_time": end,
                    "original_voice_id": f'voice_{row["voice_node_id"]}',
                    "transcripts": {provider: row["asr"]},
                    "original_transcript": row["asr"],
                    "audio_ref": str(
                        directory / "intermediate" / f"clip_{clip_id}_voices{suffix}"
                    )
                    + f'#/rows/{row["source_row_index"]}/audio_segment',
                    "assignment_run_id": f"{session}/online/clip_{clip_id}",
                    "created_graph_version": f"online_{clip_id}",
                    "original_assignment_evidence": {
                        "kind": "online_committed_voice_mapping",
                        "source_graph": str(directory / "checkpoint.pkl"),
                    },
                }
            )
    memories = []
    for node in snapshot.graph.nodes.values():
        if node.type not in ("episodic", "semantic"):
            continue
        clip_id = node.metadata["timestamp"]
        available_at = snapshot.graph.segment_times[clip_id][1]
        if available_at > snapshot.cutoff_timestamp:
            raise ValueError("future memory")
        memories.append(
            {
                "memory_node_id": str(node.id),
                "kind": node.type,
                "clip_id": clip_id,
                "available_at": available_at,
                "raw_text": "\n".join(node.metadata["contents"]),
                "raw_contents": list(node.metadata["contents"]),
                "epistemic_status": (
                    "model-generated semantic claim"
                    if node.type == "semantic"
                    else "model-generated event"
                ),
            }
        )
    assignment_path = (
        directory / "consolidation" / f"assignments_{snapshot.graph_version}.jsonl"
    )
    _write_jsonl(assignment_path, assignments)
    return {
        "assignment_jsonl": assignment_path,
        "replay": {
            "session_id": session,
            "source_graph_version": "online_" + str(snapshot.graph_version),
            "observations": observations,
            "memories": memories,
            "current_cutoff": snapshot.cutoff_timestamp,
            "graph": graph_view(snapshot.graph),
            "source_gaps": gaps,
            "segments": segments,
            "origin_seconds": 0,
            "source_root": str(directory),
        },
    }
