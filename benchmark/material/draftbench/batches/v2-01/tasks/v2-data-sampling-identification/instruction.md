# Model a sampling stage from transistor-circuit observations

Build a free-running voltage-domain Verilog-A model of the supplied SKY130 sampling-stage observations. Predict complete output trajectories for new input and clock histories.

## Spec

Use the module and ordered electrical interface in the starter. `vin` and `clock` are inputs; `vhold` is the predicted output. The source circuit is the JKU / Manuel Moser sampling stage simulated with ngspice. These observations are transistor simulations, not measured silicon or a behavioral model.

The circuit tracks when `clock < 0.9 V` and holds when `clock > 0.9 V`. Its transmission gate, dummy compensation, clock inverter and 2.44 pF holding capacitor operate at fixed 1.8 V, 25 degrees C and the tt corner. You may choose the model's internal structure, but it must retain finite acquisition and the preceding output state. A short acquisition need not reach the new input.

The read-only `testbench/data/*.csv` records have columns `time_s,vin_V,clock_V,vhold_V`, in seconds and volts. `testbench/experiments.json` provides the exact input and clock PWL knots, initial input and acquisition/hold windows. Reconstruct stimuli by linear interpolation between their knots. Quiet observation regions are compressed to a 2 ns grid; acquisition and transition regions retain 50 ps observations. All stimulus knots are separately recorded. Output observations are fitting targets; never feed the observed output back into the running model.

Each experiment starts independently with `clock=0` and output equal to the initial `vin`. The following 30 ns of visible tracking history belongs to that experiment. The fixed data package does not provide online queries to the source circuit. You may repeatedly simulate your own candidate.

There are 32 complete training experiments and two public self-tests. Four whole new experiments are held out; adjacent samples are not randomly split between training and evaluation. The prediction domain is `vin=0.2..1.6 V`, a 0/1.8 V clock, 20 ps stimulus edges, tracking durations of 0.8..6 ns and holding intervals around 20..30 ns. Input changes occur from 3 ns before to 1 ns after acquisition begins. Each record contains four to six cycles, including new combinations of intermediate inputs, durations, prior cycles and phase. Initial inputs are within 0.2..1.6 V and are fully supplied in each stimulus.

Each evaluated experiment must satisfy every applicable window:
- acquisition RMS voltage error at most 25 mV;
- sample error, at the experiment-defined time approximately 0.35 ns after acquisition ends, at most 50 mV;
- maximum absolute error within each hold window at most 50 mV.

The first 0.3..0.4 ns following the relevant edge is excluded as specified by each experiment's exact windows. Hold accuracy concerns the retained state; separate identification of long-term leakage, pedestal and feedthrough is outside this task. Do not realign predicted waveforms in time or dilute short acquisition errors with long quiet regions.

The candidate runs unchanged on the fixed Spectre backend and is compared independently with the source-circuit observations. Rechecking a candidate does not require the PDK. Regenerating the source observations would require the fixed SKY130 library and ngspice 47, and is not part of the task. All required checks must pass for score 1. A failed executed attempt scores 0 with its cause reported separately; an execution failure is not evidence of a semantic model error.

## Deliverable

- Edit `/app/circuit.va` and implement the starter's `sampling_model` interface without changing its module name, port names or order.
- Deliver a model that predicts new input and clock histories without output feedback or replaying recorded output trajectories. Any internal model and legal Verilog-A accepted by the declared backend may be used if they satisfy this contract.
- Keep the supplied observations, stimuli and diagnostic code unchanged. Only the declared VA file is collected.

Run `python3 testbench/check.py --output /app/output/public-check` from `/app` for the public self-tests. Read [the public testbench instructions](testbench/README.md) for backend setup, diagnostic outputs and observation-window details.

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
