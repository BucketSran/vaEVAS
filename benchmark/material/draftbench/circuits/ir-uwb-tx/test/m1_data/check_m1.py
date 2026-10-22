"""M1 check: serial-to-symbol converter and 8DPPM+8FSK encoder (SPEC.md 4.2, 4.3).

Scenarios
  debruijn      4097 symbols whose encoded codewords cover all 64 absolute
                codewords and all 4096 ordered adjacent pairs.
  reset_repeat  one symbol repeated (P must keep advancing by D), a reset in
                the middle of a symbol, then a short known sequence: P restarts
                from 0 and the partial symbol is discarded.

The expected words, positions and edge times come from SPEC.md rules
implemented here, not from the gold Verilog-A.

Usage: python3 check_m1.py [debruijn|reset_repeat ...]
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import uwbtest as u  # noqa: E402

T = u.T_BIT
CLK_DELAY = 10e-12
EDGE = 2e-12
T_CQ, T_ENC, T_EV, T_PW = 10e-12, 10e-12, 30e-12, 400e-12
# legacy EVAS with maxstep=10p locates ramp crossings within about 0.5 ps
TOL = 1e-12

IDS = dict(bclk=2, sym_valid=16, enc_valid=40)
SYM = [10, 11, 12, 13, 14, 15]            # sym0..sym5
POS, INC, FC = [20, 21, 22], [23, 24, 25], [26, 27, 28]
REQ = list(range(30, 38))
NODES = dict(bclk=2, sym0=10, sym1=11, sym2=12, sym3=13, sym4=14, sym5=15, sym_valid=16,
             pos0=20, pos1=21, pos2=22, inc0=23, inc1=24, inc2=25, f0=26, f1=27, f2=28,
             **{f'req{k}': 30 + k for k in range(8)}, enc_valid=40)


def capture_time(k: int) -> float:
    """k-th rising bclk crossing (clock_source: delay + k*T, edge midpoint)."""
    return CLK_DELAY + k * T + EDGE / 2


def build_tb(bits, rst_wave, stop):
    first_cap = capture_time(FIRST_CAP)
    return f"""simulator lang=spectre
global 0
{u.include_lines('module/serial_to_symbol6.va', 'module/dppm_fsk_encoder8.va',
                 'test/sources/clock_source.va', 'test/sources/edge_monitor.va')}
