# EVAS IR

This crate owns the versioned request, model, response and error types. It has
no dependency on the numerical kernel. `evas_kernel::ir` re-exports these types,
so existing kernel clients retain the same Rust paths and JSON version.

Parsing checks the schema version before decoding the model, then decodes the
original bytes. Duplicate and unknown model fields remain errors. The small
public traversal helpers enumerate operator origins, event assignments and OR
leaves; they do not evaluate expressions or execute events.

The solver, operators, intervals and transient controller remain in
`evas-kernel`. They share private numerical types and a single commit owner.
Splitting those modules is a separate design change, not a consequence of this
crate boundary. Build measurements and the decision are described in
[performance measurements](../../../experiments/performance/README.md).

Transient responses may include optional `observation_evidence` schema 1,
with effective controls, row provenance and node-bound interval columns.
Its version is independent of request IR v18; old JSON responses remain valid.
Internal Solution certificates are not serialized as duplicate fields. See the
[observation contract](../../docs/reference/observation-evidence.md) for indexing, missing
evidence, conservative hulls and qualification limits.
