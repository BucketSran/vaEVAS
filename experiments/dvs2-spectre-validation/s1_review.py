"""S1 review supplement; leaves the historical 31-condition builder unchanged.

CLI output is a condition manifest, not simulator execution or a result receipt.
Use check(rows, condition_id) for these registered conditions: the historical
checker selects S1 parameters by ID and must not receive the new ID directly.
"""
import copy
import json

from check_results import check as historical_check
from run_suite import conditions as historical_conditions


REORDERED_ID = 's1-default-reordered'
SOURCE_CARD = 'n_v1_02_reordered'


def conditions():
    baseline = {c['id']: c for c in historical_conditions()}
    original = baseline['s1-default']
    reordered = copy.deepcopy(original)
    reordered.update(id=REORDERED_ID, card=SOURCE_CARD,
                     source_cards=[SOURCE_CARD], comparison_condition=original['id'])
    return [original, baseline['s1-override'], reordered]


def check(rows, condition_id):
    """Apply the fixed absolute oracle, including to the reordered encoding.

    The new condition has the default condition's exact stimulus, parameters and
    observation contract. Comparing two backend outputs alone is insufficient.
    Unknown IDs fail rather than silently selecting the override parameters.
    """
    registered = {c['id']: c for c in conditions()}
    if condition_id not in registered:
        raise ValueError('unregistered S1 review condition: '+condition_id)
    reference_id = registered[condition_id].get('comparison_condition', condition_id)
    return historical_check(rows, registered[reference_id])


if __name__ == '__main__':
    print(json.dumps(conditions(), indent=2))
