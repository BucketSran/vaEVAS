"""Prepare immutable ADC calibration inputs without launching a simulator."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
TASK=ROOT/'benchmark/tasks/va08-adc-linearity'


def prepare(output):
    output.mkdir(parents=True,exist_ok=False)
    source=(TASK/'solution/reference.va').read_text()
    count='        hits[code]=hits[code]+1;'
    trace='        $fwrite(sample_file,"%d,%.17g,%d\\n",n,$abstime,code);'
    variants={'reference':source,
              'old-code':source.replace('timer(5.75u,1u)','timer(5.25u,1u)'),
              'missing-first':source.replace(count,'        if (n>0) '+count.strip()).replace(trace,'        if (n>0) '+trace.strip()),
              'missing-last':source.replace(count,'        if (n<4095) '+count.strip()).replace(trace,'        if (n<4095) '+trace.strip()),
              'all-samples':source.replace('254.0*hits[k]/internal_count','254.0*hits[k]/4096.0'),
              'reversed-bits':source,
              'ideal-only':source.replace('dnl=254.0*hits[k]/internal_count-1.0;','dnl=0;')}
    for bit in range(8):
        variants['reversed-bits']=variants['reversed-bits'].replace(
            f'if (V(dout[{bit}])>=0.5) code=code+{1<<bit};',
            f'if (V(dout[{bit}])>=0.5) code=code+{1<<(7-bit)};')
    for name,text in variants.items(): (output/(name+'.va')).write_text(text)
    spec=importlib.util.spec_from_file_location('adc',ROOT/'benchmark/checkers/adc_linearity.py')
    adc=importlib.util.module_from_spec(spec);spec.loader.exec_module(adc)
    cases=json.loads((TASK/'tests/cases.json').read_text())
    for case in cases:
        work=output/case['name'];work.mkdir()
        (work/'adc.va').write_text(adc.adc_source(case['thresholds'],case['delay']))
        (work/'tb.scs').write_text(adc.netlist())
    files={str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted(output.rglob('*')) if p.is_file()}
    manifest=dict(status='prepared_only',simulator_executed=False,files=files,
                  checker_sha256=adc.sha(ROOT/'benchmark/checkers/adc_linearity.py'),
                  cases_sha256=adc.sha(TASK/'tests/cases.json'),
                  resources=dict(case_timeout_s=90,verifier_timeout_s=600,threads=1,cpus=1,memory_mb=1024,storage_mb=2048),
                  expected=dict(reference='4/4 pass',mutants='6 targeted single-case rejections; not a full cross product'),
                  calibration_cases={'old-code':'ideal-fast','missing-first':'ideal-fast','missing-last':'ideal-fast','all-samples':'endpoint-shift','reversed-bits':'alternating-slow','ideal-only':'alternating-slow'},
                  argv=['spectre','-64','tb.scs','+log','spectre.log','-format','psfascii','-raw','psf','+lqtimeout','5','+mt=1'])
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(prepare(args.output.resolve()),indent=2))
