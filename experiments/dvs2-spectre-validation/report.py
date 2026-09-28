"""Post-run metadata audit and report; does not modify inputs or scoring."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def settings(log):
    result={}
    units={'s':1,'ms':1e-3,'us':1e-6,'ns':1e-9,'ps':1e-12,'fs':1e-15}
    for name in ['vabstol','iabstol','reltol','stop','step','maxstep','method']:
        matches=re.findall(r'^\s*'+name+r' = ([^\n]+)$',log,re.M)
        if not matches: raise ValueError('missing effective setting: '+name)
        values=[]
        for text in matches:
            text=text.split(',')[0].strip()
            if name=='method': values.append(text)
            else:
                tokens=text.split()
                value=float(tokens[0])
                if len(tokens)>1: value*=units[tokens[1]]
                values.append(value)
        if any(v!=values[0] for v in values): raise ValueError('inconsistent effective setting: '+name)
        result[name]=values[0]
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path)
    parser.add_argument('analysis',type=Path)
    parser.add_argument('archive',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('refuse to overwrite report directory')
    analysis=json.loads(args.analysis.read_text()); root=args.root
    assert analysis['file_manifest_sha256']==sha(root/'FILE_MANIFEST.json')
    audit=[]; warnings=Counter(); groups=defaultdict(Counter); histories=defaultdict(Counter)
    for r in analysis['records']:
        work=root/'runs'/r['condition']/r['profile']
        log=(work/'spectre.log').read_text()
        actual=settings(log)
        requested=json.loads((work/'requested_settings.json').read_text())
        match=all(actual[k]==v if isinstance(v,str) else math.isclose(actual[k],v,rel_tol=1e-12,abs_tol=0)
                  for k,v in requested.items() if k in actual)
        if not match: raise ValueError('effective settings mismatch: '+r['condition']+'/'+r['profile'])
        codes=Counter(re.findall(r'WARNING \(([^)]+)\)',log))
        warnings.update(codes)
        audit.append(dict(condition=r['condition'],profile=r['profile'],effective=actual,requested_match=match,warning_codes=dict(codes)))
        groups[r['card']][r['analysis']['status']]+=1
        for by_scenario in r['analysis'].get('history',{}).values():
            for label,data in by_scenario.items():histories[label][data['status']]+=1
    args.output.mkdir(parents=True)
    tool=json.loads((root/'TOOL_IDENTITY.json').read_text())
    receipt=dict(run_id=root.name,date='2026-09-28',host_alias='thu-sui',backend='spectre',
        tool_version=(root/'version.log').read_text().strip(),binary_sha256=tool['binary_sha256'],
        input_manifest_sha256=sha(root/'INPUT_MANIFEST.json'),file_manifest_sha256=sha(root/'FILE_MANIFEST.json'),
        raw_archive_sha256=sha(args.archive),raw_archive_bytes=args.archive.stat().st_size,
        analysis_sha256=sha(args.analysis),reporter_sha256=sha(Path(__file__)),
        verified_archived_files=len(json.loads((root/'FILE_MANIFEST.json').read_text())),
        summary=analysis['summary'],effective_settings_verified=len(audit),warning_codes=dict(warnings),
        history_counts={k:dict(v) for k,v in histories.items()},
        execution_elapsed_sum_s=sum(r['elapsed_s'] for r in analysis['records']),formal_dvs_qualification='I')
    (args.output/'RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
    (args.output/'effective-settings.json').write_text(json.dumps(audit,indent=2)+'\n')
    (args.output/'analysis.json').write_bytes(args.analysis.read_bytes())
    print(json.dumps(receipt,indent=2))
    print('By card:',json.dumps({k:dict(v) for k,v in groups.items()}))


if __name__=='__main__': main()
