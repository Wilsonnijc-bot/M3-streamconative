"""Native M3 identity state. No dependency on offline consolidation or model runtimes."""
from collections import Counter
from copy import deepcopy
import hashlib
import json
import math
import re

FEATURE = re.compile(r'<((?:voice|face|character)_\d+)>')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    allow_nan=False).encode('utf-8')).hexdigest()


def consolidated(graph):
    return getattr(graph, 'identity_revision', 0) > 0


def initialize(graph):
    defaults = dict(character_metadata={}, observation_character_mappings={},
                    reference_character_mappings={}, identity_observations={},
                    reviewed_feature_support={}, retired_character_ids=[],
                    identity_revision=0, identity_history=[], identity_dirty=False)
    for key, value in defaults.items():
        if not hasattr(graph, key):
            setattr(graph, key, deepcopy(value))
    if not hasattr(graph, 'character_mappings'):
        graph.refresh_equivalences()
    rebuild_reverse(graph)
    used = list(graph.character_mappings) + graph.retired_character_ids
    graph.next_character_id = max(getattr(graph, 'next_character_id', 0),
                                  max([int(c.split('_')[-1]) + 1 for c in used] or [0]))


def rebuild_reverse(graph):
    reverse = {}
    for character, features in graph.character_mappings.items():
        for feature in features:
            if feature in reverse and reverse[feature] != character:
                raise ValueError('feature belongs to multiple native characters: ' + feature)
            reverse[feature] = character
    graph.reverse_character_mappings = reverse


def new_character(graph):
    character = 'character_' + str(graph.next_character_id)
    graph.next_character_id += 1
    graph.character_mappings[character] = []
    return character


def reference_key(node_id, content_index, start, end):
    return f'{node_id}:{content_index}:{start}:{end}'


def resolve_identity(graph, feature_id, *, observation_id=None, memory_reference=None):
    character, source, evidence = None, 'raw_fallback', {}
    if consolidated(graph):
        character = graph.observation_character_mappings.get(observation_id)
        if character:
            record = graph.identity_observations.get(observation_id, {})
            if record.get('feature_id') not in (None, feature_id):
                raise ValueError('observation does not belong to referenced feature')
            source, evidence = 'observation_override', record
        if character is None and memory_reference is not None:
            record = graph.reference_character_mappings.get(memory_reference)
            if record:
                character, source, evidence = record['character_id'], 'memory_reference_override', record
    if character is None:
        # The reverse dictionary is a cache, never an independent identity source.
        owners = [c for c, features in getattr(graph, 'character_mappings', {}).items()
                  if feature_id in features or feature_id == c]
        if len(owners) > 1:
            raise ValueError('ambiguous native character ownership')
        if owners:
            character, source = owners[0], 'character_mapping'
    if character is not None and character not in graph.character_mappings:
        raise ValueError('scoped assignment targets a retired or absent character')
    metadata = getattr(graph, 'character_metadata', {}).get(character, {}) if consolidated(graph) else {}
    name = metadata.get('canonical_name')
    return dict(feature_id=feature_id, character_id=character, canonical_name=name,
                identity=name or character or feature_id, source=source,
                provenance=evidence or metadata)


def canonicalize_contents(graph, contents, *, node_id=None, observation_id=None):
    if not consolidated(graph):
        return list(contents), []
    output, traces = [], []
    for index, text in enumerate(contents):
        spans = {(m.start(), m.end()): m.group(1) for m in FEATURE.finditer(text)}
        if node_id is not None:
            for record in graph.reference_character_mappings.values():
                if str(record['node_id']) == str(node_id) and record['content_index'] == index:
                    start, end = record['start'], record['end']
                    if text[start:end] != record['mention']:
                        raise ValueError('reference span no longer matches immutable source')
                    spans[(start, end)] = record['mention'].strip('<>')
        replacements = []
        for (start, end), feature in sorted(spans.items()):
            if any(start < b and a < end for a, b in spans if (a, b) != (start, end)):
                raise ValueError('overlapping identity reference occurrences')
            key = reference_key(node_id, index, start, end)
            resolution = resolve_identity(graph, feature, observation_id=observation_id,
                                          memory_reference=key)
            traces.append(dict(content_index=index, start=start, end=end,
                               original=text[start:end], **resolution))
            replacements.append((start, end, resolution['identity']))
        for start, end, identity in reversed(replacements):
            text = text[:start] + identity + text[end:]
        output.append(text)
    return output, traces


