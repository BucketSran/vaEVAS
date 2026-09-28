# Spectre verification protocol, 2026-09-28

The user requested execution on the existing `thu-sui` host. This batch contains
31 current conditions: 14 unchanged v1 conditions, the `v6-standard` revision
of v1's lowpass condition, and all 16 conditions from the seven new candidate
cards. The frozen v1 array spelling, inputs, results, and tag are preserved.
No EVAS, other simulator, model API, benchmark task or historical 126-variant
suite is run. This is a standalone simulator experiment, outside Harbor.

## Budget and input identity

- Spectre only; base and fine settings; serial execution, one pinned CPU and one
  requested Spectre thread. At most 62 circuit attempts, no automatic retries.
- Each attempt has a 90-second wall limit, including a 30-second license wait.
  A timeout terminates only that attempt's owned process group.
- Time scale T=1 us. E1 stops at 3 us; all other conditions stop at 4 us.
- Base step/maxstep=1 ns, reltol=1e-5, vabstol=1e-8, iabstol=1e-12.
  Fine step/maxstep=100 ps, reltol=1e-6, vabstol=1e-9, iabstol=1e-13.
  Both request traponly, normal DC initialization and no forced strobe.
- Freeze all generated DUTs, netlists, settings, condition descriptions, analysis
  source and this protocol before execution. Verify the input manifest remotely.
  Export accepted points as PSF ASCII. Preserve logs, tool version, executable
  and setup-script hashes, runtime, exit codes, raw waveforms and file manifest.
- Use a new private run directory. Never reuse or overwrite an earlier attempt.
  Archive all results, including failed executions, and verify hashes locally.

## Independent checks and their limits

Every exported input and output point is checked. Required signals must be
finite, times strictly increasing from zero to the declared stop, maximum gap
at most 1.001 ns, and prescribed input mismatch at most 1e-7 V. Invalid or
missing observations yield an observation failure, never a numerical pass.
No crossing interpolation, waveform decimation or dropped boundary points.

The 15 legacy/revised conditions retain their v1 analytic screen. Event cases
V3/V4/V5 also use the previously calibrated exact-rational common-history
checker. New E1/E2/C1 use the same checker with independently declared event
counts, initial states, priorities, sample slopes and instance-local histories.
C2 checks the continuous node against the closed-form convolution and the held
node against a common sampling history. Its nonlinear target is linearized on
the 40 ps legal event domain; |z''|<=1.2 and the resulting 9.6e-10 V remainder
plus roundoff are covered by a 1e-9 V reserve from the 1 mV target.

History checks report both exact-export B=0 and candidate B=0.25 mV scenarios.
D1 independently integrates the prescribed linear input. Reset flag and voltage
must admit one common onset/release witness within the legal windows; the flag
is an observed output, not event ground truth. Outside every legal value is F;
a failed witness search with no exclusion proof remains I. D2 checks analytic
accumulated and circular phase (1e-4 cycle), wrapped range and sequence (2/4
observed wraps), and analytic sine voltage (1 mV). S1 checks the sum of all
three contributions at every point (1 mV); C2's continuous node uses 0.6 mV.

All new cards have synthetic correct, distinguishing incorrect, and invalid-
observation controls, plus independent hand anchors. History and D1 uncertainty
band controls exercise I. These calibrations are finite controls, not full
checker certification. Candidate input, timestamp and voltage uncertainties
are not proven physical bounds. The 1e-7 V input gate does not itself qualify
input-root timing or between-export behavior. Raw numerical screening uses the
prescribed-input/exact-export assumptions; sensitivity is explicitly separate.

A successful run and finite target agreement do not establish continuous-time
correctness, formal DVS qualification, whole-language support, cross-backend
portability or accuracy on unrelated circuits. Formal qualification remains I.
Calibration failures must be corrected before freezing; observed simulation
failures must be preserved and diagnosed without loosening the frozen target.
