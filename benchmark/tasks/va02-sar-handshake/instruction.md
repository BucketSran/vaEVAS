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

## Seven-bit asynchronous SAR control
Module `L2_7bit_sar_logic(CLKC,CLKS,DCMPP,DCMPN,CMPCK,DO,DCTRLP,DCTRLN)`.
Input scalars CLKC,CLKS,DCMPP,DCMPN; output CMPCK; output buses DO[6:0],
DCTRLP[6:1],DCTRLN[6:1]. Parameters real vdd=1.1,t_logic_delay=200p.
Logic threshold vdd/2, levels 0/vdd. Output rise/fall time is 10ps.

On initial_step and every rising CLKS, reset the bit index to 6 and all outputs
to zero. A rising CLKC starts a conversion by setting CMPCK high. A rising edge
on either comparator output DCMPP or DCMPN acknowledges the comparison:
set CMPCK low; if index>=0, store (DCMPP>DCMPN) in DO[index]. For index>=1,
a stored one sets DCTRLN[index]=1; a stored zero sets DCTRLP[index]=1.
Previously written bits and controls persist until reset; unselected controls stay 0.
The falling edge of the asserted comparator output advances to the next index;
reassert CMPCK iff another bit remains (index>=0 after decrement). After bit 0,
CMPCK remains low. Its target transitions are delayed by t_logic_delay; bus
targets have zero delay. After completion, no further comparator pulses occur
until reset. A subsequent CLKS resets the whole conversion, including DO.
Stimuli are one-hot comparator pulses, with non-simultaneous separated edges;
CLKC is a single start pulse after reset, and CLKS never overlaps a comparison.
Legal tests use vdd>0 and t_logic_delay>=0, including vdd>2V.
