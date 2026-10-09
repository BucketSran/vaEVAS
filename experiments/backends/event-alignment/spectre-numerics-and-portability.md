# Spectre event numerics and model portability

Research date: 2026-10-09. This note separates installed manual contracts, Cadence staff explanations, existing local measurements, and engineering proposals. It does not change EVAS semantics or historical acceptance results. No simulator was run for this research.

## Sources and identity

The reviewed installed documents are Product Version 21.1. Only the Verilog-A reference is January 2022. The simulator reference is September 2022 and the user guide is October 2022. Their local PDF SHA256 values were recomputed and matched the existing [retrieval manifest](/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/spectre-docs-20261008/manuals/MANIFEST.json):

| ID | Manual and exact local path | SHA256 |
| --- | --- | --- |
| VA | [Cadence Verilog-A Language Reference](/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/spectre-docs-20261008/manuals/veriaref.pdf) | `de216de12fa3580c2c67fd1ea06bcd0a7d75bca52ed142ea23e596e140a69bad` |
| REF | [Spectre Circuit Simulator Reference](/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/spectre-docs-20261008/manuals/spectreref.pdf) | `22c4fbaf521f5efa2809a70e6ec96fab58a883a5a2b165b6a5b1ad297d6408e8` |
| USER | [Spectre Classic Simulator, Spectre APS, Spectre X, and Spectre XPS User Guide](/Users/bucketsran/Documents/TsingProject/research/vaEVAS/current/runs/spectre-docs-20261008/manuals/spectreuser.pdf) | `4857ceff4dc523b5b897157a1f88068d4a413f0f56d656f2efeaba993e1ff4d6` |

Page references below are printed manual pages. This document set belongs to the installed Spectre21.1 tree; it does not establish that every paragraph was updated for `21.1.0.509.isr12`, the binary version in the existing event evidence. Text extracts were searched and relevant sections read. Public searches used Cadence sources; community replies are attributed explanations, not a complete algorithm specification.

## Input PWL and solver steps

USER, "Reading Piecewise Linear (PWL) Vector Values from a File", pp.141-142, defines `vsource type=pwl` time/value pairs and file syntax. "Time Is Not Strictly Increasing", p.910, documents an error for non-increasing times. REF, options p.200, documents `src_allbrkpts`: it can make every user PWL point a transient breakpoint, with per-source `allbrkpts` taking precedence.