Xbclk (bclk) uwb_clock_source period={T!r} delay={CLK_DELAY!r} tr={EDGE!r}
Vrst (rst 0) vsource type=pwl wave={rst_wave}
Vdin (din 0) vsource type=pwl wave={u.pwl_bits(bits, first_cap, T)}
Xs2p (bclk din rst sym5 sym4 sym3 sym2 sym1 sym0 sym_valid) uwb_serial_to_symbol6
Xenc (sym5 sym4 sym3 sym2 sym1 sym0 sym_valid rst pos2 pos1 pos0 inc2 inc1 inc0 f2 f1 f0 req7 req6 req5 req4 req3 req2 req1 req0 enc_valid) uwb_dppm_fsk_encoder8
{u.monitor_lines(NODES)}
opts options reltol=1e-6 vabstol=1e-6
tran tran stop={stop!r} maxstep=10p
save sym_valid enc_valid
"""


# reset released between bclk edges 4 and 5 -> first capture is edge 5
FIRST_CAP = 5
RST_RELEASE = capture_time(4) + T / 2


def symbol_bits(syms):
    return [(s >> (5 - k)) & 1 for s in syms for k in range(6)]


def check_stream(rep, edges, syms, first_cap_index, t_from, t_to, label):
    """Check S2P words and encoder outputs for syms captured from first_cap_index on."""
    sv_rise = [t for t in edges.times(16, 1) if t_from < t < t_to]
    sv_fall = [t for t in edges.times(16, 0) if t_from < t < t_to]
    ev_rise = [t for t in edges.times(40, 1) if t_from < t < t_to]
    n_words = len(syms)
    # the last symbol's sym_valid falls only when the next symbol's third bit arrives
    rep.check(f'{label}: sym_valid rising edges', len(sv_rise) == n_words,
              f'{len(sv_rise)} vs {n_words}')
    exp_rise = [capture_time(first_cap_index + 6 * n + 5) + T_CQ + EDGE / 2 for n in range(n_words)]
    worst = max((abs(a - b) for a, b in zip(sv_rise, exp_rise)), default=0.0)
    rep.check(f'{label}: sym_valid rise = 6th capture + t_cq', worst < TOL, f'worst {worst*1e12:.3f} ps')
    exp_fall = [capture_time(first_cap_index + 6 * (n + 1) + 2) + T_CQ + EDGE / 2 for n in range(len(sv_fall))]
    worst = max((abs(a - b) for a, b in zip(sv_fall, exp_fall)), default=0.0)
    rep.check(f'{label}: sym_valid fall = 3rd capture of next symbol + t_cq', worst < TOL,
              f'worst {worst*1e12:.3f} ps')
    bad = [n for n, t in enumerate(sv_rise) if u.bus_value(edges, SYM, t + 5e-12) != syms[n]]
    rep.check(f'{label}: S2P words equal the sent symbols', not bad, f'{len(bad)} wrong, first {bad[:5]}')

    # encoder: one word per sym_valid falling edge
    p = 0
    exp = []
    for s in syms[:len(sv_fall)]:
        d, f = u.gray_to_bin(s >> 3), u.gray_to_bin(s & 7)
        p = (p + d) % 8
        exp.append((p, d, f))
    rep.check(f'{label}: one enc_valid rising edge per accepted word', len(ev_rise) == len(sv_fall),
              f'{len(ev_rise)} vs {len(sv_fall)}')
    worst = max((abs(e - (s + T_EV + EDGE / 2)) for e, s in zip(ev_rise, sv_fall)), default=0.0)
    rep.check(f'{label}: enc_valid rise = word + t_ev', worst < TOL, f'worst {worst*1e12:.3f} ps')
    ev_fall = [t for t in edges.times(40, 0) if t_from < t < t_to]
    worst = max((abs(e - (s + T_PW)) for e, s in zip(ev_fall, ev_rise)), default=0.0)
    rep.check(f'{label}: enc_valid high for t_pw', worst < TOL, f'worst {worst*1e12:.3f} ps')
    bad = []
    seen = []
    for n, t in enumerate(ev_rise):
        pe, de, fe = exp[n]
        got = (u.bus_value(edges, POS, t), u.bus_value(edges, INC, t), u.bus_value(edges, FC, t),
               u.bus_value(edges, REQ, t))
        if got != (pe, de, fe, 1 << fe):
            bad.append((n, got, (pe, de, fe, 1 << fe)))
        seen.append(8 * got[0] + got[2])
    rep.check(f'{label}: P/D/F/one-hot equal the reference', not bad, f'{len(bad)} wrong, first {bad[:3]}')
    # data outputs change only at word + t_enc
    allowed = [s + T_ENC + EDGE / 2 for s in sv_fall]
    stray = []
    for ident in POS + INC + FC + REQ:
        for t in edges.times(ident):
            if t_from < t < t_to and min(abs(t - a) for a in allowed) > TOL:
                stray.append((ident, t))
    rep.check(f'{label}: encoder outputs change only at word + t_enc', not stray, f'{len(stray)} stray edges')
    return seen


def scenario_debruijn():
    cws = u.codeword_sequence()
    syms = u.symbols_for_codewords(cws)
    bits = symbol_bits(syms)
    # stop after the last word's sym_valid falls, before another word could complete
    stop = capture_time(FIRST_CAP + len(bits) + 3) + 50e-12
    rst = f'[0 1 {u.fmt_ps(RST_RELEASE - 1e-12)} 1 {u.fmt_ps(RST_RELEASE + 1e-12)} 0]'
    return build_tb(bits, rst, stop), syms, cws


def run(name):
    out = u.out_dir_for(f'm1_{name}')
    rep = u.Report(f'm1_{name}')
    if name == 'debruijn':
        tb, syms, cws = scenario_debruijn()
        out.mkdir(parents=True, exist_ok=True)
        (out / 'tb.scs').write_text(tb)
        res = u.run_evas(out / 'tb.scs', out)
        edges = u.parse_edges(res)
        bclk = edges.times(2, 1)
        worst = max(abs(t - capture_time(k)) for k, t in enumerate(bclk))
        rep.check('bclk source edges at delay + k*T', worst < TOL, f'worst {worst*1e12:.3f} ps')
        seen = check_stream(rep, edges, syms, FIRST_CAP, RST_RELEASE, 1.0, 'debruijn')
        rep.check('all 64 absolute codewords observed', len(set(seen)) == 64, f'{len(set(seen))}')
        rep.check('all 4096 ordered adjacent codeword pairs observed',
                  len(set(zip(seen, seen[1:]))) == 4096, f'{len(set(zip(seen, seen[1:])))}')
    elif name == 'reset_repeat':
        # A: symbol Gray(3)Gray(5) eleven times -> P = 3, 6, 1, 4, ...
        sym_a = (u.gray(3) << 3) | u.gray(5)
        part_a = [sym_a] * 11
        # reset during the 12th symbol, after two of its bits
        n_bits_a = 6 * 11 + 2
        t_rst_on = capture_time(FIRST_CAP + n_bits_a - 1) + T / 2
        rst_off_edge = FIRST_CAP + n_bits_a + 7          # released before this capture
        t_rst_off = capture_time(rst_off_edge - 1) + T / 2
        part_b = u.symbols_for_codewords([10, 3, 63, 0, 45, 45, 7])
        bits = symbol_bits(part_a) + [1, 0] + [0] * 7 + symbol_bits(part_b)
        # the PWL helper samples bit j at first_cap + j*T, so the gap bits fill the reset window
        stop = capture_time(rst_off_edge + 6 * len(part_b) + 3) + 50e-12
        rst = (f'[0 1 {u.fmt_ps(RST_RELEASE - 1e-12)} 1 {u.fmt_ps(RST_RELEASE + 1e-12)} 0 '
               f'{u.fmt_ps(t_rst_on - 1e-12)} 0 {u.fmt_ps(t_rst_on + 1e-12)} 1 '
               f'{u.fmt_ps(t_rst_off - 1e-12)} 1 {u.fmt_ps(t_rst_off + 1e-12)} 0]')
        tb = build_tb(bits, rst, stop)
        out.mkdir(parents=True, exist_ok=True)
        (out / 'tb.scs').write_text(tb)
        res = u.run_evas(out / 'tb.scs', out)
        edges = u.parse_edges(res)
        check_stream(rep, edges, part_a, FIRST_CAP, RST_RELEASE, t_rst_on, 'before reset')
        # reset is asynchronous: every output that was high falls within 5 ps
        late = []
        for ident in SYM + POS + INC + FC + REQ + [16, 40]:
            if edges.level(ident, t_rst_on - 1e-15) == 1:
                falls = [t for t in edges.times(ident, 0) if t_rst_on <= t <= t_rst_on + 5e-12]
                if not falls:
                    late.append(ident)
        rep.check('reset clears the outputs at once (asynchronous), not at a clock edge', not late,
                  f'late ids {late}')
        # during reset: outputs return to zero and stay there
        t_mid = (t_rst_on + t_rst_off) / 2
        rep.check('reset clears sym, sym_valid and encoder outputs',
                  u.bus_value(edges, SYM, t_mid) == 0 and edges.level(16, t_mid) == 0
                  and u.bus_value(edges, POS + INC + FC, t_mid) == 0 and u.bus_value(edges, REQ, t_mid) == 0
                  and edges.level(40, t_mid) == 0)
        seen = check_stream(rep, edges, part_b, rst_off_edge, t_rst_off, 1.0, 'after reset')
        rep.check('after reset P restarts from 0 (codewords as sent)', seen == [10, 3, 63, 0, 45, 45, 7],
                  f'{seen}')
    else:
        raise SystemExit(f'unknown scenario {name}')
    rep.write(out)
    print(f"{name}: {'PASS' if rep.ok else 'FAIL'}  ({out})")
    return rep.ok


if __name__ == '__main__':
    names = sys.argv[1:] or ['reset_repeat', 'debruijn']
    ok = all([run(n) for n in names])
    sys.exit(0 if ok else 1)
