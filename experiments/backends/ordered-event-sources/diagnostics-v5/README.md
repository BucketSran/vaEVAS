# Single-factor reference diagnostics

All three actual attempts produced waveforms, and all 90 retained raw files passed hash verification. Effective solver settings were read from the actual log and PSF. The initial v5 deployment was never executed. Its v5b replacement only adapts SHA-only manifest entries to the runner's SHA/byte-count format; source and deck bytes are unchanged.

| Diagnostic | Final retained state | Finite voltage check | Finite callback check |
| --- | --- | --- | --- |
| Hidden, timer tolerance 1 ps | n=2, q=1, h=1, m=1 | P; maximum z error 1.854e-12 V | I; first bracket is 1.000000004 ns |
| Hidden, timer tolerance 1 fs, cross removed | n=2, q=1, h=0, m=1 | P; maximum z error 2.50000024e-10 V and y=0 | I; same first-bracket limit |
| Mixed, additional ±0.25 ns output strobes | n=2, k=1, j=1 | P; y error is zero | P; first bracket is 0.500000011 ns |

Removing only the cross at 1 fs restores the expected retained timer/integrator state. Keeping the cross and changing only the timer tolerance to 1 ps also restores it. These observations associate the earlier anomaly with this combination; they do not identify a closed-source internal mechanism. Exact endpoints and the order within coalesced records remain inconclusive in all three configurations. All earlier F/I outcomes remain in their original groups.

Saved row counts of 35/35/54 differ from accepted step counts of 130/111/154. The finite checks use every retained row and do not claim access to every calculated step. Candidate EVAS execution is reported separately.

This supplement contains frozen sources, decks, manifests, the derived checker and calibration, plus compact receipts. Raw waveforms, logs and binaries remain local-only. Checksums identify those artifacts but are not public download links.

The `candidate_EVAS` pending field in the original diagnostic receipt describes the reference-analysis checkpoint. It is not the latest candidate status. See the [versioned EVAS executions](../candidate-phase/README.md) for subsequent results; the original diagnostic verdicts remain unchanged.
