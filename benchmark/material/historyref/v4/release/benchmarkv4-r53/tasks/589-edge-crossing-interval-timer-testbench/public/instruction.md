# Edge Crossing Interval Timer Testbench

## Task Contract

Write one top-level Spectre testbench that verifies the public contract of the
supplied read-only `Edge Crossing Interval Timer` DUT. The evaluator runs the same submitted bytes
against the correct DUT and five anonymous semantic negative DUTs. Your
testbench must accept the correct DUT and expose all five behavioral faults.

## Public Verilog-A Interface

- Artifact `cross_interval_163p333_ref.va`:
  - Module `cross_interval_163p333_ref` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `a` (input, electrical)
    - position 3: `b` (input, electrical)
    - position 4: `delay_out` (output, electrical)
    - position 5: `seen_out` (output, electrical)

Stable public Spectre binding:

The submitted `testbench.scs` must use the supplied DUT through this public binding:

- Include path: `./dut/cross_interval_163p333_ref.va`
- DUT instance: `IDUT (vdd vss a b delay_out seen_out) cross_interval_163p333_ref`
- Required saved public traces: `vth_ref_default`, `scale_ps_ref_default`, `tedge_ps_ref_default`, `vdd_default`, `vss_default`, `a_default`, `b_default`, `delay_out_default`, `seen_out_default`, `vth_ref_override`, `scale_ps_ref_override`, `tedge_ps_ref_override`, `vdd_override`, `vss_override`, `a_override`, `b_override`, `delay_out_override`, `seen_out_override`
- Use one bounded transient analysis with a finite positive stop time.

You must design the stimulus yourself. Save traces as bare public signal names
(for example `clk`, not suffixed or hierarchical forms such as `clk:V` or
`XDUT.clk`). Do not redefine the DUT, drive DUT output nets, save
hierarchical/private nodes, or use checker/gold/internal files.

## Public Parameter Contract

- `cross_interval_163p333_ref.vth` defaults to `0.45` V; valid range: finite real within the VSS-to-VDD logic range; sets rising-edge thresholds for a and b relative to VSS.
- `cross_interval_163p333_ref.scale_ps` defaults to `200.0` ps; valid range: scale_ps > 0; sets measured-delay normalization for delay_out.
- `cross_interval_163p333_ref.tedge` defaults to `2e-11` s; valid range: tedge > 0; sets output transition smoothing.


## Required Behavior

Create stimulus and save traces sufficient for the fixed evaluator oracle to check:

- `P_A_EDGE_ARMS`: exercise and make observable: A rising a crossing arms a fresh measurement and clears seen_out until completion. Required traces: `time`, `a_default`, `seen_out_default`, `a_override`, `seen_out_override`.
- `P_FIRST_B_EDGE_CAPTURES`: exercise and make observable: The first rising b crossing after an armed a edge captures their elapsed time; b edges before arming do not complete a measurement. Required traces: `time`, `a_default`, `b_default`, `delay_out_default`, `seen_out_default`, `a_override`, `b_override`, `delay_out_override`, `seen_out_override`.
- `P_DELAY_NORMALIZATION`: exercise and make observable: Delay_out equals the VDD-to-VSS rail span multiplied by measured delay in picoseconds divided by scale_ps. Required traces: `time`, `scale_ps_ref_default`, `vdd_default`, `vss_default`, `a_default`, `b_default`, `delay_out_default`, `scale_ps_ref_override`, `vdd_override`, `vss_override`, `a_override`, `b_override`, `delay_out_override`.
- `P_COMPLETION_MARKER`: exercise and make observable: Seen_out is rail-high after a valid a-then-b capture and rail-low while a newly armed measurement is incomplete. Required traces: `time`, `vdd_default`, `vss_default`, `a_default`, `b_default`, `seen_out_default`, `vdd_override`, `vss_override`, `a_override`, `b_override`, `seen_out_override`.
- `P_SINGLE_CAPTURE_PER_ARM`: exercise and make observable: Additional b crossings after completion do not change delay_out until the next rising a edge rearms the timer. Required traces: `time`, `a_default`, `b_default`, `delay_out_default`, `seen_out_default`, `a_override`, `b_override`, `delay_out_override`, `seen_out_override`.

Use any deterministic stimulus layout that makes every required public behavior
observable. Exact event counts, absolute event times, sample density, and
reference-deck ordering are not part of the contract unless stated explicitly
above.


The following canonical public behavior is normative for this derived form:

The supplied DUT measures the interval from a rising edge on
`a` to the next rising edge on `b` and exposes both the measured interval and a
completion marker.

Required observable behavior:

- On a rising `a` crossing, arm a fresh measurement and clear the completion
  marker.
- On the first rising `b` crossing after the armed `a` edge, compute the elapsed
  time in picoseconds.
- Drive `delay_out` as `V(VDD,VSS) * measured_delay_ps / scale_ps`.
- Drive `seen_out` high after a valid `a`-then-`b` measurement and low while a
  measurement is armed but incomplete.
- Ignore additional `b` crossings until a new rising `a` edge starts the next
  measurement.

Use voltage-coded logic referenced to `VDD` and `VSS`, keep the model pure
behavioral Verilog-A, and do not use transistor-level devices, AC/noise
analysis, waveform files, validation artifacts, or simulator side channels.


The required trace names are: `time`, `vth_ref_default`, `scale_ps_ref_default`, `tedge_ps_ref_default`, `vdd_default`, `vss_default`, `a_default`, `b_default`, `delay_out_default`, `seen_out_default`, `vth_ref_override`, `scale_ps_ref_override`, `tedge_ps_ref_override`, `vdd_override`, `vss_override`, `a_override`, `b_override`, `delay_out_override`, `seen_out_override`.

## Modeling Constraints

- Submit one self-contained top-level transient `.scs` file.
- Use only the declared `./dut/...` source paths and public DUT interfaces.
- Do not redefine the DUT, drive declared DUT outputs, inspect private internals,
  access undeclared files, or emit a self-reported result.
- Missing traces, setup errors, and invalid runs do not count as behavioral kills.

## Output Contract

Return exactly one artifact named `testbench.scs`. Do not return a DUT,
checker, script, data file, waveform, or auxiliary deck.
