"""Build all retrieval artifacts before committing the native graph version."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

from .common import read, write


def deployment_config():
    path = Path(os.environ.get('CONSOLIDATION_DEPLOYMENT_CONFIG',
                               Path(__file__).with_name('deployment.json')))
    config = read(path)
    allowed = {'embedding_model','embedding_dimension','embedding_base_url','embedding_batch_size',
               'embedding_max_retries','embedding_timeout_seconds','relation_model','relation_base_url',
               'relation_max_retries','relation_timeout_seconds','build_relations','generate_sparse_embeddings'}
    if set(config) != {'mandol'} or set(config['mandol']) - allowed:
        raise ValueError('deployment config must contain only public Mandol build settings')
    return config


def build_retrieval_bundle(staged, graph, config):
    from .native import m3_module
    staged = Path(staged).resolve()
    video_id = 'm3_' + hashlib.sha256(graph.identity_session.encode()).hexdigest()[:20]
    m3_module('m3_agent.export_mandol').export_graph(staged/'graph.pkl', staged/'mandol_input', video_id)
    write(staged/'deployment.json', config)
    interpreter = os.environ.get('MANDOL_PYTHON', sys.executable)
    root = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env['PYTHONPATH'] = os.pathsep.join([str(root), str(root/'Mandol/src'), env.get('PYTHONPATH','')])
    command = [interpreter, '-m', 'consolidation.mandol_worker', '--input', str(staged/'mandol_input'),
               '--output', str(staged/'mandol'), '--config', str(staged/'deployment.json'),
               '--version', graph.graph_version, '--receipt', str(staged/'mandol_ready.json')]
    with (staged/'mandol_build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(command, env=env,
            cwd=os.environ.get('MANDOL_WORKDIR', str(root/'Mandol')),
            stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError('Mandol reindex failed; inspect last_reindex_failure.log (exit '+str(result.returncode)+')')
    receipt = read(staged/'mandol_ready.json')
    if receipt.get('status') != 'ready' or receipt.get('graph_version') != graph.graph_version:
        raise ValueError('Mandol returned an invalid readiness receipt')
    if not all(receipt.get(k) for k in ('dense_verified','bm25_verified','splade_verified')):
        raise ValueError('Mandol did not verify all retrieval indexes')
    manifest = read(staged/'mandol/m3_adapter_manifest.json')
    if manifest.get('source_graph_version') != graph.graph_version:
        raise ValueError('Mandol index belongs to a different native graph version')
    if manifest['counts']['source_memories'] != read(staged/'mandol_input/manifest.json')['memory_count']:
        raise ValueError('Mandol memory count does not match the canonical export')
    return receipt
