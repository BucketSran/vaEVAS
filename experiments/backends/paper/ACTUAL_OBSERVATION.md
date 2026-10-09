# Actual EVAS evidence adapter

`actual_observation.py` derives a new packet from actual response evidence. It
requires frozen core, condition, actual work directory and independent source
review. It does not execute a backend, modify old artifacts or change paper
criteria. The old five positional arguments remain supported; missing execution
identity keeps native roles unknown.

```sh
python3 -B experiments/backends/paper/actual_observation.py \
  FROZEN/core.json CO-SH-01 ACTUAL/runs/CO-SH-01 SOURCE-REVIEW.json NEW-OUTPUT \
  --lane ACTUAL --build-record COLLECTED/build/BUILD.json \
  --source-manifest COLLECTED/SOURCE_MANIFEST.json --tool-profile TOOL-PROFILE.json \
  --producer-repo PINNED-AUDITED-REPO
```

The new output directory must be outside the actual work directory. Both new
files use compact JSON. `evidence.json` binds every consumed artifact; hashes
bind bytes and do not independently prove mathematical or execution semantics.
`observation.json` calls the unchanged qualifier with precisely the old rows.

Source review schema 1 uses `cards_sha256` (or the earlier
`core-v1.json_file_sha`) and `records`. Exactly one record must match condition,
source byte SHA256 and canonical single-card SHA256 (`json.dumps(card,
sort_keys=True,separators=(',',':'),ensure_ascii=True)` encoded UTF-8). Only
`reviewed` with nonempty textual basis (string or list of strings) establishes
source review; review limits remain in the packet.

Optional execution inputs are existing receipts, never created by this adapter.
The verifier checks lane FILE_MANIFEST bytes/hashes, actual successful launch and
cleanup, STARTED source/deck/tool identities, final-record source/card/normalized
identity and worker completion. It binds BUILD's successful compiler stage,
actual compiler hashes, source revision, source manifest and Cargo.lock to the
kernel hash in TOOL_IDENTITY and the profile's build_record_sha256. The profile
must also match the actual tool profile identity and kernel path/hash. The source
manifest's five native producer files must equal the audited producer repository
(the adapter's repository by default). Missing chain inputs keep native unknown;
stale or conflicting supplied identities fail closed. A kernel's absent
self-reported build revision is not repaired: the separate actual build receipt
supplies the source/build/binary chain.

| Role | Actual basis | Remaining limit |
| --- | --- | --- |
| source | Independently reviewed source/card identity | Source review alone is not execution evidence |
| time | Every raw timestamp equals its binary64 request; exact rational serialization bounds include anchors, centers and actual stop versus decimal stop | Callback uncertainty belongs in output certificates |
| voltage | Maximum exact rational radius around each unchanged observable representative using exported interval endpoints | Missing interval rows remain unknown; containment is transport validation, not independent mathematical certificate verification |
| inputs | Exact Fraction sup of decimal reference and binary64 request PWL curves over the full actual executed domain | Actual curve must cover the domain; unsupported or nonmonotone inputs stay unknown |
| native initial | Certified native t=0 plus actual initial_settled and every callback/trigger lower bound strictly positive | Stateless identity additionally proves no states/events/operators; initialization alone cannot prove pre-callback order |
| counters / phase | Unchanged certified native point observations sharing one actual committed response/history | Arbitrary implicit dense history rows remain unknown |
| boundary cohort | Unique frozen breakpoint request ID, exact raw center row, native provenance and bound serialization | No nearest-neighbor match or invented request ID; unresolved centers remain a required missing role |

The input proof uses the actual request stop, not an unexecuted decimal tail.
Both exact PWL curves are compared at the union of their knots and domain
endpoints; the absolute affine difference reaches its maximum at an endpoint.
Per-input exact numerator/denominator and outward binary64 bound are recorded.
The decimal reference uses the existing `oracle.pwl` endpoint hold semantics
when actual stop rounds past the decimal endpoint. The actual Rust source is
never extended and must cover the complete actual domain. Explicit time evidence
retains decimal stop, actual stop, last-row identity and the stop roundoff bound.
Input representation error and actual-input output certificate remain separate;
this does not claim ideal-input output error or a continuous output theorem.

Native mapping follows the audited implementation, not a label substitution.
Accepted controller frames are copied native records. Certified causal frames
select a consistent physical transaction phase, solve/certify at the actual
requested time and publish only after successful overall commitment. Stateless
rows solve independently at requested times (previous solution is an initial
guess), and require a compiled program with no states/events/operators. These
paths map to paper `accepted` only with actual execution/source identity and
that row's interval certificate. Original response origins remain unchanged in
`actual_sample_origins`. For implicit history, only separately certified t=0 is
recognized here; internal accepted endpoint times are not exported, so other
rows remain unknown. Unknown origins and missing certificates remain unknown.

Boundary records use the actual `breakpoint_requests.json`, not generated IDs.
All fields and boundary rows are taken from the same raw response and unchanged
normalized rows; the evidence does not independently run callback histories or
synthesize bracket values. Actual controls are reported separately and never
substitute for voltage uncertainty. Missing roles include boundary cohort when
windows require it. The unchanged qualifier/checker still applies all original
gaps, budgets, event and behavioral checks.

```sh
python3 -B -m unittest discover -s experiments/backends/paper \
  -p test_actual_observation.py -v
```

Synthetic test receipts and reviews calibrate transport and fail-closed rules;
they are not actual paper execution or source-review evidence.
