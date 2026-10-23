"""Public contract for the RO frequency calibration: stimuli, replay, checks.

Expected outputs are computed here from the Spec rules, the stimulus and the
observed ref and roclk crossings; the checker never reads a reference model's
waveform and never predicts a count from the RO tuning law.
"""
from __future__ import annotations

import bisect

import uwbtask as u

EDGE = 2e-12            # stimulus edge (linear, centred on the stated time)
TOL = 20e-12            # crossing-time tolerance of the output edges (S10)
AMB = 3e-12             # a roclk crossing closer than this to a window edge is ambiguous
SEP = 1e-9              # starts and resets stay this far from ref edges; output-changing events this far apart (S9)
T_REF = 1 / 48e6        # reference period
CAL_W = 2e-9            # cal_start pulse width
DEFAULTS = dict(ratio=14, n_win=192, n_settle=2, tol=1, n_lost=64, code_init=512,
                vdd=1.0, vth=0.5, tr=2e-12, t_cq=10e-12)
RO_DEFAULTS = dict(f0=600e6, fstep=0.25e6)   # the fixed public RO model's defaults, for reference


def cal_time(p):
    """Approximate duration of one full calibration: 11 windows with their settling."""
    q = {**DEFAULTS, **p}
    return 11 * (q['n_settle'] + q['n_win']) * T_REF


def inst(name, params=None, ro=None):
    return dict(name=name, params=params or {}, ro=ro or {})


# ------------------------------------------------------------------ cases ---

def public_cases():
    p16 = dict(n_win=16)
    normal = dict(name='normal', vin=1.0, ref=dict(delay=0.37e-9), rst=[(0.0, 10e-9)], cal=[50e-9],
                  instances=[inst('a', p16)], stop=50e-9 + cal_time(p16) + 200e-9)
    p24 = dict(n_win=24)
    t_stop = 50e-9 + 3.5 * 26 * T_REF            # the reference stops inside the bit-6 window
    lost = dict(name='ref_lost', vin=1.0, ref=dict(delay=1.13e-9, t_stop=t_stop), rst=[(0.0, 10e-9)],
                cal=[50e-9], instances=[inst('a', p24)], stop=t_stop + 400e-9)
    return [normal, lost]


# --------------------------------------------------------------- netlist ---

def ramp_cross(t_mid, v0, v1, vth):
    """Crossing time of a linear EDGE-long ramp centred on t_mid."""
    return t_mid - EDGE / 2 + (vth - v0) / (v1 - v0) * EDGE


def stimulus(case):
    vin = case['vin']
    ref = case['ref']
    extra = f" t_stop={ref['t_stop']!r}" if ref.get('t_stop') else ''
    lines = [f"Xref (ref) uwb_clock_source period={T_REF!r} delay={ref['delay']!r} tr={EDGE!r} vdd={vin!r}{extra}"]
    cs = [(0.0, 0)]
    for t in case['cal']:
        cs += [(t, 1), (t + CAL_W, 0)]
    lines.append(f'Vcal (cal 0) vsource type=pwl wave={u.pwl_levels(cs, EDGE, vin)}')
    rs = [(0.0, 1 if case['rst'] and case['rst'][0][0] == 0.0 else 0)]
    for on, off in case['rst']:
        if on > 0:
            rs.append((on, 1))
        rs.append((off, 0))
    lines.append(f'Vrst (rst 0) vsource type=pwl wave={u.pwl_levels(rs, EDGE, vin)}')
    return '\n'.join(lines)


def ids(k):
    base = 100 * (k + 1)
    return dict(ref=base, ro=base + 1, code=[base + 10 + i for i in range(10)],
                done=base + 20, fail=base + 21, busy=base + 22, probe=base + 30)


