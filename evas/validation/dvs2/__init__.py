"""Shared DVS conditions and independent scientific checks."""
from pathlib import Path
from .cases import T, PROFILES, conditions, v1
from .checker import check


def source_files(repo):
    """Enumerate the scientific source closure for a caller's frozen identity."""
    directory = Path(repo)/'evas/validation/dvs2'
    if not (directory/'__init__.py').is_file():
        raise ValueError('shared DVS science sources missing')
    return tuple(sorted(directory.glob('*.py')))
