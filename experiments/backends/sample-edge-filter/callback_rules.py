"""Freeze one-factor Spectre callback probes and audit exact event observations.

Diagnostic variants never replace the original chain's strict phase checker.
Use callback_probe.py run for bounded, serial execution of frozen inputs.
"""
import argparse
from fractions import Fraction
import json
import math
from pathlib import Path
import re
from callback_probe import save, sha, stage_failure, read_native
from callback_policy import covers_windows


def freeze(original, output):
    output.mkdir(parents=True, exist_ok=False)
    source = (original / 'dut.va').read_text()
    deck = (original / 'tb.scs').read_text()
    settings = json.loads((original / 'requested_settings.json').read_text())
    bare = re.sub(r' strobetimes=\[[^]]*\]', '', deck)
    clean = re.sub(r'V(?:clk|rst) .*', lambda m: m[0].split(' type=')[0] +
                   ' type=dc dc=0', bare)
    dc = re.sub(r'Vu .*', lambda m: m[0].split(' type=')[0] +
                ' type=dc dc=0.25', clean)
    nominal = 4e-6
    variants = []

    def add(name, src, tb, reason, parent, start=1e-6, period=1e-6):
        variants.append((name, src, tb, dict(reason=reason, parent=parent,
                         start_s=start, period_s=period)))

    add('00-original-minimal', source, deck, 'Reproduce prior instrumented minimal case', 'prior')
    add('01-no-strobes', source, bare, 'Remove only forced observation times', '00-original-minimal')
    add('02-unused-inputs-dc', source, clean, 'Remove unused clock/reset PWL corners', '01-no-strobes')
    add('03-all-inputs-dc', source, dc, 'Remove remaining input PWL corners', '02-unused-inputs-dc')
    add('04-dc-repeat', source, dc, 'Bit-identical repeat in independent process', '03-all-inputs-dc')
    for name, old, new in [('05-ttol-zero','1e-12','0'),
                           ('06-ttol-small','1e-12','1e-20'),
                           ('07-ttol-large','1e-12','1e-8')]:
        add(name, source.replace(','+old+'))', ','+new+'))'), dc,
            'Change timer time tolerance only', '03-all-inputs-dc')
    for name, value in [('08-transres-zero','0'), ('09-transres-small','1e-24')]:
        add(name, source, dc.replace(' method=traponly', ' transres='+value+' method=traponly'),
            'Change transition resolution only', '03-all-inputs-dc')
    for name, value in [('10-step-half', settings['maxstep_s']/2),
                        ('11-step-third', settings['maxstep_s']/3)]:
        add(name, source, re.sub(r'maxstep=\S+', 'maxstep='+format(value,'.17g'), dc),
            'Change maximum time step only', '03-all-inputs-dc')
    for name, point in [('12-strobe-before-ulp', math.nextafter(nominal,-math.inf)),
                        ('13-strobe-at', nominal),
                        ('14-strobe-after-ulp', math.nextafter(nominal,math.inf)),
                        ('15-strobe-before-ttol', nominal-5e-13),
                        ('16-strobe-after-ttol', nominal+5e-13)]:
        add(name, source, dc.replace(' strobeoutput=', ' strobetimes=['+format(point,'.17g')+'] strobeoutput='),
            'Insert one forced time near fourth callback', '03-all-inputs-dc')
    binary = 2**-20
    add('17-binary-period', source.replace('9.9999999999999995e-07',format(binary,'.17g')), dc,
        'Change start and period to exact power-of-two', '03-all-inputs-dc', binary, binary)
    add('18-one-shot', re.sub(r'timer\([^)]*\)', 'timer(3.9999999999999998e-6,0,1e-12)', source),
        dc, 'One-shot event separates periodic accumulation', '03-all-inputs-dc', nominal, 0.)
    for name, tb in [('19-strobe-before-ttol-zero', variants[15][2]),
                     ('20-strobe-after-ttol-zero', variants[16][2])]:
        add(name, source.replace(',1e-12))', ',0))'), tb,
            'Change timer tolerance on forced-time probe', name.replace('19','15').replace('20','16').replace('-zero',''))
    for name, src, tb, meta in variants:
        work = output / name
        work.mkdir()
        (work/'dut.va').write_text(src)
        (work/'tb.scs').write_text(tb)
        actual = dict(settings)
        actual['maxstep_s'] = float(re.search(r'maxstep=(\S+)',tb)[1])
        save(work/'requested_settings.json', actual)
        save(work/'probe.json', meta)
    save(output/'MANIFEST.json', {str(p.relative_to(output)): sha(p)
                                  for p in sorted(output.rglob('*')) if p.is_file()})


