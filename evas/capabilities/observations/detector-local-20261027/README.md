# PR4 local construction and detector calibration receipts

These receipts bind the explicit source capture in capture.json. The source.patch and source.commit preserve that local construction; the final PR and CI input identities are recorded separately.

Discovery uses the literal workflow TestLoader entries under Python 3.12 without running test bodies. Calibration controls execute only the selected test assertions against retained or synthetic observations and block DUT calls. The 22 unique controls passed under Python 3.12 and 3.14 after the preserved AST-format portability repair. These checks do not grant scientific or E1 qualification.

original-inputs retains the exact historical bytes selected by the calibration provenance manifest. extract_fixtures.py records the executed local extraction recipe and its original directory layout; it is not a repository command. Git fixture isolation and final fast-gate receipts remain in the candidate review evidence.
