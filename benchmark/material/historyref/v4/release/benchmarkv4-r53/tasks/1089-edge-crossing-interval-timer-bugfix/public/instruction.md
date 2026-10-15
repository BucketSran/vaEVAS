# Edge Crossing Interval Timer Bugfix

## Task Contract

The supplied Verilog-A system violates its public circuit contract. Repair the
complete editable bundle.

## Public Verilog-A Interface

Preserve this exact artifact and module interface:

- Artifact `cross_interval_163p333_ref.va`:
  - Module `cross_interval_163p333_ref` (entry)
    - position 0: `VDD` (inout, electrical)
    - position 1: `VSS` (inout, electrical)
    - position 2: `a` (input, electrical)
    - position 3: `b` (input, electrical)
    - position 4: `delay_out` (output, electrical)
    - position 5: `seen_out` (output, electrical)

## Public Parameter Contract

- `cross_interval_163p333_ref.vth` defaults to `0.45` V; valid range: finite real within the VSS-to-VDD logic range; sets rising-edge thresholds for a and b relative to VSS.
- `cross_interval_163p333_ref.scale_ps` defaults to `200.0` ps; valid range: scale_ps > 0; sets measured-delay normalization for delay_out.
- `cross_interval_163p333_ref.tedge` defaults to `2e-11` s; valid range: tedge > 0; sets output transition smoothing.


## Required Behavior

The repaired bundle must satisfy every public property:

- `P_A_EDGE_ARMS`: restore: A rising a crossing arms a fresh measurement and clears seen_out until completion. Required traces: `time`, `a_default`, `seen_out_default`, `a_override`, `seen_out_override`.
- `P_FIRST_B_EDGE_CAPTURES`: restore: The first rising b crossing after an armed a edge captures their elapsed time; b edges before arming do not complete a measurement. Required traces: `time`, `a_default`, `b_default`, `delay_out_default`, `seen_out_default`, `a_override`, `b_override`, `delay_out_override`, `seen_out_override`.
- `P_DELAY_NORMALIZATION`: restore: Delay_out equals the VDD-to-VSS rail span multiplied by measured delay in picoseconds divided by scale_ps. Required traces: `time`, `scale_ps_ref_default`, `vdd_default`, `vss_default`, `a_default`, `b_default`, `delay_out_default`, `scale_ps_ref_override`, `vdd_override`, `vss_override`, `a_override`, `b_override`, `delay_out_override`.
- `P_COMPLETION_MARKER`: restore: Seen_out is rail-high after a valid a-then-b capture and rail-low while a newly armed measurement is incomplete. Required traces: `time`, `vdd_default`, `vss_default`, `a_default`, `b_default`, `seen_out_default`, `vdd_override`, `vss_override`, `a_override`, `b_override`, `seen_out_override`.
- `P_SINGLE_CAPTURE_PER_ARM`: restore: Additional b crossings after completion do not change delay_out until the next rising a edge rearms the timer. Required traces: `time`, `a_default`, `b_default`, `delay_out_default`, `seen_out_default`, `a_override`, `b_override`, `delay_out_override`, `seen_out_override`.


The following canonical public behavior is normative for this derived form:

This task asks for the `cross_interval_163p333_ref` behavioral DUT module, not
a testbench. The module measures the interval from a rising edge on
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


## Modeling Constraints

- Use deterministic crossing events and retained measurement state.
- Use rail-referenced smoothed voltage outputs only.
- Do not hard-code validation intervals or use waveform files, transistor-level devices, AC/noise analysis, or simulator side channels.
- Preserve the exact file set, module graph, ports, parameters, and public traces.
- Do not add debug outputs, validation state, side channels, or stimulus-specific fixes.

## Output Contract

Return the repaired bundle with exactly these paths: `cross_interval_163p333_ref.va`.
Every supplied `.va` file is editable; do not add or omit files.