def analyze(root, output, inputs):
    execution_manifest = json.loads((root/'MANIFEST.json').read_text())
    for name,digest in execution_manifest.items():
        if sha(root/name)!=digest:
            raise ValueError('changed execution artifact: '+name)
    manifest = json.loads((inputs/'MANIFEST.json').read_text())
    for name, digest in manifest.items():
        if sha(inputs/name) != digest:
            raise ValueError('changed frozen input: '+name)
    expected_names = sorted({str(Path(name).parent) for name in manifest if name.endswith('/probe.json')})
    if not expected_names:
        raise ValueError('no frozen probe cases')
    records = []
    for name in expected_names:
        work = root/name
        if not (work/'RESULT.json').exists():
            records.append(dict(probe=name, observation_check=False, callbacks=[], failure='missing RESULT'))
            continue
        for relative, digest in manifest.items():
            if str(Path(relative).parent)==name and sha(root/relative)!=digest:
                raise ValueError('executed input differs from frozen input: '+relative)
        execution = json.loads((work/'RESULT.json').read_text())
        meta = json.loads((work/'probe.json').read_text())
        rows = json.loads((work/'rows.json').read_text()) if (work/'rows.json').exists() else []
        if rows:
            raw = work/'psf/tran.tran.tran'
            if execution.get('raw_sha256')!=sha(raw) or read_native(raw,'spectre')!=rows:
                raise ValueError('native waveform identity/parsed rows mismatch')
        callbacks = []
        for match in re.finditer(r'CALLBACK\s+(\d+)\s+(\S+)\s+(\S+)',
                                 (work/'spectre.log').read_text(), re.M):
            n, t, q = int(match[1]), float(match[2]), float(match[3])
            if not math.isfinite(t) or not math.isfinite(q):
                raise ValueError('nonfinite callback observation')
            exact = Fraction(meta['start_s'])+(n-1)*Fraction(meta['period_s'])
            target = float(exact)
            native = next((r for r in rows if r['an']==n), None)
            callbacks.append(dict(n=n, time_s=t, time_hex=t.hex(), held=q,
                ideal_rational=str(exact), rounded_ideal_s=target,
                offset_from_rounded_ulp=(t-target)/math.ulp(target),
                offset_from_exact_s=float(Fraction(t)-exact),
                native_time_s=native['time'] if native else None,
                native_cb_s=native['cb'] if native else None,
                log_native_agree=bool(native and native['time']==t and native['cb']==t)))
        expected = 1 if not meta['period_s'] else math.floor(
            (Fraction(json.loads((work/'requested_settings.json').read_text())['stop_s'])-
             Fraction(meta['start_s']))/Fraction(meta['period_s']))+1
        schedule=list(map(float,re.search(r'@\(timer\(([^)]*)',(work/'dut.va').read_text())[1].split(',')))
        stop=json.loads((work/'requested_settings.json').read_text())['stop_s']
        records.append(dict(probe=work.name, metadata=meta, expected_count=expected,
            native_start_s=rows[0]['time'] if rows else None,native_end_s=rows[-1]['time'] if rows else None,
            timer_windows_covered=covers_windows(rows,*schedule,stop),
            callbacks=callbacks, execution=execution,
            observation_check=(not stage_failure(execution['execution']) and not execution.get('analysis_failure')
                and covers_windows(rows,*schedule,stop)
                and all(math.isfinite(v) for r in rows for v in r.values())
                and all(a['time']<b['time'] for a,b in zip(rows,rows[1:]))
                and [c['n'] for c in callbacks]==list(range(1,expected+1))
                and all(c['log_native_agree'] for c in callbacks)),
            source_sha256=sha(work/'dut.va'), deck_sha256=sha(work/'tb.scs'),
            raw_sha256=sha(work/'psf/tran.tran.tran') if rows else None))
    save(output, dict(records=records, expected_probe_count=len(expected_names),
                     input_manifest_sha256=sha(inputs/'MANIFEST.json'),
                     scope='Spectre-only diagnosis; original strict failures remain'))
    for row in records:
        print(row['probe'], 'observations='+str(row['observation_check']),
              'offsets='+str([c['offset_from_rounded_ulp'] for c in row['callbacks']]))
    if not records or not all(r['observation_check'] for r in records):
        raise SystemExit(1)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('mode', choices=['freeze','analyze'])
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--inputs', type=Path)
    args=parser.parse_args()
    if args.mode=='freeze':
        freeze(args.source,args.output)
    else:
        if args.inputs is None:
            parser.error('analyze requires --inputs for fixed denominator and input identity')
        analyze(args.source,args.output,args.inputs)
