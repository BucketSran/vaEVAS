# <Concrete engineering task>

<State the supplied engineering context and the work to complete in one or two sentences.>

## Spec

<State the required circuit behavior or measurement, its reference, and legal operating conditions. Retain each distinct acceptance-relevant behavior. Combine cases already implied by a clear rule rather than reducing detail by word or bullet count.>
<For a new model, specify required parameter names, meanings, types, defaults, and valid ranges. The solver implements their declarations. For an existing model, identify the supplied full source and required changes.>
<For event-driven work, define initialization, completion, cancellation and timing references. Distinguish input ramps, any allowed output delay or transition, and measurement exclusions. State how startup, reset release and window endpoints are handled; do not prescribe an internal operator or invent an unapproved time limit.>
<State acceptance accuracy separately from circuit performance limits when established. Keep conditions that determine correctness here, including applicable timing references, error bounds and any excluded event neighborhood. In an early draft, use one brief draft label and named TBD fields at the relevant conditions; keep known behavior and references. Put pending-item rationale, old-checker discrepancies, repair plans and historical results in author-only SOURCE.md, not the solver instruction.>
<For a short task, integrate the operating domain and acceptance scale into Spec without separate Constraints or Operating conditions and acceptance subsections. Keep concrete observation-point construction and runtime diagnostics in the public testbench documentation. Summarize final-test scope and scoring briefly: failed task attempts score zero, with failure causes recorded separately. Do not describe a runtime failure as proof of a semantic model error.>

## Deliverable

- Edit `/app/circuit.va` and implement the model using the module and port declarations supplied in the starter.
- <State the engineering implementation to deliver. For behavior-defined tasks, explicitly accept any implementation that satisfies the specified interface and external behavior; do not prescribe internal state variables or event organization. Retain any task-required component responsibilities.>
- <State necessary port roles, permitted components or dependencies, and model restrictions. Attach each restriction to its object: a prohibition on model file or process access must name the submitted model, not the solver's testing tools.>
- <State any enforced artifact limits or required report format. Omit this bullet when there are none beyond the fixed footer.>

<For multi-file deliverables, replace the paths and interface wording above with the exact editable files and required entry points. Open a directory only when needed and state allowed additions, deletions and renames. Identify task-specific fixed materials and any required report fields without repeating the full Spec.>

<Give the actual public check command after the bullets and link its public usage documentation. If it combines preflight and behavioral checks, describe that actual entry rather than inventing a standalone preflight command. Put backend versions, per-case timeouts, output layout and diagnostic exit codes in the public testbench README.>
<When moving observation details or runtime information out of this instruction, retain them in existing public documentation and verify the link from the solver's /app environment. Keep repository links in the separate Chinese review entry. Do not discard acceptance requirements or point to private author files. Do not add a generic Verilog-A tutorial or example set to a spec-reconstruction task.>

<For a single-file task, copy only the two prose paragraphs between the markers below to the end of the instruction. Remove both marker lines and all authoring prompts from the solver-facing file.>

<!-- BEGIN VABENCH EXECUTION FOOTER -->
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
<!-- END VABENCH EXECUTION FOOTER -->
