"""Render a VideoGraph object, native checkpoint, or graph JSON for human review.

Standalone CLI (standard library only):
    python videograph_markdown.py graph.pkl -o memories.md

No models are loaded and no graph mutations or identity refreshes are performed.
"""
import argparse
import base64
from collections import Counter, defaultdict
import html
import json
import os
from pathlib import Path
import pickle
import re


class _GraphState:
    """Inert destination for the attributes stored in an M3 pickle."""


class _NodeState:
    pass


class _GraphUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        # Do not import videograph: importing it initializes the model runtime.
        if module in ('mmagent.videograph', 'videograph', 'StreamMeCo.mmagent.videograph'):
            if name == 'VideoGraph':
                return _GraphState
            if name in ('VideoGraph.Node', 'Node'):
                return _NodeState
        raise pickle.UnpicklingError(f'Unsupported checkpoint class: {module}.{name}')


def _visible(key):
    return 'embedding' not in str(key).lower()


def graph_view(graph):
    """Preserve reviewable graph state without embeddings or derived identities."""
    if isinstance(graph, dict) and isinstance(graph.get('nodes'), list):
        return graph
    state = vars(graph) if not isinstance(graph, dict) else graph
    nodes = []
    for node in state['nodes'].values():
        fields = vars(node) if not isinstance(node, dict) else node
        nodes.append({k: v for k, v in fields.items() if _visible(k)})
    return {
        'nodes': sorted(nodes, key=lambda n: n['id']),
        'edges': [{'source': s, 'target': t, 'weight': w}
                  for (s, t), w in sorted(state['edges'].items())],
        'edge_storage': 'directed',
        'state_complete': True,
        'graph_attributes': {k: v for k, v in state.items()
                             if k not in ('nodes', 'edges') and _visible(k)},
    }


def load_graph(path):
    """Read native M3 state without executing its classes, or read graph JSON."""
    path = Path(path)
    if path.suffix.lower() in ('.pkl', '.pickle'):
        with path.open('rb') as handle:
            return graph_view(_GraphUnpickler(handle).load())
    return graph_view(json.loads(path.read_text()))


def _cell(value):
    return html.escape(str(value), quote=False).replace('|', '&#124;').replace('\n', '<br>')


def _table(headers, rows):
    return ['| ' + ' | '.join(headers) + ' |',
            '| ' + ' | '.join('---' for _ in headers) + ' |'] + [
                '| ' + ' | '.join(str(v) for v in row) + ' |' for row in rows] + ['']


def _json(value):
    # HTML is escaped only in prose, never inside code fences.
    text = json.dumps(value, ensure_ascii=False, indent=2)
    fence = '`' * max(3, 1 + max((len(s) for s in re.findall(r'`+', text)), default=0))
    return [fence + 'json', text, fence, '']


def render_character_dictionary(graph, source, output, snapshot_name, level=2):
    """Show the actual query-time dictionary separately from construction state."""
    mappings = graph_view(graph).get('graph_attributes', {}).get('character_mappings')
    if mappings is None:
        return []
    grouped = {k: v for k, v in mappings.items() if len(v) > 1}
    target = os.path.relpath(source, Path(output).parent)
    result = ['#' * level + ' Query-time character_mappings', '',
              f'From saved query snapshot **{snapshot_name}** '
              f'([original graph](<{target}>)). These are the mappings used for retrieval, '
              'shown separately from the construction checkpoint.', '',
              f'**{len(mappings)} characters**: {len(mappings)-len(grouped)} single-feature mappings; '
              f'{len(grouped)} mappings join multiple features.', '']
    if grouped:
        result += _table(['Character', 'Linked face / voices'],
                         [[k, ', '.join(f'`{feature}`' for feature in values)]
                          for k, values in grouped.items()])
    result += [f'<details><summary>Show full dictionary ({len(mappings)} entries)</summary>', '',
               '```json', '{']
    result += ['  ' + json.dumps(k, ensure_ascii=False) + ': ' + json.dumps(v, ensure_ascii=False)
               + (',' if i < len(mappings)-1 else '') for i, (k, v) in enumerate(mappings.items())]
    result += ['}', '```', '', '</details>', '']
    return result


