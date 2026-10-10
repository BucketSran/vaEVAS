"""Build versioned, fixed-interface component and causal replacement fixtures.

The healthy partner is a stimulus adapter, not the verdict: v2_spec derives
the response independently. Only the tested helper is candidate code in each
component condition. No candidate Verilog-A is parsed or rewritten at grading.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'experiments/benchmark_v2/spec_modeling'
VERSION = 'system-interfaces-v2'
CONFIG = {
    '091': ('chopper_gain_core', 'synchronous_lp_state'),
    '307': ('sample_phase_cell', 'integrator_state_cell'),
    '308': ('reset_sample_latch', 'signal_sample_latch'),
}
SENTINELS = {
    '091': {'voutp': '.22', 'voutn': '.67', 'settled': '.9', 'offset_residual': '.14'},
    '307': {'vout': '.63', 'phase_metric': '.22', 'valid': '0.0'},
    '308': {'vout': '.61', 'offset_dbg': '.23', 'valid': '.9'},
}
EMPTY_OUTPUTS = {
    '091': {'demod_sample': '0.0', 'baseband_ref': '0.0', 'event_strobe': '0.0'},
    '307': {'sample_node': '0.45', 'sample_valid': '0.0'},
    '308': {'reset_node': '0.45'},
}


def consumer_probe(source, sid):
    # Author-owned fixture transformation only; never applied to a submission.
    declaration = source.split('analog begin', 1)[0]
    return declaration + 'analog begin\n' + ''.join(
        f' V({node}) <+ {"0" + value if value.startswith(".") else value};\n'
        for node, value in SENTINELS[sid].items()
    ) + 'end\nendmodule\n'


def producer_probe(source, sid):
    replacements = {
        '091': [('sample_q=polarity*amplified', 'sample_q=0.16'),
                ('ref_q=gain*input_diff', 'ref_q=0.16')],
        '307': [('sample_v = V(vin);', 'sample_v = 0.62;')],
        '308': [('reset_sample = V(vin);', 'reset_sample = 0.31;')],
    }
    for old, new in replacements[sid]:
        if old not in source:
            raise ValueError(f'{sid}: missing authored fixture edit: {old}')
        source = source.replace(old, new)
    return source


def build_cases(task, sid):
    cases = json.loads((task / 'tests/cases.json').read_text())[:2]
    producer, consumer = CONFIG[sid]
    sources = {p.stem: p.read_text() for p in (task / 'solution').glob('*.va')}
    base = cases[0]
    for mode, selected in [('component-producer', producer),
                           ('component-consumer', consumer),
                           ('producer', consumer), ('consumer', producer)]:
        case = copy.deepcopy(base)
        case['name'] = 'architecture-' + mode
        case['structure_probe'] = mode
        case['architecture_version'] = VERSION
        case['support'] = {}
        if mode.startswith('component-'):
            # A checker-owned top binds the fixed public interface. The real
            # candidate top is not elaborated in an isolated component test.
            case['support']['architecture_top.va'] = sources['dut']
            case['netlist'] = case['netlist'].replace(
                'ahdl_include "dut.va"', 'ahdl_include "architecture_top.va"')
            other = consumer if selected == producer else producer
            case['support']['architecture_partner.va'] = sources[other]
            case['netlist'] = case['netlist'].replace(
                f'ahdl_include "{other}.va"', 'ahdl_include "architecture_partner.va"')
            if sid == '091' and mode == 'component-producer':
                boundary = ['IDUT.demod_sample_i', 'IDUT.baseband_ref_i', 'IDUT.event_strobe_i']
                case['signals'] += boundary
                case['netlist'] += 'save ' + ' '.join(boundary) + '\n'
        else:
            other = producer if mode == 'producer' else consumer
            substitute = (producer_probe(sources[other], sid) if mode == 'producer'
                          else consumer_probe(sources[other], sid))
            case['support']['architecture_replacement.va'] = substitute
            case['netlist'] = case['netlist'].replace(
                f'ahdl_include "{other}.va"', 'ahdl_include "architecture_replacement.va"')
        cases.append(case)
    return cases


def bypass_candidate(task, sid):
    """Both required helpers are active; private copies drive real outputs."""
    producer, consumer = CONFIG[sid]
    top = (task / 'solution/dut.va').read_text()
    duplicate = top
    for name in CONFIG[sid]:
        duplicate = re.sub(r'\b' + name + r'\b', 'private_' + name, duplicate)
    # Keep a second independent public-helper chain, with public outputs sunk
    # into private nets. This is harder than merely declaring empty helpers.
    block = top.split('parameter', 1)[1].split('endmodule', 1)[0]
    block = 'parameter' + block
    # Only the instance portion is duplicated. Public parameters already exist.
    start = block.index(producer + ' #')
    block = block[start:]
    ports = SENTINELS[sid]
    for node in ports:
        block = re.sub(r'\b' + node + r'\b', 'unused_' + node, block)
    for old in ('ICHOP', 'ILP', 'XSAMPLE', 'XINT', 'XRST', 'XSIG'):
        block = re.sub(r'\b' + old + r'\b', 'UNUSED_' + old, block)
    # Separate the two chains' internal wires, so the replacement cannot alter
    # the private-copy circuit indirectly through a shared producer driver.
    nets = {'091': ['demod_sample_i', 'baseband_ref_i', 'event_strobe_i'],
            '307': ['sample_node', 'sample_valid'], '308': ['reset_node']}[sid]
    for net in nets:
        block = re.sub(r'\b' + net + r'\b', 'unused_' + net, block)
    declarations = 'electrical ' + ','.join('unused_' + n for n in [*ports, *nets]) + ';\n'
    duplicate = duplicate.replace('parameter', declarations + 'parameter', 1)
    duplicate = duplicate.replace('endmodule', block + '\nendmodule', 1)
    for name in CONFIG[sid]:
        source = (task / 'solution' / (name + '.va')).read_text()
        duplicate += re.sub(r'\bmodule\s+' + name + r'\b', 'module private_' + name, source)
    return duplicate


def main():
    plan = json.loads((OUT / 'run-plan.json').read_text())
    plan = [r for r in plan if r['variant'] not in ('architecture-empty', 'architecture-bypass')]
    for sid, (producer, consumer) in CONFIG.items():
        task = next((ROOT / 'benchmark/tasks').glob('v2-spec-' + sid + '-*'))
        cases = build_cases(task, sid)
        (task / 'tests/cases.json').write_text(json.dumps(cases, indent=2) + '\n')
        for name in ('v2_structure.py',):
            shutil.copy2(ROOT / 'benchmark/checkers' / name, task / 'tests' / name)
        (task / 'tests/verify.py').write_text(
            'from v2_runtime import main\n'
            '# Explicit transitive import keeps prepare/sync self-contained.\n'
            'from v2_spec import evaluate as _external_dependency\n'
            'from v2_structure import evaluate\n'
            "if __name__=='__main__':main(evaluate)\n")
        contract = json.loads((task / 'tests/contract.json').read_text())
        contract['architecture_version'] = VERSION
        (task / 'tests/contract.json').write_text(json.dumps(contract, indent=2) + '\n')
        for variant in ('architecture-empty', 'architecture-bypass'):
            dest = OUT / 'candidates' / task.name / variant
            dest.mkdir(parents=True, exist_ok=True)
            for p in (task / 'solution').glob('*.va'):
                shutil.copy2(p, dest / p.name)
            if variant == 'architecture-empty':
                source = (dest / (producer + '.va')).read_text()
                # State-free shell with defined electrical outputs. A floating
                # pin could produce a backend failure instead of a graded
                # architecture rejection, so this negative drives reset values.
                body = 'analog begin\n' + ''.join(
                    f' V({n}) <+ {v};\n' for n, v in EMPTY_OUTPUTS[sid].items())
                (dest / (producer + '.va')).write_text(
                    source.split('analog begin', 1)[0] + body + 'end\nendmodule\n')
            else:
                (dest / 'dut.va').write_text(bypass_candidate(task, sid))
            plan.append(dict(task=str(task.relative_to(ROOT)), variant=variant,
                             candidate_directory=str(dest.relative_to(ROOT)), expected='fail',
                             semantic_behavior=('state-free producer shell, fixed reset-value outputs' if variant.endswith('empty') else
                                                'active required helpers bypassed by private correct chain'),
                             certification='pending-live-execution'))
    (OUT / 'run-plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    manifest_path = OUT / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for row in manifest['sources']:
        if row['source_id'] not in CONFIG:
            continue
        task = ROOT / row['assets']['task']
        row['architecture_version'] = VERSION
        row['conditions'] = [c['name'] for c in json.loads((task/'tests/cases.json').read_text())]
        for field, filename in [('instruction_sha256', 'instruction.md'),
                                ('contract_sha256', 'tests/contract.json'),
                                ('cases_sha256', 'tests/cases.json'),
                                ('checker_sha256', 'tests/verify.py')]:
            row['assets'][field] = hashlib.sha256((task/filename).read_bytes()).hexdigest()
        row['assets']['structure_checker_sha256'] = hashlib.sha256(
            (task/'tests/v2_structure.py').read_bytes()).hexdigest()
        row['variants'] = []
        for request in plan:
            if request['task'] != row['assets']['task']:
                continue
            directory = ROOT / request['candidate_directory']
            row['variants'].append(dict(id=request['variant'], expected=request['expected'],
                                        status='pending', semantic_behavior=request['semantic_behavior'],
                                        files={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                               for p in sorted(directory.glob('*.va'))}))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
