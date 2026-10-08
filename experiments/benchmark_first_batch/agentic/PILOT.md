# Fixed representative pilot

This report covers protocol A on seven fixed representatives and two requested endpoint labels, `glm-5.3` and `glm-5.3-flash`. The public feedback backend was native EVAS; frozen candidates received independent Spectre final evaluation. It is a restricted-feedback pilot, not a score for all 35 tasks or evidence for ranking task difficulty. Both labels advertise the same model family. The server response model IDs remain unknown.

The machine-readable [receipt](pilot-fixed14-receipt.json) contains all 14 cells, complete case outcomes, candidate and final-package identities, tool counts, token fields, source inventories, and independent archive audit results. Published [candidates](candidates/) retain the exact frozen source bytes. Each task has weight 1/7 within a requested route. The integration representative is a complete-repository task with four declared candidate files; it still counts as one task.

## Fixed results

| Representative | Requested label | Final score | Passed / frozen cases | Final classification | Agent phase |
| --- | --- | ---: | ---: | --- | --- |
| [spec-latched-comparator](candidates/spec-latched-comparator/glm-5.3/manifest.json) | glm-5.3 | 1 | 2/2 | complete pass | AgentTimeoutError |
| [spec-latched-comparator](candidates/spec-latched-comparator/glm-5.3-flash/manifest.json) | glm-5.3-flash | 0 | 0/2 | compile rejection | AgentTimeoutError |
| [identify-sh-acquisition](candidates/identify-sh-acquisition/glm-5.3/manifest.json) | glm-5.3 | 1 | 4/4 | complete pass | AgentTimeoutError |
| [identify-sh-acquisition](candidates/identify-sh-acquisition/glm-5.3-flash/manifest.json) | glm-5.3-flash | 0 | 0/4 | graded semantic rejection | AgentTimeoutError |
| [integrate-tdc-measurement-chain](candidates/integrate-tdc-measurement-chain/glm-5.3/manifest.json) | glm-5.3 | 1 | 3/3 | complete pass | AgentTimeoutError |
| [integrate-tdc-measurement-chain](candidates/integrate-tdc-measurement-chain/glm-5.3-flash/manifest.json) | glm-5.3-flash | 1 | 3/3 | complete pass | AgentTimeoutError |
| [repair-sar-abort](candidates/repair-sar-abort/glm-5.3/manifest.json) | glm-5.3 | 1 | 2/2 | complete pass | completed, submitted |
| [repair-sar-abort](candidates/repair-sar-abort/glm-5.3-flash/manifest.json) | glm-5.3-flash | 1 | 2/2 | complete pass | completed, submitted |
| [verify-sar-flow](candidates/verify-sar-flow/glm-5.3/manifest.json) | glm-5.3 | 0 | 0/6 | graded semantic rejection | AgentTimeoutError |
| [verify-sar-flow](candidates/verify-sar-flow/glm-5.3-flash/manifest.json) | glm-5.3-flash | 0 | 0/6 | simulation topology rejection | AgentTimeoutError |
| [measure-adc-spectrum](candidates/measure-adc-spectrum/glm-5.3/manifest.json) | glm-5.3 | 1 | 3/3 | complete pass | AgentTimeoutError |
| [measure-adc-spectrum](candidates/measure-adc-spectrum/glm-5.3-flash/manifest.json) | glm-5.3-flash | 1 | 3/3 | complete pass | completed, submitted |
| [optimize-vco-step](candidates/optimize-vco-step/glm-5.3/manifest.json) | glm-5.3 | 0 | 0/3 | graded functional rejection | AgentTimeoutError |
| [optimize-vco-step](candidates/optimize-vco-step/glm-5.3-flash/manifest.json) | glm-5.3-flash | 0 | 0/3 | graded functional rejection | AgentTimeoutError |

