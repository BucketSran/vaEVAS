# Diagnosis Guide

## Artifact and Binding Failures

Check the required artifact list before code semantics. Common causes are a wrong filename, module-name mismatch, missing `ahdl_include`, include path outside the submission/fixture contract, port-order mismatch, or a stale bug-fix copy.

Do not compensate for a binding error by changing the immutable public deck.

## Parse and Elaboration Failures

Use the first concrete source location. Inspect declaration order, module/endmodule balance, discipline and port declarations, parameter syntax, event syntax, contribution statements, array bounds, and referenced identifiers. Later errors are often cascades.

After fixing syntax, rerun before changing behavior.

## Runtime Failures

Determine whether execution reached transient analysis. Look for event loops with no time advance, invalid timing parameters, missing initialization, non-finite arithmetic, unsupported source setup, or a submission-created resource explosion. Change one suspected cause and rerun the same public case.

## Trace Problems

If a run completes but a required observation is absent:

1. Confirm the output directory named by the runtime contract.
2. Confirm `tran.csv` exists and time is strictly increasing.
3. Inspect the header for exact saved names, including escaped bus notation.
4. Confirm the node is actually driven or saved.
5. Treat a flat trace as a behavioral symptom only after ruling out binding and contribution omissions.

## Behavioral Reasoning

Convert the instruction into observable predicates, such as:

- initial value before the first event;
- edge direction and threshold crossing;
- state immediately before/after an event;
- delay, hold, pulse width, or settling window explicitly specified;
- rail or code mapping explicitly specified;
- behavior under reset, enable, or parameter overrides.

Inspect the smallest relevant time windows. Endpoint-only checks miss transient errors, and dense raw dumps obscure causality.

## When Evidence Is Inconclusive

A public run may compile and produce plausible traces without checking the complete task contract. In that case, do a static contract audit and state the gap. Do not manufacture a hidden expectation, infer a checker threshold, or describe the result as a final pass.
