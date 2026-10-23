#!/usr/bin/env python3
"""Turn the export records of the IR-UWB TX seed chain into CSV files and a
parametric DC power breakdown (SPEC.md 4.10, original spec 7.4 and 12.2).

The Verilog-A modules print records with $strobe when their export parameter
is 1. Spectre writes them to its log; EVAS writes them to strobe.txt. This
script reads either file, keeps lines that start with a record tag, and
writes:

  symbols.csv        SYM: every captured word (t, n, raw Gray word, D, P, F)
  scheduled.csv      PGS: every scheduled pulse (lane, P, F, pol, tap offsets,
                     timing-error draws, common latency)
  branch_states.csv  SCH: one row per branch state change (t, branch, slot, from, to)
  gates.csv          SCH: lane gate intervals (lane, t_on, t_off)
  activations.csv    ACT: every cold start of an RF branch (f_act, a_dev, phase, ...)
  phase_noise.csv    PN:  phase-diffusion grid points
  calibration.csv    CAL: calibration outcomes
  taps.csv           TAP: static tap skews
  power.json/.md     state times, starts, powered-branch statistics and,
                     when every needed parameter is given, the DC energy
  manifest.json      record counts, units, time origin and file identities

Usage:
  python3 uwb_export.py LOG OUTDIR [--params power_params.json] [--t0 S] [--t1 S]
                        [--models DIR]

--t0/--t1 bound the accounting window (default: first to last record).
Energy is reported only when every parameter it needs is a number; the
template power_params.json keeps them null until transistor extraction gives
values (SPEC.md 7: do not invent small numbers to show low power).
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

TAGS = {'SYM', 'PGS', 'SCH', 'ACT', 'PN', 'CAL', 'TAP'}
STATES = ['OFF', 'PRECHARGE', 'RELEASE_SETTLE', 'ACTIVE', 'TAIL', 'HOLD']


def read_records(path):
    recs = {t: [] for t in TAGS}
    for line in Path(path).read_text(errors='replace').splitlines():
        parts = line.split()
        if parts and parts[0] in TAGS:
            recs[parts[0]].append([float(x) for x in parts[1:]])
    return recs


def write_csv(path, header, rows):
    with open(path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def branch_transitions(sch):
    """SCH snapshots -> per-branch state changes and lane gate intervals."""
    state = {k: 0 for k in range(8)}
    slot_of = {k: -1 for k in range(8)}
    trans, gates, gate_on = [], [], {0: None, 1: None}
    for r in sch:
        t, b0, s0, b1, s1, ga, gb = r[0], int(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5]), int(r[6])
        new = {k: 0 for k in range(8)}
        slot = {k: -1 for k in range(8)}
        if b0 >= 0 and s0 > 0:
            new[b0], slot[b0] = s0, 0
        if b1 >= 0 and s1 > 0:
            new[b1], slot[b1] = s1, 1
        for k in range(8):
            if new[k] != state[k]:
                trans.append((t, k, slot[k] if new[k] else slot_of[k], state[k], new[k]))
                state[k] = new[k]
                slot_of[k] = slot[k]
        for lane, g in ((0, ga), (1, gb)):
            if g and gate_on[lane] is None:
                gate_on[lane] = t
            elif not g and gate_on[lane] is not None:
                gates.append((lane, gate_on[lane], t))
                gate_on[lane] = None
    return trans, gates, gate_on


def accounting(trans, gates, pgs, t0, t1, params):
    """State times, starts and the original-spec 7.4 energy terms."""
    time_in = {k: [0.0] * 6 for k in range(8)}
    starts = 0
    last = {k: (t0, 0) for k in range(8)}
    events = []
    for t, k, _slot, a, b in sorted(trans):
        if t < t0 or t > t1:
            if t < t0:
                last[k] = (t0, b)
            continue
        lt, ls = last[k]
        time_in[k][ls] += t - lt
        last[k] = (t, b)
        if a in (0, 1) and b in (2, 3):
            starts += 1
        events.append((t, (b != 0) - (a != 0)))
    for k in range(8):
        lt, ls = last[k]
        time_in[k][ls] += t1 - lt
    # powered-branch statistics
    n, peak, area, tp = 0, 0, 0.0, t0
    for t, d in sorted(events):
        area += n * (t - tp)
        n += d
        peak = max(peak, n)
        tp = t
    area += n * (t1 - tp)
    gate_time = sum(min(b, t1) - max(a, t0) for _l, a, b in gates if b > t0 and a < t1)
    pulses = sum(1 for _l, a, _b in gates if t0 <= a <= t1)
    bits = 6 * pulses
    dur = t1 - t0
    tot = [sum(time_in[k][s] for k in range(8)) for s in range(6)]
    out = dict(window_s=[t0, t1], duration_s=dur, pulses=pulses, payload_bits=bits,
               state_time_s={STATES[s]: tot[s] for s in range(6)},
               cold_starts=starts, starts_per_bit=(starts / bits if bits else None),
               mean_powered_branches=area / dur if dur > 0 else None, peak_powered_branches=peak,
               precharge_share=(tot[1] / sum(tot[1:]) if sum(tot[1:]) > 0 else None),
               hold_share=(tot[5] / sum(tot[1:]) if sum(tot[1:]) > 0 else None),
               gate_time_s=gate_time)
    need = ['p_state_w', 'e_start_extra_j', 'p_logic_w', 'e_pulse_switch_j', 'p_pa_active_w', 'p_pa_idle_w',
            'e_calibration_j', 'calibration_period_s']
    missing = [k for k in need if params.get(k) is None or
               (k == 'p_state_w' and any(params[k].get(s) is None for s in STATES))]
    if missing:
        out['energy'] = dict(status='pending extraction', missing=missing)
        return out
    ps = params['p_state_w']
    e_ro = sum(tot[s] * ps[STATES[s]] for s in range(6))
    e_start = starts * params['e_start_extra_j']
    e_logic = dur * params['p_logic_w']
    e_switch = pulses * params['e_pulse_switch_j']
    e_pa = gate_time * params['p_pa_active_w'] + (dur - gate_time) * params['p_pa_idle_w']
    e_cal = params['e_calibration_j'] * dur / params['calibration_period_s']
    total = e_ro + e_start + e_logic + e_switch + e_pa + e_cal
    out['energy'] = dict(status='computed', parameters=params, terms_j=dict(
        ro_states=e_ro, start_extra=e_start, clock_pg_logic=e_logic, switch_dpc=e_switch, pa=e_pa,
        calibration_amortized=e_cal), total_j=total, p_dc_w=total / dur if dur > 0 else None,
        e_per_bit_j=total / bits if bits else None)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log')
    ap.add_argument('outdir')
    ap.add_argument('--params')
    ap.add_argument('--t0', type=float)
    ap.add_argument('--t1', type=float)
    ap.add_argument('--models', help='directory of the .va files, for the manifest identities')
    a = ap.parse_args()
    out = Path(a.outdir)
    out.mkdir(parents=True, exist_ok=True)
    recs = read_records(a.log)
    write_csv(out / 'symbols.csv', ['t_capture_s', 'n', 'gray_word', 'D', 'P', 'F'],
              [[r[0], int(r[1]), int(r[2]), int(r[3]), int(r[4]), int(r[5])] for r in recs['SYM']])
    write_csv(out / 'scheduled.csv', ['t_schedule_s', 'n', 'lane', 'P', 'F', 'pol', 'start_tap', 'end_tap',
                                      'precharge_tap', 'jitter_s', 'position_err_s', 'width_err_s', 'latency_s'],
              [[r[0]] + [int(x) for x in r[1:9]] + r[9:13] for r in recs['PGS']])
    trans, gates, _open = branch_transitions(recs['SCH'])
    write_csv(out / 'branch_states.csv', ['t_s', 'branch', 'slot', 'from_state', 'to_state'],
              [[t, k, s, STATES[a], STATES[b]] for t, k, s, a, b in trans])
    write_csv(out / 'gates.csv', ['lane', 't_on_s', 't_off_s'], gates)
    write_csv(out / 'activations.csv', ['t_release_s', 'branch', 'n', 'f_act_hz', 'a_dev_v', 'phi_act_rad',
                                        'f_dev_hz', 'g_res_db'],
              [[r[0], int(r[1]), int(r[2])] + r[3:8] for r in recs['ACT']])
    write_csv(out / 'phase_noise.csv', ['t_grid_s', 'branch', 'activation', 'phi_pn_rad', 'increment_rad'],
              [[r[0], int(r[1]), int(r[2]), r[3], r[4]] for r in recs['PN']])
    write_csv(out / 'calibration.csv', ['t_s', 'done', 'code', 'count'],
              [[r[0], int(r[1]), int(r[2]), int(r[3])] for r in recs['CAL']])
    write_csv(out / 'taps.csv', ['tap', 'skew_s', 'common_latency_s'],
              [[k, r[2 + k], r[1]] for r in recs['TAP'] for k in range(16)])
    times = [r[0] for v in recs.values() for r in v]
    t0 = a.t0 if a.t0 is not None else (min(times) if times else 0.0)
    t1 = a.t1 if a.t1 is not None else (max(times) if times else 0.0)
    params = json.loads(Path(a.params).read_text()) if a.params else {}
    params = {k: v for k, v in params.items() if not k.startswith('_')}
    power = accounting(trans, gates, recs['PGS'], t0, t1, params)
    (out / 'power.json').write_text(json.dumps(power, indent=1) + '\n')
    md = ['| quantity | value |', '| --- | --- |']
    for k, v in power.items():
        if k != 'energy':
            md.append(f'| {k} | {v} |')
    md.append(f"| energy | {power['energy']['status']} |")
    if power['energy']['status'] == 'computed':
        for k, v in power['energy']['terms_j'].items():
            md.append(f'| energy.{k} (J) | {v:.4g} |')
        md.append(f"| P_DC (W) | {power['energy']['p_dc_w']:.4g} |")
        md.append(f"| E per bit (J) | {power['energy']['e_per_bit_j']:.4g} |")
    else:
        md.append(f"| missing parameters | {', '.join(power['energy']['missing'])} |")
    (out / 'power.md').write_text('\n'.join(md) + '\n')
    ident = {}
    if a.models:
        for p in sorted(Path(a.models).glob('*.va')):
            ident[p.name] = hashlib.sha256(p.read_bytes()).hexdigest()
    manifest = dict(source_log=str(a.log), record_counts={k: len(v) for k, v in recs.items()},
                    units=dict(time='s', frequency='Hz', phase='rad', amplitude='V', energy='J', power='W'),
                    time_origin='simulation time 0', accounting_window_s=[t0, t1], model_sha256=ident,
                    note='RF and supply waveforms are the simulator outputs (outp, outn); this export holds events.')
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    print(json.dumps(manifest['record_counts']))
    print((out / 'power.md').read_text())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
