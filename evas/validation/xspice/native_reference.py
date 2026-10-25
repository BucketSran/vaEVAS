"""Admit coherent successful native Spectre records before grading waveforms."""

import hashlib
import json
from pathlib import Path
import re


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_reference(directory, source, deck):
    d = Path(directory)
    if (d / "sample_hold.va").read_bytes() != source or (
        d / "tb.scs"
    ).read_text() != deck:
        raise ValueError("native Spectre physical input differs: " + str(d))
    result = json.loads((d / "result.json").read_text())
    if (
        type(result.get("exit_code")) is not int
        or result["exit_code"] != 0
        or result.get("timed_out") is not False
    ):
        raise ValueError("native Spectre process did not succeed: " + str(d))
    log = (d / "spectre.log").read_text()
    version = re.search(r"^Version ([^\s]+)", log, re.M)
    if (
        not version
        or "Spectre (R) Circuit Simulator" not in log
        or not re.search(r"^spectre completes with 0 errors,", log, re.M)
        or "Total time required for tran analysis" not in log
    ):
        raise ValueError(
            "native Spectre completion/version evidence missing: " + str(d)
        )
    started = json.loads((d / "STARTED.json").read_text())
    if started.get("netlist_sha256") != sha(d / "tb.scs") or started.get(
        "va_sha256"
    ) != sha(d / "sample_hold.va"):
        raise ValueError(
            "native Spectre execution inputs do not match STARTED receipt: " + str(d)
        )
    tool = d.parent.parent / "TOOL_IDENTITY.json"
    identity = json.loads(tool.read_text())
    if not isinstance(identity.get("spectre_sha256"), str) or not re.fullmatch(
        "[0-9a-f]{64}", identity["spectre_sha256"]
    ):
        raise ValueError("native Spectre tool identity missing: " + str(d))
    raw = d / "psf/tran.tran.tran"
    if not raw.is_file() or raw.stat().st_size == 0:
        raise ValueError("native Spectre waveform missing: " + str(d))
    return {
        "path": str(d),
        "version": version.group(1),
        "spectre_binary_sha256": identity["spectre_sha256"],
        "tool_identity_sha256": sha(tool),
        "va_sha256": sha(d / "sample_hold.va"),
        "deck_sha256": sha(d / "tb.scs"),
        "wave_sha256": sha(raw),
        "log_sha256": sha(d / "spectre.log"),
        "result_sha256": sha(d / "result.json"),
        "started_sha256": sha(d / "STARTED.json"),
    }
