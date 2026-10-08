"""Tamper calibration on disposable copies; never modify original observations."""
import argparse,json,shutil,tempfile
from pathlib import Path
from check import analyze

def calibrate(collection):
 analyze(collection/'spectre-output/runs')
 result={}
 with tempfile.TemporaryDirectory(prefix='transition-evidence-calibration-',dir=Path(__file__).parent) as tmp:
  copied=Path(tmp)/'collection';shutil.copytree(collection,copied)
  targets={'empty_unpacked_manifest':copied/'spectre-output/FILE_MANIFEST.json','replaced_known_psf':copied/'spectre-output/runs/three-arg--sparse/psf/tran.tran.tran'}
  for name,p in targets.items():
   original=p.read_bytes();p.write_bytes(b'{}\n' if name=='empty_unpacked_manifest' else original+b'changed_known_member\n')
   try:analyze(copied/'spectre-output/runs')
   except ValueError as exc:
    result[name]=dict(rejected=True,reason=str(exc))
    if 'unpacked member differs from archive' not in str(exc):raise AssertionError('unexpected refusal path') from exc
   else:raise AssertionError('tampered archive member was accepted')
   finally:p.write_bytes(original)
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('collection',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.write_text(json.dumps(calibrate(a.collection),indent=2)+'\n')
