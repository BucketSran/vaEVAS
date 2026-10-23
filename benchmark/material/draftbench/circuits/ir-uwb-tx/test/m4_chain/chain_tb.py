"""Testbench builder for the integrated seed chain (M4).

CDC test condition (SPEC.md section 5): the bit clock is an ideal 4.032 GHz
clock, exactly 6x the RO at code 288, with a fixed phase; the RO code is
held at 288 by ideal sources. Not a CDC solution.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import uwbtest as u  # noqa: E402

T = u.T_BIT
CLK_DELAY = 10e-12
EDGE = 2e-12
FIRST_CAP = 5


def capture_time(k):
    return CLK_DELAY + k * T + EDGE / 2


RST_RELEASE = capture_time(4) + T / 2

IDS = dict(
    sym_valid=16, enc_valid=40,
    pre_a=50, rf_a=51, sa0=52, sa1=53, sa2=54, pol_a=55,
    pre_b=60, rf_b=61, sb0=62, sb1=63, sb2=64, pol_b=65,
    gate_a=70, gate_b=71, conflict=72, overrun=73,
    **{f'pwr{k}': 80 + k for k in range(8)},
    **{f'pre{k}': 90 + k for k in range(8)},
    **{f'rel{k}': 100 + k for k in range(8)},
    **{f'ph{k}': 120 + k for k in range(16)},
)


def _params(d):
    return ''.join(f' {k}={v!r}' for k, v in (d or {}).items())


def build(symbols, *, n_pre=2, rf=True, pol_bits=None, save_rf=False, extra_stop=6, dpc_db=None,
          ro_phi=None, sched_params='', en_wave=None, pg=None, ro=None, br=None, out=None,
          export=0, monitors=None, maxstep=10e-12):
    """Seed chain netlist. pg/ro/br/out are extra parameter dicts for the pulse
    generator, master RO, every RF branch (branch k gets seed = br seed + 7 k and
    id = k) and the output stage; export = 1 turns on the export records."""
    bits = [(s >> (5 - k)) & 1 for s in symbols for k in range(6)]
    stop = capture_time(FIRST_CAP + len(bits)) + extra_stop * u.TS
    taps = ' '.join(f'ph{k}' for k in range(15, -1, -1))
    code = ' '.join(f'c{b}' for b in range(9, -1, -1))
    lines = [
        'simulator lang=spectre', 'global 0',
        u.include_lines('module/serial_to_symbol6.va', 'module/dppm_fsk_encoder8.va',
                        'module/master_ro16.va', 'module/pulse_generator.va', 'module/ro_scheduler8.va',
                        'module/rf_ro_branch.va', 'module/envelope_lane.va', 'module/tx_output.va',
                        'test/sources/clock_source.va', 'test/sources/edge_monitor.va'),
        '\n'.join(f'Vc{b} (c{b} 0) vsource dc={(288 >> b) & 1}' for b in range(10)),
        f'Xbclk (bclk) uwb_clock_source period={T!r} delay={CLK_DELAY!r} tr={EDGE!r}',
        f'Vrst (rst 0) vsource type=pwl wave=[0 1 {u.fmt_ps(RST_RELEASE - 1e-12)} 1 {u.fmt_ps(RST_RELEASE + 1e-12)} 0]',
        f'Vdin (din 0) vsource type=pwl wave={u.pwl_bits(bits, capture_time(FIRST_CAP), T)}',
        'Ven (en 0) vsource dc=1' if en_wave is None else f'Ven (en 0) vsource type=pwl wave={en_wave}',
    ]
    if pol_bits is None:
        lines.append('Vpol (pol 0) vsource dc=0')
    else:
        # polarity bit per symbol, changed mid-symbol so the encoder-to-PG latch sees it settled
        lines.append(f'Vpol (pol 0) vsource type=pwl wave={u.pwl_bits(pol_bits, capture_time(FIRST_CAP + 9), u.TS)}')
    lines += [
        'Xs2p (bclk din rst sym5 sym4 sym3 sym2 sym1 sym0 sym_valid) uwb_serial_to_symbol6',
        'Xenc (sym5 sym4 sym3 sym2 sym1 sym0 sym_valid rst p2 p1 p0 i2 i1 i0 f2 f1 f0 '
        f'q7 q6 q5 q4 q3 q2 q1 q0 enc_valid) uwb_dppm_fsk_encoder8{_params(dict(export=export) if export else None)}',
        f'Xro ({code} {taps}) uwb_master_ro16{_params({**(ro or {}), **({"export": export} if export else {})})}',
        f'Xpg ({taps} p2 p1 p0 f2 f1 f0 pol enc_valid en rst pre_a rf_a sa2 sa1 sa0 pol_a '
        f'pre_b rf_b sb2 sb1 sb0 pol_b overrun) uwb_pulse_generator n_pre={n_pre}'
        f'{_params({**(pg or {}), **({"export": export} if export else {})})}',
        f'Xsch (pre_a rf_a sa2 sa1 sa0 pre_b rf_b sb2 sb1 sb0 rst '
        f'{" ".join(f"pwr{k}" for k in range(7, -1, -1))} {" ".join(f"pre{k}" for k in range(7, -1, -1))} '
        f'{" ".join(f"rel{k}" for k in range(7, -1, -1))} gate_a gate_b conflict nsup '
        f'{" ".join(f"st{k}" for k in range(7, -1, -1))}) uwb_ro_scheduler8 n_pre={n_pre} {sched_params}'
        f'{_params(dict(export=export) if export else None)}',
    ]
    if rf:
        for k in range(8):
            phi = '' if ro_phi is None else f' phi0={ro_phi[k]!r}'
            extra = dict(br or {})
            if br or export:
                extra['seed'] = extra.get('seed', 101) + 7 * k
                extra['id'] = k
            if export:
                extra['export'] = export
            lines.append(f'Xbr{k} (pwr{k} pre{k} rel{k} vro{k}) uwb_rf_ro_branch f_rf={u.CARRIERS[k]!r}{phi}{_params(extra)}')
        lines.append('Xenva (gate_a ph0 env_a) uwb_envelope_lane')
        lines.append('Xenvb (gate_b ph0 env_b) uwb_envelope_lane')
        dpc = '' if dpc_db is None else ' ' + ' '.join(f'dpc_db{k}={v!r}' for k, v in enumerate(dpc_db))
        lines.append(f'Xout ({" ".join(f"vro{k}" for k in range(7, -1, -1))} env_a env_b gate_a gate_b '
                     f'sa2 sa1 sa0 sb2 sb1 sb0 pol_a pol_b outp outn) uwb_tx_output{dpc}{_params(out)}')
    lines.append(u.monitor_lines(IDS if monitors is None else {k: IDS[k] for k in monitors}))
    lines.append('opts options reltol=1e-6 vabstol=1e-6')
    lines.append(f'tran tran stop={stop!r} maxstep={maxstep!r}')
    save = 'nsup'
    if rf and save_rf:
        save += ' outp outn env_a env_b ' + ' '.join(f'vro{k}' for k in range(8))
    lines.append(f'save {save}')
    return '\n'.join(lines) + '\n', stop
