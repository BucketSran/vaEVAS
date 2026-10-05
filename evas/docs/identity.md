# Package and kernel identity

Query package metadata without a manifest:

```sh
PYTHONPATH=evas/src python3 -m evas version --json
```

Query the selected executable and its compatibility facts:

```sh
cargo build --locked --manifest-path evas/rust_core/Cargo.toml
PYTHONPATH=evas/src python3 -m evas version --json --kernel evas/rust_core/target/debug/evas-kernel
evas/rust_core/target/debug/evas-kernel --version --json
```

Neither query compiles a model or runs numerical work. The kernel command returns
without reading stdin and bypasses simulation diagnostic capture.

The Python response uses `identity_version=1`. `package` contains the distribution
name, version, `metadata_source` and `build_revision`. A source invocation reads
this package's `pyproject.toml`; an installed invocation uses distribution
metadata when that source file is absent. No revision is recorded by the current package
build, so `build_revision` is null. `platform` describes the running Python host.

Without `--kernel`, `kernel.status` is `not_requested`. An explicit selection
records its resolved `path`, file `sha256`, `reported` identity and status. The
SHA256 comes from the selected file, not its name or the current checkout.
The kernel reports `identity_version=1`, `name`, its Cargo package `version`,
`build_revision`, `ir_schema_version`, `request_protocol_version` and its build
platform's `os` and `arch`. Current builds record no source revision; null does
not mean current HEAD. Rebuilding changed source never acquires a guessed old
revision.

`compatibility.ir_schema_version` is the Python compiler's IR contract version.
`compatibility.status` is `not_checked`, `ir_matched` or `ir_mismatch`. Matching
means only that the kernel reports the same IR schema; it does not certify every
model or numerical result. The request format has no independently versioned
metadata, so `request_protocol_version` is null on both sides. The separate
`evas-ir` crate package version is not a request protocol version.

A missing, non-executable, wrong, malformed, incompatible or timed-out selected
kernel returns exit 2. Stdout still contains available identity with
`kernel.status=error`; stderr contains the existing versioned machine diagnostic.
An identity query has a five-second timeout and never selects another binary.
The direct kernel query contains no artifact hash because the Python caller owns
the selected path and hashes the file. Normal compile/solve/transient/simulate
CLI behavior is unchanged. This interface does not supply platform wheels,
a released tag, kernel discovery or installation guarantees.

Implementation is in `src/evas/identity.py`, the early Python CLI dispatch in
`src/evas/__main__.py`, and the early Rust CLI dispatch in `rust_core/src/main.rs`.
The public CLI regressions are in `tests/test_identity.py`; real compile and
transient smoke results belong to each execution receipt.

Special files, including devices and FIFOs, are rejected before hashing. The kernel query timeout applies after the finite regular-file hash is computed.
