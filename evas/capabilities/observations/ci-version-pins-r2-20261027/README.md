# CI version pins, review-r1 fixes

Built on 6bfa35ea. The pin test reads every runs-on, matrix runner, setup-python and matrix Python declaration in any quoting and fails on unknown forms; comment lines and trailing shell comments no longer satisfy a pin. The catalog inventory accepts only a numeric major.minor or major.minor.patch declaration. Criteria, collector and language profile are unchanged. Scientific qualification is false.