Andrew Beckett explains that short PWL files normally get breakpoints at each point; large files may need `allbrkpts=yes`. Breakpoints force solving at the knot and attention around its derivative discontinuity. His [solver explanation](https://community.cadence.com/cadence_technology_forums/f/mixed-signal-design/38557/spectre-solver-for-veriloga/1354513) describes fewer than 20 points; it does not resolve the exactly-20 case. A [second reply](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/43338/how-we-can-use-the-single-vcvs-file-containing-n-waveforms-for-generating-the-n-voltage-waveform-sources-in-ade-xl) says the larger-file default assumes a smooth waveform.

That smoothness assumption concerns breakpoint selection. It does not document automatic spline smoothing of input PWL. The piecewise-linear model implies an affine segment between knots; this mathematical reading does not choose between floating-point evaluation graphs such as `v0+(v1-v0)*(t-t0)/(t1-t0)` and a precomputed slope. The reviewed manuals do not contain the complete primitive `vsource` model chapter, so this research does not establish all source-specific smoothing options. Verilog-A `transition`, `slew`, table interpolation, and Fourier interpolation are separate mechanisms.

USER, "Tolerance Control Parameters", p.251, gives Newton tolerance `abstol + reltol*Ref` and LTE tolerance as that quantity times `lteratio`. It describes comparing the computed solution with a polynomial prediction from prior steps, then shortening the step when the difference is too large. REF, transient analysis pp.454-455, describes backward Euler, trapezoidal and Gear methods. `traponly` and `gear2only` use their named method almost exclusively; `trap` can select among all three. Thus an integration-method name alone does not specify all restart, prediction or event-local numerical choices.

## Three different crossing operations

VA, "Detecting and Using Analog Events", pp.128-130, specifies `cross(expr, direction, time_tol, expr_tol, enable)`. A detected event occurs after the crossing, within the time and expression tolerance box. Both explicit tolerances must be satisfied. The default time tolerance is 1 second; the documented default expression tolerance is `1e-9 + reltol*max_value_of_the_signal`. The operator reduces steps to resolve the crossing. This contract gives a permitted neighborhood, not a unique representable callback timestamp.

VA, "Finding When a Signal Is Zero", p.138, says `last_crossing` estimates the crossing time by interpolation and does not control steps. Combining it with `cross` can improve accuracy. The reviewed passage does not specify interpolation degree or arithmetic ordering. Beckett's [sampling reply](https://community.cadence.com/cadence_technology_forums/f/mixed-signal-design/51222/accurate-sampling-or-scheduling-an-accurante-time-event-in-spectre) distinguishes improved time estimation from improved sampled value. Replacing `$abstime` with `last_crossing` therefore does not establish that a callback's sampled state occurred at the estimated root.

The ViVA/OCEAN calculator `cross` operates on a saved waveform. Beckett's [calculator explanation](https://community.cadence.com/cadence_technology_forums/f/mixed-signal-design/36481/cross-function) describes linear interpolation between bracketing points in its DC-sweep example. That is evidence about calculator postprocessing, not the algorithm used by transient `@(cross(...))`. In a separate [transient delay reply](https://community.cadence.com/cadence_technology_forums/f/custom-ic-design/47400/transient-sim-accuracy/1372268), he recommends an `@cross` monitor to force steps close to the threshold and reduce measurement interpolation error.

## Strobe, precision and nearby events

REF, transient pp.443 and 456, and USER, output control pp.253-254, say strobe forces a solver step at the selected output time, so that sample is computed. Cadence's [strobe technical article](https://community.cadence.com/cadence_blogs_8/b/cic/posts/spectre-tech-tips-using-the-spectre-strobe-feature) confirms this, distinguishes `strobeoutput=all` from `strobeonly`, and describes `strobetimes` for selected times. `maxstep` limits the step size but does not force alignment to measurement times. A strobe grid can therefore affect the solve path; it is not merely an output-format setting.

REF, transient p.442, documents `transres=1e-9*stop`. Nearby input-waveform corners within that interval may be combined into one forced point, after which error control selects steps. The manual warns of lost detail. This passage does not establish that every cross/timer callback is universally merged by the same rule.

Beckett's [transition-resolution explanation](https://community.cadence.com/cadence_technology_forums/f/mixed-signal-design/51223/issue-in-transition-filter-transient-slope-settings-in-verilog-a-model/1382197) states that time uses double precision with a 53-bit significand and that the simulator needs margin around its resolution. Reducing `transres` too far can cause convergence trouble. Binary64 storage by itself does not disclose exact operation ordering, fused multiply-add use, root candidate selection, zero ties, simultaneous callback ties, or the rounding mode of each internal calculation. None of the reviewed passages specifies those details. Verilog-A real-to-integer conversion rules and decimal print precision answer different questions.

REF, "Important considerations for using multithreading", p.249, explicitly warns that changed device evaluation order can change round-off and that the same result may not be reproducible under multithreading, while remaining within input tolerances. This is a scoped warning about device multithreading, not proof that every single-thread run varies or that C1's cause is threading.

## What existing C1 evidence establishes

The [event-control note](event-reference-controls.md) records a ramp from 0 to 3 V over binary64 `6e-6`, a binary64 `0.7` threshold and query `1.4e-6`. The exact root defined by those binary inputs is about `1.0002668543e-23` seconds later than the query, less than one ULP. EVAS reports the old state there; the original actual Spectre callback gives the new state with a rounded zero guard.

Changing strobe/query or cross controls changes the measured callback. The [shared-callback analysis](c1-shared-callback.md) supports one persistent event history per recorded run, while preserving strict C1 phase failure and missing requested-query coverage. The local prototype at `runs/c1-rounded-guard-prototype-20261008/README.md` matches only 3/6 recorded callback times. Its arithmetic checks and analytical downstream fit do not constitute a new controller run or a universal C1 fix.

## Proposed portability policy

C1's ordinary cross-triggered sampling is legal; it does not warrant a blanket warning. The observed sensitive point is querying extremely close to the boundary and interpreting the returned old/new state. Functional instability requires downstream evidence; the present measurements do not show that every such sample causes a functional problem.

A nonblocking runtime portability advisory is preferable to a static prohibition when observed evidence shows that an ultra-close query or boundary-dependent decision can change under a documented reference configuration. It can report the expression, query distance, event tolerances and the conflicting recorded phases. Exact-equality patterns or narrowly separated independent events can motivate a diagnostic, but their presence alone does not establish instability. A local diagnostic may report sub-ULP boundary separation without running Spectre, but must describe cross-simulator impact as a possibility. A claim that a particular Spectre configuration returns the other phase requires paired evidence. If sensitivity arises only in an observation request, attach the advisory to that request rather than labeling the Verilog-A model faulty. This proposal changes neither semantics nor the original F/I results.

Model authors can express hysteresis or a physical tolerance, use the event's declared direction to update its intended state, and avoid assuming that a callback guarantees `V(in)==threshold`. A measurement can use `last_crossing` for its estimated timestamp while retaining `@cross` for step control. These are proposals; they must preserve the intended model behavior and cannot substitute for simulator correctness.

The reviewed documentation supports reproducible tolerance-based experiments with frozen versions, settings, stimulus identity and measurement paths. It is insufficient for a document-only bit-for-bit reimplementation of Spectre's internal crossing strategy. That does not prove recovery is impossible. Additional version-specific help, vendor clarification, or controlled experiments could disclose more. EVAS should keep its own numerical contract explicit and retain actual Spectre comparisons for compatibility claims. Adding a warning would explain a portability risk; it would not close the existing strict alignment gap.

The current candidate implements a narrower local advisory than the possibilities
above: committed cross certificates within one binary64 neighbor of a saved output
query. It does not infer a Spectre phase, inspect all model equality predicates,
or cover timer/VCO boundaries. See the [runtime advisory contract](../../../evas/docs/reference/diagnostics.md#事件边界观察的可移植性提示)
and the independent [strobe control contract](../../../evas/docs/reference/strobe.md).