def retrieval_contents(graph, node_id):
    node = graph.nodes[node_id]
    return canonicalize_contents(graph, node.metadata['contents'], node_id=node_id)[0]


def refresh_characters(graph):
    """Consolidated graphs retain identity; new construction features start unnamed."""
    if not consolidated(graph) and not getattr(graph, 'identity_runtime_active', False):
        return False
    initialize(graph)
    known = set(graph.reverse_character_mappings) | set(graph.reviewed_feature_support)
    for node in graph.nodes.values():
        if node.type not in ('voice', 'img'):
            continue
        feature = ('face_' if node.type == 'img' else 'voice_') + str(node.id)
        if feature not in known:
            graph.character_mappings[new_character(graph)] = [feature]
            graph.identity_dirty = True
    rebuild_reverse(graph)
    return True


def admit_observations(graph, feature, contents, first_index):
    """New observations can inherit a >75% reviewed majority, never cast votes."""
    if not consolidated(graph):
        return
    support = graph.reviewed_feature_support.setdefault(feature, {'counts': {}, 'total': first_index})
    for offset, text in enumerate(contents):
        uid = f'{feature}/content_{first_index + offset}'
        if uid in graph.identity_observations:
            continue
        support['total'] += 1
        counts = support['counts']
        winner = max(counts, key=counts.get) if counts else None
        record = dict(feature_id=feature, raw_text=text, reviewed=False, provisional=True)
        if winner and counts[winner] / support['total'] > .75:
            graph.observation_character_mappings[uid] = winner
            record['character_id'] = winner
        graph.identity_observations[uid] = record
    support['complete'] = False
    for features in graph.character_mappings.values():
        if feature in features:
            features.remove(feature)
    graph.identity_dirty = True
    rebuild_reverse(graph)


def prepare_texts(graph, contents):
    if (consolidated(graph) and graph.identity_dirty
            and not getattr(graph, 'identity_reindex_async', False)):
        reindex_text(graph)
    return canonicalize_contents(graph, contents)[0]


def configured_embed(texts):
    from .utils.chat_api import get_embeddings_batch
    return get_embeddings_batch('text-embedding-3-large', texts)[0]


