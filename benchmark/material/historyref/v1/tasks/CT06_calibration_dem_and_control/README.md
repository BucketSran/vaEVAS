# CT06 Calibration, DEM, and Control Audit

CT06 covers voltage-domain behavioral blocks that sit around analog/mixed-signal
cores: calibration update logic, DEM element-selection logic, and one closed-loop
calibration flow. It is not a generic digital-control bucket; a task stays here
only when its observable behavior is tied to analog calibration, trimming, or
unit-element selection.

| ID | Entry | Level | Circuit role | Keep rationale | Primary public checks |
| --- | --- | --- | --- | --- | --- |
| CT06-01 | `vbr1_l1_trim_calibration_controller` | L1 | Signed trim-voltage update from an error polarity. | Covers analog trim actuator generation. | reset to nominal trim, directional trim movement, clamp range |
| CT06-02 | `vbr1_l1_gain_trim_controller` | L1 | Bounded gain-control update around a measured/target value. | Distinct from trim-voltage generation because the observable state is gain code/control. | low measured value increases control, high measured value decreases control, clamp |
| CT06-03 | `vbr1_l1_calibration_deadband_controller` | L1 | Calibration update with deadband hold. | Covers practical calibration hysteresis/deadband behavior. | hold inside deadband, move outside deadband, clamp |
| CT06-04 | `vbr1_l1_successive_approximation_calibration_search_fsm` | L1 | Successive-approximation calibration search. | Covers binary-search style calibration, not a generic FSM. | step halving, direction follows error, done after search window |
| CT06-05 | `vbr1_l1_element_shuffler` | L1 | Non-monotonic one-hot element permutation for DEM-style element usage. | Kept as the small permutation baseline after removing duplicate rotating/window pointer variants. | one-hot permutation sequence `2,0,3,1,2,0` |
| CT06-06 | `vbr1_l1_dwa_dem_encoder` | L1 | 16-element DWA pointer and cell-enable encoder driven by input code. | Covers data-converter DEM/DWA behavior over a wider element set. | sampled-code pointer advance, one-hot pointer, circular cell window wrap |
| CT06-07 | `vbr1_l2_complete_calibration_loop` | L2 | Closed-loop error/trim/actuator calibration flow. | CT06 L2 anchor: demonstrates a composed calibration loop rather than a standalone controller. | raw error correction, bounded negative-feedback response, convergence metric |

Design notes:

- `element_shuffler` is intentionally small. It is retained only as a compact
  DEM permutation baseline; stronger DEM coverage comes from the 16-element DWA
  encoder.
- `dwa_dem_encoder` is the CT06 bridge back to data converters: the checker
  requires the pointer to advance by sampled code, wrap across 16 elements, and
  emit a circular selected-cell window.
- The CT06 L2 task is intentionally a complete calibration loop. It should not
  be replaced by another shallow controller unless the replacement also exposes
  closed-loop functional evidence.
