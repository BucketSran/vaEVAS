# PR6 review-r4 fixes on 340ef10e

One source commit closes two defect classes. The Markdown support audit accepts only the generated rendering up to requirement order and record order within a requirement (R4-01, R4-02). The generator checks every new Rust receipt strictly whether or not its source is published, and the CI toolchain-selection guard is a whitelist with the fuzz-smoke nightly as its one exception (R4-03, R4-04). Criteria, collector, language profile and workflows are unchanged. Scientific qualification is false.
