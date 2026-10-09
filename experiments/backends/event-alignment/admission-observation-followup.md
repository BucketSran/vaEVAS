# Compilation, reference precision and observation follow-up

This is an unmerged follow-up to PR #108. It does not replace the original
C1, #79 or VCO boundary verdicts. Runtime checks below use `5ddf820d8b4aa5f0c847905da86f4fee470b94db`;
the paper runner at `830c8168ada17122bb64932553a02591181461d9` has identical EVAS
runtime sources. New execution and qualification results are recorded separately.

## Compilation admission

Active expanded decimal literals require digits on both sides of a decimal
point. Electrical declarations and constants must have an explicit supported
definition or include. The versioned built-in voltage-domain header is a limited
standard environment, not an implicit declaration and not the full Verilog-AMS
discipline implementation. Each independent source root has its own macro,
include-guard and nature/discipline environment; includes within that root share
the environment. Module definitions remain available for hierarchy construction.
See [the frontend contract](../../../evas/docs/frontend-admission.md).

Three new actual Spectre configurations isolate the root-scope rule. If module B
omits its header, both A-then-B and B-then-A reject `electrical` in B with
VACOMP-2259/1814. If every module explicitly includes the same guarded header,
the simulation completes. EVAS previously accepted the first order; commit
`1c3708e5` removes this order dependence. Existing frozen models remain unchanged.

Active package and differential-test sources now use explicit headers and legal
decimal literals. The six frozen smoke sources are unchanged: recompilation
accepts three and refuses three. The default eleven-condition differential lane
retains those three as `compile_refused` and continues the remaining conditions.
Separately named successor fixtures retain the original manifests and change
only the headers/literal spelling needed for admission. A local ngspice 47 run
completed six conditions, retained three compile refusals and two unsupported
conditions. That run used the worker's older debug kernel and is a CI-consumer
check, not a comparison of the current integrated runtime.

## Reference precision is an observed result

The [reference workflow](reference-precision.md) freezes the model, requested
observations, per-output budgets and target/confirmation pair before execution.
It keeps every attempted level, the actual setting readback and the independent
checker result. It cannot convert a failed reference into a passing one by
choosing another pair after seeing the outputs.

The newly executed M1 ladder uses the same source and `traponly`, with maxstep
125 ns. Each level has a successful scoped setting readback.

| Level | reltol / vabstol / iabstol | Maximum independent z error | Independent result |
| --- | --- | --- | --- |
| Baseline | 1e-9 / 1e-11 V / 1e-15 A | 1.174248113e-6 V | F |
| Target | 1e-10 / 1e-12 V / 1e-16 A | 3.318596315e-7 V | P |
| Confirmation | 1e-11 / 1e-13 V / 1e-17 A | 8.675726419e-9 V | P |

These results show decreasing continuous-output error in this experiment. The
separate target/confirmation exact-time comparison still contains 69 values
outside their original per-output budgets. Its largest h2 timestamp-output
difference is 3.129306707e-7 V against 1e-7 V. Three required binary64 times are
missing from both outputs. The finite stability qualification remains I, with
the known pairwise failures retained. The independent checker has its original
serialization allowance and common-event-history contract; it answers a
different question from this exact-time comparison. Neither result replaces
the other.

## Boundary controls retain the original failures

For #79, four new runs compare the original model and a print-only observer,
each with short and extended stop. Within each duration, all saved values and
times are identical between the two sources. The short and extended runs also
have an identical 654-row prefix. At exactly 3 s, count remains 1, preserving
the original strict failure. The second actual callback occurs at
3.00000000113469411644 s; at 3 s + 200 ns, count is 2. The continuous error is
below 1 microvolt throughout both saved trajectories. A roughly 0.542 nV
history offset explains most of the late crossing. This finite observation
does not identify Spectre's private integration algorithm.

The extended run actually contains the requested 3 s + 400 ns row and final
log record, but its coarse setting export prints stop as 3 s. That exact
setting comparison remains a mismatch; it is not evidence that the simulation
stopped at 3 s. Original incomplete automatic readback records are preserved.

