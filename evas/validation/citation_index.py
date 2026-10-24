"""Machine-checked citations from experiments back to validation contracts.

An edge records where a maintained contract is read. It does not authorize
reusing one execution for another obligation. DVS science migration and the
final reuse decision stay with the reviewer.
"""
from pathlib import Path


EDGES = (
    {
        "case_family": "sample-edge-filter",
        "contract": "evas/validation/sample_edge_filter/contract.py",
        "experiment": "experiments/backends/sample-edge-filter/run.py",
        "citation": "evas/validation/sample_edge_filter",
    },
    {
        "case_family": "transition-integral",
        "contract": "evas/validation/paper/transition_integral_precision.py",
        "experiment": "experiments/backends/support/transition_integral_run.py",
        "citation": "transition_integral_precision",
    },
    {
        "case_family": "legacy-chain",
        "contract": "evas/validation/paper/legacy_chain_precision.py",
        "experiment": "experiments/backends/support/legacy_chain_run.py",
        "citation": "legacy_chain_precision",
    },
    {
        "case_family": "coefficient-first-order",
        "contract": "evas/validation/paper/coefficient_first_order.py",
        "experiment": None,
        "citation": "CoefficientFirstOrder",
    },
    {
        "case_family": "shaped-range-oracle",
        "contract": "evas/tests/helpers/generate_shaped_range_oracle.py",
        "experiment": None,
        "citation": "fraction_value_slope_enclosure_binary64_bits",
    },
    {
        "case_family": "ordinary-integer-prefix",
        "contract": "evas/tests/helpers/check_ordinary_integer_prefix_fixture.py",
        "experiment": None,
        "citation": "program_matches_frontend",
    },
    {
        "case_family": "rational-transition-rollback",
        "contract": "evas/tests/helpers/check_rational_transition_fixture.py",
        "experiment": None,
        "citation": "frozen_rewritten",
    },
    {
        "case_family": "history-consumer",
        "contract": "evas/tests/helpers/check_history_consumer_fixture.py",
        "experiment": None,
        "citation": "public_pass_is_private_rollback_pass",
    },
)


def check(root):
    root = Path(root)
    rows = []
    for edge in EDGES:
        contract = root / edge["contract"]
        if not contract.is_file():
            raise SystemExit(f"missing contract {edge['contract']}")
        experiment = edge["experiment"]
        if experiment is not None:
            path = root / experiment
            if not path.is_file():
                raise SystemExit(f"missing experiment {experiment}")
            if edge["citation"] not in path.read_text():
                raise SystemExit(f"{experiment} does not cite {edge['citation']}")
        elif edge["citation"] not in contract.read_text():
            raise SystemExit(f"{edge['contract']} lost citation {edge['citation']}")
        rows.append({
            "case_family": edge["case_family"],
            "contract": edge["contract"],
            "experiment": experiment,
            "execution_reuse": False,
        })
    return {"execution_reuse": "not_authorized", "edges": rows}
