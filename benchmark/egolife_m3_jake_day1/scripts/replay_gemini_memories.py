"""Export saved, cumulative Gemini graphs at elapsed source-video cutoffs."""
import hashlib
import json
from collections import Counter

from render_results import ROOT, graph_markdown, link, table, write, saved_graph


def clock(seconds):
    centiseconds = round(seconds * 100)
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, fraction = divmod(remainder, 100)
    return f"{hours:02}:{minutes:02}:{secs:02}.{fraction:02}"


def main():
    raw = ROOT / 'provenance/raw/gemini/results'
    out = ROOT / 'results/gemini/replays'
    metadata_path = raw / 'memory/q10_uncompressed/metadata.json'
    segments = json.loads(metadata_path.read_text())['source_segments']
    origin = segments[0]['absolute_start_seconds']
    records, rows = [], []
    for minutes in (20, 40, 60):
        cutoff = origin + minutes * 60
        eligible = [s for s in segments if s['absolute_end_seconds'] <= cutoff]
        selected = eligible[-1]
        segment_id = selected['segment_id']
        source = raw / f'clip_audits/clip_{segment_id}_graph.json'
        audit = json.loads((raw / f'clip_audits/clip_{segment_id}_audit.json').read_text())
        graph, source = saved_graph(source)
        assert len(graph['nodes']) == audit['counts']['nodes_after_clip']
        assert all(n.get('metadata', {}).get('timestamp', 0) <= segment_id
                   for n in graph['nodes'])
        counts = Counter(n['type'] for n in graph['nodes'])
        end = selected['absolute_end_seconds']
        filename = f'memories_{minutes:02}min.md'
        skipped = [s['segment_id'] for s in eligible if s.get('status') == 'skipped']
        degraded = [s['segment_id'] for s in eligible if s.get('asr_failures')]
        text = [
            f'# Gemini — cumulative memory at {minutes} minutes', '',
            f'Elapsed time is measured on the source-video clock from DAY1 {clock(origin)}, '
            'not model execution time.', '',
            f'Requested cutoff: **DAY1 {clock(cutoff)}**. Latest completed segment: '
            f'**{segment_id}**, ending at **DAY1 {clock(end)}** '
            f'(**{clock(end-origin)} elapsed**).', '',
            f'The cutoff falls within the next segment. This replay uses the last saved '
            f'committed graph before the cutoff, leaving **{cutoff-end:.2f} seconds** '
            'of the in-progress segment unrepresented.', '',
            'This is the complete cumulative uncompressed graph at that checkpoint, '
            'including voice transcripts as they existed then. It is rendered directly '
            'from the historical graph, not filtered from the final graph. No model was rerun.', '',
            'Embedding arrays and encoded media are omitted. Semantic memories are '
            'model inferences, not independently verified facts.', '',
            f'Skipped segments through this checkpoint: {skipped or "none"}. '
            f'ASR-degraded segments: {degraded or "none"}.', '',
            table(['Events', 'Semantic memories', 'Voice identities', 'Face identities'],
                  [[counts['episodic'], counts['semantic'], counts['voice'], counts['img']]]), '',
            'Source: ' + link(source, out, 'exact saved graph') + '. '
            + link(out / 'README.md', out, 'All replay checkpoints') + '.', '',
        ]
        text += graph_markdown(graph, f'Committed memory — segment {segment_id}', source, out / filename)
        rendered = '\n'.join(text)
        assert rendered.count('<a id=') == len(graph['nodes'])
        write(out / filename, rendered)
        rows.append([link(out / filename, out, f'{minutes} minutes'),
                     clock(end-origin), segment_id, len(graph['nodes']),
                     counts['voice'], counts['img']])
        records.append(dict(minutes=minutes, cutoff_seconds=cutoff,
                            checkpoint_end_seconds=end, segment_id=segment_id,
                            source_graph=str(source.relative_to(ROOT)),
                            source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                            markdown=str((out / filename).relative_to(ROOT)),
                            node_counts=dict(counts)))
    manifest = ROOT / 'provenance/replays/gemini.json'
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(dict(
        origin_seconds=origin, selection='latest completed segment at or before source-clock cutoff',
        source_metadata=str(metadata_path.relative_to(ROOT)), checkpoints=records), indent=2) + '\n')
    write(out / 'README.md', '\n'.join([
        '# Gemini — memory replays', '',
        f'Cumulative constructed memories at 20, 40 and 60 minutes after DAY1 {clock(origin)}. '
        'These are historical saved graphs, including historical voice-node contents.', '',
        'Each checkpoint ends 12.08 seconds before the requested cutoff because '
        'memory is committed by segment. The segment crossing the cutoff is excluded.', '',
        table(['Replay', 'Actual elapsed coverage', 'Last segment', 'Total nodes',
               'Voice identities', 'Face identities'], rows), '',
        link(manifest, out, 'Selection provenance and source hashes') + '.', '',
        'Regenerate with `python3 scripts/replay_gemini_memories.py` from the experiment folder.',
    ]))
    print(table(['Replay', 'Coverage', 'Segment', 'Nodes', 'Voices', 'Faces'], rows))


if __name__ == '__main__':
    main()
