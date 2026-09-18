"""Strict per-operation schemas; malformed decisions do not discard valid peers."""
from jsonschema import Draft202012Validator

STR = {'type': 'string', 'minLength': 1}
IDS = {'type': 'array', 'items': STR, 'minItems': 1, 'uniqueItems': True}
PERSON = {'type': 'string', 'pattern': '^person_[0-9]+$'}
VOICE = {'type': 'string', 'pattern': '^voice_[0-9]+$'}
NODE = {'anyOf': [STR, {'type': 'integer'}]}
FIELDS = {
    'assign_cluster': {'voice_ids': {'type':'array','items':VOICE,'minItems':1,'uniqueItems':True},
        'target_entity_id': PERSON, 'evidence_ids': IDS,
        'confidence': {'type':'number','minimum':0,'maximum':1}, 'rationale': STR,
        'excluded_utterance_ids': {'type':'array','items':STR,'uniqueItems':True}},
    'merge_voice': {'voice_ids': {'type':'array','items':VOICE,'minItems':1,'uniqueItems':True}, 'target_entity_id': PERSON, 'evidence_ids': IDS},
    'reassign_utterances': {'utterance_ids': IDS, 'from_voice_id': VOICE, 'target_entity_id': PERSON, 'evidence_ids': IDS},
    'set_name': {'entity_id': PERSON, 'name': STR, 'evidence_ids': IDS},
    'resolve_reference': {'memory_node_id': NODE, 'mention': STR, 'entity_id': PERSON, 'evidence_ids': IDS},
    'revise_claim': {'memory_node_id': NODE, 'status': {'enum':['contradicted','superseded']},
                     'replacement': {'type':['string','null']}, 'evidence_ids': IDS},
    'defer': {'target_ids': IDS, 'reason': STR},
}
DECISIONS = {}
for op, fields in FIELDS.items():
    properties = dict(fields, op={'const':op}, decision_id=STR)
    required = list(properties)
    if op == 'set_name':
        properties['aliases'] = {'type':'array','items':STR,'uniqueItems':True}
    if op == 'resolve_reference':
        properties.update(content_index={'type':'integer','minimum':0},
                          start={'type':'integer','minimum':0}, end={'type':'integer','minimum':1})
        # An occurrence selector is optional, but never partially specified.
    properties['confidence'] = {'type':'number','minimum':0,'maximum':1}
    properties['rationale'] = STR
    properties['depends_on'] = {'type':'array','items':STR,'uniqueItems':True}
    DECISIONS[op] = {'type':'object','properties':properties,'required':required,'additionalProperties':False}
    if op == 'resolve_reference':
        DECISIONS[op]['dependentRequired'] = {key: ['content_index','start','end']
                                              for key in ('content_index','start','end')}
ENVELOPE = {'type':'object', 'properties': {
    'schema_version': {'const':1}, 'session_id':STR, 'base_graph_version':STR,
    'evidence_cutoff_s': {'type':'number','minimum':0}, 'decisions':{'type':'array'}},
    'required':['schema_version','session_id','base_graph_version','evidence_cutoff_s','decisions'],
    'additionalProperties':False}
PATCH_SCHEMA = dict(ENVELOPE, properties=dict(ENVELOPE['properties'], decisions={
    'type':'array','items':{'oneOf':list(DECISIONS.values())}}))


def validate_envelope(patch):
    Draft202012Validator(ENVELOPE).validate(patch)


def validate_decision(decision):
    if not isinstance(decision, dict) or decision.get('op') not in DECISIONS:
        raise ValueError('unknown operation')
    Draft202012Validator(DECISIONS[decision['op']]).validate(decision)
