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

## Periodic ZOOM/SAR ADC timing generator
Module `CLOCK_VA(RST,S,SAR,RES,INT,CLK_SAR,ZOOM,CLK_ZOOM,RST_ZOOM)`;
all ports are outputs. Every output starts low. High level vdd, low 0; use
transition(target,0,trise,tfall). Target pulse start times and widths below are
before transition smoothing. For every m>=0 define B=init_delay+m*RST_period.
Indices i=0..S_num-1, j and k as indicated:

| Output | Start time | Width |
|---|---|---|
|RST|B|RST_width|
|S|B+S_delay+i*S_interval|S_width|
|SAR|B+SAR_delay+i*S_interval|SAR_num*SAR_interval|
|CLK_SAR|B+SAR_delay+i*S_interval+j*SAR_interval, j<SAR_num|SAR_width|
|RES|B+RES_delay+i*S_interval+j*RES_interval, j<RES_num|RES_width|
|INT|B+INT_delay+i*S_interval+j*INT_interval, j<INT_num|INT_width|
|ZOOM|B+ZOOM_delay+i*S_interval+j*INT_interval, j<INT_num|ZOOM_num*ZOOM_interval|
|CLK_ZOOM|B+ZOOM_delay+i*S_interval+j*INT_interval+k*ZOOM_interval, j<INT_num,k<ZOOM_num|ZOOM_width|
|RST_ZOOM|B+INT_delay+i*S_interval+j*INT_interval+INT_width+0.5ns, j<INT_num|4ns|

Defaults (SI units, *_num are integer, others real):
- `vdd = 1.1`
- `init_delay = 5e-09`
- `trise = 1e-10`
- `tfall = 1e-10`
- `RST_period = 3.2e-06`
- `RST_width = 9.5e-09`
- `S_delay = 1e-08`
- `S_interval = 8e-07`
- `S_width = 5e-08`
- `S_num = 4`
- `SAR_delay = 6.5e-08`
- `SAR_width = 2.5e-09`
- `SAR_interval = 5e-09`
- `SAR_num = 7`
- `RES_delay = 1.05e-07`
- `RES_width = 2e-08`
- `RES_interval = 8e-08`
- `RES_num = 8`
- `INT_delay = 1.3e-07`
- `INT_width = 2.5e-08`
- `INT_interval = 8e-08`
- `INT_num = 8`
- `ZOOM_delay = 1.6e-07`
- `ZOOM_width = 2.5e-09`
- `ZOOM_interval = 5e-09`
- `ZOOM_num = 4`

Tests use positive counts and intervals, positive edge times much shorter than pulse
widths, and pulses of each individual output that do not overlap or cross its next
RST period. Different outputs may overlap intentionally. Counts and delays vary.