def apply_conclusions(graph, conclusions, observations, references, *, cutoff, provenance):
    """Apply a complete reviewed prefix to a staged native graph, before reindexing.

    Conclusion keys are request-local aliases, not stored runtime identities.
    Observations carry `entity_id`, `feature_id`, and optional evidence/confidence.
    """
    initialize(graph)
    if cutoff < getattr(graph, 'identity_cutoff', 0):
        raise ValueError('cannot apply earlier identity evidence to a later graph')
    old_owners = dict(graph.reverse_character_mappings)
    old_scoped = dict(graph.observation_character_mappings)
    old_features = deepcopy(graph.character_mappings)
    assignments = {o['observation_id']: o.get('entity_id') for o in observations}
    if len(assignments) != len(observations):
        raise ValueError('duplicate observation ID')
    if set(assignments.values()) - {None} - set(conclusions):
        raise ValueError('observation targets unknown conclusion')
    candidates = {}
    for alias, entity in conclusions.items():
        scores = Counter()
        for observation in observations:
            if observation.get('entity_id') != alias:
                continue
            owner = old_scoped.get(observation['observation_id']) or old_owners.get(observation.get('feature_id'))
            if owner:
                scores[owner] += 1
        native = entity.get('native_character_id')
        candidates[alias] = (native, scores)
    selected, reserved = {}, set()
    # Established native identities take precedence over incidental feature overlap.
    order = sorted(conclusions, key=lambda a: (candidates[a][0] is None,
                    -max(candidates[a][1].values(), default=0), a))
    for alias in order:
        native, scores = candidates[alias]
        compatible = [c for c in scores if c not in reserved and
                      (not graph.character_metadata.get(c, {}).get('canonical_name') or
                       graph.character_metadata[c]['canonical_name'] == conclusions[alias].get('canonical_name'))]
        if native in graph.character_mappings and native not in reserved:
            survivor = native
        elif compatible:
            survivor = min(compatible, key=lambda c: (-scores[c], int(c.split('_')[-1])))
        else:
            survivor = new_character(graph)
        selected[alias] = survivor
        reserved.add(survivor)
    affected = set()
    by_feature = {}
    for observation in observations:
        feature = observation.get('feature_id')
        if feature:
            match = re.fullmatch(r'(voice|face)_(\d+)', feature)
            if not match or int(match[2]) not in graph.nodes:
                raise ValueError('unknown reviewed feature')
            node = graph.nodes[int(match[2])]
            if node.type != ('img' if match[1] == 'face' else 'voice'):
                raise ValueError('reviewed feature type mismatch')
            by_feature.setdefault(feature, []).append(observation)
            if feature in old_owners:
                affected.add(old_owners[feature])
        uid = observation['observation_id']
        graph.observation_character_mappings.pop(uid, None)
        target = selected.get(observation.get('entity_id'))
        record = {k: deepcopy(v) for k, v in observation.items() if k != 'entity_id'}
        record.update(reviewed=True, provisional=False)
        if target:
            graph.observation_character_mappings[uid] = target
            record['character_id'] = target
        graph.identity_observations[uid] = record
    for feature, members in by_feature.items():
        # Admission placeholders are superseded by the next complete prefix review.
        for uid in list(graph.identity_observations):
            if uid.startswith(feature + '/content_') and uid not in assignments:
                del graph.identity_observations[uid]
                graph.observation_character_mappings.pop(uid, None)
        node = graph.nodes[int(feature.split('_')[-1])]
        total = max(len(members), len(node.metadata.get('contents', [])))
        counts = Counter(selected[o['entity_id']] for o in members if o.get('entity_id'))
        complete = (len(members) == len(node.metadata.get('contents', []))
                    and sum(counts.values()) == total)
        graph.reviewed_feature_support[feature] = dict(total=total, counts=dict(counts),
            complete=complete, cutoff=cutoff)
        for features in graph.character_mappings.values():
            if feature in features:
                features.remove(feature)
        if complete and len(counts) == 1:
            graph.character_mappings[next(iter(counts))].append(feature)
    # Null source attribution can contaminate any of its recorded raw candidates.
    for observation in observations:
        if observation.get('feature_id') is None:
            for feature in observation.get('candidate_feature_ids', []):
                for features in graph.character_mappings.values():
                    if feature in features:
                        features.remove(feature)
                support = graph.reviewed_feature_support.setdefault(feature, {'counts': {}, 'total': 0})
                support['complete'] = False
    for alias, character in selected.items():
        entity = conclusions[alias]
        supported = [o for o in observations if o.get('entity_id') == alias]
        confidence = [o['confidence'] for o in supported if o.get('confidence') is not None]
        metadata = graph.character_metadata.setdefault(character, {'merged_character_ids': []})
        metadata.update(canonical_name=entity.get('canonical_name'), aliases=entity.get('aliases', []),
            name_evidence=deepcopy(entity.get('name_evidence', [])),
            confidence=min(confidence) if confidence else None,
            evidence_ids=sorted(set(entity.get('name_evidence', []) +
                              [eid for o in supported for eid in o.get('evidence_ids', [])])),
            consolidation_provenance=deepcopy(provenance))
    # Retire only exhausted, affected characters. Unrelated or partially moved ones survive.
    retired = {}
    for character in sorted(affected - reserved):
        if graph.character_mappings[character] or character in graph.observation_character_mappings.values():
            continue
        targets = {selected[o['entity_id']] for o in observations if o.get('entity_id') and
                   (old_scoped.get(o['observation_id']) == character or
                    o.get('feature_id') in old_features.get(character, []))}
        if len(targets) != 1:
            continue
        target = next(iter(targets))
        # Existing occurrence assignments are redirected as part of the structural merge.
        for record in graph.reference_character_mappings.values():
            if record['character_id'] == character:
                record['character_id'] = target
        lineage = [character] + graph.character_metadata.get(character, {}).get('merged_character_ids', [])
        graph.character_metadata[target]['merged_character_ids'] = sorted(set(
            graph.character_metadata[target]['merged_character_ids'] + lineage))
        retired[character] = target
        del graph.character_mappings[character]
        graph.character_metadata.pop(character, None)
        graph.retired_character_ids = sorted(set(graph.retired_character_ids + lineage))
    reviewed_memories = {str(n) for n in provenance.get('reviewed_memory_ids', [])}
    graph.reference_character_mappings = {k: v for k, v in graph.reference_character_mappings.items()
                                          if str(v['node_id']) not in reviewed_memories}
    for reference in references:
        node_id = int(reference['memory_node_id'])
        node = graph.nodes[node_id]
        if node.type not in ('semantic', 'episodic'):
            raise ValueError('reference must target a text node')
        target = selected[reference['entity_id']]
        found = 0
        for index, content in enumerate(node.metadata['contents']):
            for match in re.finditer(re.escape(reference['mention']), content):
                if 'content_index' in reference and (index, match.start(), match.end()) != (
                        reference['content_index'], reference['start'], reference['end']):
                    continue
                key = reference_key(node_id, index, match.start(), match.end())
                record = dict(node_id=node_id, content_index=index, start=match.start(), end=match.end(),
                              mention=reference['mention'], character_id=target,
                              evidence_ids=reference.get('evidence_ids', []))
                previous = graph.reference_character_mappings.get(key)
                if previous and previous['character_id'] != target:
                    raise ValueError('conflicting reference occurrence assignments')
                graph.reference_character_mappings[key] = record
                found += 1
        if not found:
            raise ValueError('reference mention/occurrence not present in source')
    graph.identity_revision += 1
    graph.identity_cutoff = cutoff
    graph.identity_dirty = True
    rebuild_reverse(graph)
    report = dict(revision=graph.identity_revision, retired_characters=retired,
                  conclusion_characters=selected, provenance=deepcopy(provenance))
    graph.identity_history.append(report)
    return report


