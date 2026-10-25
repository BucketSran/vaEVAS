"""Frozen circuits, independent stimuli and observation contracts for r53."""

from pathlib import Path
from r53_reference import ramp_input, levels, value

SOURCES = Path(__file__).resolve().parents[2] / "examples/xspice/r53"
FILES = {"104": "source_sample_hold.va", "210": "sample_hold_5v_clock.va",
         "148": "four_channel_edge_sampler.va", "115": "two_bit_counter_marker.va",
         "068": "multiphase_clock_generator_4ph.va", "124": "smooth_comparator_tanh.va"}


def pulse_clock(inst, first, high, stop):
    text = f"vc{inst} csrc{inst} 0 pulse(0 {high} {first} 100p 100p 4n 10n)\n"
    text += f"rck{inst} csrc{inst} clk{inst} 1k\ncck{inst} clk{inst} 0 100f\n"
    knots, times = [(0.0, 0.0)], []
    count = int((stop - first) / 10e-9) + 1
    for k in range(count):
        t = first + k * 10e-9
        knots.extend([(t, 0.0), (t + 100e-12, high),
                      (t + 4.1e-9, high), (t + 4.2e-9, 0.0)])
    for k in range(count):
        lo, hi = first + k * 10e-9, first + k * 10e-9 + 1e-9
        for _ in range(70):
            mid = (lo + hi) / 2
            if value(knots, mid, 100e-12) < high / 2:
                lo = mid
            else:
                hi = mid
        if (lo + hi) / 2 < stop:
            times.append((lo + hi) / 2)
    return text, {"knots": knots, "tau": 100e-12, "time_budget": 0.0}, times


def sampler(fid, model, inject=False, bad=False):
    stop = 48e-9
    multi = fid == "148"
    inputs = {"in" + str(i): {"bias": b, "slope": m, "tau": tau}
              for i, (b, m, tau) in enumerate([(0.1, 1e7, 0.7e-9),
                  (0.8, -7e6, 0.4e-9), (0.25, 3e6, 1.1e-9), (0.4, 5e6, 1.5e-9)][:4 if multi else 1])}
    text = "r53 sample capture with external RC networks\n"
    for i, (name, inp) in enumerate(inputs.items()):
        text += f"vd{i} drive{i} 0 pwl(0 {inp['bias']} {stop} {inp['bias']+inp['slope']*stop})\n"
        text += f"ri{i} drive{i} {name} 1k\nci{i} {name} 0 {inp['tau']/1000}\n"
    specs, signals = {}, {}
    for inst in ("a", "b") if multi else ("a",):
        first = 5e-9 if inst == "a" else 7e-9
        high = 1.2 if multi else (5.0 if fid == "210" else 0.9)
        clock_text, signal, times = pulse_clock(inst, first, high, stop)
        text += clock_text
        signals["clk" + inst] = signal
        opts = f'evas_trace="trace-{inst}.csv"'
        if inject and inst == "a":
            opts += " evas_inject=true evas_inject_time=15n"
            if bad:
                opts += " evas_bad_state=true"
        text += f".model m{inst} {model}({opts})\n"
        ports = ["in" + str(i) for i in ([0, 1, 2, 3] if inst == "a" else [2, 0, 3, 1])[:4 if multi else 1]]
        outs = [f"out{inst}{i}" for i in range(len(ports))]
        connection = ["clk" + inst, *ports, *outs] if multi else [ports[0], outs[0], "clk" + inst]
        text += f"a{inst} " + " ".join(connection) + f" m{inst}\n"
        states = [(t, [ramp_input(inputs[p], t) for p in ports]) for t in times]
        specs[inst] = {"events": states, "indices": list(range(len(ports))), "initial": [0.0] * len(ports)}
        for i, (port, out) in enumerate(zip(ports, outs)):
            knots = levels([(t, values[i]) for t, values in states], 0, 50e-12 if multi else (10e-12 if fid == "210" else 20e-12))
            signals[out] = {"knots": knots}
            tau = (0.4 + 0.15 * i + (0.2 if inst == "b" else 0)) * 1e-9
            rc = f"rc{inst}{i}"
            text += f"ro{inst}{i} {out} {rc} 1k\nco{inst}{i} {rc} 0 {tau/1000}\n"
            signals[rc] = {"knots": knots, "tau": tau}
    return text, {"stop": stop, "inputs": inputs, "signals": signals, "states": specs}


