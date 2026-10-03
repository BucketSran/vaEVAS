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

## Loaded, slew-limited single-pole opamp macro model
Module `opamp(vout,vref,vin_p,vin_n,vspply_p,vspply_n)`; all electrical;
vout,vin_p,vin_n inout, other ports input. Real parameters with defaults:
gain=835e3, freq_unitygain=1e6 Hz, rin=1e6 ohm, vin_offset=0 V,
ibias=0 A, iin_max=100u A, slew_rate=0.5e6 V/s, rout=80 ohm, vsoft=0.5 V.
All resistance, frequency, gain, current limit, slew rate and vsoft are positive.

Implement this behavioral circuit (not a hard-clipped voltage source):
- Differential input branch vin_p -> vin_n carries (V(vin_p,vin_n)+vin_offset)/rin.
  Each input receives a bias current ibias flowing from vref to that input.
- Let x be an internal dominant-pole node voltage relative to vref.
  C=iin_max/slew_rate, gm=2*pi*freq_unitygain*C, R=gain/gm.
  A current clip(gm*(V(vin_p,vin_n)+vin_offset),-iin_max,+iin_max) enters x.
  From x to vref connect C, R, and a 100 megaohm shunt in parallel.
- The output is a Thevenin source of voltage x relative to vref with series
  resistance rout. External resistive and capacitive loads must participate in
  the circuit solution; do not force the unloaded output voltage on vout.
- Let y=V(vout) (absolute ground-referenced). Add current leaving the internal
  node: gm*(y-V(vspply_p)+vsoft) if y>V(vspply_p)-vsoft;
  gm*(y-V(vspply_n)-vsoft) if y<V(vspply_n)+vsoft; otherwise zero.
  This is soft-limit feedback, not hard output clipping.
- Use the normal DC operating point to initialize energy storage. No forced
  zero initial condition. No supply-current/power-conservation model is required.

Tests include small-signal gain/dominant-pole response, both polarities of slew
and saturation/recovery, load-dependent response, input bias/offset and finite
input resistance, and a nonzero vref. Equivalent circuit realizations are accepted.
