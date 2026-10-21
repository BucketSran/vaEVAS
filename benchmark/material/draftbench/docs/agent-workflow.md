# Author and review benchmark tasks

Use this workflow for benchmark circuit-family review, task design, and authorized
construction. Preserve the requested stage. Review and documentation work do not
authorize model experiments, remote simulation, publication, or task acceptance.

## Select the authoritative material

| Need | Source |
| --- | --- |
| Human decisions and current review questions | [Review principles](design.md) and the circuit-family README |
| Scope, modeling assumptions, provenance and task contribution | [Design reference](design-reference.md) |
| Given materials, deliverables and boundaries of the five actions | [Task types](task-types.md) |
| Package layout, public interfaces and artifact declarations | [Task package contract](task-package.md) |
| Stage gates, runtime evidence, grading and reproduction | [Evaluation reference](evaluation.md) |
| Current task behavior | Its short behavior agreement and source/modeling choices; the public instruction is completed with the assets and grading |
| Current package progress | The owning batch README; link original evidence rather than copying it |
| Existing work records | [#72](https://github.com/BucketSran/vaEVAS/issues/72) for overall construction, [#107](https://github.com/BucketSran/vaEVAS/issues/107) for definitions and representative tasks, [circuit-harness #5](https://github.com/BucketSran/circuit-harness/issues/5) for shared execution reliability |

Reference documents may retain their established language. This English workflow
owns execution order and completion criteria; it does not duplicate their detailed
contracts. Do not create a second translated rule set or rewrite frozen evidence.

## 1. Recover the requested stage and circuit assets

Read the current task and existing batch record. Inspect Git status and preserve
other writers' files under the [workspace rules](../../../../docs/contributing/workspaces.md).
Identify the circuit family, relevant modules, actual connections, source versions,
and the work expected from the solver. Read only the reference sections needed for
the next decision.

Classify the route as based on a device circuit or entirely Verilog-A. For the former, identify
whether runtime uses fixed data, online device simulation, or a mixed circuit.
Keep circuit provenance separate from the backend used to execute the candidate.

For a batch, recover the agreed task list, representative tasks, behavior boundaries
and authorized execution scope from the existing batch record. Use the
[human participation rules](evaluation.md#人工介入与批量交付) to distinguish decisions
that need human judgment from authoring and checks the agent should complete.
Reuse valid decisions; do not turn each task or unresolved field into a new approval.

Complete when the owning files, accepted decisions, runtime dependencies and
unresolved scope are explicit. A source circuit running in ngspice does not establish
that a candidate VA task runs there; all-VA does not establish EVAS compatibility.

## 2. Build only the authorized design stage

Use the existing package layout and lint entry in the evaluation reference. Keep
human review short and Chinese, solver instructions English, and detailed sources
in their owning reference. Run the stage check when changing authoring materials;
fix a detected format error instead of copying it into another task.

Proceed in this order, returning to earlier decisions when evidence changes them:

1. Establish the application and a short behavior agreement from actual code,
   research, circuit requirements and human decisions. Distinguish source-backed
   behavior, explicit modeling choices and open questions in SOURCE.md. Identify
   the solver's work, observable outcomes and typical errors. Numerical limits,
   grading tolerances and runtime evidence may remain pending at this stage.
   Use [the extraction procedure below](#extract-and-review-a-behavior-agreement)
   to establish what the available evidence supports before writing requirements.
2. When gold construction is authorized, build a reference asset with traceable
   sources and documented adaptations. Keep working parameters separate from
   grading tolerances. A gold file is a candidate reference, not proof of correctness;
   check key behavior against sources, analytic examples or independent observations.
3. Use that asset and the behavior agreement to design public tests, final evaluation
   and scoring through [the per-task procedure below](#design-public-checks-and-final-evaluation).
   Keep unresolved definitions and numerical limits explicit. A completed design
   review does not establish that its checker has been implemented or calibrated.
4. Complete the English instruction against the actual starter, public commands and
   grading contract. Keep an early instruction draft concise and explicit about unknowns.
   Apply the [content responsibilities](task-package.md#单文件题的目标规范): put behavior,
   legal operating conditions and acceptance bounds in Spec; use Deliverable bullets
   for files, interfaces, engineering work, implementation freedom and model restrictions.
   Apply the [behavior-detail and draft rules](task-package.md#行为说明的详细程度与草稿边界):
   retain each distinct acceptance-relevant behavior and merge cases already implied
   by a clear rule. Judge all supplied public specifications together, not prompt length.
   In an early draft, use a brief draft label and named TBD fields for unresolved
   conditions. Keep development history, pending-item rationale and checker repair
   plans in author records; public usage notes identify provisional bench feedback.
   A restriction on submitted-model I/O must not prohibit the solver's testing tools.
   In short tasks, integrate conditions and acceptance into Spec rather than adding
   separate Constraints or Operating conditions and acceptance subsections.
   Put observation-point construction and runtime details in the existing public
   testbench documentation. If moving detail, retain its public access and verify
   the link; keep all requirements that determine correctness explicit in Spec.
   Keep solver links rooted in /app and give repository-resolvable links in the
   existing Chinese review entry. Validate each in its own layout.
   Apply the [score and diagnostic policy](evaluation.md#任务分数与失败原因): failed
   task attempts score zero; record the failure cause separately. A zero score
   caused by an execution problem does not demonstrate a semantic model error.
   For a single-file task, copy only the prose between the execution-footer markers in
   [INSTRUCTION.md](../templates/INSTRUCTION.md) unchanged to the end of the instruction;
   remove the marker lines and all authoring prompts from the solver-facing file.
   Follow the [reference-material policy](task-package.md#固定执行尾段与参考材料);
   do not add a generic Verilog-A tutorial or model example set to a spec-reconstruction task.
   Record unresolved items through the existing metadata and SOURCE sections described
   in the evaluation reference. Never fill invented numbers, references or success
   records to pass lint. Calibration and model trials still require execution authority.

Before returning an instruction draft, compare it with the behavior agreement,
checker and public materials. Check for missing requirements, invented commands,
restrictions with an unclear subject, and prescribed internal implementation choices.
For each graded behavior, identify its public clause or the rule that unambiguously
implies it. Confirm that shortening removed repetition rather than a distinct
condition, and that author status has not replaced a solver-facing requirement.
Verify that startup, reset release and measurement-window boundaries have consistent
rules, that solver and human links resolve in their respective layouts, and that
failure scores are not confused with diagnostic causes. These are author checks,
not a requirement to add a separate timing section to every solver instruction.
Run the existing package lint and report remaining content questions in the current
task record. A lint pass checks structure, not the semantic content split or completeness.

Complete when the requested stage has its real assets and evidence, with remaining
questions explicit. Early drafts need neither a checker nor runtime results. Only
advance metadata.stage when its requirements are met; lint cannot authenticate
sources, completeness, human approval or the actual order in which files were written.

### Extract and review a behavior agreement

Use this procedure when defining a task or recovering requirements from existing
assets. Code can reveal an implemented behavior or a tested condition. Whether that
behavior is required, which alternatives are allowed, and why a numerical target
matters also need an engineering basis or an explicit author choice. The
[30-task source study](../research/spec-extraction-study.md) gives examples and
the limits of reverse reconstruction.

A task may explicitly designate public code or a bench as part of its normative
definition. Record that designation and version; do not infer authority merely
from a file being named gold, test or specification.

1. Inventory the supplied evidence at a fixed version. Identify the original
   requirements and their public references, candidate reference implementation,
   faulty baseline, public benches, final checker, build configuration and historical
   results. Follow the configured top level and source list before interpreting an
   unused test or model. Include code dependencies and public configuration files;
   a filename beginning with a dot is not a reason to omit it. Distinguish material
   excluded by the researcher, unavailable in the source snapshot, and supplied only
   by an uninspected runtime dependency. An empty reference patch or another task's
   baseline is not gold.
2. Recover observable obligations with their conditions and evidence. For each
   distinct behavior, identify the input and relevant history, output or property,
   reference event or value, applicable conditions, and any numerical acceptance
   bound. Trace it to source lines or a recorded author decision. Put source-backed
   facts in SOURCE.md's behavior basis, proposed assumptions in modeling choices,
   and conflicts or missing intent in open items. An inference remains an inference
   until its basis or the author choice is established. Use a short table when it
   helps; no extra schema or parallel status file is required.
3. Separate the model's stated applicability, the domain over which the task requires
   correctness, the concrete tests, and the numerical measurement budget. A few
   voltages, codes or PVT combinations do not establish an interval, a Cartesian
   product, or the legal domain. Conversely, a finite check does not narrow an
   existing interval requirement. Distinguish circuit performance, permitted model
   error, and solver or measurement uncertainty. For a metric, record its reference,
   units, sign, normalization, aggregation window and boundary convention. Explain
   whether a point sample, an average, or an interval maximum is required.
4. Examine what the artifacts actually establish. Follow assertions and failure
   propagation rather than test names, comments or logs. Note missing assertions,
   an oracle derived from the same implementation, unbounded waits, and incompatible
   public/final histories or windows. Keep the intended obligation and its current
   test coverage separate. Gold supplies one candidate implementation; by itself it does not
   set a topology mandate, a device whitelist, implementation freedom, or the
   authorized repair scope. Preserve both sides of a source conflict and resolve
   it against the engineering purpose and recorded decisions. Do not silently let
   either the checker or the published prose win every disagreement.
5. Test whether the proposed agreement determines which outputs are allowed. Use a
   legal input and history for which two plausible readings disagree about whether
   an output is correct, then identify the missing rule. The agreement need not
   select one exact output. Differences within tolerance, explicitly permitted
   nondeterminism and implementation choices may all be valid. Equivalent allowed
   external behavior with different internal states does not require an extra rule.
   For time-dependent tasks, include startup, reset release, cancellation and a
   legal window endpoint as applicable. Do not invent arbitrary edge exclusions to
   make the checker easier. Reuse established choices; ask the human only for a
   consequential unresolved author decision, with a recommendation, its basis and
   the effect on the task. Keep unsupported targets as named TBDs.
6. Write the public instruction from that agreement. Lead with the engineering work,
   then state observable behavior, required domain and acceptance bounds in Spec.
   State deliverables, necessary restrictions and permitted implementation choices
   under the existing package rules. Publish normative measurement definitions and
   referenced material through the instruction or its linked public documentation.
   Keep private test values and author deliberation out of the public instruction.
   Do not present a reconstruction of tested cases as the complete original intent.

For existing assets with uncertain provenance, or a representative task introducing
a new behavior or measurement, an independent reconstruction can expose gaps. Give
one fresh session only checker, available reference code and code benches. Keep the
actual prompt and standalone specification documents out of its input; record the
packet, omissions and any specification-like code comments. Freeze its reconstructed
Spec and evidence notes before a different session compares them with the full
original public contract and relevant artifacts. Classify differences as extraction
errors, intent absent from the artifacts, source conflicts, measurement gaps or
missing public context. Archive the first draft before correcting an input omission;
do not use knowledge of the actual prompt to improve a purported blind reconstruction.
Fresh context and access records do not prove isolation from model pretraining or
access outside the allowed paths.

This reverse check is an authoring diagnostic, not a mandatory pair of sessions for
every edit. For a new task without an original prompt, review against the engineering
basis and declared author choices instead. Also read the proposed public materials
without private gold or checker details and identify what an independent engineer
can determine. A shorter faithful instruction is preferable to a test-by-test
transcription, but it must retain each distinct condition that determines correctness.

Complete this step when each acceptance obligation has a public rule and a traceable
basis, measurement conventions are explicit, and remaining author choices or
conflicts are recorded in the owning SOURCE sections. An incomplete agreement may
remain a draft. Static review does not qualify gold, demonstrate checker coverage,
establish achievable numerical accuracy or authorize execution.

### Design public checks and final evaluation

Apply this procedure to each task, starting with the current representative task.
Use the [evaluation-design contract](evaluation.md#逐题-checker-与终评设计) for the
required record and coverage rules. Keep the plan in the existing SOURCE sections,
linking code and evidence as they become available. Reuse framework code across
tasks; establish each task's requirements and expected results separately.

1. Map every acceptance requirement to its public clause or agreed behavior source.
   Define the stimulus, expected result or property, observable quantity and pass rule.
   Complete when each row has these definitions or identifies the specific unresolved
   meaning. A numerical TBD must still name its quantity, unit and reference.
2. Assign public examples and final cases to that map. Explain what each final
   variation distinguishes, and how the expected result follows from the behavior
   basis independently of candidate or gold outputs. Complete when every requirement
   has planned coverage and every final case stays within the public contract.
3. Specify measurement and execution details using the linked contract. For timing
   tasks, work through a legal endpoint or shortest-window example, including
   parameter overrides. Complete when event references, allowed response, observation
   exclusions and trace completeness agree, or record the exact unresolved conflict.
4. Plan checker calibration with an independent expected-result example, representative
   correct alternatives and targeted wrong candidates. Include collection, failure
   scoring and diagnostics. Complete when each planned check says what result would
   support or refute the checker; mark all unperformed checks as planned.
5. Reconcile the design with Spec, the public bench documentation and the final
   evaluation entry. Use the existing package lint for the current stage. Complete
   when the requirement map has no unexplained gaps, public materials contain all
   correctness rules, and pending definitions, numbers and execution evidence remain
   visible in SOURCE and the existing metadata.

Keep the detailed requirement map as author material. Present it to the human when
reviewing a representative task, a consequential exception, or an explicit request.
For routine batch items, report the task's contribution, check results and unresolved
decisions in the short batch summary. Keep grading pending while its rules or
calibration remain unresolved; use the existing stage gates.

### Reuse the workflow across a batch

1. Prepare the batch proposal in its existing README: circuit routes, engineering
   actions, sources, distinct contributions and representative tasks. Carry forward
   agreed behavior boundaries. Complete when scope decisions are recorded and any
   remaining choice has a concrete recommendation, evidence and consequence.
2. Build the representative package through the steps above. When authorized, check
   gold, correct alternatives, targeted errors, artifact collection and independent
   final evaluation. Use authorized model trials to assess difficulty and iteration
   cost. Complete when the reusable parts and their verified scope are explicit;
   a drafted workflow or a gold-only pass does not qualify the scoring pipeline.
3. Generate the remaining authorized tasks in small groups. Reuse layout, execution
   plumbing and checked conventions. Derive each task's behavior, expected answers,
   cases and numerical limits from its own basis. Run the existing lint per task,
   review the requirement map, and perform authorized calibration for each package.
   Fix routine defects directly. Keep affected tasks pending when evidence is missing,
   and continue independent tasks within scope.
4. Deliver one compact batch summary with a row for every task and links to its
   actual package and evidence. Highlight new assumptions, departures from the
   representative design and unresolved failures. Complete when each task has an
   explicit content recommendation, runtime status and version; record human
   acceptance only for the tasks and versions actually reviewed.

Design drafts may be produced while runtime remains pending. Reusing an executable
scoring workflow requires representative execution evidence for the affected path.
For a new engineering action or backend dependency, verify that path before scaling
it. Preserve the current R01-first plan and its model-trial dependency for later
difficulty decisions. This procedure does not authorize experiments or publication.

## 3. Record runtime maturity independently

Use the evaluation reference to distinguish asset execution, full package delivery,
independent grading/calibration, and Agentic public-tool iteration. Record only
observed facts for a named version, backend and setup in the existing batch record.
Link the original run evidence; leave unexecuted or unresolved checks explicit.

When execution is authorized, run the checks required by that stage. A contract
draft need not already contain a checker. A calibrated package needs meaningful
correct alternatives and semantic negative controls, not just a passing reference.
Verify collection and independent evaluation through the actual package entry.

For Agentic readiness, distinguish model-free tool-path checks from actual model
trials. Check that public feedback and retries fit the declared resource contract;
hidden evaluation remains separate. Keep fixed-data modeling separate from tasks
that explicitly allow querying the source circuit.

Complete when runtime claims resolve to matching evidence or a specific gap.
Failed task attempts retain a zero score and a separate diagnostic cause under
this policy; backend failure alone leaves candidate semantic correctness unknown.
Not-yet-run checks remain pending and receive no invented score. Reuse old evidence
only within its identity and scope, following the evaluation reference's revalidation rules.

## 4. Deliver a short human review and a recoverable handoff

Write the human entry in Chinese using the batch summary defined in the
[human participation rules](evaluation.md#人工介入与批量交付). Give the task's purpose
and contribution, content conclusion, runtime conclusion and decisions needed.
Use detailed source, waveform or checker discussion for selected review items.
Put technical definitions in their owning reference, numerical results in their original evidence,
and package progress in the batch record. Link these instead of repeating them.
For shared definition changes, preserve reasons and evidence in the owning existing
issue when publication is authorized; otherwise keep the handoff locally in the
existing task record. Task progress and historical records do not override current
contracts.

For documentation changes, check the diff, package registration, moved requirements
and local links, including anchors and inbound references. Preserve old links or
update their maintained callers. Report what was actually checked and what was not
run. Use the existing task record for follow-up; keep EVAS requests separate from
benchmark task acceptance.

Complete when the requested stage has a concise Chinese review entry, a batch record
backed by evidence, no lost contract requirements, and an explicit next decision or
dependency. Commit, publish, merge and retire a checkout only within current
authorization; a completed local edit is not integration into main.
