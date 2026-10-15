# Finite-acquisition track-and-hold

Implement a voltage-domain track-and-hold model for a sampling front end. It must preserve incomplete acquisition and sample history when the acquisition window is short.

## Spec

Use the interface and parameters declared in `/app/circuit.va`. All voltages are relative to ground. Let `x = V(vout)` and `u = (V(vin) - vmid) / vscale`:

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

Change only `/app/circuit.va`. Preserve its declared interface and parameters. Do not drive the input or control ports.

## Deliverable

Edit and submit `/app/circuit.va`. The public example is `/app/testbench/tb.scs`; run it with:

```sh
cd /app/testbench && spectre tb.scs -format psfascii -raw psf
```
