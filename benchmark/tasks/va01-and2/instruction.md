Write a self-contained Spectre-compatible Verilog-A model to `/work/dut.va`.
Use standard `disciplines.vams` and `constants.vams` headers as needed. All ports
use the electrical discipline. Preserve the module, port order, parameter names,
and bus indices specified below. Do not read external files, launch processes,
or inspect simulator identity. Equivalent implementations are accepted.

The evaluator checks transient behavior, initialization, multiple legal parameter
settings, and external loading where specified. Only this specification is provided;
the reference source and tests are hidden. No simulator feedback is available in
this one-shot track. Return only the complete Verilog-A source, without explanation.
The runner saves your response as `/work/dut.va`.

## Two-input analog logic AND (control task)
Module `and2(out, in1, in2)`. Inputs in1,in2; output out.
Parameters: real vh=1.1, vl=0, vth=0.55, td=0, tt=0 (seconds for td,tt).
The target output is vh exactly when BOTH inputs are strictly greater than vth,
otherwise vl. Detect threshold crossings so a large solver timestep does not miss
changes. Drive the output through transition(target,td,tt), including correct DC
and initial output. tt=0 is permitted (simulator minimum transition applies).
Tested inputs do not linger exactly on the threshold; vh>vl, td>=0, tt>=0.
