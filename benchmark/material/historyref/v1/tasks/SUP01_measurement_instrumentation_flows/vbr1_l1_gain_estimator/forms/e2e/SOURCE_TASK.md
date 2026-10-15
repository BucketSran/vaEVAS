# Designed Release Task: vbr1_l1_gain_estimator

- Source path: `designed_release_spec:vbr1_l1_gain_estimator`
- Form: `e2e`
- prompt.md: `True`
- meta.json: `True`
- checks.yaml: `True`
- gold/: `True`
- sim_correct checks: `True`
- parity checks: `pending`
- release-ready checks: `True`

This form replaces the earlier copied `gain_extraction_smoke` system so CT07 has
a standalone L1 measurement helper rather than a duplicate of the L2 gain
extraction flow.