def netlist(case, candidate, tb_dir, stop, maxstep):
    lines = ['simulator lang=spectre', 'global 0',
             f'ahdl_include "{candidate}"',
             f'ahdl_include "{tb_dir / "master_ro16.va"}"',
             f'ahdl_include "{tb_dir / "clock_source.va"}"',
             f'ahdl_include "{tb_dir / "edge_monitor.va"}"',
             f'ahdl_include "{tb_dir / "output_probe.va"}"', stimulus(case)]
    tp = probe_time(case)
    for k, ins in enumerate(case['instances']):
        n = ins['name']
        p = {**DEFAULTS, **ins['params']}
        code = [f'k{n}{i}' for i in range(9, -1, -1)]
        taps = [f'ph{n}{i}' for i in range(15, -1, -1)]
        ro = ' '.join(f'{key}={val!r}' for key, val in {'vdd': case['vin'], **ins['ro']}.items())
        lines.append(f'Xro{n} ({" ".join(code + taps)}) master_ro16 {ro}'.rstrip())
        params = ' '.join(f'{key}={val!r}' for key, val in ins['params'].items())
        pins = ['ref', f'ph{n}0', 'cal', 'rst'] + code + [f'done{n}', f'fail{n}', f'busy{n}']
        lines.append(f'Xcal{n} ({" ".join(pins)}) ro_frequency_cal {params}'.rstrip())
        m = ids(k)
        vin_th, vout = p['vth'], p['vdd'] / 2
        mons = [('ref', m['ref'], vin_th), (f'ph{n}0', m['ro'], vin_th)]
        mons += [(f'k{n}{i}', m['code'][i], vout) for i in range(10)]
        mons += [(f'{g}{n}', m[g], vout) for g in ('done', 'fail', 'busy')]
        lines += [f'Xmon_{node}_{ident} ({node}) uwb_edge_monitor id={ident} vth={th!r}' for node, ident, th in mons]
        outs = ' '.join(code + [f'done{n}', f'fail{n}', f'busy{n}'])
        lines.append(f'Xprobe{n} ({outs}) uwb_output_probe id={m["probe"]} vth={vout!r} t_probe={tp!r}')
    lines += ['opts options reltol=1e-6 vabstol=1e-6', f'tran tran stop={stop!r} maxstep={maxstep!r}',
              f"save busy{case['instances'][0]['name']}"]
    return '\n'.join(lines) + '\n'


def stop_time(case):
    return case['stop']


def first_event(case):
    """Stated time of the first cal_start or rst rising edge after t = 0."""
    return min(list(case['cal']) + [on for on, _ in case['rst'] if on > 0])


def probe_time(case):
    """The output levels before calibration are read 5 ns before the first event."""
    return first_event(case) - 5e-9


