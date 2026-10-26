# PR4 E1 observations from CI 40384473617

This archive preserves the fixed candidate 168a9d7a4305e7ce21d1577b4ca1dda65beae4ce,
tree 32034ffd54c8006ac13ff4d475aaf5313b6e436e. The independent Astra decision in
review/review-report.json accepts the exact observations and 7737-condition mapping.
The two maintenance findings remain outside that evidence acceptance. No scientific
qualification or context activation is granted by these files.

bundle/ contains the ten registration evidence roles. Nine files retain their
original bytes. kernel_binary stores one gzip member because its 105862328 decoded
bytes exceed GitHub's 100 MiB regular-file limit. storage.json records both stored
and materialized lengths and SHA256 values. Decompression preserves the reviewed
kernel byte for byte. The optional materializer encoding is a separate pending
implementation increment; the compressed file is data and is not executable.

The bundle report and shard_reports preserve the actual merged report and all
four original report byte strings. stdout and stderr concatenate the original
four streams in shard-index order; proof/e1-bundle-stream-boundaries.json records
exact offsets, lengths and hashes. snapshot_manifest retains all producer inputs.
The original 13 zipped GitHub artifacts, JSONL streams, build logs and full local
review scratch remain in the owning task's retained CI directory. GitHub Actions
artifacts expire; those local archives are not claimed to be published here.

Source and prior calibration evidence remain at their fixed Git revisions.
This archive does not replace the original C0 baseline, old failures, expected
failures or the 20 separately retained scientific candidates.
