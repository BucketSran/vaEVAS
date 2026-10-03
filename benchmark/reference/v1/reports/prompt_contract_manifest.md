# vaBench Release Prompt Contract Manifest

Date: 2026-06-23

| Metric | Value |
| --- | ---: |
| status | `pass` |
| prompt version | `public-contract-v3` |
| runner wrapper | `release-runner-wrapper-v6` |
| prompts | 300 |

## Form Counts

| Form | Prompts |
| --- | ---: |
| `bugfix` | 62 |
| `dut` | 66 |
| `e2e` | 86 |
| `tb` | 86 |

## Change Summary

- Normalized all release prompts to explicit public benchmark contracts.
- Added explicit Spectre .scs scaffold guidance for TB/E2E prompts, including ahdl_include and instance syntax.
- Moved runner-only wrapper, ICL, and repair-feedback protocol out of public prompts.
- Removed explicit bug-root-cause hints from bugfix prompts; bugfix tasks now expose only public behavior and observable mismatch framing.
- Recorded runner-side baseline wrapper `release-runner-wrapper-v6` for Question/Answer markers and shared EVAS/Spectre rules.
- Recorded target artifact names from release_task/gold assets for prompt-version traceability.
- Old model-baseline results should be treated as historical and rerun before comparison.

## Claim Policy

- Public prompts are benchmark contracts: task contract only: form, target artifacts, interfaces, public observables, public behavior checks, and output contract.
- Runner wrappers remain outside the prompt body: model invocation protocol, output extraction markers, optional repair feedback, and optional ICL variants.
- EVAS rules remain shared runner guidance: shared voltage-domain and EVAS/Spectre compatibility guidance injected by runners, not benchmark prompt content.
- Baseline comparability: public-contract-v2, public-contract-v3, and different runner wrapper versions are not directly comparable without rerun.

## Sample Rows

| Task | Form | Target Artifacts | Prompt SHA256 |
| --- | --- | --- | --- |
| `vbr1_l1_binary_weighted_voltage_dac:bugfix` | `bugfix` | `dut_fixed.va` | `c6780853e4a8` |
| `vbr1_l1_binary_weighted_voltage_dac:dut` | `dut` | `simple_binary_voltage_dac_4b.va` | `e6549df38f3f` |
| `vbr1_l1_binary_weighted_voltage_dac:e2e` | `e2e` | `simple_binary_voltage_dac_4b.va`, `tb_simple_binary_voltage_dac_4b_ref.scs` | `2863e0d38b89` |
| `vbr1_l1_binary_weighted_voltage_dac:tb` | `tb` | `tb_simple_binary_voltage_dac_4b_ref.scs` | `fd64844a5a0d` |
| `vbr1_l1_capacitive_weighted_sar_feedback_dac:bugfix` | `bugfix` | `dut_fixed.va` | `ce474cf76fdb` |
| `vbr1_l1_capacitive_weighted_sar_feedback_dac:dut` | `dut` | `cdac_cal.va` | `d54889ff1ef4` |
| `vbr1_l1_capacitive_weighted_sar_feedback_dac:e2e` | `e2e` | `cdac_cal.va`, `tb_cdac_cal_ref.scs` | `fbd66c934173` |
| `vbr1_l1_capacitive_weighted_sar_feedback_dac:tb` | `tb` | `tb_cdac_cal_ref.scs` | `4bb6564c0e35` |
| `vbr1_l1_clocked_adc_quantizer:bugfix` | `bugfix` | `dut_fixed.va` | `cb62206ef1ea` |
| `vbr1_l1_clocked_adc_quantizer:dut` | `dut` | `flash_adc_3b.va` | `b393d63239ae` |
| `vbr1_l1_clocked_adc_quantizer:e2e` | `e2e` | `flash_adc_3b.va`, `tb_flash_adc_3b_ref.scs` | `0a5b0fa93f47` |
| `vbr1_l1_clocked_adc_quantizer:tb` | `tb` | `tb_flash_adc_3b_ref.scs` | `5b701f41b800` |
| `vbr1_l1_dac_mismatch_unit_weighting_model:bugfix` | `bugfix` | `dut_fixed.va` | `10a2b9121757` |
| `vbr1_l1_dac_mismatch_unit_weighting_model:dut` | `dut` | `dac_mismatch_unit_weighting_model.va` | `afe228baee46` |
| `vbr1_l1_dac_mismatch_unit_weighting_model:e2e` | `e2e` | `dac_mismatch_unit_weighting_model.va`, `tb_dac_mismatch_unit_weighting_model.scs` | `b2cf71c6a8d0` |
| `vbr1_l1_dac_mismatch_unit_weighting_model:tb` | `tb` | `tb_dac_mismatch_unit_weighting_model.scs` | `20898e4ee613` |
| `vbr1_l1_pipeline_adc_stage:bugfix` | `bugfix` | `dut_fixed.va` | `36789d00ab38` |
| `vbr1_l1_pipeline_adc_stage:dut` | `dut` | `pipeline_stage.va` | `41487781382b` |
| `vbr1_l1_pipeline_adc_stage:e2e` | `e2e` | `pipeline_stage.va`, `tb_pipeline_stage_ref.scs` | `a12306e0368f` |
| `vbr1_l1_pipeline_adc_stage:tb` | `tb` | `tb_pipeline_stage_ref.scs` | `939b810242bd` |
