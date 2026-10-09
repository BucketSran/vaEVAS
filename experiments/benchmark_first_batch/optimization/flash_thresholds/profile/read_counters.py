"""Read trusted instrumented diagnostic archives; never enter timed denominator."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import tarfile

ROOT=Path(__file__).parent


def read(archive,role):
    source=(ROOT/(role+'.va')).read_bytes()
    with tarfile.open(archive) as tar:
        report=json.loads(tar.extractfile('run/work/verifier/report.json').read())
        if report.get('status')!='completed' or report.get('reward')!=1:raise ValueError('profiling must preserve independent functional correctness')
        records=[]
        for case in report['cases']:
            if case['passed'] is not True or case['returncode']!=0:raise ValueError('profiling simulation failed')
            prefix=f'run/work/verifier/{case["name"]}'
            actual=tar.extractfile(prefix+'/original/dut.va').read()
            if actual!=source or tar.extractfile(prefix+'/dut.va').read()!=source:
                raise ValueError('profiling source is not the frozen trusted instrumented model')
            merged=tar.extractfile(prefix+'/stdout.log').read()
            matches=re.findall(rb'(?:^|[.0-9])profile\s+callbacks=\s*(\d+)\s+comparisons=\s*(\d+)\s+samples=\s*(\d+)\s*$',merged,re.M)
            if len(matches)!=1:raise ValueError('missing or ambiguous profile counter line')
            callbacks,comparisons,samples=map(int,matches[0])
            if samples!=case['expected_samples'] or not callbacks or not comparisons:raise ValueError('profiling did not perform expected conversions')
            records.append(dict(case=case['name'],role=role,passed=True,preserved_callbacks=callbacks,
                                preserved_comparisons=comparisons,observed_samples=samples,
                                source_sha256=hashlib.sha256(source).hexdigest(),merged_stream_sha256=hashlib.sha256(merged).hexdigest(),
                                graded_waveform_sha256=case['waveform_sha256']))
    return dict(kind='non_timed_trusted_instrumented_profile',archive_sha256=hashlib.sha256(Path(archive).read_bytes()).hexdigest(),
                counter_semantics='saved simulator state; rejected attempts may be rolled back',records=records)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--role',choices=['baseline','reference'],required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise FileExistsError('diagnostic output must be new')
    args.output.write_text(json.dumps(read(args.archive,args.role),indent=2)+'\n')

if __name__=='__main__':main()
