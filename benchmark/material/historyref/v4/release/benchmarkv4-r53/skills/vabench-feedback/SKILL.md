---
name: vabench-feedback
description: Diagnose and iterate on vaBench DUT, testbench, and bug-fix submissions using only the task's public EVAS runtime contract and public outputs. Use when `public/task/evas_runtime.json` is available and the agent must interpret compile, runtime, log, or waveform evidence without treating it as a private score.
---

# vaBench Feedback

Use this skill to turn the facility's public EVAS evidence into the next concrete edit. It is a diagnosis workflow, not an oracle: public execution can expose syntax, runtime, trace, and visible-behavior problems, but Spectre and the private evaluator remain the final judge.

## Guardrails

- Read only public task files, the candidate submission, and public EVAS outputs.
- Never look for evaluator files, gold implementations, checker source, hidden cases, or private mutations.
- Run only the fixed command or fixed case set declared by `public/task/evas_runtime.json`.
- Never replace the declared deck with an agent-authored diagnostic deck when drawing benchmark conclusions.
- Treat `evas` success as evidence that public execution completed, not as proof of functional correctness or final score.
- Keep hypotheses tied to observed evidence. Do not invent expected values that the public contract does not state.

## Workflow

1. Read `public/task/instruction.md` and identify the required artifacts and observable behavior.
2. Read `public/task/evas_runtime.json`; verify its schema, candidate path, command, and available cases before running anything.
3. Check that every declared candidate artifact exists and that module names, includes, ports, and paths match the public contract.
4. Run the fixed public EVAS contract through the available interface:
   - With a `run_evas` tool, call it directly. DUT and bug-fix tasks take no case; testbench tasks require one declared case.
   - In the bash runtime, execute the contract's command exactly. For testbench tasks, substitute only a declared `{case}` and `{dut_root}` pair.
5. Classify the earliest reliable failure using the table below.
6. Make the smallest edit that tests one hypothesis.
7. Rerun the same failing command or case first. Once it clears, rerun the remaining public cases required for that form.
8. Re-read the instruction and artifact contract before submission. Report public evidence separately from unverified private correctness.

## Failure Classification

| Class | Evidence | First response |
| --- | --- | --- |
| Artifact contract | Missing/wrong file, unsafe include, wrong module or path | Repair layout and bindings before changing behavior |
| Parse or elaboration | Syntax error, unresolved name, illegal declaration, include failure | Reduce to the reported source location and correct language structure |
| Runtime | Timeout, panic, invalid event/source setup, no completed transient | Inspect the last successful phase and remove the smallest runtime blocker |
| Missing observation | Expected public output file, saved node, or trace column absent | Verify save names, escaped bus names, output directory, and contribution path |
| Behavioral mismatch | Run completes but public trace contradicts an explicit task invariant | Compare one invariant at a time at relevant event times, then edit its producer |
| Inconclusive public pass | Command succeeds and no explicit public invariant is violated | Audit unexercised edges, parameters, timing boundaries, and contract compliance; do not claim final pass |

Stop at the first earlier-layer failure: waveform reasoning is unreliable while artifact, parse, or runtime failures remain.

## Evidence Discipline

For each iteration, keep a compact record:

```text
hypothesis: one falsifiable cause
evidence: exact public log line, trace column, or task invariant
edit: smallest source change testing the hypothesis
rerun: exact fixed command/case
outcome: confirmed, rejected, or still inconclusive
```

When waveforms are available, inspect event windows rather than only endpoints. Check monotonic time, required columns, rail/threshold conventions stated by the task, edge direction, initialization, and behavior immediately before and after each triggering event.

## Form Routing

- **DUT:** run the one fixed visible deck; diagnose interface, initialization, event/state update, and output contribution in that order.
- **Bug fix:** preserve the public interface and unrelated behavior; reproduce the visible failure before editing, then make the narrowest causal repair.
- **Testbench:** run the `reference` case and all five declared `mutation_01` through `mutation_05` cases. A mutation label alone does not define the expected process exit code; use only explicit public observations and the authored testbench's documented measurements.

Read [references/runtime-contract.md](references/runtime-contract.md) before the first run. Read [references/form-workflows.md](references/form-workflows.md) for the active task form. Read [references/diagnosis.md](references/diagnosis.md) when a run completes but the next edit is unclear.

## Completion Check

Before finalizing:

- Every required artifact is present in `public/submission/`.
- The fixed public command/case set has been rerun after the final edit.
- No public parse, runtime, or required-trace failure remains.
- The candidate still matches filenames, module names, ports, parameters, includes, and output protocol.
- The conclusion says exactly what public EVAS established and leaves private Spectre scoring unclaimed.
