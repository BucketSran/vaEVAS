"""Read-only diagnostic analysis against unchanged baseline contracts."""
import argparse, hashlib, json, math, re, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/dvs2-spectre-validation'))
from check_results import check, read_waveform


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def save(p,value):
    with p.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('root',type=Path);ap.add_argument('output',type=Path)
    args=ap.parse_args();root=args.root;output=args.output
    assert not output.exists() and not output.resolve().is_relative_to(root.resolve())
    manifest=read(root/'FILE_MANIFEST.json')
    for rel,d in manifest.items():
        p=root/rel
        assert p.resolve().is_relative_to(root.resolve()) and sha(p)==d['sha256'] and p.stat().st_size==d['bytes']
    baseline=ROOT/'runs/dvs2-four-backend-20260928-01'
    receipt=read(ROOT/'experiments/dvs2-four-backend-validation/results/RECEIPT.json')
    assert sha(baseline/'FILE_MANIFEST.json')==receipt['file_manifest_sha256']
    matrix_path=ROOT/'experiments/dvs2-four-backend-validation/results/matrix.json'
    assert sha(matrix_path)==receipt['matrix_sha256']
    matrix=read(matrix_path);lookup={(r['backend'],r['condition'],r['profile']):r for r in matrix['records']}
    out=[]
    for r in read(root/'RESULTS.json'):
        w=root/'probes'/r['id'];b=r['backend'];c=read(w/'condition.json')
        source=baseline/'runs'/b/r['condition']/r['profile'];original=read(source/'result.json')
        assert all(sha(source/n)==h for n,h in r['baseline_hashes'].items())
        item={k:r[k] for k in ['id','backend','condition','profile','mutation','prediction']}
        item['baseline_status']=lookup[b,r['condition'],r['profile']]['analysis']['status']
        item['input_hashes']={n:sha(w/n) for n in ['dut.va','tb.scs','condition.json']}
        if 'waveform' in r:
            assert sha(w/r['waveform'])==r['waveform_sha256']
            rows=read_waveform(w/r['waveform'],b);item['analysis']=check(rows,c)
            item['waveform_sha256']=r['waveform_sha256'];item['first_sample']=rows[0];item['last_sample']=rows[-1]
            if b=='gnucap':
                item['logging_only_waveform_identical']=r['waveform_sha256']==original['waveform_sha256']
                assert item['logging_only_waveform_identical'],r['id']
                log=(w/'simulate.log').read_text()
                item['trace']=[dict(line=i,text=line) for i,line in enumerate(log.splitlines(),1) if '[DEBUG-dvs2b]' in line]
                item['trace_log_sha256']=sha(w/'simulate.log')
            if r['id'].startswith('evas-s1'):
                item['last_write_models_max_residual_v']={
                    'bias':max(abs(x['vout']-.125) for x in rows),
                    'last_input_contribution':max(abs(x['vout']+.5*x['v']) for x in rows),
                    'correct_sum':max(abs(x['vout']-(1.5*x['u']-.5*x['v']+.125)) for x in rows)}
        elif b=='openvaf_ngspice':
            log=(w/'compile.log').read_text();start=log.index('Optimized evaluation MIR');end=log.index('Compilation unit:')
            item.update(compile_exit_code=r['compile']['exit_code'],evaluation_mir=log[start:end].strip(),compile_log_sha256=sha(w/'compile.log'))
        else:
            log=(w/'simulate.log').read_text()
            item.update(execution_exit_code=r['execution']['exit_code'],error_lines=[line for line in log.splitlines() if 'ERROR' in line])
        out.append(item);print(r['id'],item.get('analysis',{}).get('status',item.get('error_lines','MIR')),flush=True)
    family=lambda c: 'event' if c.startswith(('v3-','v4-','e1-','e2-','c1-')) else 'timer' if c.startswith('v5-') else 'filter_or_filter_composition' if c.startswith(('v6-','c2-')) else 'implicit_equation' if c.startswith('v7-') else 'integrator' if c.startswith('d1-') else 'phase' if c.startswith('d2-') else 'contribution_sum' if c.startswith('s1-') else 'static'
    failures={b:{p:dict(Counter(family(r['condition']) for r in matrix['records'] if r['backend']==b and r['profile']==p and r['analysis']['status']!='observations_within_targets')) for p in ['base','fine']} for b in ['evas','openvaf_ngspice','gnucap']}
    output.mkdir(parents=True)
    result=dict(run_id=root.name,baseline_matrix_sha256=sha(matrix_path),analyzer_sha256=sha(Path(__file__)),baseline_failure_families=failures,records=out,formal_dvs_qualification='I')
    save(output/'probes.json',result)
    stages=read(root/'STAGE_COUNTS.json');assert stages=={'simulate':13,'compile':5}
    archive=root.with_suffix('.tar.gz')
    save(output/'RECEIPT.json',dict(run_id=root.name,host_alias='thu-sui',input_manifest_sha256=sha(root/'INPUT_MANIFEST.json'),file_manifest_sha256=sha(root/'FILE_MANIFEST.json'),raw_archive_sha256=sha(archive),raw_archive_bytes=archive.stat().st_size,verified_archived_files=len(manifest),probes_sha256=sha(output/'probes.json'),stage_counts=stages,probe_count=len(out),runner_sha256=sha(root/'run.py'),analyzer_sha256=sha(Path(__file__)),baseline_matrix_sha256=sha(matrix_path),timeout_count=sum(r.get('execution',{}).get('timed_out',False)+r.get('compile',{}).get('timed_out',False) for r in read(root/'RESULTS.json')),comparison_scores_changed=False))
    print(json.dumps(failures,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
