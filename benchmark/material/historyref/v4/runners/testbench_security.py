from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


_INCLUDE_RE = re.compile(r"\b(?:ahdl_include|include)\s+[\"']([^\"']+)[\"']", re.IGNORECASE)
_MODULE_RE = re.compile(r"\bmodule\s+[A-Za-z_][A-Za-z0-9_$]*", re.IGNORECASE)
_INSTANCE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*"
    r"([A-Za-z_][A-Za-z0-9_$]*)\b(.*)$",
    re.IGNORECASE,
)
_TRAN_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_$]*)\s+tran\b(.*)$", re.IGNORECASE)
_SAVE_RE = re.compile(r"^\s*save\s+(.+)$", re.IGNORECASE)
_SOURCE_KINDS = {
    "vsource",
    "isource",
    "bsource",
    "vcvs",
    "vccs",
    "cccs",
    "ccvs",
}
_ESCAPE_PATTERNS = {
    "process_execution": re.compile(r"\b(?:shell|system|exec|spawn|unix)\b", re.IGNORECASE),
    "network_access": re.compile(r"\b(?:socket|tcp|udp|https?|ftp|curl|wget)\b", re.IGNORECASE),
    "simulator_scripting_escape": re.compile(r"\b(?:ocean|skill|ipcBeginProcess)\b", re.IGNORECASE),
}
_SI_SCALE = {
    "": 1.0,
    "f": 1e-15,
    "p": 1e-12,
    "n": 1e-9,
    "u": 1e-6,
    "m": 1e-3,
    "k": 1e3,
    "meg": 1e6,
    "g": 1e9,
}


@dataclass(frozen=True)
class SecurityFinding:
    rule: str
    detail: str

    def render(self) -> str:
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class SecurityResult:
    valid: bool
    findings: tuple[SecurityFinding, ...]

    @property
    def diagnostics(self) -> tuple[str, ...]:
        return tuple(item.render() for item in self.findings)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    lines = []
    for raw in text.splitlines():
        line = raw.split("//", 1)[0]
        if line.lstrip().startswith("*"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _logical_lines(text: str) -> list[str]:
    logical: list[str] = []
    pending = ""
    bracket_depth = 0
    for raw in _strip_comments(text).splitlines():
        line = raw.strip()
        if not line:
            continue
        pending = f"{pending} {line}".strip()
        bracket_depth += line.count("[") + line.count("(")
        bracket_depth -= line.count("]") + line.count(")")
        continued = pending.endswith("\\")
        if continued:
            pending = pending[:-1].rstrip()
        if bracket_depth <= 0 and not continued:
            logical.append(pending)
            pending = ""
            bracket_depth = 0
    if pending:
        logical.append(pending)
    return logical


def _parse_number(token: str) -> float | None:
    match = re.fullmatch(
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z]*)",
        token.strip(),
    )
    if match is None:
        return None
    number, suffix = match.groups()
    if "e" in number.lower():
        return float(number)
    normalized = suffix.lower().removesuffix("s")
    scale = _SI_SCALE.get(normalized)
    return None if scale is None else float(number) * scale


def _allowed_includes(contract: dict[str, Any]) -> set[str]:
    supplied = contract.get("supplied_inputs") or {}
    legacy = {
        str(item["testbench_include_path"])
        for key in ("read_only_dut_artifacts", "read_only_support_artifacts")
        for item in supplied.get(key) or []
        if item.get("testbench_include_path")
    }
    if legacy:
        return legacy

    artifact_contract = contract.get("artifact_contract") or {}
    binding = contract.get("testbench_binding") or {}
    template = str(binding.get("source_path_template") or "./dut/{artifact_path}")
    result: set[str] = set()
    for file_record in artifact_contract.get("files") or []:
        artifact_path = file_record.get("path")
        if artifact_path:
            result.add(template.format(artifact_path=str(artifact_path)))
    for public_path in contract.get("supplied_support_artifacts") or []:
        relative = str(public_path).removeprefix("supplied_dut/")
        result.add(template.format(artifact_path=relative))
    return result


def _required_includes(contract: dict[str, Any]) -> set[str]:
    """Return DUT sources that must be bound, excluding optional support files."""
    supplied = contract.get("supplied_inputs") or {}
    legacy_dut = {
        str(item["testbench_include_path"])
        for item in supplied.get("read_only_dut_artifacts") or []
        if item.get("testbench_include_path")
    }
    if legacy_dut:
        return legacy_dut

    artifact_contract = contract.get("artifact_contract") or {}
    binding = contract.get("testbench_binding") or {}
    template = str(binding.get("source_path_template") or "./dut/{artifact_path}")
    return {
        template.format(artifact_path=str(file_record["path"]))
        for file_record in artifact_contract.get("files") or []
        if file_record.get("path")
    }


