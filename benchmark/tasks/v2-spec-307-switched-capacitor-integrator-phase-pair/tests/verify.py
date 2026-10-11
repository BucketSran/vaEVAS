from v2_runtime import main
# Explicit transitive import keeps prepare/sync self-contained.
from v2_spec import evaluate as _external_dependency
from v2_structure import evaluate
if __name__=='__main__':main(evaluate)
