"""Preserve backend records and report observation facts, without grading behavior."""
from __future__ import annotations
import importlib.util
import hashlib
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
READER_DIR = ROOT/'experiments/archive/dvs2-starter-pilot'
READER_DEPENDENCIES = (READER_DIR/'analyze.py', READER_DIR/'suite.py')


def read_native(path, backend):
    """Reuse existing format parsers. Format does not establish sample provenance.

    The coordinator must supply origins from actual backend export semantics.
    """
    aliases = {'openvaf_r_ngspice':'openvaf_ngspice','gnucap_modelgen':'gnucap',
               'spectre':'spectre','evas':'evas'}
    if backend not in aliases:
        raise ValueError('unknown backend')
    # Load the legacy parser with its exact local suite, without polluting global
    # imports used by other experiment modules.
    old_suite = sys.modules.get('suite')
    spec = importlib.util.spec_from_file_location('suite',READER_DIR/'suite.py')
    suite = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(suite)
    sys.modules['suite'] = suite
    try:
        spec = importlib.util.spec_from_file_location('paper_native_reader',READER_DIR/'analyze.py')
        reader = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(reader)
        return reader.read_waveform(path,aliases[backend])
    finally:
        if old_suite is None:
            sys.modules.pop('suite',None)
        else:
            sys.modules['suite'] = old_suite


def bounded(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0


def normalize_observation(card, backend, rows, origins, qualification=None, *, contract, T=1e-6):
    """Export raw values, observed gaps and explicit qualification for the checker.

    A caller's uncertainty certificate must name evidence. No measured gaps,
    solver tolerances or interpolation flags create a voltage/time error bound.
    """
    q = dict(qualification or {})
    issues = []
    if backend not in ('spectre','evas','openvaf_r_ngspice','gnucap_modelgen'):
        issues.append('unknown backend')
    if len(rows)!=len(origins) or any(o not in ('accepted','interpolated','unknown') for o in origins):
        issues.append('missing or invalid sample origins')
    if not rows:
        issues.append('missing rows')
    for row in rows:
        if any(not isinstance(row.get(p),(int,float)) or not math.isfinite(row[p])
               for p in ['time',*card['observables']]):
            issues.append('missing or nonfinite required column')
            break
    times = [r['time'] for r in rows] if not issues else []
    if times and any(a>=b for a,b in zip(times,times[1:])):
        issues.append('non-monotone or duplicate time')
        times = []
    gap = max((b-a for a,b in zip(times,times[1:])),default=None)
    coverage = bool(times) and times[0] == 0 and times[-1] >= card['stop_T']*T
    windows = []
    exact = []
    for w in card['observation_windows']:
        start,end,center = w['start_T']*T,w['end_T']*T,w['center_T']*T
        # Intersect every interval with the window, including intervals crossing
        # its edges. Looking only at contained rows hides an empty window.
        gaps = [min(b,end)-max(a,start) for a,b in zip(times,times[1:]) if a<end and b>start]
        local = max(gaps,default=None)
        indices = [i for i,t in enumerate(times) if t==center]
        exact.extend(indices)
        windows.append({'start_s':start,'end_s':end,'center_s':center,
                        'max_gap_s':local,'required_max_gap_s':w['max_gap_s'],
                        'exact_center_rows':indices,
                        'coverage':bool(times) and times[0]<=start and times[-1]>=end})
    # Small relative allowance handles binary time differences, not physical error.
    gap_ok = coverage and gap is not None and gap <= contract['sample_gap_s']*(1+1e-10)
    local_ok = all(w['coverage'] and w['max_gap_s'] is not None and
                   w['max_gap_s']<=w['required_max_gap_s']*(1+1e-10) and w['exact_center_rows'] for w in windows)
    native = len(origins)==len(rows) and bool(rows) and all(o=='accepted' for o in origins)
    uncertainty_ok = all(bounded(q.get(k)) for k in ('time_error_s','voltage_error_V','input_error_V'))
    uncertainty_ok = uncertainty_ok and q['time_error_s']<=contract['required_observation_error']['time_s'] and q['voltage_error_V']<=contract['required_observation_error']['voltage_V'] and q['input_error_V']<=contract['input_error_V']
    certificates = q.get('qualification_evidence', {})
    required_roles = ['source','time','voltage','inputs','native_initial']
    if any(p in ('count','na','nb') for p in card['observables']):
        required_roles.append('native_counters')
    if card['id'] in ('CP-02','CO-VCO-01'):
        required_roles.append('native_phase')
    def valid_certificate(role):
        entry = certificates.get(role) if isinstance(certificates,dict) else None
        if not isinstance(entry,dict) or not entry.get('method') or not entry.get('artifact_path') or not entry.get('sha256'):
            return False
        try:
            return hashlib.sha256(Path(entry['artifact_path']).read_bytes()).hexdigest()==entry['sha256']
        except (OSError,TypeError,ValueError):
            return False
    evidence_ok = all(valid_certificate(role) for role in required_roles)
    interpolation_ok = native or (all(o!='unknown' for o in origins) and bounded(q.get('interpolation_error_bound_V')) and bounded(q.get('voltage_error_V')) and q['interpolation_error_bound_V']<=q['voltage_error_V'] and evidence_ok)
    qualified = not issues and bool(q.get('qualified')) and uncertainty_ok and evidence_ok and gap_ok and local_ok and interpolation_ok
    qualification_out = {**q,'time_unit':'s','voltage_unit':'V',
        'time_error_s':q.get('time_error_s'),'voltage_error_V':q.get('voltage_error_V'),
        'input_error_V':q.get('input_error_V'),'qualified':qualified,
        'source_validated':q.get('source_validated') is True,
        'input_bounds_qualified':q.get('input_bounds_qualified') is True and evidence_ok and bounded(q.get('input_error_V')),
        'native_counters':native,'native_phase':native,
        'native_initial':bool(times) and bool(origins) and origins[0]=='accepted' and times[0]==0 and q.get('native_initial') is True and valid_certificate('native_initial'),
        'exact_time_qualified':native and q.get('exact_time_qualified') is True and evidence_ok,
        'global_gap_qualified':gap_ok,'local_gap_qualified':local_ok}
    return {'schema_version':1,'condition':card['id'],'backend':backend,
        'status':'observation_invalid' if issues else 'observation_available',
        'units':{'time':'s','voltage':'V'},'rows':rows,'qualification':qualification_out,
        'metadata':{'sample_origins':origins,'actual_max_gap_s':gap,'coverage':coverage,
                    'local_windows':windows,'exact_boundary_rows':sorted(set(exact)),
                    'issues':issues,'claim':'fixed observations only; no continuous-time guarantee'}}