def _entry_modules(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    artifact_contract = contract.get("artifact_contract") or {}
    for file_record in artifact_contract.get("files") or []:
        for module in file_record.get("modules") or []:
            if module.get("role") == "entry":
                result[str(module["name"])] = module
    return result


def _public_parameter_names(contract: dict[str, Any], module_name: str) -> set[str]:
    module = _entry_modules(contract).get(module_name)
    if module is None:
        return set()
    return {str(item["name"]) for item in module.get("parameters") or [] if item.get("name")}


def _declared_bindings(contract: dict[str, Any]) -> list[dict[str, Any]]:
    legacy = list((contract.get("supplied_inputs") or {}).get("dut_instances") or [])
    if legacy:
        return legacy
    return list((contract.get("testbench_binding") or {}).get("instances") or [])


def _public_output_nets(contract: dict[str, Any]) -> set[str]:
    modules = _entry_modules(contract)
    outputs: set[str] = set()
    for binding in _declared_bindings(contract):
        if binding.get("public_output_nets"):
            outputs.update(str(item).lower() for item in binding["public_output_nets"])
            continue
        module = modules.get(str(binding.get("module_ref") or ""))
        if module is None:
            continue
        directions = {str(port["name"]): str(port.get("direction") or "") for port in module.get("ports") or []}
        for connection in binding.get("connections") or []:
            if directions.get(str(connection.get("port_ref") or "")) == "output":
                outputs.add(str(connection.get("net") or "").lower())
    return outputs


def _binding_signature(
    binding: dict[str, Any]
) -> tuple[str, str, tuple[str, ...], tuple[tuple[str, str], ...]]:
    ordered_nets = binding.get("ordered_nets")
    if ordered_nets is None:
        connections = sorted(binding.get("connections") or [], key=lambda item: int(item.get("position", 0)))
        ordered_nets = [str(item.get("net") or "") for item in connections]
    return (
        str(binding.get("name") or ""),
        str(binding.get("module_ref") or "").lower(),
        tuple(str(item) for item in ordered_nets),
        tuple(
            sorted(
                (str(name), str(value))
                for name, value in (binding.get("parameter_overrides") or {}).items()
            )
        ),
    )


def _instance_parameters(text: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (match.group(1), match.group(2))
            for match in re.finditer(
                r"\b([A-Za-z_][A-Za-z0-9_$]*)\s*=\s*([^\s]+)", text
            )
        )
    )


def _expand_signal(name: str) -> set[str]:
    match = re.fullmatch(r"(.+)\[(\d+):(\d+)\]", name)
    if match is None:
        return {name.lower()}
    base, first, last = match.groups()
    start = int(first)
    stop = int(last)
    step = -1 if start > stop else 1
    return {f"{base}{index}".lower() for index in range(start, stop + step, step)}


def _is_zero_current_anchor(kind: str, line: str) -> bool:
    """A literal zero-DC current source observes a node without driving it."""
    if kind.lower() != "isource":
        return False
    match = re.search(r"\bdc\s*=\s*([^\s]+)", line, re.IGNORECASE)
    value = _parse_number(match.group(1)) if match else None
    return value == 0.0 and not re.search(r"\b(?:type|wave|ampl|mag)\s*=", line, re.IGNORECASE)


