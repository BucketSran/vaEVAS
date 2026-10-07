#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from circuit_task import main
from first_batch_integration import evaluate
if __name__ == "__main__":
    main(evaluate)
