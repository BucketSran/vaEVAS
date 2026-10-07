#!/usr/bin/env python3
"""Freeze all final cases and honestly limited native public materials."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import sys
from runtime import ROOT, REPO, HARNESS, PUBLIC_CHECKOUT, PYTHON, CODEX, save
from public_protocol import append_note
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(REPO))
from experiments.benchmark_first_batch.runtime import prepare
from alphaapollo.common.execution.chips.benchmark_spectre import package_identity
from alphaapollo.common.execution.chips.current_evas_session import (
    create_session, session_action, close_session,
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    match = re.fullmatch(r'([+-]?(?:[0-9]*\.)?[0-9]+(?:[eE][+-]?[0-9]+)?)([a-zA-Z]*)', value.rstrip(','))
    if not match:
        raise ValueError('unsupported numeric literal: ' + value)
    scales = {'': 1, 'f': 1e-15, 'p': 1e-12, 'n': 1e-9, 'u': 1e-6,
              'm': 1e-3, 'k': 1e3, 'meg': 1e6, 'g': 1e9}
    return float(match[1]) * scales[match[2].lower()]


def public_manifest(text, reference, candidate_files):
    sources = {}
    for node, wave in re.findall(r'^V\w+\s+\((\w+)\s+0\)\s+vsource type=pwl wave=\[([^\]]*)\]', text, re.M):
        values = [number(v) for v in wave.split()]
        if len(values) % 2:
            raise ValueError('unpaired public PWL values')
        sources[node] = [[values[i], values[i + 1]] for i in range(0, len(values), 2)]
    match = re.search(r'^(?:DUT|Xbench|Xmeasure|XDUT)\s+\(([^)]*)\)\s+(\w+)([^\n]*)', text, re.M)
    if match is None:
        raise ValueError('public top instance not identified')
    nodes, module_name, parameter_text = match.groups()
    source = (reference / 'dut.va').read_text()
    port_match = re.search(r'\bmodule\s+' + re.escape(module_name) + r'\s*\(([^)]*)\)', source)
    if port_match is None:
        raise ValueError('public top module not identified')
    ports = [p.strip() for p in port_match[1].split(',')]
    if len(ports) != len(nodes.split()):
        raise ValueError('public instance port count mismatch')
    instance = {'name': 'dut', 'module': module_name,
                'connections': dict(zip(ports, nodes.split()))}
    parameters = {k: number(v) for k, v in re.findall(r'(\w+)=([^\s]+)', parameter_text)}
    if parameters:
        instance['parameters'] = parameters
    transient = re.search(r'tran tran stop=(\S+) maxstep=(\S+)', text)
    if transient is None:
        raise ValueError('public transient limits not identified')
    stop, step = [number(v) for v in transient.groups()]
    if stop <= 0 or step <= 0:
        raise ValueError('public transient limits must be positive')
    times = [i * step for i in range(math.floor(stop / step) + 1)]
    if times[-1] < stop:
        times.append(stop)
    return {'models': candidate_files, 'instances': [instance],
            'transient': {'sources': sources, 'output_times': times, 'stop': stop, 'max_step': step},
            'tolerances': {'vabstol': 1e-9, 'reltol': 1e-6}}


def snapshot(args):
    for value in [args.task_id, args.label]:
        if Path(value).name != value or value in {'.', '..'}:
            raise ValueError('task and label must be single directory components')
    task = REPO / 'benchmark/tasks' / args.task_id
    root = ROOT / 'representatives' / f'{args.task_id}-{args.label}'
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    reference = root / 'reference'
    shutil.copytree(task / 'solution', reference)
    if not (reference / 'dut.va').exists():
        spec = importlib.util.spec_from_file_location('public_fit', task / 'solution/fit.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        (reference / 'dut.va').write_text(module.model(module.fit(task / 'environment/public')))
    plan = prepare(task, reference / 'dut.va', root / 'final-preparation', HARNESS)
    package = root / 'final-all-conditions'
    shutil.copytree(plan['cases'][0]['package'], package)
    (package / 'tests/cases.json').write_bytes((task / 'tests/cases.json').read_bytes())
    manifest = json.loads((package / 'manifest.json').read_text())
    manifest['condition_id'] = 'all-conditions-' + args.label
    manifest['files'] = {str(x.relative_to(package)): {'sha256': sha(x), 'bytes': x.stat().st_size}
                         for x in package.rglob('*') if x.is_file() and x.name != 'manifest.json'}
    (package / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    save(root / 'final-identity.json', {
        'identity': package_identity(package, purpose='final'), 'source_identity': plan['source_identity'],
        'simulator_executed': False,
        'case_names': [x['name'] for x in json.loads((package / 'tests/cases.json').read_text())],
    })
    contract = json.loads((task / 'tests/contract.json').read_text())
    materials = root / 'public-materials'
    public_source = task / 'environment/public'
    public_names = {str(x.relative_to(public_source)) for x in public_source.rglob('*') if x.is_file()}
    project = materials / 'project' if public_names.intersection(contract['candidate_files']) else materials
    shutil.copytree(public_source, project)
    instruction = (task / 'instruction.md').read_text().replace(
        '公开自测网表在 `/work/public/visible.scs`，用有授权的 Spectre 自测；远端公开调用入口由评测环境提供。',
        '公开固定刺激由 EVAS 工具提供。Spectre形式网表仅供阅读，本环境没有公开Spectre入口。')
    instruction += '\n本次公开仿真后端为EVAS，部分Verilog-A或固定fixture组合可能被拒绝。尚未验证本题完整公开仿真；工具错误不构成最终判定，不按该限制缩减题目。/work/public保留公开数据和Python分析材料，可用于本地分析；提及Spectre的自测脚本不能据此认为本环境提供了该调用入口。最终全部条件在独立Spectre评分。\n'
    if project != materials:
        instruction = instruction.replace('/work/public/', '/work/public/project/').replace(
            'public/smoke.py', 'public/project/smoke.py')
        instruction += '\n公开源工程因文件名与正式候选相同而归档在/work/public/project；正式交付路径仍按候选清单。\n'
    netlists = sorted(project.glob('*.scs'))
    text = netlists[0].read_text() if netlists else json.loads((project / 'smoke_cases.json').read_text())[0]['netlist']
    fixtures = [x for x in re.findall(r'ahdl_include\s+"([^"]+)"', text)
                if x not in contract['candidate_files'] and not x.endswith('../dut.va')]
    if fixtures:
        instruction += '\n公开EVAS限制：本会话只装载正式候选文件，不装载固定公共fixture ' + ', '.join(fixtures) + '；因此evas_simulate不能执行完整闭环/测量电路，只能用于有限的候选兼容性诊断。请阅读所提供的fixture源码和Python材料分析，不能把该工具返回当作完整公共网表仿真结果。\n'
    (materials / 'instruction.md').write_text(append_note(instruction))
    declaration = {'task_id': task.name, 'task_version': manifest['task_version'],
                   'public_files': sorted(str(x.relative_to(materials)) for x in materials.rglob('*') if x.is_file()),
                   'candidate_files': contract['candidate_files'], 'feedback_fields': ['diagnostics', 'observations'],
                   'manifest': public_manifest(text, reference, contract['candidate_files'])}
    save(root / 'public-declaration.json', declaration)
    save(root / 'public-limitations.json', {
        'public_top_instance_only': True, 'immutable_fixture_models_not_in_manifest': fixtures,
        'public_full_circuit_reproducibility': 'not_verified',
        'reason': 'native models must equal candidate_files; no separate immutable fixture model'
                  if fixtures else 'original reference probe pending',
        'probe_requested': args.public_probe, 'model_requests': 0, 'remote_solves': 0,
    })
    if args.public_probe and not fixtures:
        session = root / 'public-reference-session'
        create_session(task=declaration, materials=materials, checkout=PUBLIC_CHECKOUT,
                       kernel=Path(args.kernel).resolve(), directory=session, image=None,
                       backend='native_codex_sandbox', codex=CODEX, python=PYTHON.resolve(),
                       max_actions=max(10, len(contract['candidate_files']) + 1), max_simulations=1, timeout_s=120)
        writes = [session_action(session, {'action_id': f'write-{i}', 'tool': 'evas_write',
                  'arguments': {'path': name, 'content': (reference / name).read_text()}})
                  for i, name in enumerate(contract['candidate_files'])]
        result = session_action(session, {'action_id': 'reference-simulate', 'tool': 'evas_simulate', 'arguments': {}})
        save(root / 'public-reference-result.json', {
            'writes': writes, 'simulation': result, 'close': close_session(session, 'completed'),
            'reference_files': {name: sha(reference / name) for name in contract['candidate_files']},
            'model_calls': 0, 'remote_solves': 0,
        })
        print('public_execution', result.get('result', {}).get('execution', result.get('error')))
    print('prepared', root, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('task_id')
    parser.add_argument('--label', default='v1')
    parser.add_argument('--kernel', required=True)
    parser.add_argument('--public-probe', action='store_true')
    snapshot(parser.parse_args())


if __name__ == '__main__':
    main()
