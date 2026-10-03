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

## Phase-continuous voltage-controlled square-wave oscillator
Module `dig_vco(vin,vout)`. Input vin, output vout. Real parameters:
center_freq=2500 (Hz), vco_gain=1 (Hz/V), vlogic_high=5, vlogic_low=0,
tdel=0, trise=1n, tfall=1n (seconds). Instantaneous frequency
f(t)=center_freq+vco_gain*V(vin). All test frequencies are strictly positive.

At t=0 accumulated phase in cycles is zero and the target output is high.
Accumulate the time integral of instantaneous frequency continuously; do not reset
phase when vin changes. The target is high when fractional phase is in [0,0.5),
low in [0.5,1). Output transition(target,tdel,trise,tfall). Control is constant or
piecewise linear, including changes during an oscillator half-cycle. Need correct
edge times across many cycles and parameter changes. No frequency clipping or
random noise is required. tdel>=0, trise,tfall>0; output levels may be nonzero-low.
