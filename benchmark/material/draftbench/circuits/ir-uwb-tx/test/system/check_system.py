"""System check: the hierarchical seed transmitter, from power-up to RF.

uwb_tx_seed (system/tx_seed.va) calibrates its RO against a 48 MHz reference
(n_win = 192), then transmits PRBS data. The checker does not read internal
nodes except the exported frame clock clk672 for the first frame reference: it decodes the transmitted
symbols from outp - outn like a simple receiver and compares them with the
sent symbols.
  - pulses: |outp - outn| above 0.2 V, grouped (gaps under 180 ps bridged);
  - DPPM: D[n] = round(dt/delta) - 16 mod 8 between consecutive pulse starts
    (P[-1] = 0 relative to the frame edge for the first pulse); the pulse start
    is the energy centroid minus half the window (the threshold midpoint used
    first was off by up to 37 ps on cold-start pulses);
  - FSK: zero crossings in the middle half of each pulse -> nearest carrier;
  - symbol = Gray(D) Gray(F).

Usage: python3 check_system.py
"""
import csv
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'lib'))
import uwbtest as u  # noqa: E402

EDGE = 2e-12
T_REF = 1 / 48e6
T_CAL = 50e-9
T_DONE_EST = T_CAL + 11 * 194 * T_REF       # 44.5 us after cal_start
T_DATA = T_DONE_EST + 300e-9                 # bclk starts here
N_SYM = 40


def build(symbols):
    bits = [(s >> (5 - k)) & 1 for s in symbols for k in range(6)]
    first_cap = T_DATA + EDGE / 2
    stop = first_cap + len(bits) * u.T_BIT + 6 * u.TS
    # tx_seed.va includes its modules (Spectre compiles each ahdl_include file alone)
    mods = ['system/tx_seed.va', 'test/sources/clock_source.va', 'test/sources/edge_monitor.va']
    tb = f"""simulator lang=spectre
global 0
{u.include_lines(*mods)}
Xref (ref) uwb_clock_source period={T_REF!r} delay=0.37n tr={EDGE!r}
Xbclk (bclk) uwb_clock_source period={u.T_BIT!r} delay={T_DATA!r} tr={EDGE!r}
Vrst (rst 0) vsource type=pwl wave=[0 1 10n 1 10.002n 0]
Vcal (cal 0) vsource type=pwl wave=[0 0 {u.fmt_ps(T_CAL - 1e-12)} 0 {u.fmt_ps(T_CAL + 1e-12)} 1 {u.fmt_ps(T_CAL + 2e-9)} 1 {u.fmt_ps(T_CAL + 2.002e-9)} 0]
Vdin (din 0) vsource type=pwl wave={u.pwl_bits(bits, first_cap, u.T_BIT)}
Vpol (pol 0) vsource dc=0
Xtx (bclk din rst ref cal pol outp outn done fail conflict nsup clk672) uwb_tx_seed
{u.monitor_lines(dict(done=4, fail=5, conflict=6))}
{u.monitor_lines(dict(clk672=100))}
opts options reltol=1e-6 vabstol=1e-6
tran tran stop={stop!r} maxstep=200p
save outp outn
"""
    return tb, stop


def main():
    rnd = random.Random(7)
    symbols = [rnd.randrange(64) for _ in range(N_SYM)]
    out = u.out_dir_for('system_decode')
    rep = u.Report('system_decode')
    tb, stop = build(symbols)
    out.mkdir(parents=True, exist_ok=True)
    (out / 'tb.scs').write_text(tb)
    res = u.run_evas(out / 'tb.scs', out)
    edges = u.parse_edges(res)
    done = [t for t in edges.times(4, 1) if t > 1e-9]
    rep.check('calibration ends with done before the data starts', bool(done) and done[0] < T_DATA,
              f'done at {done[0]*1e6:.4f} us' if done else 'no done')
    rep.check('no fail and no conflict', not [t for t in edges.times(5, 1) if t > 1e-9]
              and not edges.times(6, 1))
    rows = list(csv.DictReader(open(res['tran'])))
    t = [float(r['time']) for r in rows]
    v = [float(r['outp']) - float(r['outn']) for r in rows]
    rep.check('no RF output before the data', max(abs(x) for ti, x in zip(t, v) if ti < T_DATA) < 1e-9)
    # decode like a receiver: the shared decoder of m5/check_m5.py (pulse
    # groups above 0.2 V, start = energy centroid - 9 delta/2, DPPM from pulse
    # spacing, FSK from zero crossings around the centre)
    sys.path[:0] = [str(Path(__file__).resolve().parent.parent / 'm5'),
                    str(Path(__file__).resolve().parent.parent / 'm4_chain')]
    import check_m5

    class FrameEdges:
        def times(self, ident, direction=None):
            return [x for x in edges.times(100, 1) if x > 1e-9]

    wave = dict(time=t, outp=[float(r['outp']) for r in rows], outn=[float(r['outn']) for r in rows])
    decoded = check_m5.decode(dict(wave=wave, edges=FrameEdges(), recs={}))
    rep.check('one pulse per sent symbol', len(decoded) >= N_SYM, f'{len(decoded)} pulses for {N_SYM} symbols')
    got = decoded[:N_SYM]
    bad = [n for n in range(N_SYM) if got[n] != symbols[n]]
    rep.check('decoded symbols equal the sent symbols (DPPM by pulse spacing, FSK by zero crossings)',
              not bad, f'{N_SYM - len(bad)}/{N_SYM} correct, first wrong {bad[:5]}')
    rep.write(out)
    print(f"system_decode: {'PASS' if rep.ok else 'FAIL'}  ({out})")
    return rep.ok


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
