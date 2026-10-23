"""Checker calibration: typical wrong implementations must be rejected.

Each mutant copies module/ to the run directory, applies one textual change
that models a mistake the SPEC rules out, and reruns the named check. A
mutant is "killed" when the check fails. A surviving mutant means the checks
cannot see that mistake.

Usage: python3 mutants.py [mutant ...]
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / 'lib'))
import uwbtest as u  # noqa: E402

HERE = Path(__file__).resolve().parent
MUTANTS = [
    # name, file, old, new, check script, scenario
    ('s2p_lsb_first', 'serial_to_symbol6.va',
     'n5 = s4; n4 = s3; n3 = s2; n2 = s1; n1 = s0; n0 = bit_in;',
     'n0 = s4; n1 = s3; n2 = s2; n3 = s1; n4 = s0; n5 = bit_in;', 'm1_data/check_m1.py', 'reset_repeat'),
    ('s2p_valid_early_fall', 'serial_to_symbol6.va', 'if (cnt == 3) begin', 'if (cnt == 1) begin',
     'm1_data/check_m1.py', 'reset_repeat'),
    ('enc_no_gray_decode', 'dppm_fsk_encoder8.va', 'd = 4 * g5 + 2 * (g5 ^ g4) + (g5 ^ g4 ^ g3);',
     'd = 4 * g5 + 2 * g4 + g3;', 'm1_data/check_m1.py', 'reset_repeat'),
    ('enc_absolute_position', 'dppm_fsk_encoder8.va', 'p = (p + d) % 8;', 'p = d;',
     'm1_data/check_m1.py', 'reset_repeat'),
    ('enc_rising_edge_capture', 'dppm_fsk_encoder8.va', '@(cross(V(sym_valid) - vth, -1))',
     '@(cross(V(sym_valid) - vth, +1))', 'm1_data/check_m1.py', 'reset_repeat'),
    ('ro_phase_reset_on_code', 'master_ro16.va',
     't_last = $abstime - r / (16 * f);\n            t_next = $abstime + (1 - r) / (16 * f);',
     't_last = $abstime;\n            t_next = $abstime + 1 / (16 * f);', 'm2_clock/check_m2.py', 'ro_step'),
    ('cal_inverted_decision', 'ro_frequency_cal.va', 'if (cnt <= target)', 'if (cnt >= target)',
     'm2_clock/check_m2.py', 'cal_recal'),
    ('cal_window_one_short', 'ro_frequency_cal.va', 'if (nref >= n_win) begin', 'if (nref >= n_win - 1) begin',
     'm2_clock/check_m2.py', 'cal_no_conv'),
    ('pg_no_preparation_frame', 'pulse_generator.va', 's_a = a + 16 + pend_p;', 's_a = a + pend_p;',
     'm3_pulse/check_pg.py', 'positions'),
    ('pg_width_8_taps', 'pulse_generator.va', 'parameter integer n_width = 9 from [1:9];',
     'parameter integer n_width = 8 from [1:9];', 'm3_pulse/check_pg.py', 'positions'),
    ('pg_single_lane', 'pulse_generator.va', 'lane = 1 - lane;', 'lane = 0;', 'm3_pulse/check_pg.py', 'positions'),
    ('sch_steal_busy_slot_a', 'ro_scheduler8.va',
     'la_slot = -1; conf = 1; t_conf_off = $abstime + t_conf;   // drop the symbol',
     's0_br = k; s0_st = 1; s0_pend = 1; la_slot = 0;', 'm4_chain/check_chain.py', 'conflict'),
    ('sch_steal_busy_slot_b', 'ro_scheduler8.va',
     'lb_slot = -1; conf = 1; t_conf_off = $abstime + t_conf;   // drop the symbol',
     's0_br = k; s0_st = 1; s0_pend = 1; lb_slot = 0;', 'm4_chain/check_chain.py', 'conflict'),
    ('sch_warm_restarts_precharge', 'ro_scheduler8.va',
     'la_slot = 0; s0_pend = s0_pend + 1;             // warm: already powered',
     'la_slot = 0; s0_pend = s0_pend + 1; s0_st = 1;', 'm4_chain/check_chain.py', 'hold'),
    ('sch_no_hold', 'ro_scheduler8.va',
     's0_st = 5;                                  // tail done',
     's0_st = 0; s0_br = -1;', 'm4_chain/check_chain.py', 'hold'),
    ('sch_no_tail', 'ro_scheduler8.va', 'parameter real t_tail = 150p from [0:inf);',
     'parameter real t_tail = 0 from [0:inf);', 'm4_chain/check_chain.py', 'hold'),
    ('branch_global_phase', 'rf_ro_branch.va',
     'phase = phi_act + 2 * `M_PI * f_act * (u + df_start',
     'phase = phi_act + 2 * `M_PI * f_act * ($abstime + df_start', 'm3_pulse/check_rf.py', 'branch'),
    ('branch_oscillates_in_precharge', 'rf_ro_branch.va', '@(cross(V(rel) - vth, +1)) begin',
     '@(cross(V(pwr) - vth, +1)) begin', 'm3_pulse/check_rf.py', 'branch'),
    ('env_half_cosine', 'envelope_lane.va', 'w = 2 * `M_PI / tw;', 'w = `M_PI / tw;',
     'm3_pulse/check_rf.py', 'envelope'),
    ('out_ignores_polarity', 'tx_output.va', '(1 - 2 * qa) * ga', 'ga', 'm4_chain/check_chain.py', 'hold'),
    ('out_ignores_dpc', 'tx_output.va', 'ga = (ka == 0) * g0 + (ka == 1) * g1', 'ga = g0 + 0 * g1',
     'm4_chain/check_chain.py', 'hold'),
    ('sch_hold_ignores_tpre', 'ro_scheduler8.va', 't_wait = t_hold - n_pre * delta0;', 't_wait = t_hold;',
     'm4_chain/check_chain.py', 'hold_idle'),
    ('sch_no_preempt', 'ro_scheduler8.va', 'end else if (s0_st == 5 && s0_pend == 0) begin',
     'end else if (0 && s0_st == 5 && s0_pend == 0) begin', 'm4_chain/check_chain.py', 'preempt'),
    ('pg_no_overrun', 'pulse_generator.va', 'ovr = 1; t_ovr_off = $abstime + t_ovr;', 't_ovr_off = $abstime + t_ovr;',
     'm3_pulse/check_pg.py', 'en_late'),
    # M5 (SPEC.md 4.10)
    ('m5_release_at_rf_only', 'ro_scheduler8.va', 'if (V(rst) < vth && la_slot == 0 && s0_st == 1) begin',
     'if (0 && V(rst) < vth && la_slot == 0 && s0_st == 1) begin', 'm5/check_m5.py', 'lead'),
    ('m5_lead_shifts_rf_window', 'pulse_generator.va', 'r_a = s_a - n_lead;', 'r_a = s_a - n_lead; s_a = s_a - n_lead;',
     'm5/check_m5.py', 'lead'),
    ('m5_activation_offset_dropped', 'rf_ro_branch.va', 'f_act = f_dev + df_act;', 'f_act = f_dev;',
     'm5/check_m5.py', 'activation'),
    ('m5_phase_restarts_at_zero', 'rf_ro_branch.va', 'if (phi_random) phi_act = $rdist_uniform(seed_a, 0, 2 * `M_PI);',
     'if (phi_random) begin phi_act = $rdist_uniform(seed_a, 0, 2 * `M_PI); phi_act = 0; end', 'm5/check_m5.py', 'activation'),
    ('m5_phase_noise_not_integrated', 'rf_ro_branch.va', 'pn_base = pn_base + pn_slope * ($abstime - t_pn_k);',
     'pn_base = 0;', 'm5/check_m5.py', 'phase_noise'),
    ('m5_residual_redrawn_each_activation', 'rf_ro_branch.va', 'f_act = f_dev + df_act;',
     'f_act = f_dev + df_act + $rdist_normal(seed_a, 0, sigma_f_res);', 'm5/check_m5.py', 'static'),
    ('m5_jitter_only_on_rf', 'pulse_generator.va', 'else t_a_pon = $abstime + t_lat_eff + j_a;',
     'else t_a_pon = $abstime + t_lat_eff;', 'm5/check_m5.py', 'timing'),
    ('m5_width_error_on_start', 'pulse_generator.va', 'else t_a_ron = $abstime + t_lat_eff + j_a + ep_a;',
     'else t_a_ron = $abstime + t_lat_eff + j_a + ep_a + ew_a;', 'm5/check_m5.py', 'timing'),
    ('m5_leak_includes_connected_branch', 'tx_output.va', 'vall = vall - ca * va - ((cb && !(ca && kb == ka)) ? vb : 0);',
     'vall = vall;', 'm5/check_m5.py', 'isolation'),
    ('m5_tap_skew_not_applied', 'master_ro16.va', 'if (n5 != l5) tt5 = $abstime + lat_eff + sk5;',
     'if (n5 != l5) tt5 = $abstime + lat_eff;', 'm5/check_m5.py', 'tap_skew'),
    ('cal_no_lost_watchdog', 'ro_frequency_cal.va', 'if (lost > n_lost) begin', 'if (0 && lost > n_lost) begin',
     'm2_clock/check_m2.py', 'cal_ref_lost'),
]


def run(m):
    name, fname, old, new, script, scen = m
    base = Path(os.environ.get('UWB_OUT', u.REPO / 'runs/uwb-tx-vabench-20261022/evas')) / 'mutants' / name
    mod = base / 'module'
    if mod.exists():
        shutil.rmtree(mod)
    shutil.copytree(u.FAMILY / 'module', mod)
    src = (mod / fname).read_text()
    if src.count(old) < 1:
        return name, 'BAD-MUTANT (pattern not found)'
    (mod / fname).write_text(src.replace(old, new))
    env = dict(os.environ, UWB_MODULE_DIR=str(mod), UWB_OUT=str(base / 'out'))
    p = subprocess.run([sys.executable, str(HERE / script), scen], capture_output=True, text=True, env=env)
    (base / 'check.log').write_text(p.stdout + '\n' + p.stderr)
    fails = [l for l in p.stdout.splitlines() if l.startswith('FAIL')]
    if p.returncode == 0:
        return name, 'SURVIVED'
    why = fails[0] if fails else (p.stderr.strip().splitlines() or ['error'])[-1]
    return name, f'killed: {why[:150]}'


if __name__ == '__main__':
    want = set(sys.argv[1:])
    results = [run(m) for m in MUTANTS if not want or m[0] in want]
    for name, r in results:
        print(f'{name:32s} {r}')
    survived = [n for n, r in results if not r.startswith('killed')]
    print(f'{len(results) - len(survived)}/{len(results)} killed')
    sys.exit(1 if survived else 0)
