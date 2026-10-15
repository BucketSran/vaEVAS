# vaBench Release Package Manifest

Date: 2026-06-23

This package-level manifest indexes every release entry and materialized
form. It is a navigation and machine-consumption layer, not simulator
certification evidence.

## Summary

| Metric | Value |
| --- | ---: |
| status | `in_progress` |
| planned entries | 86 |
| entries | 86 |
| forms | 300 |
| core entries | 73 |
| support entries | 13 |
| core forms | 265 |
| support forms | 35 |
| content denominator entries | 73 |
| content-excluded entries | 13 |
| content denominator forms | 265 |
| content-excluded forms | 35 |
| certified entries | 86 |
| certified forms | 300 |
| pending entries | 0 |
| pending forms | 0 |
| scored entries | 73 |
| scored forms | 265 |
| core scored entries | 73 |
| core scored forms | 265 |
| support scored entries | 0 |
| support scored forms | 0 |
| L0 conformance cases | 4 |

## Entry Status Counts

| Status | Count |
| --- | ---: |
| `certified` | 86 |

## Form Status Counts

| Status | Count |
| --- | ---: |
| `certified` | 300 |

## Claim Boundary

- This manifest is an index over package assets and reports; it is not simulator certification evidence.
- Rows with counted_in_score=false must not enter benchmark score denominators.
- Rows with content_denominator_included=false remain package assets but are excluded from strong benchmark content claims.
- Rows with track=support are auxiliary measurement/stimulus assets and must be reported separately from the core circuit score.
- Imported subset certification must not be phrased as full release certification.
- claim_gate_status=in_progress
- release_status_planned_entries=79