def reindex_text(graph, embed=None):
    """Compare actual embedding inputs; commit no vector until every batch succeeds."""
    configured = embed is None
    embed = embed or configured_embed
    changes, representations, flat = [], {}, []
    for node in graph.nodes.values():
        if node.type not in ('episodic', 'semantic'):
            continue
        contents, traces = canonicalize_contents(graph, node.metadata['contents'], node_id=node.id)
        previous = node.metadata.get('retrieval_contents', node.metadata['contents'])
        representations[node.id] = (contents, traces)
        if contents != previous:
            changes.append((node.id, len(flat), len(contents)))
            flat.extend(contents)
    vectors = embed(flat) if flat else []
    if len(vectors) != len(flat):
        raise ValueError('embedding backend returned the wrong number of vectors')
    expected = {len(v) for n in graph.nodes.values() if n.type in ('semantic', 'episodic') for v in n.embeddings}
    for vector in vectors:
        if not vector or not all(math.isfinite(float(x)) for x in vector):
            raise ValueError('invalid text embedding')
        if expected and len(vector) not in expected:
            raise ValueError('configured embedding dimension differs from native index')
    for node_id, start, count in changes:
        graph.nodes[node_id].embeddings = vectors[start:start + count]
    for node_id, (contents, traces) in representations.items():
        graph.nodes[node_id].metadata.update(retrieval_contents=contents,
            retrieval_identity_trace=traces, embedding_input_fingerprint=fingerprint(contents))
    graph.identity_dirty = False
    backend = {'kind': 'injected_test_backend'}
    if configured:
        from .utils.chat_api import config
        settings = config['text-embedding-3-large']
        backend = dict(kind='configured_m3', alias='text-embedding-3-large',
                       model=settings.get('model', 'text-embedding-3-large'),
                       endpoint=settings.get('base_url'), provider=settings.get('provider'))
    return dict(changed_node_ids=[c[0] for c in changes], embedded_text_count=len(flat), backend=backend,
                unchanged_text_node_ids=[n for n in representations if n not in {c[0] for c in changes}])