def render_graph(graph, title='Video graph', level=1, source=None, output=None):
    """Compact review: node text, adjacent edges, and stored character mappings."""
    graph = graph_view(graph)
    nodes = sorted(graph['nodes'], key=lambda n: n['id'])
    edges = graph.get('edges', [])
    attrs = graph.get('graph_attributes', {})
    prefix = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    anchor = lambda i: f'{prefix}-node-{i}'
    ref = lambda i: f'[{i}](#{anchor(i)})'
    section = lambda name: ['#' * (level + 1) + ' ' + name, '']
    counts = Counter(n['type'] for n in nodes)
    adjacency = defaultdict(list)
    lookup = {(e['source'], e['target']): e.get('weight', 1) for e in edges}
    seen = set()
    link_count = 0
    for (a, b), weight in lookup.items():
        if (a, b) in seen:
            continue
        symmetric = graph.get('edge_storage') != 'directed' or lookup.get((b, a)) == weight
        suffix = '' if weight == 1 else f' (weight {_cell(weight)})'
        adjacency[a].append(('↔' if symmetric else '→') + ' ' + ref(b) + suffix)
        if a != b:
            adjacency[b].append(('↔' if symmetric else '←') + ' ' + ref(a) + suffix)
        seen.add((a, b))
        if symmetric:
            seen.add((b, a))
        link_count += 1
    result = ['#' * level + ' ' + title, '',
              f"**{len(nodes):,} nodes · {link_count:,} links** — "
              f"{counts['episodic']:,} events, {counts['semantic']:,} inferences, "
              f"{counts['voice']:,} voices, {counts['img']:,} faces.", '',
              'Links appear beside each node. ↔ means a shared connection; arrows show '
              'one-way connections. Unmarked weights are 1. Nodes without links are unconnected.', '']
    result += section('Character mappings')
    mappings = attrs.get('character_mappings')
    if mappings is None:
        result += [('Not stored in this construction checkpoint.' if graph.get('state_complete')
                    else 'Not included in this JSON export.'), '']
    elif not mappings:
        result += ['Empty — no character mappings stored.', '']
    else:
        single = sum(len(v) == 1 for v in mappings.values())
        result += [f'{len(mappings)} characters: {single} single-feature mappings, '
                   f'{len(mappings)-single} mappings joining multiple features.', '',
                   '<details><summary>Show character → face / voice mappings</summary>', '']
        def feature(value):
            match = re.fullmatch(r'(voice|face)_(\d+)', str(value))
            return f'[{value}](#{anchor(int(match[2]))})' if match else _cell(value)
        result += _table(['Character', 'Face / voice'],
                         [[_cell(k), ', '.join(feature(v) for v in values)]
                          for k, values in mappings.items()])
        result += ['</details>', '']
    kinds = [('episodic', 'Events'), ('semantic', 'Inferences'), ('voice', 'Voices'), ('img', 'Faces')]
    kinds += [(kind, str(kind)) for kind in sorted(set(counts) - {k for k, _ in kinds})]
    for kind, heading in kinds:
        selected = [n for n in nodes if n['type'] == kind]
        if not selected:
            continue
        result += section(heading)
        for node in selected:
            node_id = node['id']
            metadata = node.get('metadata', {})
            contents = metadata.get('contents', [])
            if isinstance(contents, str):
                contents = [contents]
            links = ' · '.join(adjacency[node_id])
            # Keep complete transcripts available without dominating the review page.
            result += [f'<a id="{anchor(node_id)}"></a>', '']
            if kind in ('voice', 'img'):
                name = ('voice' if kind == 'voice' else 'face') + f'_{node_id}'
                result += [f'<details><summary>{name} · {len(contents)} '
                           f'{"speech entries" if kind == "voice" else "images"} · '
                           f'{len(adjacency[node_id])} links</summary>', '']
                if links:
                    result += [links, '']
                for index, content in enumerate(contents, 1):
                    media = _face_image(content) if kind == 'img' else None
                    if media and output:
                        data, extension = media
                        output_path = Path(output)
                        asset = output_path.parent / (output_path.stem + '.assets') / f'face_{node_id}_{index}.{extension}'
                        asset.parent.mkdir(parents=True, exist_ok=True)
                        asset.write_bytes(data)
                        result += [f'![{name}]({os.path.relpath(asset, output_path.parent)})', '']
                    elif media:
                        result += [f'- Face image ({media[1]}).']
                    else:
                        result += ['- ' + _cell(content)]
                result += ['', '</details>', '']
            else:
                clip = f' · clip {metadata["timestamp"]}' if 'timestamp' in metadata else ''
                content = ' / '.join(_cell(v) for v in contents) or '(no text)'
                result += [f'- **{node_id}**{clip}: {content}' +
                           (f'  **Links:** {links}' if links else ''), '']
    if source:
        target = os.path.relpath(source, Path(output).parent) if output else str(Path(source).resolve())
        result += [f'[Original graph](<{target}>) · Embeddings and internal metadata omitted.', '']
    return result


def _face_image(content):
    if not isinstance(content, str):
        return None
    try:
        data = base64.b64decode(content, validate=True)
    except (ValueError, TypeError):
        return None
    if data.startswith(b'\xff\xd8\xff'):
        return data, 'jpg'
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return data, 'png'
    if data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        return data, 'webp'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Native M3 .pkl or exported graph .json')
    parser.add_argument('-o', '--output', type=Path, required=True)
    parser.add_argument('--title', default='Video graph')
    args = parser.parse_args()
    graph = load_graph(args.input)
    text = '\n'.join(render_graph(graph, args.title, source=args.input, output=args.output))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text.rstrip() + '\n')
    print(f'Exported {len(graph["nodes"])} nodes and {len(graph.get("edges", []))} edge records to {args.output}')


if __name__ == '__main__':
    main()