def counter(fid, model, inject=False, bad=False):
    stop = 137e-9
    text = "r53 integer counter: three complete wraps and return low\n"
    signals, specs = {}, {}
    for inst, first in (("a", 5e-9), ("b", 7e-9)):
        clock_text, signal, times = pulse_clock(inst, first, 1.0, stop)
        text += clock_text
        signals["clk" + inst] = signal
        opts = f'evas_trace="trace-{inst}.csv"'
        if inject and inst == "a":
            opts += " evas_inject=true evas_inject_time=35n"
            if bad:
                opts += " evas_bad_state=true"
        text += f".model m{inst} {model}({opts})\na{inst} clk{inst} out{inst} m{inst}\n"
        events = [(t, [i % 4, int(i % 4 == 0)]) for i, t in enumerate(times, 1)]
        specs[inst] = {"events": events, "indices": [0, 1], "initial": [0.0, 0.0], "integer": True}
        knots = levels([(t, states[1]) for t, states in events], 0, 10e-12, delay=10e-12)
        signals["out" + inst] = {"knots": knots}
        tau = 0.4e-9 if inst == "a" else 0.7e-9
        text += f"ro{inst} out{inst} rc{inst} 1k\nco{inst} rc{inst} 0 {tau/1000}\n"
        signals["rc" + inst] = {"knots": knots, "tau": tau}
    return text, {"stop": stop, "signals": signals, "states": specs}


def combine(terms):
    times = sorted({t for knots, weight in terms for t, _ in knots})
    return [(t, sum(weight * value(knots, t) for knots, weight in terms)) for t in times]


def clock(fid, model, inject=False, bad=False):
    stop = 57e-9
    text = "r53 pure timer clock with loaded differential reference\n"
    signals, specs, differences = {}, {}, {}
    initial = [0.9, 0.0, 0.0, 0.9]
    events, state = [], initial[:]
    for k in range(1, 12):
        for i in ([1, 3] if k % 2 else [0, 2]):
            state[i] = 0.9 - state[i]
        events.append((k * 5e-9, state[:]))
    level_knots = [levels([(t, s[i]) for t, s in events], initial[i], 20e-12) for i in range(4)]
    for inst, bias, rref in (("a", 0.3, 500.0), ("b", 0.6, 1000.0)):
        opts = f'evas_trace="trace-{inst}.csv"'
        if inject and inst == "a":
            opts += " evas_inject=true evas_inject_time=4n"
            if bad:
                opts += " evas_bad_state=true"
        ref = "vss" + inst
        outs = [f"out{inst}{i}" for i in range(4)]
        text += f"vb{inst} bias{inst} 0 {bias}\nrr{inst} bias{inst} {ref} {rref}\n"
        text += f".model m{inst} {model}({opts})\na{inst} {ref} "
        text += " ".join(f"%vd({n} {ref})" for n in outs) + f" m{inst}\n"
        loads = [20000.0, 30000.0, 40000.0, 50000.0]
        g = 1 / rref + sum(1 / r for r in loads)
        ref_knots = combine([([(0.0, bias / rref / g)], 1),
                             *[(knots, -1 / r / g) for knots, r in zip(level_knots, loads)]])
        signals[ref] = {"knots": ref_knots}
        for i, (out, knots, r) in enumerate(zip(outs, level_knots, loads)):
            signals[out] = {"knots": combine([(ref_knots, 1), (knots, 1)])}
            rc = f"rc{inst}{i}"
            tau = (0.4 + 0.2 * i) * 1e-9
            text += f"rl{inst}{i} {out} 0 {r}\nro{inst}{i} {out} {rc} 1k\nco{inst}{i} {rc} {ref} {tau/1000}\n"
            relative = rc + "_relative"
            differences[relative] = [rc, ref]
            signals[relative] = {"knots": knots, "tau": tau}
        specs[inst] = {"events": events, "indices": [0, 1, 2, 3], "initial": initial}
    return text, {"stop": stop, "signals": signals, "states": specs,
                  "differences": differences, "rollback_kind": "timer"}


