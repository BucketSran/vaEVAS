"""Spectre-only callback instrumentation; never substitutes for the original cases.

Freeze source/deck variants first, then run each once with the shared process and
identity checks. $strobe and the cb output observe $abstime inside the callback.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/backends/paper'))
from inputs import save, sha
from runner import preflight, verify_tool, stage, stage_failure, effective_settings
from observations import read_native

LIMITS = dict(stage_timeout_s=90, license_timeout_s=30,
              memory_limit_bytes=4*1024**3, file_limit_bytes=32*1024**2, threads=1)


def freeze(original, output):
    output.mkdir(parents=True, exist_ok=False)
    old_source = (original / 'dut.va').read_text()
    old_deck = (original / 'tb.scs').read_text()
    # Instrument both the callback log and a persistent last-callback node.
    source = old_source.replace('h,e,f,n)', 'h,e,f,n,cb)')
    source = source.replace('h,e,f,n;', 'h,e,f,n,cb;')
    source = source.replace('ah,ae,af,an)', 'ah,ae,af,an,cb)')
    source = source.replace('ah,ae,af,an;', 'ah,ae,af,an,cb;')
    source = source.replace('real q;', 'real q; real callback;')
    source = source.replace('count=0;', 'count=0; callback=0;')
    source = source.replace('count=count+1;', 'count=count+1; callback=$abstime; '
                            '$strobe("CALLBACK %0d %.17g %.17g",count,callback,q);')
    source = source.replace('V(n)<+count;', 'V(n)<+count; V(cb)<+callback;')
    deck = old_deck.replace('ah ae af an)', 'ah ae af an cb)')
    deck = deck.replace('save u clk rst ah ae af an', 'save u clk rst ah ae af an cb')
    minimal = '\n'.join(line for line in source.splitlines()
                        if not line.startswith('V(e)<+') and not line.startswith('V(f)<+'))
    # Tie removed outputs to avoid unrelated floating nodes in the control.
    minimal = minimal.replace('end endmodule', 'V(e)<+0; V(f)<+0;\nend endmodule', 1)
    variants = [('original', old_source, old_deck),
                ('instrumented', source, deck),
                ('minimal', minimal, deck),
                ('minimal-no-strobetimes', minimal,
                 re.sub(r' strobetimes=\[[^]]*\]', '', deck))]
    # Binary-exact start/period is a numeric-representation control only.
    binary = minimal.replace('9.9999999999999995e-07,9.9999999999999995e-07',
                             '9.5367431640625e-07,9.5367431640625e-07')
    variants.append(('binary-no-strobetimes', binary,
                     re.sub(r' strobetimes=\[[^]]*\]', '', deck)))
    for name, src, tb in variants:
        work = output / name
        work.mkdir()
        (work / 'dut.va').write_text(src)
        (work / 'tb.scs').write_text(tb)
        shutil.copy2(original / 'requested_settings.json', work / 'requested_settings.json')
    save(output / 'MANIFEST.json', {str(p.relative_to(output)): sha(p)
                                   for p in sorted(output.rglob('*')) if p.is_file()})


def freeze_roots(output):
    """Same physical model for both simulators; no callback instrumentation."""
    output.mkdir(parents=True, exist_ok=False)
    for delay in (0., .125):
        for accuracy, tol in [('loose', 1e-3), ('tight', 1e-12)]:
            work = output / ('delay-' + str(delay) + '-' + accuracy)
            work.mkdir()
            source = ('`include "disciplines.vams"\n'
                'module dut(u,e,y,n); input u; output e,y,n; electrical u,e,y,n; integer q;\n'
                'analog begin @(initial_step) q=0; '
                f'@(cross(pow(V(u),2)-2,1,{tol:.17g},{tol:.17g})) q=1;\n'
                f'V(e)<+transition(q,{delay:.17g},0.5,0.5);\n'
                "V(y)<+laplace_nd(V(e),'{1},'{1,0.25}); V(n)<+q; end endmodule\n")
            settings = dict(stop_s=3., maxstep_s=1/256, reltol=1e-9,
                            vabstol_V=1e-11, iabstol_A=1e-15)
            tb = ('simulator lang=spectre\nahdl_include "dut.va"\n'
                  'Vu (u 0) vsource type=pwl wave=[0 0 3 3]\n'
                  'dut (u e y n) dut\n'
                  'simulatorOptions options precision="%.17g" reltol=1e-9 vabstol=1e-11 iabstol=1e-15\n'
                  'tran tran stop=3 maxstep=0.00390625 errpreset=conservative method=traponly '
                  'strobetimes=[0 1 1.75 2.5 3] strobeoutput=all compression=no skipcount=1\n'
                  'save u e y n\n')
            (work/'dut.va').write_text(source)
            (work/'tb.scs').write_text(tb)
            save(work/'requested_settings.json', settings)
            save(work/'case.json', dict(delay=delay, root_tolerance=tol,
                                       eva_voltage_budgets=[1e-10,1e-3], stop=3., inputs={'u':[[0,0],[3,3]]}))
    save(output / 'MANIFEST.json', {str(p.relative_to(output)): sha(p)
                                   for p in sorted(output.rglob('*')) if p.is_file()})


def run(inputs, output, profile_path, only=None):
    manifest = json.loads((inputs / 'MANIFEST.json').read_text())
    for name, digest in manifest.items():
        if sha(inputs / name) != digest:
            raise ValueError('changed input: ' + name)
    output.mkdir(parents=True, exist_ok=False)
    profile = json.loads(profile_path.read_text())
    tool, env = preflight('spectre', profile, output, LIMITS)
    save(output / 'TOOL_IDENTITY.json', tool)
    records = []
    for original in sorted(p for p in inputs.iterdir() if p.is_dir()):
        if only and original.name not in only:
            continue
        verify_tool(tool, profile, env)
        work = output / original.name
        shutil.copytree(original, work)
        (work / 'run.csh').write_text(tool['setup'] + tool['binary'] +
            ' -64 tb.scs +log spectre.log -format psfascii -raw psf +lqtimeout 30 +mt=1\nexit $status\n')
        result = stage(['/bin/csh', '-f', 'run.csh'], work, 'simulate', LIMITS)
        record = dict(probe=original.name, execution=result,
                      source_sha256=sha(work/'dut.va'), deck_sha256=sha(work/'tb.scs'))
        raw = work / 'psf/tran.tran.tran'
        if not stage_failure(result) and raw.exists():
            try:
                save(work / 'rows.json', read_native(raw, 'spectre'))
                record.update(raw_sha256=sha(raw), effective_settings=effective_settings(work,'spectre'))
            except Exception as error:
                record['analysis_failure'] = str(error)
        elif not stage_failure(result):
            record['analysis_failure'] = 'Missing native transient output'
        save(work / 'RESULT.json', record)
        records.append(record)
        print(original.name, 'execution_failure=' + str(stage_failure(result)),
              'analysis_failure=' + str(record.get('analysis_failure')), flush=True)
        if not result.get('cleanup', {}).get('complete', False):
            raise RuntimeError('incomplete cleanup')
    save(output / 'RESULTS.json', records)
    save(output / 'MANIFEST.json', {str(p.relative_to(output)): sha(p)
                                   for p in sorted(output.rglob('*')) if p.is_file()})
    if not records or any(stage_failure(r['execution']) or r.get('analysis_failure') for r in records):
        raise SystemExit(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze', 'roots', 'run'])
    parser.add_argument('inputs', type=Path)
    parser.add_argument('output', type=Path, nargs='?')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--only', nargs='+')
    args = parser.parse_args()
    if args.mode == 'roots':
        if args.output is not None:
            parser.error('roots takes only its new output directory')
        freeze_roots(args.inputs)
    elif args.output is None:
        parser.error('freeze/run require input and output directories')
    elif args.mode == 'freeze':
        freeze(args.inputs, args.output)
    else:
        if args.profile is None:
            parser.error('run requires --profile')
        run(args.inputs, args.output, args.profile, args.only)
