"""Validate reusable native publication using a saved accepted consolidation run."""
import argparse
from copy import deepcopy
import hashlib
from html import escape
from pathlib import Path

from .common import read, write, digest
from .native import load_graph, publish_native, m3_module


def vector_hash(node):
    return digest(node.embeddings)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-graph', required=True)
    parser.add_argument('--accepted-version', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--verify-existing', action='store_true', help='verify CURRENT without re-embedding')
    args = parser.parse_args()
    output, accepted = Path(args.output), Path(args.accepted_version)
    for name, expected in read(accepted/'manifest.json')['sha256'].items():
        if Path(name).name != name or hashlib.sha256((accepted/name).read_bytes()).hexdigest() != expected:
            raise ValueError('saved consolidation manifest does not match')
    state, packet, patch, execution = [read(accepted/(name+'.json')) for name in ('state','evidence','patch','execution')]
    if state['decision_history'][-1]['accepted'] != execution['accepted']:
        raise ValueError('saved state does not match accepted decisions')
    original = load_graph(args.source_graph)
    raw = {str(n.id): deepcopy(n.metadata['contents']) for n in original.nodes.values()}
    hashes = {str(n.id): vector_hash(n) for n in original.nodes.values()}
    for memory in packet['memories']:
        if '\n'.join(raw[memory['memory_node_id']]) != memory['raw_text']:
            raise ValueError('native source differs from reviewed source text')
    replay = dict(session_id=packet['session_id'])
    if args.verify_existing:
        from .pipeline import session_directory
        directory = session_directory(output/'published', packet['session_id'])
        destination = directory/'versions'/read(directory/'CURRENT.json')['version']
    else:
        print('NATIVE_REINDEX_BEGIN', flush=True)
        destination, _ = publish_native(replay, output/'published', state, packet, patch, original,
            resolved_state=state, execution=execution, llm_artifacts=accepted)
    from .native import current_graph
    current_graph(output/'published', packet['session_id'])
    graph = load_graph(destination/'graph.pkl')
    from .native import project
    expected_graph = deepcopy(original)
    project(expected_graph, state, packet)
    for field in ('character_mappings', 'character_metadata', 'observation_character_mappings',
                  'reference_character_mappings', 'reviewed_feature_support', 'retired_character_ids'):
        assert getattr(graph, field) == getattr(expected_graph, field), field
    manifest = read(destination/'embedding_manifest.json')
    changed = set(manifest['changed_node_ids'])
    assert all(n.metadata['contents'] == raw[str(n.id)] for n in graph.nodes.values())
    assert all(vector_hash(n) == hashes[str(n.id)] for n in graph.nodes.values() if n.id not in changed)
    assert graph.edges == original.edges
    identity = m3_module('mmagent.character_identity')
    before = deepcopy(graph.character_mappings)
    meta = deepcopy(graph.character_metadata)
    scoped = deepcopy(graph.observation_character_mappings)
    graph.refresh_equivalences(); graph.order_character()
    assert graph.character_mappings == before and graph.character_metadata == meta
    assert graph.observation_character_mappings == scoped
    assert all(c in graph.character_mappings for c in scoped.values())
    assert len(scoped) == len(state['assignments'])
    named = {c: m['canonical_name'] for c, m in meta.items() if m.get('canonical_name')}
    assert sorted(named.values()) == sorted(e['canonical_name'] for e in state['entities'].values() if e['canonical_name'])
    # Native retrieval/export must work after removing all proposal-alias debugging history.
    graph.identity_history = []
    assert not any('person_' in c for c in graph.character_mappings)
    traces = []
    for node in graph.nodes.values():
        if node.type in ('semantic', 'episodic'):
            canonical, details = identity.canonicalize_contents(graph, node.metadata['contents'], node_id=node.id)
            assert canonical == node.metadata['retrieval_contents']
            traces.append(dict(node_id=node.id, original=node.metadata['contents'], canonical=canonical, resolution=details))
    export = m3_module('m3_agent.export_mandol')
    if args.verify_existing:
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            export.export_graph(destination/'graph.pkl', Path(temporary)/'export', 'native-character-fixture')
            for filename in ('memories.jsonl', 'entities.jsonl'):
                assert (Path(temporary)/'export'/filename).read_bytes() == (output/'mandol'/filename).read_bytes()
    else:
        export.export_graph(destination/'graph.pkl', output/'mandol', 'native-character-fixture')
    write(output/'verification.json', dict(status='passed', source_graph_sha256=hashlib.sha256(Path(args.source_graph).read_bytes()).hexdigest(),
        accepted_version=str(accepted), published_version=str(destination),
        source_contents_sha256=digest(raw), source_embeddings_sha256=hashes,
        published_embeddings_sha256={str(n.id):vector_hash(n) for n in graph.nodes.values()},
        changed_text_node_ids=sorted(changed), untouched_vector_count=len(graph.nodes)-len(changed),
        assignments=len(scoped), consolidated_characters=len(meta), names=named,
        raw_contents_preserved=True, edges_preserved=True, refresh_preserved=True,
        proposal_state_required_for_retrieval=False))
    write(output/'identity_traces.json', traces)
    settings = m3_module('mmagent.utils.chat_api').config['text-embedding-3-large']
    write(output/'metadata/embedding_backend.json', {k:settings[k] for k in
        ('model','provider','base_url','api_key_env') if k in settings})
    lines=['# Native M3 character integration', '',
        f'Published native graph: [{destination.name}]({destination.relative_to(output)}/graph.pkl)',
        f'Assigned observations: {len(scoped)}. Consolidated characters: {len(meta)}.',
        f'Re-embedded text nodes: {len(changed)}. Untouched embedding collections: {len(graph.nodes)-len(changed)}.', '',
        '- [Verification and hashes](verification.json)', '- [Full identity traces](identity_traces.json)',
        '- [Native graph JSON]('+str(destination.relative_to(output)/'graph.json')+')',
        '- [Character changes]('+str(destination.relative_to(output)/'identity_changes.json')+')',
        '- [Embedding manifest]('+str(destination.relative_to(output)/'embedding_manifest.json')+')',
        '- [Mandol memories](mandol/memories.jsonl)', '',
        '## Retrieval text changes', '']
    for item in traces:
        if item['original'] != item['canonical']:
            lines.extend([f"### Memory {item['node_id']}", '', '**Original:** '+ escape('\n'.join(item['original'])),
                          '', '**Retrieval:** '+ escape('\n'.join(item['canonical'])), ''])
    (output/'README.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print('NATIVE_FIXTURE_VERIFIED', len(scoped), 'assigned', len(changed), 'reindexed', flush=True)


if __name__ == '__main__':
    main()
