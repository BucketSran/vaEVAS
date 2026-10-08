# Review adjudication

The complete GLM source report concerns fixed `57a9f90b`; its local-only source
report remains in `current/runs/issue-closure-20261008/review/glm-initial-loop-source-v1/`.
The production correction is `4cb15800735047048e4a6d551f039e376e4c3a66`.

- F1 is confirmed. A public dynamic-index probe returned generic `compile_error`.
  The corrected path returns `unsupported_initial_event` with the index token.
  The focused test first failed on the old code and then passed after the fix.
  An earlier test attempt used the wrong exception API and errored; the corrected
  red test uses `CompileError.diagnostic['code']`. Both logs remain local.
- F2 is missing review context, rather than an accepted out-of-bounds assignment.
  `frontend.compile_sources` binds hierarchy through `bind_hierarchy`; its `visit`
  calls `scalarize_nodes`, which now expands initial and analog loops. Then
  `InstanceCompiler.compile` calls `scalarize_arrays`, whose `element()` checks
  every expanded array index against the declaration. A later `i=2` iteration
  writing `q[2]` in `q[0:1]` publicly rejects. The contract names that consumer.
- F3 is a legal zero-trip boundary. Expansion produces no assignments, so it
  initializes no element. The cross leaf remains an empty-body monitored event.
  The public test compares the loop with an explicit empty initial/cross body:
  both have zero persistent states, constant output, and one empty cross record.
  Reading the unused real still rejects as an unassigned local. This does not
  introduce implicit zero initialization or a new persistent-state classification.
- F4 identifies an overbroad inference if the frozen window were described as
  all LRM-permitted timer behavior. It is a stricter frozen Spectre probe window.
  The [Accellera LRM](https://accellera.org/images/downloads/standards/v-ams/VAMS-LRM-2023.pdf),
  timer section, says an explicit tolerance places a point within that tolerance;
  it only gives the at/just-beyond default when tolerance is omitted.
  The vendor-authored [Cadence Verilog-A Language Reference 13.1.1](https://wiki.eecs.yorku.ca/lab/emil/_media/mmsim13_11_480:veriaref.pdf),
  printed page 124, describes the first timer step as at or just beyond start.
  That older vendor document is background, not proof of all contemporary LRM
  behavior or the installed Spectre version. The original single-sided window,
  source, manifest and voltage budget remain unchanged. An earlier admissible
  LRM timer event could fail this narrower probe, which is not an LRM violation.
  The actual recorded timer stage begins at exported token `0.25` in both
  instances, so this run satisfies the original window without relaxing it.

Astra also requested a separate strict phase-agreement verdict. The checker now
reports an observed native/candidate stage difference as strict phase F; its
window-compatibility and same-stage voltage verdicts remain separate. Missing
candidate time queries leave strict phase I and numerical pairing F. No observed
phase difference occurs in this actual run, so all three pairing dimensions are P.

## Final consumer findings E1/E2

E1 is confirmed as a missing frozen-control qualification. The shared PR109
reader already rejects malformed/ambiguous metadata and log/PSF disagreement,
but consistency alone does not match the frozen requested controls or declared
effective profile. `settings_contract.py` now checks that mapping explicitly;
consistent wrong-control negative examples reject. The actual original controls
pass offline with no numerical rerun, and the prior numerical evidence remains
bound to its original source/kernel/request identities.

E2 is publicly reachable: 64 nested identity macros in an initial zero-trip
loop index add the active genvar path and exceed the call-site identity budget.
The original `constant()` wrapper and new initialization wrapper reclassified
that resource rejection. The index, initial-value, and shared constant wrappers
now propagate `resource_budget` unchanged. The public index and RHS probes first
failed and now pass with category resource. Ordinary dynamic initial values and
indices keep their unsupported diagnostic. This changes rejection metadata only.

After normal merge of main 3bb75df4, source dc177010 builds successfully and
84 relevant public regressions pass. All four accepted Programs, including origin
metadata, serialize exactly like the original requests. Earlier tuple/list Python
container comparison was corrected to JSON equality; the failed development
offline attempt is not claimed as a pass. The offline settings evidence executes
no kernel or Spectre and preserves the earlier immutable numeric responses.
