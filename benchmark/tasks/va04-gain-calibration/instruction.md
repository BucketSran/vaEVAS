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

## Alternating pipeline ADC gain calibration controller
Module `TEST_D2A_PIPE_ADC_GAIN_CAL(DIN2,DOUT1,CLKS,GAINCTRL,DDIFF,DOP,DOM,GCTRLCODE)`.
Inputs DIN2[6:0],CLKS; outputs DOUT1[3:0],GAINCTRL[6:0] and scalar diagnostics.
Parameters real Vlo=0,Vhi=0.9,Vth=0.45,tt=100p; integer gaincodeinit=90 (0..127).
Use tt for every output's rise/fall transition, no delay. Bus bit 0 is LSB.

Initially: gain code=gaincodeinit, DOUT1=8, stored positive ADC code P=96,
stored negative ADC code M=32, difference D=0. At successive rising CLKS edges:
1. First/odd edge: decode DIN2 bits using strict >Vth; update M. Keep D,P,gain
   unchanged; set DOUT1=7.
2. Second/even edge: update P from DIN2; set D=P-M (signed), then update
   gain = clamp(gain + 64 - D, 0, 127); set DOUT1=8.
Repeat. Falling clocks do nothing. DIN2 can change between edges without changing
stored state. Drive DOUT1 and GAINCTRL as logic buses Vlo/Vhi. Diagnostic voltage
DDIFF=D/100 V, DOP=P/100 V, DOM=M/100 V, GCTRLCODE=gain/100 V, regardless of Vhi.
Legal tests vary levels, thresholds, tt, initial code, and ADC code sequence;
negative differences and both clipping boundaries must work.
