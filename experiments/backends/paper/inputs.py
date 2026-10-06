"""Materialize a new paper batch without compiling or launching a backend.

Historical comparison plans and contracts are not imported or modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[3]
BACKENDS = ('spectre', 'evas', 'openvaf_r_ngspice', 'gnucap_modelgen')


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open('x') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')


def binding(card):
    """Select the last declared module, preserving the card's actual hierarchy."""
    modules = re.findall(r'\bmodule\s+(\w+)\s*\(([^)]*)\)\s*;', card['source'])
    if not modules:
        raise ValueError('no explicit module ports')
    module, ports = modules[-1]
    ports = [p.strip() for p in ports.split(',')]
    if set(ports) != set(card['observables']):
        raise ValueError('top module ports differ from observables')
    return {'top_module': module, 'instance': 'dut', 'ports': ports,
            'parameters': card['parameters'], 'hierarchy': 'preserve exact VA source',
            'source_legality': 'pending actual source and backend qualification'}


def requested_times(card, contract, T):
    """Requested output times, never a certificate of accepted-step accuracy."""
    stop = card['stop_T'] * T
    count = math.ceil(stop / contract['sample_gap_s'])
    times = {i * stop / count for i in range(count + 1)}
    for window in card['observation_windows']:
        start, end = window['start_T'] * T, window['end_T'] * T
        count = math.ceil((end-start) / window['max_gap_s'])
        times.update(start + i*(end-start)/count for i in range(count+1))
        times.add(window['center_T'] * T)
    times.update(a['t_T'] * T for a in card['anchors'])
    return sorted(times)


def breakpoint_requests(card, T):
    """Disconnected ideal-source corners; requested events, not accepted proof.

    Prefer explicit centers/anchors over nearly identical floating grid points.
    One extra subdivision leaves room for this 3fs coalescing.
    """
    stop=card['stop_T']*T
    critical={0.0,stop,*(w['center_T']*T for w in card['observation_windows']),
              *(a['t_T']*T for a in card['anchors'])}
    points=set(critical)
    for w in card['observation_windows']:
        start,end=w['start_T']*T,w['end_T']*T
        n=math.ceil((end-start)/w['max_gap_s'])+1
        for i in range(n+1):
            t=start+i*(end-start)/n
            if not any(abs(t-c)<3e-15 for c in critical):
                points.add(t)
    ordered=sorted(points)
    # Two native rows per requested/global point is a planning allowance, not
    # a bound on adaptive solver work. Runtime limits remain authoritative.
    estimated_rows=2*(math.ceil(stop/2e-10)+len(ordered)+1)
    waveform_bytes=estimated_rows*(len(card['observables'])+2)*32
    if waveform_bytes>32*1024**2*.8:
        raise ValueError('local breakpoint output estimate exceeds file budget')
    return {'schema_version':1,'mechanism':'disconnected ideal PWL source corners',
            'auxiliary_node':'paper_observer','coupling':'only ground shared; no DUT port or stimulus connection',
            'installed_semantics':'unknown; primary source mapping and actual preflight required',
            'gnucap_requested_dtmin_s':1e-15,'critical_coalescing_s':3e-15,
            'records':[{'request_id':f"{card['id']}:breakpoint:{i}",'time_s':t} for i,t in enumerate(ordered)],
            'estimated_rows':estimated_rows,'estimated_waveform_bytes':waveform_bytes,
            'estimated_condition_bytes':2*waveform_bytes+2*1024**2,
            'file_limit_bytes':32*1024**2,'condition_limit_bytes':256*1024**2,
            'estimate_claim':'planning only; actual output size and native origins must be measured'}


def gnucap_observer(records):
    """SPICE + continuation avoids the snapshot's 4096-byte physical read buffer.

    Only complete time/value pairs are moved; decimal tokens and order are exact.
    The logical source still has one independent node and ground connection.
    """
    lines=[]
    line='Vpaper_observer paper_observer 0 PWL('
    for i,record in enumerate(records):
        pair=f"{record['time_s']:.17g} {i%2}"
        if len(line)+1+len(pair)+1>240:
            lines.append(line)
            line='+'
        line+=' '+pair
    return '\n'.join([*lines,line+')'])