def validate_testbench(
    candidate: Path,
    contract: dict[str, Any],
    policy: dict[str, Any],
) -> SecurityResult:
    findings: list[SecurityFinding] = []
    try:
        candidate_size = candidate.stat().st_size
    except OSError as exc:
        return SecurityResult(False, (SecurityFinding("candidate_read", type(exc).__name__),))
    max_candidate_bytes = int((policy.get("limits") or {}).get("max_candidate_bytes", 1_000_000))
    if candidate_size > max_candidate_bytes:
        findings.append(SecurityFinding("unbounded_resource_use", "candidate bytes exceed the public limit"))
    try:
        text = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return SecurityResult(False, (SecurityFinding("candidate_read", type(exc).__name__),))
    if candidate.is_symlink():
        findings.append(SecurityFinding("candidate_symlink", "candidate artifact must be a regular file"))

    allowed = _allowed_includes(contract)
    if "allowed_include_paths" in policy:
        policy_allowed = set(str(item) for item in policy.get("allowed_include_paths") or [])
    else:
        policy_allowed = allowed
    if policy_allowed != allowed:
        findings.append(SecurityFinding("security_policy_integrity", "allowed include projection differs from contract"))
    includes = _INCLUDE_RE.findall(_strip_comments(text))
    for include in includes:
        path = PurePosixPath(include)
        if path.is_absolute():
            findings.append(SecurityFinding("absolute_path", "absolute include paths are forbidden"))
        if ".." in path.parts:
            findings.append(SecurityFinding("path_traversal", "parent traversal is forbidden"))
        if include not in allowed:
            findings.append(SecurityFinding("undeclared_include", f"include is not declared: {include}"))
    missing_includes = sorted(_required_includes(contract) - set(includes))
    if missing_includes:
        findings.append(SecurityFinding("declared_dut_binding", "missing declared DUT include(s)"))
    if len(includes) != len(set(includes)):
        findings.append(SecurityFinding("declared_dut_binding", "duplicate DUT include is forbidden"))

    cleaned = _strip_comments(text)
    if _MODULE_RE.search(cleaned) or re.search(r"simulator\s+lang\s*=\s*(?:veriloga|ahdl)", cleaned, re.IGNORECASE):
        findings.append(SecurityFinding("dut_redefinition", "candidate may not define Verilog-A modules"))
    for rule, pattern in _ESCAPE_PATTERNS.items():
        if pattern.search(cleaned):
            findings.append(SecurityFinding(rule, "forbidden simulator escape token"))

    logical = _logical_lines(text)
    instances: list[tuple[str, str, tuple[str, ...], tuple[tuple[str, str], ...]]] = []
    output_nets = _public_output_nets(contract)
    tran_lines: list[str] = []
    saved: set[str] = set()
    for line in logical:
        match = _INSTANCE_RE.match(line)
        if match:
            name, node_text, kind, trailing = match.groups()
            nodes = tuple(token for token in re.split(r"[\s,]+", node_text.strip()) if token)
            instances.append((name, kind.lower(), nodes, _instance_parameters(trailing)))
            if (
                kind.lower() in _SOURCE_KINDS
                and output_nets.intersection(node.lower() for node in nodes)
                and not _is_zero_current_anchor(kind, line)
            ):
                findings.append(SecurityFinding("direct_dut_output_drive", f"source {name} drives a DUT output"))
        tran = _TRAN_RE.match(line)
        if tran:
            tran_lines.append(tran.group(2))
        save = _SAVE_RE.match(line)
        if save:
            for token in re.split(r"[\s,]+", save.group(1).strip()):
                if not token:
                    continue
                if any(marker in token for marker in (".", ":", "/", "@")):
                    findings.append(SecurityFinding("private_hierarchical_probe", "hierarchical save target is forbidden"))
                saved.update(_expand_signal(token))

    expected_bindings = [_binding_signature(item) for item in _declared_bindings(contract)]
    entry_modules = {name.lower() for name in _entry_modules(contract)}
    actual_bindings = [item for item in instances if item[1] in entry_modules]
    expected_base = Counter(item[:3] for item in expected_bindings)
    actual_base = Counter(item[:3] for item in actual_bindings)
    parameters_valid = True
    if expected_base == actual_base:
        expected_parameters = {item[:3]: item[3] for item in expected_bindings}
        for name, module_name, nodes, parameters in actual_bindings:
            parameter_names = [parameter_name for parameter_name, _value in parameters]
            if len(parameter_names) != len(set(parameter_names)):
                parameters_valid = False
                break
            required = dict(expected_parameters[(name, module_name, nodes)])
            actual = dict(parameters)
            if any(actual.get(key) != value for key, value in required.items()):
                parameters_valid = False
                break
            public_names = _public_parameter_names(contract, module_name)
            if set(actual) - set(required) - public_names:
                parameters_valid = False
                break
    if expected_base != actual_base or not parameters_valid:
        findings.append(SecurityFinding("declared_dut_binding", "DUT instance name, module, or ordered terminals differ"))

    if not tran_lines:
        findings.append(SecurityFinding("transient_analysis", "one bounded transient analysis is required"))
    limits = policy.get("limits") or {}
    max_stop = float(limits.get("max_stop_time_s", 1.0))
    for args in tran_lines:
        match = re.search(r"\bstop\s*=\s*([^\s]+)", args, re.IGNORECASE)
        stop = _parse_number(match.group(1)) if match else None
        if stop is None or stop <= 0.0:
            findings.append(SecurityFinding("unbounded_resource_use", "transient stop must be a finite positive literal"))
        elif stop > max_stop:
            findings.append(SecurityFinding("unbounded_resource_use", "transient stop exceeds the public limit"))
    max_analyses = int(limits.get("max_analyses", 4))
    if len(tran_lines) > max_analyses:
        findings.append(SecurityFinding("unbounded_resource_use", "too many transient analyses"))

    required = {
        expanded
        for item in (contract.get("trace_contract") or {}).get("required_signals") or []
        if str(item).lower() != "time"
        for expanded in _expand_signal(str(item))
    }
    missing_saved = sorted(required - saved)
    if missing_saved:
        findings.append(SecurityFinding("all_required_public_traces", "missing required save signal(s)"))
    max_saved = int(limits.get("max_saved_signals", max(64, len(required) + 16)))
    if len(saved) > max_saved:
        findings.append(SecurityFinding("unbounded_resource_use", "saved-signal count exceeds the public limit"))

    unique = {(item.rule, item.detail): item for item in findings}
    ordered = tuple(unique[key] for key in sorted(unique))
    return SecurityResult(not ordered, ordered)
