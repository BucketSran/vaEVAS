"""Frozen P0 stimuli; the prior alias VA files remain byte-identical."""

from fractions import Fraction
from pathlib import Path

SOURCES = Path(__file__).resolve().parents[2] / "examples/xspice/aliases"
FILES = {"affine": "affine_input_aliases.va", "selected": "selected_body_alias.va",
         "direct": "direct_input_expressions.va"}
CASES = ("ramp", "supply", "selected", "commonmode", "direct")
BUDGETS = {"event_s": 1e-13, "state_V": 1e-4, "platform_V": 1e-4,
           "edge_V": 5e-3, "rc_V": 1e-4, "pair_event_s": 2e-13,
           "pair_platform_V": 2e-4, "pair_edge_V": 1e-2,
           "pair_grid_s": 1e-9, "retry_pair_V": 5e-8}


def configuration(case):
    if case not in CASES:
        raise ValueError(case)
    stop = 6e-9
    clk = [(0, 0), (4e-9, 1.2), (stop, 1.2)]
    vdd = [(0, 1.2), (4e-9, 1.4), (stop, 1.4)]
    root, captured = Fraction(28, 11), Fraction(221, 550)
    if case == "supply":
        clk = [(0, .8), (stop, .8)]
        vdd = [(0, 1.6), (4e-9, .8), (stop, .8)]
        root, captured = Fraction(1), Fraction(17, 50)
    selected = case == "selected"
    if selected:
        captured = Fraction(193, 550)
    vin = [(0, .5 if selected else .3), (3e-9, .56 if selected else .36),
           (3.02e-9, .8), (stop, .8)]
    instances, inputs = {}, {}
    for inst in ("a", "b") if case == "commonmode" else ("a",):
        shift = .4 if inst == "b" else 0
        ports = {p: p + inst for p in ("clk", "vin", "vdd", "vss", "y")}
        for port, knots in {"clk": clk, "vin": vin, "vdd": vdd,
                            "vss": [(0, .2), (stop, .2)]}.items():
            inputs[ports[port]] = [(t, v + shift) for t, v in knots]
        instances[inst] = {"ports": ports, "output": ports["y"], "rc": "rc" + inst,
                           "tau_s": .9e-9 if inst == "b" else .6e-9,
                           "event_ns": [root.numerator, root.denominator],
                           "captured_V": [captured.numerator, captured.denominator],
                           "initial": 0.0, "rise_s": 50e-12}
    return {"case": case, "source": "selected" if selected else "direct" if case == "direct" else "affine",
            "stop": stop, "inputs": inputs, "instances": instances,
            "budgets": BUDGETS,
            "answer_basis": "PWL algebra: .3x=.7+.025x gives28/11ns and221/550V; constant clock gives1ns and17/50V. Selected body captures .3+.02*(28/11)=193/550V. RC solves tau*y'+y=u with y(0)=0."}


def deck(cfg, model, mode="normal"):
    text = "P0 moving threshold, event capture and downstream RC\n"
    for name, knots in cfg["inputs"].items():
        text += "v" + name + " " + name + " 0 pwl(" + " ".join(
            f"{t:.17g} {v:.17g}" for t, v in knots) + ")\n"
    for inst, spec in cfg["instances"].items():
        options = f'evas_trace="trace-{inst}.csv"'
        if inst == "a" and mode in ("retry", "leak"):
            options += " evas_inject=true evas_inject_time=2n"
            if mode == "leak":
                options += " evas_bad_state=true"
        text += f".model m{inst} {model}({options})\na{inst} " + " ".join(
            spec["ports"][p] for p in ("clk", "vin", "vdd", "vss", "y")) + f" m{inst}\n"
        text += f"ro{inst} {spec['output']} {spec['rc']} 1k\nco{inst} {spec['rc']} 0 {spec['tau_s']/1000:.17g}\n"
    nodes = [*cfg["inputs"], *(s[n] for s in cfg["instances"].values() for n in ("output", "rc"))]
    step = ".5p" if mode == "dense" else "1p"
    return (text + ".options method=gear maxord=2 reltol=1e-10 vntol=1e-13 abstol=1e-16\n.save "
            + " ".join("v(" + n + ")" for n in nodes)
            + f"\n.tran {step} {cfg['stop']:.17g} 0 {step}\n.control\nset filetype=ascii\nset numdgt=17\nrun\nwrite wave.raw all\nquit\n.endc\n.end\n")
