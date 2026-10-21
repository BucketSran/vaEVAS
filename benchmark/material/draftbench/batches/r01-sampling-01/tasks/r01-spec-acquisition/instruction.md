# Finite-acquisition track-and-hold

Implement a voltage-domain track-and-hold model for a sampling front end. It must preserve incomplete acquisition and sample history when the acquisition window is short.

## Spec

Use the interface declared in `/app/circuit.va`. Implement the following real-valued configurable parameters. All voltages are relative to ground.

| Parameter | Meaning | Default | Valid range |
| --- | --- | --- | --- |
| `vth` | Control threshold | 0.9 V | No additional range constraint |
| `vinit` | Initial and reset target | 0.9 V | No additional range constraint |
| `tau_acq` | Base acquisition time constant | 10 ns | Greater than 0 |
| `vmid` | Input normalization midpoint | 0.9 V | No additional range constraint |
| `vscale` | Input normalization scale | 0.9 V | Greater than 0 |
| `acq_curvature` | Input dependence coefficient | 0.6 | At least 0 |
| `tau_reset` | Reset time constant | 2 ns | Greater than 0 |

Let `x = V(vout)` and `u = (V(vin) - vmid) / vscale`:

```text
tau_eff = tau_acq * (1 + acq_curvature * u*u)

V(rst) > vth:                         dx/dt = (vinit - x) / tau_reset
otherwise, V(track) > vth:            dx/dt = (V(vin) - x) / tau_eff
otherwise:                           dx/dt = 0
```

Initialize `x` to `vinit` at transient start, regardless of the initial control levels. Reset takes priority over tracking and returns the state toward `vinit` with a finite time constant. Releasing reset resumes the applicable mode from the current state.

Tracking uses the instantaneous input throughout the acquisition window. Entering hold freezes the current state; starting another acquisition continues from that state. Control changes must not introduce output jumps. Do not add charge injection, droop, clipping, or output smoothing.

Voltage parameters are in volts, time constants in seconds, and `acq_curvature` is dimensionless. Experiments use `vin` between 0.1 and 1.7 V and 0/1.8 V controls with 200 ps linear edges. Acquisition windows are 4–100 ns, reset pulses are 2–20 ns, and holds are at most 20 µs. Inputs may change during tracking or hold, and reset may interrupt either mode. Initial control levels may be high or low. Parameter overrides are `vinit` in 0.4–0.9 V and `tau_acq` in 10–17 ns; the other parameters use their declared defaults.

The maximum absolute output error against the specified continuous response must be at most 2 mV over each tested trajectory. This is model accuracy: a short-window sample may remain far from `vin` and still be correct.

### Constraints

Change only `/app/circuit.va`. Preserve its declared interface and implement the parameter requirements above. Do not drive the input or control ports.

## Deliverable

Edit and submit `/app/circuit.va`. The public example is `/app/testbench/tb.scs`; run it with:

```sh
cd /app/testbench && spectre tb.scs -format psfascii -raw psf
```

This is an implementation task, not a repository-audit task.
Work in /app and modify only the declared deliverable; do not edit public development benches, model libraries, or external fixtures.
Make one bounded inspection pass over this instruction, the declared deliverable, supplied starter material, and public development benches.
As the task solver, create a runnable candidate in the file named in the Deliverable section before beginning detailed exploration, and keep that file updated as you work.
If your working time expires, the evaluator copies that file exactly as it exists at that moment and runs the verifier on it.
If the file is missing or empty, the result is zero reward.
Temporary files are not submitted.

If a concrete model, tool, or execution problem appears, investigate it as needed before continuing.
Iterate by editing the declared deliverable and using public development benches to diagnose observed behavior.
Do not repeatedly enumerate files, reread unchanged references, or retry unchanged discovery commands instead of editing and simulating.
