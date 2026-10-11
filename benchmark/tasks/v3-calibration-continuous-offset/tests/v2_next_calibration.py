"""Independent terminal-waveform contracts for calibration extensions."""
import bisect
import statistics


def edges(rows, signal):
    result=[]
    for a,b in zip(rows,rows[1:]):
        if a[signal]<.45<=b[signal]:
            result.append(a['time']+(b['time']-a['time'])*(.45-a[signal])/(b[signal]-a[signal]))
    return result


def evaluate(rows,case,work):
    checks=[]
    def check(name,actual,limit):
        checks.append({'name':name,'actual':actual,'limit':limit,'passed':actual<=limit})
    if case['kind']=='fractional-pll':
        reset_start=None;reset_feedback=[];reset_qualification=[]
        for row in rows:
            if row['rst']>.45:
                if reset_start is None:reset_start=row['time']
                if row['time']-reset_start>=2.2e-9:
                    reset_feedback.append(abs(row['fb']))
                    reset_qualification.append(abs(row['lock']))
            else:reset_start=None
        if reset_feedback:
            check('reset-feedback-clear',max(reset_feedback),.1)
            check('reset-qualification-clear',max(reset_qualification),.1)
        dco=edges(rows,'dco');fb=edges(rows,'fb');ref=edges(rows,'ref')
        for j,window in enumerate(case['windows']):
            start,end,n,fraction=window
            ds=[t for t in dco if start<=t<=end];fs=[t for t in fb if start<=t<=end];rs=[t for t in ref if start<=t<=end]
            if min(len(ds),len(fs),len(rs))<20:
                check(f'{j}:missing-edges',1,0);continue
            alignment=[]
            for t in fs:
                k=bisect.bisect_left(dco,t)
                alignment.append(min(abs(t-r) for r in dco[max(0,k-1):k+1]))
            check(f'{j}:feedback-edge-causality',max(alignment),5e-10)
            counts=[bisect.bisect_right(dco,b-2e-10)-bisect.bisect_right(dco,a-2e-10) for a,b in zip(fs,fs[1:])]
            check(f'{j}:divider-illegal',sum(c not in (n,n+1) if fraction else c!=n for c in counts),0)
            check(f'{j}:divider-average',abs(statistics.mean(counts)-(n+fraction)),case['ratio_tolerance'])
            fout=(len(ds)-1)/(ds[-1]-ds[0]);fr=(len(rs)-1)/(rs[-1]-rs[0]);ff=(len(fs)-1)/(fs[-1]-fs[0])
            check(f'{j}:output-ratio',abs(fout/fr-(n+fraction)),case['frequency_tolerance'])
            check(f'{j}:feedback-ratio',abs(ff/fr-1),case['feedback_tolerance'])
            # Pair by nearest reference edge; unwrap to detect accumulated cycle drift.
            period=1/fr;phase=[]
            for t in fs:
                k=bisect.bisect_left(ref,t);near=min(ref[max(0,k-1):k+1],key=lambda r:abs(r-t))
                v=(t-near)/period
                if phase:
                    while v-phase[-1]>.5:v-=1
                    while v-phase[-1]<-.5:v+=1
                phase.append(v)
            check(f'{j}:phase-excursion-cycles',max(phase)-min(phase),case['phase_tolerance'])
            check(f'{j}:mean-phase-cycles',abs(statistics.mean(phase)),case['mean_phase_tolerance'])
            qualified=[r['lock'] for r in rows if start<=r['time']<=end]
            check(f'{j}:qualification',sum(x<.8 for x in qualified)/len(qualified),.05)
        for a,b in case.get('withdraw_windows',[]):
            check('withdraw-qualification',max(r['lock'] for r in rows if a<=r['time']<=b),.1)
    else:
        for j,(start,end) in enumerate(case['windows']):
            selected=[r for r in rows if start<=r['time']<=end]
            if not selected:raise ValueError('empty acceptance window')
            error=[abs(r['outp']-r['outn']-case['gain']*(r['inp']-r['inn'])) for r in selected]
            if case['kind']=='continuous-offset':
                check(f'{j}:signal-plus-residual',max(error),case['diff_tolerance'])
            else:
                check(f'{j}:differential-transfer',max(error),case['diff_tolerance'])
                check(f'{j}:actual-output-common-mode',max(abs((r['outp']+r['outn'])/2-case['cm_target']) for r in selected),case['cm_tolerance'])
        for a,b in case.get('hold_windows',[]):
            vals=[r['code'] for r in rows if a<=r['time']<=b]
            check('disabled-code-hold',max(vals)-min(vals),.01)
        for a,b in case.get('reset_windows',[]):
            check('reset-code-clear',max(abs(r['code']) for r in rows if a<=r['time']<=b),.01)
        off_grid_start=None;longest_off_grid=0
        for row in rows:
            if abs(row['code']-round(row['code']))>.01:
                if off_grid_start is None:off_grid_start=row['time']
                longest_off_grid=max(longest_off_grid,row['time']-off_grid_start)
            else:off_grid_start=None
        check('integer-code-after-transition',longest_off_grid,150e-9)
        check('actuator-code-bound',max(abs(r['code']) for r in rows),case.get('code_limit',64)+.01)
        check('output-rail-low',max(max(.05-r['outp'],.05-r['outn'],0) for r in rows),.001)
        check('output-rail-high',max(max(r['outp']-.95,r['outn']-.95,0) for r in rows),.001)
    return {'passed':bool(checks) and all(c['passed'] for c in checks),'checks':checks}