def decks(card, settings, bind, times, breakpoints):
    ports = ' '.join(bind['ports'])
    params = ' '.join(f'{k}={v:.17g}' for k, v in bind['parameters'].items())
    spice_sources, spectre_sources = [], []
    for name, stimulus in card['stimulus'].items():
        points = stimulus['points_s_V']
        wave = ' '.join(f'{t:.17g} {v:.17g}' for t,v in points)
        spice_sources.append(f'V{name} {name} 0 PWL({wave})')
        spectre_sources.append(f'V{name} ({name} 0) vsource type=pwl wave=[{wave}]')
    observer_wave=' '.join(f"{r['time_s']:.17g} {i%2}" for i,r in enumerate(breakpoints['records']))
    spice_sources.append('Vpaper_observer paper_observer 0 PWL('+observer_wave+')')
    signals = ' '.join(f'v({p})' for p in bind['ports'])
    stop, step = settings['stop_s'], settings['maxstep_s']
    spice_step = settings['spice_maxstep_s']
    strobes = ' '.join(f'{t:.17g}' for t in times)
    options = f"reltol={settings['reltol']:.17g} vntol={settings['vabstol_V']:.17g} abstol={settings['iabstol_A']:.17g}"
    spectre = '\n'.join(['simulator lang=spectre','ahdl_include "dut.va"', *spectre_sources,
        f"dut ({ports}) {bind['top_module']} {params}",
        f"simulatorOptions options reltol={settings['reltol']:.17g} vabstol={settings['vabstol_V']:.17g} iabstol={settings['iabstol_A']:.17g}",
        f'tran tran stop={stop:.17g} maxstep={step:.17g} errpreset=conservative method=traponly strobetimes=[{strobes}] strobeoutput=all',
        'save ' + ' '.join(bind['ports'])])+'\n'
    ng = '\n'.join(['Paper '+card['id'], *spice_sources,
        f"N0 {ports} model0",f".model model0 {bind['top_module']} {params}",
        '.options '+options+' method=trap','.control','pre_osdi dut.osdi',
        'set filetype=ascii','set wr_singlescale','set wr_vecnames','set numdgt=17','option',
        f'tran {spice_step:.17g} {stop:.17g} 0 {spice_step:.17g}',
        'wrdata waveform.txt '+signals,'option','quit','.endc','.end'])+'\n'
    override = ' #('+', '.join(f'.{k}({v:.17g})' for k,v in bind['parameters'].items())+')' if params else ''
    gc = '\n'.join(['load mgsim','load ./dut.so','verilog',
        f"\\{bind['top_module']}{override} dut({','.join(bind['ports'])});",'spice',
        'Vbench_ref bench_ref 0 0',*spice_sources[:-1],gnucap_observer(breakpoints['records']),'.options numdgt=17 dtmin=1e-15 short=1e-9 '+options,
        '.options','.print tran '+signals+' v(bench_ref)',
        f'.tran {spice_step:.17g} {stop:.17g} 0 {spice_step:.17g} trace alltime > waveform.txt','.end'])+'\n'
    evas = json.dumps({'source': 'dut.va','instances': [{'name':'dut','module':bind['top_module'],
        'ports':{p:p for p in bind['ports']},'parameters':bind['parameters']}],
        'inputs':{n:s['points_s_V'] for n,s in card['stimulus'].items()},
        'requested_times': 'requested_times.json','stop':stop,'max_step':step,
        'reltol':settings['reltol'],'vabstol':settings['vabstol_V']},indent=2)+'\n'
    return {'spectre': ('tb.scs',spectre),'evas':('request.json',evas),
            'openvaf_r_ngspice':('tb.cir',ng),'gnucap_modelgen':('tb.gc',gc)}


