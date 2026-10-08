# Integrated engineering checkpoint

The PR #108 candidate now includes reviewed main `1dd8875b` through merge
`f90971f0735054b3772415cf431ec7058fe62553`. A new local run recompiles all 12
original paper models with that frontend and executes the debug kernel. Each
condition runs once on its original query grid and once on the saved Spectre
grid, for 24 kernel requests. All 24 produce waveforms. The event records remain
identical across the two grids for all 12 conditions.

This checks the integrated candidate. It does not describe main or grant paper
qualification. The original 48-slot result and its I/F/X records remain unchanged.

## Actual Spectre comparison

The reference is actual Spectre 21.1.0.509.isr12 output. Four references come from
the earlier corrected-reference batch, and eight from the original paper batch.
Their source bytes match the frozen cards. The models, stimuli, instance
parameters and original execution controls are unchanged. This replay needs no
new Spectre execution; it tests the current EVAS compiler and kernel against
those saved observations. It does not substitute analytic waveforms for Spectre.

There are 410,908 pairs at identical parsed binary64 times, without interpolation
or nearest-point matching. Spectre has one record after the original stop in
each of EV-SH-01, TM-01 and CO-SH-01. Those three records remain in the reference
denominator and the receipt; EVAS is not run beyond the requested stop.

| Condition | Paired rows | Selected difference outside original windows | Whole-trace difference that must remain visible |
| --- | ---: | --- | --- |
| VR-01 | 30,008 | Output 4.44e-16 V | Same finite maximum |
| EX-01 | 40,005 | Frequency marker 0 V | Same finite maximum |
| EV-SH-01 | 45,836 | Held voltage 0.300 mV | 0.5997 V and a count-stage difference |
| EV-HC-01 | 20,371 | Output/count 0 V | Same finite maximum |
| EV-HC-02 | 30,368 | Output/count 0 V | 0.8 V and a count-stage difference |
| TM-01 | 40,376 | Edge output 2.000 mV | State/count-stage difference; edge maximum 2.000 mV |
| CP-01 | 30,006 | Unwrapped phase 6.00e-9 cycle | Same finite maximum |
| CP-02 | 30,855 | Phase 5.57e-14 cycle; sine 9.24e-9 V | Ordinary phase difference near 1 cycle at a wrap |
| SI-01 | 35,785 | Both held outputs 0.100 mV | Held output up to 0.4499 V and count-stage differences |
| CO-SH-01 | 46,083 | Output 0.0499192 mV; state 0.004 mV | Output 0.050 mV; count difference 0 |
| CO-HC-01 | 20,375 | Output 0.032 mV; state/count 0 | Same finite maximum |
| CO-VCO-01 | 40,840 | Phase 1.01e-8 cycle; sine 6.35e-8 V | Ordinary phase difference near 1 cycle at a wrap |

The windows and budgets were fixed before these executions. Windowed differences
help locate an error; they do not erase the whole-trace differences or establish
a shared legal callback history. Circular phase agreement does not settle the
exact wrap side. Input, export and native-observation qualification remains I.
The C1 diagnostic, VCO exact-neighbor probes and original PR #79 stop=3 contract
retain their separate failures and missing observations. They are not replaced
by the 12 paper conditions.

For CO-SH-01, the earlier combined candidate had three count-stage mismatches
and a 1.05 V maximum state difference against this same reference. The current
candidate has no count difference on the paired rows and a 4 µV maximum state
difference. This confirms progress in the integrated implementation. The older
kernel ran on Linux and the new one on macOS; it does not isolate the cause to
one patch or claim a new numerical algorithm in this increment.

## Regression and delivery scope

The new public-API regression
[`test_paper_scenarios.py`](../../../evas/tests/test_paper_scenarios.py) uses the
unchanged models and their independent card anchors. It checks held/continuous
values, final callback counts, and identical event records and common outputs
when each event/wrap window's start, center and end are added as queries, together
with anchor-interval midpoints. This regression does not request the paper's
20 ps window grid. These finite checks cannot
prove complete edges, all event timing or wrap counts, rollback, or paper
observation qualification. Existing targeted lifecycle tests remain required.

The numerical-assurance workflow now also runs the existing paper design,
criteria and backend/table calibration suites. Local synthetic calibration and
CI do not execute Spectre. Production event semantics have not changed in this
increment. PR #108 stays draft pending its original boundary obligations.

[The compact receipt](evidence/integrated-core-v1-20261009.json) records all ports,
all/windowed maxima, missing reference rows, original/new identities and the
reused reference selection. The raw bundles, scripts and full logs are local-only
at the project-visible worktree's `runs/engineering-checkpoint-20261009/`.
Kernel build revision is unreported; the receipt records its actual binary hash,
platform/version response, source checkout and empty production diff separately.
The receipt also binds the observed Cargo build command/log, toolchain and Git
source trees. This local build provenance does not invent an embedded revision.
Checksums do not provide public access to those raw files.
