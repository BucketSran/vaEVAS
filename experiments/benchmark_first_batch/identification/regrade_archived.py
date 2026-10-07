"""Regrade immutable actual Spectre PSF after a criteria-only extension.

Rejects changed old probes, stimuli, candidate, or parser assumptions. This is
regrading retained actual evidence, not a new backend execution receipt.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tarfile
from diagnose_sh_archive import rows
from prepare_candidates import ROOT

sys.path.insert(0,str(ROOT/'benchmark/checkers'))
from first_batch_identification import evaluate


def digest(content):
    return hashlib.sha256(content).hexdigest()


def regrade(task,archive_root,candidate):
    cases_path=ROOT/'benchmark/tasks'/task/'tests/cases.json'
    cases={c['name']:c for c in json.loads(cases_path.read_text())}
    results=[]
    for archive in sorted(archive_root.glob('remote/*/archive/job.tar.gz')):
        with tarfile.open(archive) as tf:
            def read(suffix):
                members=[m for m in tf.getmembers() if m.name.endswith(suffix)]
                if len(members)!=1:raise ValueError('ambiguous archive member '+suffix)
                return tf.extractfile(members[0]).read()
            original=json.loads(read('run/work/tests/cases.json'))
            original_report=json.loads(read('run/work/verifier/report.json'))
            for old in original:
                c=cases[old['name']]
                if old!={k:v for k,v in c.items() if k!='sample_grids'}:
                    raise ValueError('changed old contract; only sample_grids extension may be regraded')
                source=read(f"run/work/verifier/{c['name']}/dut.va")
                if source!=candidate.read_bytes():raise ValueError('candidate identity changed')
                wave=rows(read(f"run/work/verifier/{c['name']}/psf/tran.tran.tran").decode())
                results.append(dict(case=c['name'],archive_sha256=digest(archive.read_bytes()),
                    candidate_sha256=digest(source),spectre_version=original_report['spectre_version'],
                    old_contract_and_stimulus_unchanged=True,**evaluate(wave,c)))
    if not results:raise ValueError('no archived actual waveform')
    return dict(kind='existing_actual_spectre_waveform_regrading',task=task,source_run=archive_root.name,
        cases_sha256=digest(cases_path.read_bytes()),checker_sha256=digest((ROOT/'benchmark/checkers/first_batch_identification.py').read_bytes()),
        scope='Regrade immutable actual archived PSF against new sample grids. No simulator launched; not a new frozen-run execution receipt.',cases=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--task',required=True)
    parser.add_argument('--archive-root',type=Path,required=True);parser.add_argument('--candidate',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(regrade(args.task,args.archive_root,args.candidate),indent=2))
