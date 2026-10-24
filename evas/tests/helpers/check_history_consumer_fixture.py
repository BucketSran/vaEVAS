"""Declare history-consumer variants that share one builder.

A public waveform pass does not satisfy the private late-failure rollback
obligation. This command only reads the Rust sources.
"""
import hashlib
import json
from pathlib import Path


VARIANTS = (
    {
        "name": "accepted_schedule",
        "parameter": "late_failure=false",
        "obligation": "public waveform and same-clock sample",
        "does_not_satisfy": "private rollback",
    },
    {
        "name": "late_failure",
        "parameter": "late_failure=true",
        "obligation": "full frame retry without publication",
        "does_not_satisfy": "public waveform pass",
    },
)


def main():
    root = Path(__file__).resolve().parents[3]
    builder = root / "evas/rust_core/src/history_consumer_fixture.rs"
    private = root / "evas/rust_core/src/transient_history_consumer_tests.rs"
    public = root / "evas/rust_core/tests/history_consumer.rs"
    private_text = private.read_text()
    public_text = public.read_text()
    if "fn fixture_mode(late_failure: bool)" not in private_text:
        raise SystemExit("private history consumer lost its late_failure variant")
    if "fixture_mode(false)" not in private_text or "fixture_mode(true)" not in private_text:
        raise SystemExit("private history consumer no longer builds both variants")
    if "history_consumer_fixture" not in public_text:
        raise SystemExit("public history consumer no longer uses the shared builder")
    print(json.dumps({
        "builder_sha256": hashlib.sha256(builder.read_bytes()).hexdigest(),
        "public_test": "evas/rust_core/tests/history_consumer.rs",
        "private_test": "evas/rust_core/src/transient_history_consumer_tests.rs",
        "public_pass_is_private_rollback_pass": False,
        "variants": list(VARIANTS),
    }))


if __name__ == "__main__":
    main()
