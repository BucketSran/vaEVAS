from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROFILES = {
    "tight": {"reltol": 1e-9, "vabstol": 1e-12, "iabstol": 1e-15, "maxstep": "1n"},
    "refined": {
        "reltol": 1e-10,
        "vabstol": 1e-13,
        "iabstol": 1e-16,
        "maxstep": "0.25n",
    },
}
BASE = {
    "timer_start": 1.08e-6,
    "delay": 40e-9,
    "rise": 200e-9,
    "fall": 400e-9,
    "reset_value": 0.05,
}
CASES = {
    "timer_after": dict(BASE),
    "timer_before": dict(BASE, timer_start=0.98e-6),
    "queued_pulse": dict(BASE, timer_start=1.025e-6, delay=120e-9),
    "feedback": dict(BASE, timer_start=2.2e-6, feedback=True),
    "clock_feedback": dict(BASE, timer_start=1.18e-6, clock_feedback=True),
}
TOL = {
    "event_time_s": 50e-12,
    "voltage_V": 20e-6,
    "sequence": 1e-5,
    "rollback_pair_V": 5e-8,
}


def decks(cfg, prof, library, inject=False, bad=False, inject_time=0):
    ps = {k: cfg[k] for k in ("timer_start", "delay", "rise", "fall", "reset_value")}
    params = " ".join(f"{k}={v}" for k, v in ps.items())
    specsrc = "vclock (clk 0) vsource type=pulse val0=0 val1=1.8 delay=1u rise=10n fall=10n width=1u period=3u"
    ngsrc = "vclock clk 0 pulse(0 1.8 1u 10n 10n 1u 3u)"
    if cfg.get("clock_feedback"):
        ngsrc = "vclock pulse 0 pulse(0 1.8 1u 10n 10n 1u 3u)\nefb drive pulse out 0 0.2\nrclk drive clk 1k\ncclk clk 0 100p"
        specsrc = "vclock (pulse 0) vsource type=pulse val0=0 val1=1.8 delay=1u rise=10n fall=10n width=1u period=3u\nefb (drive pulse out 0) vcvs gain=0.2\nrclk (drive clk) resistor r=1k\ncclk (clk 0) capacitor c=100p"
    if cfg.get("feedback"):
        ngdin = "vbias bias out .2\nrfb bias din 1k\ncfb din 0 1n"
        spdin = "vbias (bias out) vsource dc=.2\nrfb (bias din) resistor r=1k\ncfb (din 0) capacitor c=1n"
    else:
        ngdin = "vdin din 0 pwl(0 .1 9u 1.0)"
        spdin = "vdin (din 0) vsource type=pwl wave=[0 .1 9u 1.0]"
    saves = "clk din out held count ticks order stamp"
    ng = f"""Generated timer-transition sample hold
{ngsrc}
{ngdin}
ash din clk out held count ticks order stamp sh
.model sh sample_hold_cm({params} evas_inject={"true" if inject else "false"} evas_bad_state={"true" if bad else "false"} evas_inject_time={inject_time} evas_trace="trace.csv")
.options method=gear maxord=2 reltol={prof["reltol"]} vntol={prof["vabstol"]} abstol={prof["iabstol"]}
.save {" ".join("v(" + x + ")" for x in saves.split())}
.tran 1n 8.4u 0 {prof["maxstep"]}
.control
set filetype=ascii
set numdgt=17
run
write wave.raw all
option
rusage tranpoints accept rejected traniter
quit
.endc
.end
"""
    sp = f"""simulator lang=spectre
global 0
ahdl_include "sample_hold.va"
{specsrc}
{spdin}
sh (din clk out held count ticks order stamp) sample_hold {params}
opts options reltol={prof["reltol"]} vabstol={prof["vabstol"]} iabstol={prof["iabstol"]} temp=27
tran tran stop=8.4u maxstep={prof["maxstep"]} method=gear2only errpreset=conservative
save {saves}
"""
    return ng, sp
