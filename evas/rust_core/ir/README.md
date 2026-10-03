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