All 14 fixed cells have a complete frozen candidate and one sealed final evaluation. The equally weighted means are 5/7 for requested `glm-5.3` and 3/7 for requested `glm-5.3-flash`. Eleven agent phases timed out; three completed naturally. These are separate observations, not a claim that all Trials succeeded.

A phase deadline freezes the latest complete candidate under the accepted harness protocol. The final score remains valid when that phase has an `AgentTimeoutError`. Those runs did not complete naturally. Action or simulation quota errors alone do not freeze the candidate. The three natural completions used `evas_submit`; no source was repaired or silently submitted after the phase. A score zero is separated into compile or simulation rejection and fully graded functional or semantic rejection. Infrastructure-null remains distinct from score zero.

The comparator Flash candidate failed compilation because `fabs` was undefined. The verification Flash candidate reached a Spectre rigid-branch-loop topology rejection; a retained earlier diagnostic found a compiler warning, which was not the fatal cause. Neither observation alone establishes circuit reasoning difficulty. Both VCO candidates received score zero after fully graded functional rejection in all three conditions. Their paired audits bind the original candidate and final package and confirm `not_run_main_functional_failure`, with zero paired attempts. They did not reach performance measurement.

## Public feedback and identities

| Representative | Requested label | Accepted public actions | Simulations: backend error / ok | Invalid-action messages |
| --- | --- | ---: | ---: | ---: |
| spec-latched-comparator | glm-5.3 | 12 | 6 / 0 | 0 |
| spec-latched-comparator | glm-5.3-flash | 5 | 2 / 0 | 0 |
| identify-sh-acquisition | glm-5.3 | 26 | 12 / 1 | 0 |
| identify-sh-acquisition | glm-5.3-flash | 8 | 4 / 0 | 0 |
| integrate-tdc-measurement-chain | glm-5.3 | 6 | 1 / 0 | 3 |
| integrate-tdc-measurement-chain | glm-5.3-flash | 11 | 3 / 0 | 0 |
| repair-sar-abort | glm-5.3 | 16 | 7 / 0 | 0 |
| repair-sar-abort | glm-5.3-flash | 11 | 5 / 0 | 0 |
| verify-sar-flow | glm-5.3 | 24 | 12 / 0 | 0 |
| verify-sar-flow | glm-5.3-flash | 6 | 3 / 0 | 0 |
| measure-adc-spectrum | glm-5.3 | 30 | 14 / 0 | 0 |
| measure-adc-spectrum | glm-5.3-flash | 9 | 4 / 0 | 0 |
| optimize-vco-step | glm-5.3 | 17 | 7 / 1 | 0 |
| optimize-vco-step | glm-5.3-flash | 9 | 4 / 0 | 0 |

Counts of accepted public actions come from session receipts. The `invalid_action` column counts matching Pi tool-result messages, not exact HTTP attempts, because one message can contain several requests. These counts do not measure all ordinary shell or Python analysis. Per-cell native Pi call counts and stop reasons remain in the receipt. The original comparator reference was itself rejected by EVAS. Several tasks could only obtain candidate compatibility diagnostics because immutable public fixture models could not be included alongside declared candidate files. The fixed receipt contains 86 public simulation responses: 84 `backend_error` and 2 `ok`. `backend_error` is an API response status. It can reflect unsupported candidate code, compilation rejection, or an entry/backend capability limit; the root cause of every individual response is not established. The retained reference probe and fixture limits demonstrate restricted feedback, but the response label alone does not establish an infrastructure outage or excuse candidate failure. Independent Spectre scores remain unchanged.

Each new fixed snapshot disclosed the current source/macro contract and complete action envelope. Historical snapshots with omitted macro rules or incomplete action envelopes remain separate. The fixed cells use the proven normal final profile, except optimization, which uses the independently calibrated 900-second/256-MiB performance profile with recorded client wait 1200 seconds and verifier deadline 1500 seconds. Public feedback limits remain independent. Initial agent settings were 1200 seconds, 80 accepted actions, 16 simulations, and an explicit 65536 provider output ceiling. They are recorded engineering settings, not user resource ceilings.

