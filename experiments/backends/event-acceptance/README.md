# Spec B baseline, candidate and actual reference comparison

P102 baseline `56473944` and candidate `5e38bdf882f41ad17f2a704268907ae0e36600d9` each executed all twelve frozen requests. All twelve requests and responses are byte-identical between revisions. Both pass the independent finite mathematical and event tests; maximum EVAS error across continuous and stored-sample channels is 2.9109159527251904e-11 V. There is no new candidate-only discrepancy. This is preservation evidence, not compatibility acceptance.

The coordinator's actual Spectre reference contains twelve successful executions and 306 verified collected files. Source identities match the original frozen VA inputs. The derived decks add seventeen significant digits to PSF output precision. All twelve actual log and PSF controls match reltol 1e-8, vabstol 1e-10, iabstol 1e-14, traponly, and their declared base/fine maxstep 0.02/0.002 s. Saved waveform rows equal accepted transient steps plus the initial row in every case. These facts support native computed-grid provenance but do not establish rounded-export enclosure bounds or exact rational callback semantics.

The frozen independent checker remains SHA `4a80e6cc91c553ae40d5d635c81ee0d11fd4436bc6fd96d88d1b1a51a13e28ff`; its 1 uV, 200 ns and exact count/order contracts are unchanged.

| Configuration | Spectre independent numeric | Spectre event observation | Qualification | Continuous max error V | Limitation |
| --- | --- | --- | --- | ---: | --- |
| E1-base | P | P | I | 1.8645e-14 | Export qualification remains I |
| E1-fine | I | I | I | 1.914e-14 | Final time token 1.0000000000000004 |
| E2-base | P | P | I | 1.8450e-14 | Export qualification remains I |
| E2-fine | I | I | I | 1.858e-14 | Final time token 1.0000000000000004 |
| E3-base | I | I | I | 1.0000e-8 | Final time token 2.0000000000000013 |
| E3-fine | I | I | I | 1.0000e-8 | Final time token 2.0000000000000013 |
| E4-base | P | P | I | 7.1552e-14 | Export qualification remains I |
| E4-fine | I | I | I | 7.4668e-14 | Final time token 2.0000000000000009 |
| E5-base | I | I | I | 2.0000e-9 | Final time token 2.0000000000000013 |
| E5-fine | I | I | I | 2.0000e-9 | Final time token 2.0000000000000013 |
| E6-base | F | P | F | 7.85259115986e-6 | Exceeds original 1 uV |
| E6-fine | F | I | F | 4.67175138126e-6 | Exceeds 1 uV; final time token 2.0000000000000009 |

Ten configurations' saved-record errors are below 1 uV; strict complete-domain numeric verdicts are P for three, I for seven and F for two. Event verdicts are P for four and I for eight. No failed or incomplete configuration is removed from the denominator.

E6's numerical discrepancy already exceeds 1 uV before the edit at 0.25 s. Its largest drift occurs at 0.49999998000000001 s, before the mode-change timer. The timer brackets are approximately [0.24999998, 0.25] and [0.49999998, 0.5], each 20 ns wide, proving finite observed deadline behavior within the original 200 ns budget. This is an actual baseline/reference numerical discrepancy, retained in the original comparison. Separate convergence diagnostics keep the source and external 1 µV budget unchanged: tightening Spectre to reltol=1e-10, vabstol=1e-12 and iabstol=1e-16 reduces the error to 0.334291 µV at maxstep=0.002 s and 0.019991 µV at maxstep=0.0001 s. This supports a reference numerical-convergence explanation without establishing Spectre’s internal algorithm. The strict-0.002 finite numerical/event checks pass; the strict-0.0001 record lacks the exact endpoint. Both retain qualification I and neither replaces an original F.

At exact rational time 0.5 in E3 and 0.75 in E4, Spectre count is 1 and EVAS count is 0, in both profiles and both EVAS revisions. These exact-boundary differences are retained separately. There are no count differences outside the event uncertainty windows among the matched finite pairs. E5's exact rational 1/3 is not representable in binary64; no nearest or rounded point is assigned exact-center status.

`finite_pairs` in the actual summary uses the same reference for both EVAS revisions. Rows are matched by explicit numeric binary64 time projection. The comparison subtracts the exact Fraction formula difference between the retained decimal time coordinate and the EVAS binary64 coordinate. It records both raw differences and correction magnitudes. Ten such continuous pair checks pass and both E6 pair checks fail for each EVAS revision. This numeric residual comparison does not qualify the exported time origin or prove exact simultaneous observation.

The original settings reader rejected Spectre's `ms`, `pV`, and `fA` display units. The failed first analysis remains in `spectre-reference-actual/`. `settings_readback_si.py` adds only those SI units, with twelve positive/reject calibration controls in `SETTINGS_SI_CALIBRATION.json`; the rerun remains separate in `spectre-reference-actual-si/`. The original acceptance checker is unchanged. Raw reference data, original failures and prior outputs remain retained. No further remote call was performed by this worker.

The frozen checker’s `failures` array records diagnostics and coverage problems; it does not list every numerical threshold violation. Read its numeric status and maximum errors together. The public receipt adds `numeric_failure_reasons` derived from the unchanged 1 µV threshold, preserving all original fields.

Compact identities and outcomes are in [receipt.json](receipt.json). Frozen shared models, input plans and the unchanged checker are [repository-contained](../../../evas/validation/event_acceptance/README.md). Complete raw outputs and execution logs remain local-only under `current/runs/event-closure-20261008/`; checksums alone do not establish public reproducibility.