def chain(clock_model, sampler_model, mode):
    stop = 58e-9
    text = "same-source timer clock drives RC-coupled sample hold\nvss vss 0 0.1\n"
    initial = [0.9, 0.0, 0.0, 0.9]
    timer_events, state = [], initial[:]
    for k in range(1, 12):
        for i in ([1, 3] if k % 2 else [0, 2]):
            state[i] = 0.9 - state[i]
        timer_events.append((k * 5e-9, state[:]))
    clock_knots = [levels([(t, s[i]) for t, s in timer_events], initial[i], 20e-12) for i in range(4)]
    opts = 'evas_trace="trace-clock.csv"'
    if "clock" in mode:
        opts += " evas_inject=true evas_inject_time=4n"
        if mode.startswith("leak"):
            opts += " evas_bad_state=true"
    text += f".model mc {clock_model}({opts})\nac vss "
    text += " ".join(f"%vd(clk{i} vss)" for i in range(4)) + " mc\n"
    signals = {f"clk{i}": {"knots": [(t, v + 0.1) for t, v in knots]} for i, knots in enumerate(clock_knots)}
    clock_input = signals["clk1"]["knots"]
    signals["sample_clk"] = {"knots": clock_input, "tau": 100e-12}
    text += "rclock clk1 sample_clk 1k\ncclock sample_clk 0 100f\n"
    inp = {"bias": 0.2, "slope": 5e6, "tau": 0.8e-9}
    text += f"vdrive drive 0 pwl(0 0.2 {stop} {0.2+5e6*stop})\nrin drive vin 1k\ncin vin 0 800f\n"
    captures = []
    for start in (5e-9, 25e-9, 45e-9):
        lo, hi = start, start + 1e-9
        for _ in range(70):
            mid = (lo + hi) / 2
            if value(clock_input, mid, 100e-12) < 0.45:
                lo = mid
            else:
                hi = mid
        t = (lo + hi) / 2
        captures.append((t, [ramp_input(inp, t)]))
    opts = 'evas_trace="trace-sample.csv"'
    if "sample" in mode:
        opts += " evas_inject=true evas_inject_time=24n"
        if mode.startswith("leak"):
            opts += " evas_bad_state=true"
    text += f".model ms {sampler_model}({opts})\nas vin out sample_clk ms\nro out rc 1k\nco rc 0 600f\n"
    knots = levels([(t, s[0]) for t, s in captures], 0, 20e-12)
    signals.update(out={"knots": knots}, rc={"knots": knots, "tau": 0.6e-9})
    return text, {"stop": stop, "inputs": {"vin": inp}, "signals": signals,
                  "states": {"clock": {"events": timer_events, "indices": [0, 1, 2, 3], "initial": initial},
                             "sample": {"events": captures, "indices": [0], "initial": [0.0]}}}


def finish(text, cfg):
    differences = cfg.get("differences", {})
    nodes = [*cfg.get("inputs", {}), *(n for n in cfg["signals"] if n not in differences),
             *(p for pair in differences.values() for p in pair)]
    nodes = list(dict.fromkeys(nodes))
    return text + ".options method=gear maxord=2 reltol=1e-10 vntol=1e-13 abstol=1e-16\n.save " + " ".join("v("+n+")" for n in nodes) + f"\n.tran 10p {cfg['stop']} 0 10p\n.control\nset filetype=ascii\nset numdgt=17\nrun\nwrite wave.raw all\nquit\n.endc\n.end\n"