def freeze(cards_path, output, *, stage_timeout_s=90, license_timeout_s=30):
    data = json.loads(cards_path.read_text())
    cards = data['cards']
    if len(cards) != 12 or len({c['id'] for c in cards}) != 12:
        raise ValueError('paper A1 requires twelve distinct frozen cards')
    if not (0 < license_timeout_s <= 30 and license_timeout_s <= stage_timeout_s <= 90):
        raise ValueError('bounded timeout required')
    output.mkdir(parents=True, exist_ok=False)
    (output/'core.json').write_bytes(cards_path.read_bytes())
    plan = []
    for card in cards:
        bind = binding(card)
        settings = {'stop_s':card['stop_T']*data['units']['T_s'], 'maxstep_s':2e-10,
                    'reltol':1e-5,'vabstol_V':1e-7,'iabstol_A':1e-12,
                    'output_request':'native records plus prescribed exact centers; requested grid does not qualify interpolation',
                    'integration_method':'traponly/trap for SPICE; unsupported by EVAS'}
        physical = {**card, 'stimulus':{n:{'points_s_V':[[t*data['units']['T_s'],v] for t,v in s['points_T_V']]}
                                         for n,s in card['stimulus'].items()}}
        times = requested_times(card,data['shared_contract'],data['units']['T_s'])
        breakpoints=breakpoint_requests(card,data['units']['T_s'])
        settings.update(spice_maxstep_s=2e-10,
                        spice_output_estimate_bytes=breakpoints['estimated_waveform_bytes'],
                        spice_observation_strategy='global 200ps plus disconnected PWL local/center breakpoint requests; actual preflight required',
                        spectral_strobe_strategy='prescribed times; strobeoutput=all; actual origin qualification pending')
        generated = decks(physical,settings,bind,times,breakpoints)
        for backend in BACKENDS:
            work = output/'runs'/backend/card['id']
            work.mkdir(parents=True)
            (work/'dut.va').write_bytes(card['source'].encode())
            save(work/'condition.json',card)
            save(work/'binding.json',bind)
            save(work/'requested_settings.json',settings)
            save(work/'requested_times.json',times)
            save(work/'breakpoint_requests.json',breakpoints)
            filename, text = generated[backend]
            (work/filename).write_text(text)
            save(work/'qualification_requirements.json',{
                'source_validated':False,'deck_validated':False,'native_counters_required':True,
                'native_phase_required':card['id'] in ('CP-02','CO-VCO-01'),
                'global_max_gap_s':data['shared_contract']['sample_gap_s'],
                'local_windows':card['observation_windows'],'time_unit':'s','voltage_unit':'V',
                'input_error_V':data['shared_contract']['input_error_V'],
                'independent_input_bounds_required':True,
                'observation_error_targets':data['shared_contract']['required_observation_error'],
                'exact_centers_required':True,'interpolation_bounds_required':True,
                'effective_settings':'unknown until tool readback','tool_identity':'unknown until explicit tool probe'})
            plan.append({'backend':backend,'condition':card['id'],'work':str(work.relative_to(output)),
                         'deck':filename,'source_sha256':sha(work/'dut.va'),
                         'condition_identity':identity(card),'status':'not_run'})
    source_paths = [Path(__file__), Path(__file__).with_name('observations.py'),
                    Path(__file__).with_name('runner.py'), Path(__file__).with_name('process.py'),
                    Path(__file__).with_name('settings_readback.py'),
                    Path(__file__).with_name('OBSERVATION_METHODS.md'),
                    ROOT/'experiments/archive/dvs2-starter-pilot/analyze.py',
                    ROOT/'experiments/archive/dvs2-starter-pilot/suite.py',
                    ROOT/'experiments/backends/dvs2-spectre-validation/report.py']
    source_identity = {}
    for path in source_paths:
        relative = str(path.relative_to(ROOT))
        target = output/'adapter_sources'/relative
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(path.read_bytes())
        source_identity[relative] = sha(path)
    save(output/'ADAPTER_IDENTITY.json',source_identity)
    runtime_paths = sorted(p for directory in ('evas/src','evas/rust_core') for p in (ROOT/directory).rglob('*')
                           if p.is_file() and (p.suffix in ('.py','.rs','.toml') or p.name=='Cargo.lock')
                           and 'target' not in p.parts and '__pycache__' not in p.parts)
    runtime_paths.append(ROOT/'evas/pyproject.toml')
    save(output/'RUNTIME_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in runtime_paths})
    checker_paths = sorted((ROOT/'evas/validation/paper').glob('*.py'))
    save(output/'CHECKER_IDENTITY.json',{str(p.relative_to(ROOT)):sha(p) for p in checker_paths})
    save(output/'RUN_PLAN.json',plan)
    save(output/'provenance.json',{'batch_id':data['batch_id'],'configurations':48,
        'simulations_per_backend':12,'max_simulation_launches':48,'automatic_retries':0,
        'stage_timeout_s':stage_timeout_s,'license_timeout_s':license_timeout_s,
        'memory_limit_bytes':4*1024**3,'file_limit_bytes':32*1024**2,'threads':1,
        'cards_sha256':sha(cards_path),'checker_status':'frozen' if checker_paths else 'pending checker integration','freeze_status':'prepared; coordinator approval required before execution',
        'tool_identity_requirement':'version, binary hash, compiler/build flags and pinned environment before actual results'})
    save(output/'INPUT_MANIFEST.json',{str(p.relative_to(output)):{'sha256':sha(p),'bytes':p.stat().st_size}
                                      for p in sorted(output.rglob('*')) if p.is_file()})
    return plan


def verify(root):
    manifest = json.loads((root/'INPUT_MANIFEST.json').read_text())
    files = {str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p != root/'INPUT_MANIFEST.json'}
    if files != set(manifest):
        raise ValueError('frozen file set drift')
    for rel, entry in manifest.items():
        p = (root/rel).resolve()
        if not p.is_relative_to(root.resolve()) or sha(p)!=entry['sha256'] or p.stat().st_size!=entry['bytes']:
            raise ValueError('frozen input drift: '+rel)
    plan = json.loads((root/'RUN_PLAN.json').read_text())
    cards = json.loads((root/'core.json').read_text())['cards']
    expected = {(b,c['id']) for b in BACKENDS for c in cards}
    if len(plan)!=48 or {(r['backend'],r['condition']) for r in plan}!=expected:
        raise ValueError('paper plan drift')
    return plan


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output',type=Path)
    parser.add_argument('--cards',type=Path,default=ROOT/'evas/validation/paper/core-v1.json')
    args = parser.parse_args()
    print(f'Prepared {len(freeze(args.cards,args.output))} configurations; no backend launched')
