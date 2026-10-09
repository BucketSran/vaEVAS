# Actual EVAS evidence adapter

`actual_observation.py` derives a **new** evidence packet from an actual run. It
requires the frozen core, condition ID, actual run directory, and explicit
independent source review. It does not execute a backend or modify the original
raw response, normalized observation, source, frozen cards, or paper criteria.

```sh
python3 -B experiments/backends/paper/actual_observation.py \
  FROZEN/core.json CO-SH-01 ACTUAL/runs/CO-SH-01 \
  SOURCE-REVIEW.json NEW-OUTPUT
```

The output directory must not exist. `evidence.json` binds the SHA256 and byte
size of every consumed file. `observation.json` calls the existing qualifier
with precisely the original rows. Both new files use compact JSON. These hashes
bind actual evidence bytes; they are not execution receipts or a replacement
for the run's existing tool identity and resource receipts.

The source review schema is version 1, with top-level
`cards_sha256` (or the earlier `core-v1.json_file_sha`) and `records`. Exactly one record must match the condition,
source byte SHA256, and single-card canonical SHA256 (`json.dumps(card,
sort_keys=True,separators=(',',':'),ensure_ascii=True)` encoded as UTF-8). Only
`status: reviewed` with nonempty textual `basis` (a string or list of strings) establishes the source role.
Unknown, failed, absent or stale reviews never default to reviewed. Tests use
synthetic reviews only to calibrate this interface.

| Role | Actual basis | Remaining limit |
| --- | --- | --- |
| source | Independent reviewed source/card identity | Review limits remain in the packet |
| time | Every returned time equals the actual requested binary64 time; exact rational outward serialization bound also covers decimal card anchors and centers | This does not bound callback localization; that uncertainty belongs in output certificates |
| voltage | Maximum exact rational distance from each returned observable to its exported solver interval endpoints | Missing interval rows stay unknown; a broad interval stays broad; the certificate concerns the actual binary64 IR/PWL system |
| inputs | Exact Fraction sup on the union of both continuous PWL knot sets and original-domain endpoints | Unsupported, nonmonotone or insufficiently covering curves stay unknown; this input error is separate from the actual-input output certificate |
| native initial | Actual `initial_settled`, accepted t=0 frame, and every exported event/trigger lower bound strictly positive | Initialization alone cannot prove a row before a t=0 callback |
| counters / phase | Unchanged voltages from accepted controller frames, without interpolation or modulo repair | Stateless, implicit-history and certified-causal query origins are reported but remain unknown under the existing paper accepted identity |

Each role records its basis or concrete missing evidence. Actual controls are
reported separately and never substitute for voltage error. Python interval
containment checks transport consistency; they do not independently verify the
Rust mathematical certificate. The adapter does not reinterpret accepted-step
counts or infer an accepted row from output density. A missing continuous input
certificate keeps full paper qualification false even when other roles have
been established. The useful result is a runnable, bound evidence
packet exposing measured certificate radii and the precise remaining obligations.

Run its calibration tests with:

```sh
python3 -B -m unittest discover -s experiments/backends/paper \
  -p test_actual_observation.py -v
```

The PWL bound compares the exact decimal card curve with the exact binary64
request curve, as retained by Rust `exact_source::Curve::source/value`. Their
difference is affine between consecutive union knots, so the absolute maximum
is attained at a union endpoint. The report records exact numerator/denominator
per input and rounds the reported supremum outward. It does not use observation
rows or numerical grids. Floating representative interpolation and returned
voltage uncertainty are separate obligations of the solver output certificate.
