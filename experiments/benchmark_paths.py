"""Locate preserved benchmark assets without rewriting historical path identities."""
from pathlib import Path


RELOCATIONS = {
    "benchmark/workbench": "benchmark/material/draftbench",
    "benchmark/reference": "benchmark/material/historyref",
    "benchmark/checkers": "benchmark/material/historyref/legacy-authoring/checkers",
    "benchmark/workbench/history/first-batch": "benchmark/material/historyref/legacy-authoring/first-batch",
}

HISTORY_TASKS = "benchmark/material/historyref/tasks"
DRAFT_BATCHES = "benchmark/material/draftbench/batches"


def task_directories(repo):
    """Author-maintained material packages, excluding the reviewed task collection."""
    root = Path(repo)
    return sorted([
        *(p for p in (root / HISTORY_TASKS).glob("*") if p.is_dir()),
        *(p for p in (root / DRAFT_BATCHES).glob("*/tasks/*") if p.is_dir()),
    ])


def material_path(repo, historical_path):
    """Resolve an old manifest path in the material tree; unrelated paths stay literal."""
    name = str(historical_path)
    old_batch = "benchmark/material/draftbench/history/first-batch"
    if name == old_batch or name.startswith(old_batch + "/"):
        return Path(repo) / ("benchmark/material/historyref/legacy-authoring/first-batch" + name[len(old_batch):])
    for prefix in ("benchmark/tasks/", "benchmark/material/draftbench/tasks/"):
        if name.startswith(prefix):
            tail = name[len(prefix):]
            identity = tail.split("/", 1)[0]
            if identity.startswith(("v2-", "v3-")):
                target = f"{DRAFT_BATCHES}/{identity[:2]}-01/tasks/{tail}"
            elif identity == "r01-spec-acquisition":
                target = f"{DRAFT_BATCHES}/r01-sampling-01/tasks/{tail}"
            else:
                target = f"{HISTORY_TASKS}/{tail}"
            return Path(repo) / target
    for old, new in sorted(RELOCATIONS.items(), key=lambda pair: len(pair[0]), reverse=True):
        if name == old or name.startswith(old + "/"):
            return Path(repo) / (new + name[len(old):])
    return Path(repo) / name


def historical_name(relative_path):
    """Keep the original key when comparing bytes with a frozen identity manifest."""
    name = str(relative_path)
    if name.startswith(DRAFT_BATCHES + "/"):
        parts = name[len(DRAFT_BATCHES) + 1:].split("/", 2)
        if len(parts) == 3 and parts[1] == "tasks":
            historical = "benchmark/tasks/" + parts[2]
            # Only invert a known relocation. Newly authored batches/tasks
            # keep their current key; they had no old manifest identity.
            if material_path(Path(), historical) == Path(name):
                return historical
        return name
    if name.startswith(HISTORY_TASKS + "/"):
        return "benchmark/tasks/" + name[len(HISTORY_TASKS) + 1:]
    for old, new in sorted(RELOCATIONS.items(), key=lambda pair: len(pair[1]), reverse=True):
        if name == new or name.startswith(new + "/"):
            return old + name[len(new):]
    return name