Pi 0.87 initializes its assistant `model` field from the configured request label. Its inspected transport preserves `responseModel` only when the response chunk model differs. All fixed cells used the inspected immutable image. Their absent `responseModel` cannot distinguish an equal response ID from an omitted response ID. Thus the receipt and format-2 candidate manifests separately retain requested and Pi-recorded labels, while independently observed server model IDs are null. Response IDs establish real generation, not vendor internal routing. Earlier derived claims of observed served identity were corrected; raw Trials and historical compact receipts were not rewritten.

The receipt retains Pi input/cache/output/reasoning/total fields and Harbor input/cache/output fields separately. Those sources can differ, so no synthetic common token total replaces them. Pi cost zero can reflect missing pricing metadata; Harbor `cost_usd: null` means actual billing is unknown. No dollar estimate is claimed.

## Evidence and reproducibility

Each nonnull final score binds one sealed evaluation. The audit verifies the inventory and result artifact hashes, fixed checker/package/criteria identity, actual candidate bytes, every case's original and executed VA bytes, inverse output relocation, and netlists. Fully graded cases require return code zero, complete PSF data ending in END, waveform hashes and actual parsed row counts. A complete pass requires all frozen conditions. Optimization archives additionally receive the formal paired audit if the main functional condition reached that stage. Reference calibration's twelve paired waveforms are distinct from model-candidate paired evidence.

Published candidates are repository-contained and scanned before and after copying. Re-evaluating them needs the fixed scoring package, backend and deployment, but no model API. Generating another candidate needs model access. The [README](README.md#candidate-source-evidence) gives a locally verified harness bundle-preparation command. Machine configuration, original transcripts and bulk waveforms remain private. Commercial Spectre and deployment access limit full reproduction; package hashes alone are not a claim that the private deployment is publicly available. A local run of the existing snapshot tool rebuilt all seven final packages from current repository assets at revision `ed7520bf6128edee09b123ab01c787cd3dfaabd9` and matched every original package SHA. It made no model or solver call. The README documents the original labels needed to obtain those packages.

One identification GLM raw tool-result file contained credential echo after an environment-reading command. The record establishes one hit file, not the number of occurrences. Its original bytes remain private with restrictive permissions; a separate redacted derivative was retained. The candidate and all 119 sealed final archive members had zero known-token hits. The public candidate and receipt scans also check generic credential patterns. The complete raw batch must not be described as credential-free. Agent-readable credential isolation is required by this observed exposure.

## Historical attempts

The four historical Trial attempts have their own denominator; three reached model calls. Deployment-only preparations are listed separately and do not inflate that denominator. The initial network/DNS failure made no model call. The first Flash generation stopped at its default output limit before producing a candidate. A later explicitly increased-budget attempt froze a candidate but its legacy final profile produced an ungraded infrastructure receipt. An explicit posthoc recovery evaluated exactly those frozen candidate and package bytes with no model call and returned score zero. The original deadline and infrastructure failure remain intact. These events do not replace or enlarge the fixed 14-cell denominator.

## Next comparison

First provide usable public circuit feedback and isolate credentials from agent-readable processes and files. Existing Harbor/harness code supports a separate remote Spectre public session without a harness modification, but it requires an isolated Docker image and public profile. The retained read-only deployment probe found Docker daemon permission denial and no public Docker profiles. A host final-evaluation profile cannot serve as an Agent public tool. This delivery does not grant broader deployment permissions or change the fixed pilot protocol.

Then freeze a new protocol version and rerun the same seven representatives and two requested routes to compare the effect of improved feedback. Record independent response-model metadata where the provider supplies it. Expand to all 35 tasks and other model families after that controlled comparison. Open-source regrading requires independent actual grading comparisons before determining eligibility for the public main set or a separate open-source regrading collection. Scores from the current EVAS backend limitations cannot establish task difficulty tiers.