class Levels:
    """Output levels: the probe reading at probe_time, then the observed crossings."""

    def __init__(self, records, tp):
        self.edges = u.Edges(records)
        self.tp = tp
        self.probe = {}
        for rec in records:
            parts = rec.split()
            if len(parts) == 4 and parts[0] == 'LEVEL':
                m = ids(int(parts[1]) // 100 - 1)
                word = int(parts[2])
                for k, ident in enumerate(m['code'] + [m['done'], m['fail'], m['busy']]):
                    self.probe[ident] = (word >> k) & 1

    def level(self, ident, t):
        lv = self.probe.get(ident, -1)          # -1: no reading, never equals a logic level
        for te, d in self.edges.by_id.get(ident, []):
            if self.tp < te <= t:
                lv = d
        return lv

    def bus(self, ids_lsb_first, t):
        bits = [self.level(i, t) for i in ids_lsb_first]
        return -1 if -1 in bits else sum(b << k for k, b in enumerate(bits))


# ---------------------------------------------------------------- replay ---

def replay(case, params, ref, ro, windows=None):
    """Replay S2-S8 from the stimulus and the observed ref/roclk rising crossings.

    Returns (updates, calibrations, margins):
      updates       [(t_decide, code, done, fail, busy)] each output state change
      calibrations  [dict(start, end, outcome, code)] one per accepted cal_start
      margins       [(t, what, distance, limit)] distance from each window edge,
                    each cal_start and the last ref edge before a watchdog fail to
                    the nearest roclk crossing, from each cal_start and rst
                    crossing to the nearest ref crossing, and between
                    consecutive output-changing events
    windows, if given, receives (t_close, trial code, count, target) per window.
    """
    p = {**DEFAULTS, **params}
    vin, vth = case['vin'], p['vth']
    target = p['n_win'] * p['ratio']
    ev = []
    for on, off in case['rst']:
        if on > 0:
            ev.append((ramp_cross(on, 0, vin, vth), 0, 'rst_on'))
        ev.append((ramp_cross(off, vin, 0, vth), 1, 'rst_off'))
    for t in case['cal']:
        ev.append((ramp_cross(t, 0, vin, vth), 2, 'cal'))
    ev += [(t, 3, 'ref') for t in ref] + [(t, 4, 'ro') for t in ro]
    ev.sort()
    rst_high = bool(case['rst']) and case['rst'][0][0] == 0.0
    shown = dict(code=p['code_init'], done=0, fail=0, busy=0)
    updates, cals, margins = [], [], []
    s = dict(busy=False, stage=None, verify=False, kept=0, trial=0, weight=0, nref=0, cnt=0, lost=0)

    def emit(t, code, done, fail, busy):
        new = dict(code=code, done=done, fail=fail, busy=busy)
        if new != shown:
            if updates:
                margins.append((t, 'output-changing event after the previous one', t - updates[-1][0], SEP))
            updates.append((t, code, done, fail, busy))
            shown.update(new)

    def stop_cal(t, outcome, code):
        if cals and cals[-1]['end'] is None:
            cals[-1].update(end=t, outcome=outcome, code=code)

    ro_sorted, ref_sorted = sorted(ro), sorted(ref)

    def near(t, seq=ro_sorted):
        i = bisect.bisect_left(seq, t)
        d = [abs(seq[j] - t) for j in (i - 1, i) if 0 <= j < len(seq)]
        return min(d) if d else float('inf')

    last_ref = None
    for t, _, kind in ev:
        if kind == 'rst_on':
            rst_high = True
            margins.append((t, 'rst rises', near(t, ref_sorted), SEP))
            if s['busy']:
                stop_cal(t, 'reset', p['code_init'])
            s.update(busy=False, stage=None)
            emit(t, p['code_init'], 0, 0, 0)
        elif kind == 'rst_off':
            rst_high = False
        elif kind == 'cal':
            margins.append((t, 'cal_start rises (ref)', near(t, ref_sorted), SEP))
            if rst_high:
                continue
            margins.append((t, 'cal_start rises (roclk)', near(t), AMB))
            if s['busy']:
                stop_cal(t, 'restarted', None)
            s.update(busy=True, stage='settle', verify=False, kept=0, weight=512, trial=512, nref=0,
                     cnt=0, lost=0)
            cals.append(dict(start=t, end=None, outcome=None, code=None))
            emit(t, 512, 0, 0, 1)
        elif kind == 'ref':
            last_ref = t
            s['lost'] = 0
            if not s['busy']:
                continue
            s['nref'] += 1
            if s['stage'] == 'settle':
                if s['nref'] >= p['n_settle']:
                    s.update(stage='count', nref=0, cnt=0)
                    margins.append((t, 'window opens', near(t), AMB))
            elif s['nref'] >= p['n_win']:
                margins.append((t, 'window closes', near(t), AMB))
                cnt = s['cnt']
                if windows is not None:
                    windows.append((t, s['trial'], cnt, target))
                s.update(stage='settle', nref=0)
                if not s['verify']:
                    if cnt <= target:
                        s['kept'] = s['trial']
                    s['weight'] //= 2
                    if s['weight'] >= 1:
                        s['trial'] = s['kept'] + s['weight']
                    else:
                        s['trial'] = s['kept']
                        s['verify'] = True
                    emit(t, s['trial'], 0, 0, 1)
                else:
                    ok = abs(cnt - target) <= p['tol']
                    s.update(busy=False, stage=None)
                    stop_cal(t, 'done' if ok else 'fail', s['kept'])
                    emit(t, s['kept'], int(ok), int(not ok), 0)
        elif kind == 'ro':
            if not s['busy']:
                continue
            if s['stage'] == 'count':
                s['cnt'] += 1
            s['lost'] += 1
            if s['lost'] > p['n_lost']:
                if last_ref is not None:
                    margins.append((last_ref, 'last ref edge before the watchdog', near(last_ref), AMB))
                s.update(busy=False, stage=None)
                stop_cal(t, 'fail', s['kept'])
                emit(t, s['kept'], 0, 1, 0)
    return updates, cals, margins


def expected_edges(params, updates):
    """Expected vdd/2 crossings [(time, dir)] of every output for one instance."""
    p = {**DEFAULTS, **params}
    half = p['tr'] / 2
    level = dict(code=p['code_init'], done=0, fail=0, busy=0)
    edges = {f'code{i}': [] for i in range(10)}
    edges.update(done=[], fail=[], busy=[])
    for t, code, done, fail, busy in updates:
        ts = t + p['t_cq'] + half
        for i in range(10):
            a, b = (level['code'] >> i) & 1, (code >> i) & 1
            if a != b:
                edges[f'code{i}'].append((ts, b))
        for g, v in (('done', done), ('fail', fail), ('busy', busy)):
            if level[g] != v:
                edges[g].append((ts, v))
        level.update(code=code, done=done, fail=fail, busy=busy)
    return edges


# ----------------------------------------------------------------- checks ---

def check(case, records):
    seen = Levels(records, probe_time(case))
    edges_seen = seen.edges
    reps = []
    for k, ins in enumerate(case['instances']):
        rep = u.Report(f"{case['name']}/{ins['name']}")
        p = {**DEFAULTS, **ins['params']}
        m = ids(k)
        ref = edges_seen.times(m['ref'], 1)
        ro = edges_seen.times(m['ro'], 1)
        updates, cals, margins = replay(case, ins['params'], ref, ro)
        amb = [x for x in margins if x[2] < x[3]]
        ro_m = min((d for _, _, d, lim in margins if lim == AMB), default=float('inf'))
        ref_m = min((d for _, _, d, lim in margins if lim == SEP), default=float('inf'))
        rep.add('event order is unambiguous (S9)',
                f'roclk >= {AMB*1e12:g} ps from window edges and starts; starts, resets >= {SEP*1e9:g} ns from ref '
                f'and output-changing events >= {SEP*1e9:g} ns apart',
                f'{len(amb)} of {len(margins)} too close; closest roclk {ro_m*1e12:.1f} ps, other {ref_m*1e9:.2f} ns'
                + (f'; first {amb[0][1]} at {amb[0][0]*1e9:.4f} ns' if amb else ''), not amb)
        t0 = seen.tp
        seen0 = (seen.bus(m['code'], t0), seen.level(m['done'], t0),
                 seen.level(m['fail'], t0), seen.level(m['busy'], t0))
        rep.add(f'outputs {(first_event(case) - t0)*1e9:g} ns before the first cal_start or reset (S7)',
                f"code {p['code_init']}, done 0, fail 0, busy 0",
                f'code {seen0[0]}, done {seen0[1]}, fail {seen0[2]}, busy {seen0[3]}',
                seen0 == (p['code_init'], 0, 0, 0))
        exp = expected_edges(ins['params'], updates)
        names = [(f'code[{i}]', f'code{i}', m['code'][i]) for i in range(10)]
        names += [(g, g, m[g]) for g in ('done', 'fail', 'busy')]
        for label, key, ident in names:
            got = edges_seen.by_id.get(ident, [])
            want = exp[key]
            ok_dir = [d for _, d in got] == [d for _, d in want]
            rep.times_match(f'{label} edges (S2-S8)', [t for t, _ in got] if ok_dir else [],
                            [t for t, _ in want], TOL)
        for n, c in enumerate(cals):
            if c['outcome'] not in ('done', 'fail'):
                rep.add(f'calibration {n + 1} (start {c["start"]*1e9:.3f} ns)', 'interrupted',
                        f"{c['outcome']} at {c['end']*1e9:.3f} ns" if c['end'] else 'still running', c['end'] is not None)
                continue
            ts = c['end'] + p['t_cq'] + p['tr'] + 2 * TOL
            got = (seen.bus(m['code'], ts), seen.level(m['done'], ts),
                   seen.level(m['fail'], ts), seen.level(m['busy'], ts))
            want = (c['code'], int(c['outcome'] == 'done'), int(c['outcome'] == 'fail'), 0)
            rep.add(f'calibration {n + 1} outcome (S4/S6)',
                    f"{c['outcome']} with code {c['code']} at {c['end']*1e9:.3f} ns",
                    f'code {got[0]}, done {got[1]}, fail {got[2]}, busy {got[3]}', got == want)
        reps.append(rep)
    return reps