For VCO, removing eight immediately adjacent binary64 strobe requests gives a
separate fourteen-point control. All fourteen requested rows, including the
four exact wrap roots, appear. All 32,811 native rows satisfy the original
ordinary phase, circular phase and sine budgets. The original failing left
neighbor is absent from this new output. Therefore this control supports
observation-grid sensitivity but does not resolve the original 22-point F/I.
The mathematical half-open wrap rule is unchanged.

## Actual EVAS observation evidence

The optional [response evidence](../../../evas/docs/observation-evidence.md)
exports actual runtime controls, the origin of each query result, and existing
per-node certified intervals. A missing interval remains unknown. The adapter
uses those intervals rather than treating a tolerance setting as an error
bound. It preserves all original waveform values and rows. Implicit integration
reports that max_step is applied; stateless evaluation reports that it is not.

On the integrated runtime, the original twelve Spec B requests pass the
independent numeric/event checks. The maximum independent voltage error is
5.373479439e-14 V. All prior public response fields are unchanged across all
twelve requests; only the optional evidence is added. All twelve original VA
sources compile, and their JSON-normalized IR equals the frozen requests.
This preservation result does not close B's remaining Spectre boundary or
main-integration obligations.

The integrated runtime passed the full 1,016-test Python suite and 211 Rust
tests, with one existing opt-in test ignored. Clippy and formatting checks also
passed. Subsequent changes are fixtures, checkers, analysis tools and
documentation; `evas/src`, kernel source and IR source remain byte-identical to
the tested runtime. Targeted admission, differential and maintenance checks
cover those later changes. These local checks do not replace the Spectre gates.

## Evidence availability and remaining decision

The refreshed [paper candidate table](../paper/candidate-table.md) uses twelve
new Linux executions from `830c8168` and the original thirty-six reference slots.
Actual source/build/native-record and error-bound evidence first produces
8 P / 4 I. The four I are caused by normalization of two distinct adjacent SI
timestamps to one binary64 value. A calibrated checker correction checks strict
ordering in the original seconds; identical or reversed seconds still reject.
Reanalysis of all forty-eight slots under that explicitly frozen checker gives
EVAS 12 P, Spectre 12 I, OpenVAF/ngspice 5 I + 7 X and Gnucap/modelgen 10 I + 2 X.
No waveform, external budget or old result is rewritten. Both original I12 and
8 P / 4 I remain available. These are finite-observation results; reference
qualification gaps and the original strict boundary obligations remain open.

All new reference runs use Spectre 21.1.0.509.isr12, binary SHA256
`72fe7e6e958b514d9a0f8bf85e7a08807ea9b34ecbd0ef5ae0586618d549889f`.
Complete logs, source/deck copies, receipts and raw outputs are retained locally
under the integration checkout's `runs/alignment-implementation-20261009/`:

| Evidence | Local directory | Collected archive SHA256 |
| --- | --- | --- |
| Root-scope comparison | `compiler-scope-v1` | `2160e38fce25470d570dd52340aa068d106ff0867df799d5c6f5c72ee3c23ef6` |
| M1 three-level reference | `reference-ladder-v1` | `6e01d278bbbd509bd7799d25bcbc66de08de51527ee21145762b668b8a5d03fc` |
| #79 callback/continuation | `event-continuation-v2` | `19b6a5cd316d5bf058327aef76b9cce6e3965b0d6dbd2875fc354c85b0dc2cb0` |
| VCO separated requests | `vco-separated-v1` | `885271cf33d7f014a3f9b0214015340121ca737c27d3fcae29a4028c046b690b` |
| Spec B preservation | `spec-b-current` | Per-request local receipts; no remote run |
| Paper EVAS12 refresh | `paper-current-v1` | `7ca2d0ea207ef2dc896e7365e29c3a37e2060d32dc1d58a02e4aea15706f0677` |

These hashes bind retained local evidence; they do not make the commercial
reference runs publicly reproducible. The old failed deployment before #79
execution is also retained. No automatic simulation retry was used.

C1/#79 still need a specific decision between retaining mathematical-root
updates with an explicitly approved engineering comparison, and changing the
public callback semantics to follow a supported numerical rule. The current
spec does not authorize silently replacing the strict boundary criteria.
VCO consumer implementation and final delivery gates remain downstream of
that decision. No issue is closed or PR recommended for merge by this report.
