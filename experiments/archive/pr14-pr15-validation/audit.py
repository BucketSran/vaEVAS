"""Post-run metadata audit. Never changes inputs, waveforms or acceptance targets."""
import argparse
from collections import Counter
from decimal import Decimal
from fractions import Fraction as Q
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
from operators import ROOT, digest, dump


def verify_archive_tree(root):
    entries=json.loads((root/'FILE_MANIFEST.json').read_text())
    verified=0;excluded=[]
    for name,entry in entries.items():
        p=root/name
        if not p.resolve().is_relative_to(root.resolve()):raise ValueError('unsafe path')
        h=entry['sha256'] if isinstance(entry,dict) else entry
        if p.exists():
            if digest(p)!=h:raise ValueError('artifact drift: '+name)
            verified+=1
        elif '.ahdlSimDB/' in name or name.endswith('.so') or any(n.startswith('._') for n in p.parts):
            excluded.append(name)
        else:raise ValueError('missing required evidence: '+name)
    return dict(manifest_sha256=digest(root/'FILE_MANIFEST.json'), verified_files=verified,
                excluded_build_cache_files=len(excluded),excluded=excluded)


def spectre_settings(log,requested):
    units={u:Q(10)**e for u,e in [('s',0),('ms',-3),('us',-6),('ns',-9),('ps',-12),('fs',-15)]}
    evidence={}
    for key,expected in requested.items():
        values=re.findall(r'^\s*'+key+r' = ([^\n]+)$',log,re.M)
        if not values:raise ValueError('missing setting '+key)
        evidence[key]=[]
        for raw in values:
            raw=raw.split(',')[0].strip()
            if isinstance(expected,str):
                if raw!=expected:raise ValueError('method mismatch')
                evidence[key].append(raw)
            else:
                tokens=raw.split(); number=Decimal(tokens[0]); scale=units[tokens[1]] if len(tokens)>1 else Q(1)
                center=Q(number)*scale; radius=Q(10)**number.as_tuple().exponent*scale/2
                if not center-radius<=Q(expected)<=center+radius:raise ValueError('outside displayed precision: '+key)
                evidence[key].append(dict(display=raw,interval_s_or_value=[float(center-radius),float(center+radius)],requested=expected))
    return evidence


def audit(parent,output):
    roots=['matrix-spectre','matrix-evas','matrix-open','operators','slew-refinement']
    verification={n:verify_archive_tree(parent/n) for n in roots}
    records=[]
    for name in ['matrix-spectre','operators','slew-refinement']:
        root=parent/name
        for c in json.loads((root/'conditions.json').read_text()):
            for profile in (['base','fine'] if name=='matrix-spectre' else [None]):
                work=root/'runs'/c['id']/profile if profile else root/c['id']
                if profile:
                    p=json.loads((work/'requested_settings.json').read_text())
                    requested={k:p[k] for k in ['stop','step','maxstep','reltol','vabstol','iabstol','method']}
                else:
                    requested=dict(stop=c['stop'],step=c['maxstep'],maxstep=c['maxstep'],
                         reltol=c['settings']['reltol'],vabstol=c['settings']['vabstol'],iabstol=1e-14,method='traponly')
                records.append(dict(suite=name,case=c['id'],profile=profile or c['profile'],backend='spectre',
                    settings=spectre_settings((work/'spectre.log').read_text(),requested),
                    log_sha256=digest(work/'spectre.log'),status='requested_settings_match_display_precision'))
    path=ROOT/'experiments/backends/dvs2-four-backend-validation/audit.py'
    spec=importlib.util.spec_from_file_location('original_audit',path)
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    root=parent/'matrix-open'
    for r in json.loads((root/'EXECUTION.json').read_text()):
        item={k:r[k] for k in ['backend','condition','profile','status']}
        if r['status']=='waveform_available':
            w=root/'runs'/r['backend']/r['condition']/r['profile']
            actual,mapping=old.setting_readback(r['backend'],(w/'simulate.log').read_text())
            requested=json.loads((w/'requested_settings.json').read_text())
            if not all(math.isclose(actual[k],requested[v],rel_tol=1e-12,abs_tol=0) for k,v in mapping.items()):
                raise ValueError('open backend settings differ')
            item.update(settings=actual,status='requested_settings_match_readback',log_sha256=digest(w/'simulate.log'))
        records.append(item)
    root=parent/'matrix-evas'
    for r in json.loads((root/'EXECUTION.json').read_text()):
        item={k:r[k] for k in ['backend','condition','profile','status']}
        if r['status']=='waveform_available':
            w=root/'runs'/r['condition']/r['profile']
            effective=json.loads((w/'effective.json').read_text());requested=json.loads((w/'requested_settings.json').read_text())
            for key,target in [('vabstol','vabstol'),('reltol','reltol'),('max_step','maxstep'),('stop','stop')]:
                if effective[key]!=requested[target]:raise ValueError('EVAS settings mismatch')
            item.update(status='adapter_request_record_verified', unsupported_spice_controls=effective['unsupported_spice_controls'])
        records.append(item)
    dump(output,dict(archive_verification=verification,records=records,
         summary=dict(Counter(r['status'] for r in records)),
         limitations='Spectre settings may be rounded in logs; checks use half-last-digit display intervals. Strobe requests remain in decks and coverage is checked from waveform times. Open-backend settings include available option readback; EVAS record is the adapter request, not an independent solver control readback.'))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('parent',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();audit(a.parent,a.output)
