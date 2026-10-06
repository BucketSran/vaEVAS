"""Compile-only manifest preflight; no kernel discovery or execution."""
import os
from pathlib import Path
import stat

from . import CompileError, Instance, compile_sources
from .manifest import parse_manifest


def _read_text(path, io_code, input_code):
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as file:
            if not stat.S_ISREG(os.fstat(file.fileno()).st_mode):
                raise OSError(f'input must be a regular file: {path}')
            return file.read().decode('utf-8')
    except OSError as exc:
        raise CompileError(str(exc), code=io_code) from exc
    except UnicodeError as exc:
        raise CompileError(str(exc), code=input_code) from exc


def compile_manifest(path):
    """Load compilation fields and return the supported source's bound program."""
    path = Path(path)
    text = _read_text(path, 'manifest_io', 'manifest_input')
    try:
        manifest = parse_manifest(text)
    except (ValueError, KeyError, TypeError) as exc:
        raise CompileError(str(exc), code='manifest_input') from exc
    sources = {}
    for name in manifest['models']:
        source = (path.parent / name).resolve()
        sources[str(source)] = _read_text(source, 'source_io', 'source_input')
    return compile_sources(sources, [Instance(**row) for row in manifest['instances']])


def lint_manifest(path):
    """Check compilation only. Successful compilation is not execution support."""
    program = compile_manifest(path)
    program.to_dict()  # Apply the public wire-tree resource guard as compilation does.
    return dict(lint_version=1, status='lint_passed', schema_version=program.schema_version,
                checks=['manifest_structure', 'source_read', 'parameter_binding',
                        'supported_source_compilation', 'ir_resource_budget'],
                not_checked=['numerical_request_validity', 'dynamic_support',
                             'numerical_acceptance', 'external_simulator_compatibility'])
