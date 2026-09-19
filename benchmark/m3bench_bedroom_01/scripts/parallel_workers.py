"""Run independent evaluation methods concurrently against unchanged snapshots."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

NAMES = {'A': 'method_A_normal_streammeco.jsonl', 'B': 'method_B_streammeco_oneshot.jsonl',
         'C': 'method_C_compressed_oneshot.jsonl', 'D': 'method_D_mandol.jsonl'}


def method_lock(results, method):
    root = Path(os.environ.get('M3BENCH_CANONICAL_RESULTS', str(results)))
    directory = root / 'method_locks'
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / f'{method}.lock').open('a')
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def write_json(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.replace(path)


def worker(method):
    run = Path(os.environ['RUN'])
    canonical = Path(os.environ['RESULTS'])
    root = run / 'parallel_eval' / method
    root.mkdir(parents=True, exist_ok=True)
    for name in ['memory', 'streammeco_compressed', 'mandol_adapted', 'mandol']:
        target = canonical / name
        if not target.is_dir():
            raise RuntimeError(f'Missing completed input: {target}')
        alias = root / name
        if not alias.is_symlink():
            alias.symlink_to(target, target_is_directory=True)
    prediction = root / NAMES[method]
    if not prediction.is_symlink():
        prediction.symlink_to(canonical / NAMES[method])
    env = dict(os.environ, M3BENCH_CANONICAL_RESULTS=str(canonical), EGOLIFE_RESULTS=str(root))
    if method == 'D':
        python = '/opt/streammeco/mandol-venv/bin/python'
        cwd = env['MANDOL']
        script = 'benchmarks/bedroom_mandol.py'
        phases = ['adapt', 'eval']
    else:
        python = '/opt/streammeco/.venv/bin/python'
        cwd = env['SMC']
        script = 'benchmarks/bedroom_benchmark.py'
        phases = ['eval']
    for phase in phases:
        command = [python, script, phase, '--qa', env['QA'], '--results', str(root), '--limit', '15']
        if method != 'D':
            command += ['--work', env['WORK'], '--method', method]
        subprocess.run(command, cwd=cwd, env=env, check=True)


def join(run):
    directory = run / 'parallel_eval'
    policy = directory / 'policy.json'
    if not policy.exists():
        return
    while True:
        status = json.loads((directory / 'status.json').read_text())
        if status['state'] == 'complete':
            break
        if status['state'] == 'failed':
            raise RuntimeError(f'Parallel evaluation failed: {status}')
        time.sleep(3)
    # The sequential coordinator calls this only after its own evaluation stages.
    # No shared telemetry writers remain when these private logs are combined.
    lock = (directory / 'merge.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX)
    canonical = Path(os.environ['RESULTS'])
    joined = directory / 'telemetry_joined.json'
    if joined.exists():
        return
    baseline = directory / 'merge_baseline'
    baseline.mkdir(exist_ok=True)
    sources = {}
    for method in status['methods']:
        for source in sorted((directory / method).glob('*.jsonl')):
            if not source.is_symlink():
                sources.setdefault(source.name, []).append(source)
    for name, paths in sources.items():
        target = canonical / name
        base = baseline / name
        if not base.exists():
            base.write_bytes(target.read_bytes() if target.exists() else b'')
        data = base.read_bytes() + b''.join(p.read_bytes() for p in paths)
        for line in data.splitlines():
            json.loads(line)
        temporary = target.with_suffix(target.suffix + '.parallel.tmp')
        temporary.write_bytes(data)
        temporary.replace(target)
    write_json(joined, {'joined_at': time.time(), 'files': list(sources), 'timings_modified': False})
    print('PARALLEL_EVALUATION_JOINED', flush=True)


def launch(methods):
    run = Path(os.environ['RUN'])
    directory = run / 'parallel_eval'
    directory.mkdir(parents=True, exist_ok=True)
    lock = (directory / 'supervisor.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    status = {'state': 'running', 'methods': methods, 'started_at': time.time(), 'exit_codes': {}}
    write_json(directory / 'status.json', status)
    completed = {}
    for method, name in NAMES.items():
        p = Path(os.environ['RESULTS']) / name
        completed[method] = [json.loads(s)['question_index'] for s in p.read_text().splitlines()] if p.exists() else []
    write_json(directory / 'policy.json', {'methods': methods, 'completed_before_parallel': completed,
               'started_at': status['started_at'], 'snapshots': 'unchanged',
               'timing_note': 'Parallel method execution; timings may include shared GPU/API contention.'})
    processes = {}
    try:
        for method in methods:
            log = (directory / f'{method}.log').open('a')
            processes[method] = subprocess.Popen([sys.executable, __file__, '--worker', method],
                                                 stdout=log, stderr=subprocess.STDOUT)
            log.close()
            print(f'PARALLEL_METHOD_START {method} pid={processes[method].pid}', flush=True)
        while len(status['exit_codes']) < len(processes):
            for method, process in processes.items():
                if method not in status['exit_codes'] and process.poll() is not None:
                    status['exit_codes'][method] = process.returncode
                    write_json(directory / 'status.json', status)
                    print(f'PARALLEL_METHOD_EXIT {method} code={process.returncode}', flush=True)
            if len(status['exit_codes']) < len(processes):
                time.sleep(2)
        status['state'] = 'complete' if all(c == 0 for c in status['exit_codes'].values()) else 'failed'
    except BaseException as exc:
        status.update(state='failed', error=str(exc))
        raise
    finally:
        status['updated_at'] = time.time()
        write_json(directory / 'status.json', status)
    if status['state'] != 'complete':
        raise RuntimeError('A parallel evaluation worker failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--methods', nargs='+', choices=list(NAMES), default=list(NAMES))
    parser.add_argument('--worker', choices=list(NAMES))
    parser.add_argument('--join', action='store_true')
    args = parser.parse_args()
    if args.worker:
        worker(args.worker)
    elif args.join:
        join(Path(os.environ['RUN']))
    else:
        launch(args.methods)
