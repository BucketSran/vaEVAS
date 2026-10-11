"""Local, fail-closed open-backend evidence adapter; never edits execution evidence.

An approved proof digest is a caller-owned review trust boundary, not a boolean
inside an untrusted receipt. Approve it only after the independent reviews. All
manifest digests below must come from the verified frozen/raw manifests, not be
computed from the candidate work directory by the caller. Qualification covers
export origin and solver controls; callback ordering and scientific grading stay
with their existing checkers.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "experiments/backends/paper"))
from settings_readback import ngspice, gnucap, ReadbackError

PINS = {
    "openvaf_r_ngspice": {
        "image": "sha256:233b15bcc2bdfd40c915dbf6ed41d731306f64083885d1255ae1bdd37cdcb555",
        "image_key": "ngspice", "exe": "/opt/ngspice/bin/ngspice", "deck": "tb.cir",
        "compiled": "dut.osdi", "mapping": "ngspice-explicit-tmax-v1",
        "binaries": {"/opt/ngspice/bin/ngspice": "e9b0e776ac656de5e470f6b339c4a7254c961d77714b4b94f4b71be2422e7b46"}},
    "gnucap_modelgen": {
        "image": "sha256:6a094609a9dbe4e6e535625807569a212d681ecf6a66fa5d532344f10121a698",
        "image_key": "gnucap", "exe": "/opt/gnucap/bin/gnucap", "deck": "tb.gc",
        "compiled": "dut.so", "mapping": "gnucap-time-ticks-v1",
        "binaries": {"/opt/gnucap/bin/gnucap": "cc96c5fca3772f20cd143c38105aa05d97af5bcd661b066bd3abc2d0ece41478",
                     "/opt/gnucap/lib/libgnucap.so": "7f1028e75e073eb601e29f68bf9cb84495d90f3e9f15f3ff136ad286ff36ab34",
                     "/opt/gnucap/lib/gnucap/gnucap-default-plugins.so": "ec6f8f74661378c61d801ee9b1cf5c74bd078d9acdc84dde25517e617f8df0c8"}}}
INPUTS = ("dut.va", "condition.json", "requested_settings.json", "requested_times.json", "observation_plan.json")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class EvidenceSchemaError(ValueError):
    """Malformed evidence data, as distinct from an adapter implementation error."""


def object_value(value, name):
    if not isinstance(value, dict):
        raise EvidenceSchemaError(name + " must be a JSON object")
    return value


def load(path):
    try:
        value = json.loads(Path(path).read_text())
    except json.JSONDecodeError as exc:
        raise EvidenceSchemaError(Path(path).name + " is not valid JSON") from exc
    return object_value(value, Path(path).name)


def gate(issues, **facts):
    return {"status": "unknown" if issues else "qualified", "issues": list(issues), **facts}


def positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def safe_file(root, name):
    p = (Path(root) / name).resolve()
    if not p.is_relative_to(Path(root).resolve()) or not p.is_file():
        raise ValueError("missing or escaping artifact: " + name)
    return p


def verify_files(root, names, manifest):
    object_value(manifest, "trusted manifest")
    for name in names:
        if not re.fullmatch(r"[0-9a-f]{64}", str(manifest.get(name, ""))):
            raise ValueError("missing trusted manifest digest: " + name)
        if sha(safe_file(root, name)) != manifest[name]:
            raise ValueError("artifact identity mismatch: " + name)


def proof_bundle(path, root, backend, approved_digest):
    """Validate retrievable evidence; caller supplies the reviewed bundle SHA."""
    if not approved_digest or sha(path) != approved_digest:
        raise ValueError("proof bundle is not approved at its exact digest")
    proof = load(path); pin = PINS[backend]
    if proof.get("schema") != "open-backend-proof-v1" or proof.get("backend") != backend:
        raise ValueError("wrong proof schema/backend")
    if proof.get("image_id") != pin["image"] or proof.get("binary_hashes") != pin["binaries"]:
        raise ValueError("proof installed identity mismatch")
    argv_digests = proof.get("argv_sha256")
    if not isinstance(argv_digests, list) or not argv_digests or any(
            not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for digest in argv_digests):
        raise EvidenceSchemaError("proof argv_sha256 must be a nonempty list of lowercase 64-hex digests")
    attachments = object_value(proof.get("attachments", {}), "proof attachments")
    if not attachments:
        raise ValueError("proof has no retrievable attachments")
    verify_files(root, attachments, attachments)
    reviews = object_value(proof.get("reviews", {}), "proof reviews")
    if set(reviews) != {"astra", "glm"}:
        raise ValueError("both independent review attachments are required")
    for review in reviews.values():
        object_value(review, "individual proof review")
        if not isinstance(review.get("path"), str) or review.get("path") not in attachments:
            raise ValueError("review attachment absent")
        if review.get("sha256") != attachments[review["path"]]:
            raise ValueError("review attachment digest mismatch")
    if len({r["path"] for r in reviews.values()}) != 2 or len({r["sha256"] for r in reviews.values()}) != 2:
        raise ValueError("independent review reports must have distinct paths and digests")
    return proof


def gc_number(token):
    m = re.fullmatch(r"([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)([a-zA-Z]*)", token)
    if not m:
        raise ValueError("unknown Gnucap numeric token: " + token)
    scales = {"": 1, "f": 1e-15, "p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "K": 1e3, "G": 1e9}
    if m[2] not in scales:
        raise ValueError("unknown Gnucap numeric suffix")
    value = float(m[1]) * scales[m[2]]
    if not positive(value):
        raise ValueError("invalid Gnucap numeric setting")
    return value


def gc_options(log, key):
    tokens = re.findall(r"\b" + re.escape(key) + r"=\s*(\S+)", log)
    values = [gc_number(t) for t in tokens]
    if not values or any(v != values[0] for v in values):
        raise ValueError("missing/conflicting Gnucap setting " + key)
    return values[0]


NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
NAME = r"[A-Za-z_][A-Za-z0-9_]*"


def source_lines(lines, *, continued=False):
    """Consume only complete voltage sources; '+' belongs to an open PWL."""
    count = 0
    while lines and lines[0].startswith("V"):
        line = lines.pop(0)
        if continued and "PWL(" in line:
            while ")" not in line and lines and lines[0].startswith("+"):
                line += " " + lines.pop(0)[1:].strip()
        match = re.fullmatch(r"V" + NAME + r"\s+" + NAME + r"\s+0\s+(?:PWL\(\s*(.*?)\s*\)|(" + NUMBER + r"))", line)
        if not match:
            raise ValueError("unreviewed voltage source or continuation")
        if match[1] is not None:
            tokens = match[1].split()
            if len(tokens) < 2 or len(tokens) % 2 or any(not re.fullmatch(NUMBER, t) for t in tokens):
                raise ValueError("PWL continuation must contain only numeric pairs")
            values = [float(t) for t in tokens]
            times = values[::2]
            if not all(math.isfinite(v) for v in values) or times[0] < 0 or any(b < a for a, b in zip(times, times[1:])):
                raise ValueError("invalid PWL source data")
        elif not math.isfinite(float(match[2])):
            raise ValueError("invalid DC source")
        count += 1
    if count == 0:
        raise ValueError("missing source block")
    return lines


def control_block(deck, backend):
    """Validate every noncomment line before consuming approved mechanism facts."""
    lines = [l.strip() for l in deck.splitlines() if l.strip() and not l.lstrip().startswith("*")]
    if backend == "openvaf_r_ngspice":
        if not lines or not re.fullmatch(r"Paper [\w-]+", lines.pop(0)):
            raise ValueError("wrong NG title")
        source_lines(lines)
        if not lines or not re.fullmatch(r"N0(?: " + NAME + r")+ model0", lines.pop(0)):
            raise ValueError("wrong NG instance")
        model = lines.pop(0) if lines else ""
        if not re.fullmatch(r"\.model model0 " + NAME + r"(?: " + NAME + r"=" + NUMBER + r")*", model):
            raise ValueError("unreviewed NG model")
        if not lines or not lines.pop(0).startswith(".options "):
            raise ValueError("missing NG options")
        if len(lines) != 13 or lines[0] != ".control" or lines[-2:] != [".endc", ".end"]:
            raise ValueError("unreviewed NG whole deck grammar")
        commands = lines[1:-2]
        setup = ["pre_osdi dut.osdi", "set filetype=ascii", "set wr_singlescale", "set wr_vecnames", "set numdgt=17", "option"]
        if commands[:6] != setup or commands[8:] != ["option", "quit"]:
            raise ValueError("unreviewed NG setup/load/control command")
        if not re.fullmatch(r"wrdata waveform\.txt(?: v\(" + NAME + r"\))+", commands[7]):
            raise ValueError("unreviewed NG export vector expression")
        tokens = commands[6].split()
        if not tokens or tokens[0] != "tran":
            raise ValueError("missing NG transient")
    else:
        if len(lines) < 5 or lines[:3] != ["load mgsim", "load ./dut.so", "verilog"] or lines[4] != "spice":
            raise ValueError("wrong GN language/plugin preamble")
        parameter = r"\." + NAME + r"\(" + NUMBER + r"\)"
        instance = r"\\" + NAME + r"(?: #\(" + parameter + r"(?:, " + parameter + r")*\))? dut\(" + NAME + r"(?:," + NAME + r")*\);"
        if not re.fullmatch(instance, lines[3]):
            raise ValueError("unreviewed GN module/parameter binding")
        allowed = source_lines(lines[5:], continued=True)
        if len(allowed) != 5 or not allowed[0].startswith(".options numdgt=17 method=trap dtmin=1e-16 trtol=7 dtratio=1e9 ") or allowed[1] != ".options" or allowed[4] != ".end":
            raise ValueError("wrong GN full control grammar")
        if not re.fullmatch(r"\.print tran(?: v\(" + NAME + r"\))+", allowed[2]):
            raise ValueError("unreviewed GN print expressions")
        if not re.fullmatch(r"\.tran " + NUMBER + r" " + NUMBER + r" 0 " + NUMBER + r" trace alltime > waveform\.txt", allowed[3]):
            raise ValueError("GN must be a fresh exact alltime transient")
        opts = allowed[0].split()[1:]
        parsed = dict(item.split("=", 1) for item in opts)
        if len(parsed) != len(opts) or set(parsed) != {"numdgt", "method", "dtmin", "trtol", "dtratio", "short", "reltol", "vntol", "abstol"}:
            raise ValueError("unreviewed GN options")
        if parsed["short"] != "1e-9":
            raise ValueError("unreviewed GN short option")
        tokens = allowed[3].split()[:5]
    if len(tokens) != 5 or tokens[3] != "0" or any(not re.fullmatch(NUMBER, tokens[i]) for i in (1,2,4)):
        raise ValueError("unsupported transient shape")
    step, stop, cap = map(float, (tokens[1], tokens[2], tokens[4]))
    if not all(positive(v) for v in (step, stop, cap)):
        raise ValueError("nonpositive explicit transient control")
    return {"stop_s": stop, "maxstep_s": cap}


def execution_identity(work, pin, tool, raw):
    names = ("simulate-final.json", "simulate.log", "waveform.txt", pin["compiled"], "INPUT_IDENTITY.json", "RESULT.json")
    verify_files(work, names, raw)
    result = load(work / "RESULT.json")
    if result.get("status") != "waveform_available":
        raise ValueError("execution has no complete waveform")
    expected_backend = "openvaf_r_ngspice" if pin["deck"] == "tb.cir" else "gnucap_modelgen"
    if result.get("backend") != expected_backend or result.get("label") != work.name or result.get("deck") != pin["deck"]:
        raise ValueError("RESULT execution target mismatch")
    if result.get("waveform") != "waveform.txt" or result.get("waveform_sha256") != raw["waveform.txt"]:
        raise ValueError("RESULT waveform identity mismatch")
    if object_value(result.get("compiled_artifacts", {}), "RESULT compiled_artifacts").get(pin["compiled"]) != raw[pin["compiled"]]:
        raise ValueError("RESULT loaded compiled artifact mismatch")
    execution = load(work / "simulate-final.json")
    if execution.get("status") != "completed" or execution.get("returncode") != 0 or execution.get("timeout") is not False:
        raise ValueError("simulation did not complete")
    if execution.get("log_sha256") != sha(work / "simulate.log") or object_value(execution.get("container_cleanup", {}), "execution container_cleanup").get("complete") is not True:
        raise ValueError("execution log/cleanup mismatch")
    argv = execution.get("argv", [])
    if not isinstance(argv, list) or not all(isinstance(arg, str) for arg in argv):
        raise EvidenceSchemaError("execution argv must be a list of strings")
    tail = [pin["exe"]] + (["-b"] if pin["deck"] == "tb.cir" else []) + [pin["deck"]]
    if argv[-len(tail):] != tail or argv.count(pin["image"]) != 1:
        raise ValueError("simulation command/image mismatch")
    if not all(x in argv for x in ("run", "--rm", "--read-only", "--pull=never", "--network=none")):
        raise ValueError("missing fresh fixed container controls")
    images = object_value(tool.get("images", {}), "tool images")
    image = object_value(images.get(pin["image_key"], {}), "tool backend image")
    if image.get("config_id") != pin["image"]:
        raise ValueError("tool image identity mismatch")
    return execution


def waveform_complete(path, backend, stop, log):
    """Account for every raw data line; no filtering, interpolation or trimming."""
    lines = Path(path).read_text().splitlines()
    issues = []
    if not lines or not lines[0].split() or lines[0].split()[0] != ("time" if backend == "openvaf_r_ngspice" else "#Time"):
        return gate(["unknown waveform header"])
    columns = len(lines[0].split()); times = []
    for line in lines[1:]:
        tokens = line.split()
        if len(tokens) != columns:
            return gate(["raw row/column accounting mismatch"])
        try: values = [float(t) for t in tokens]
        except ValueError: return gate(["unrecognized raw numeric row"])
        if not all(math.isfinite(v) for v in values): return gate(["nonfinite raw row"])
        times.append(values[0])
    if not times or times[0] != 0 or any(b <= a for a, b in zip(times, times[1:])):
        issues.append("incomplete or nonmonotone raw times")
    if not times or abs(times[-1] - stop) > 16 * math.ulp(stop):
        issues.append("raw end outside existing 16ulp stop boundary")
    if backend == "openvaf_r_ngspice":
        counts = re.findall(r"No\. of Data Rows\s*:\s*(\d+)", log)
        if len(counts) != 1 or int(counts[0]) != len(times): issues.append("plot/raw row mismatch")
        if not log.rstrip().endswith("ngspice-46 done"): issues.append("missing normal NG completion")
    return gate(issues, row_count=len(times))


def qualify_open_backend(work, backend, tool, frozen_manifest, raw_manifest, *, proof_path=None,
                         evidence_root=None, approved_proof_sha256=None):
    """Pure local qualification. Missing evidence is unknown, never a DUT failure.

    The approved bundle must explicitly cover the exact environment factory,
    full argv, input grammar and loaded artifacts. Each run_scopes entry binds
    argv_sha256, all six frozen_manifest digests and compiled_sha256. Broad DUT
    or integrator declarations cannot replace this binding. Its runtime/native
    claims are independent, so partial closed evidence remains useful.
    """
    work = Path(work); issues = []; output = {k: gate(["not evaluated"]) for k in ("identity", "config", "runtime", "native", "integrator", "diagnostics", "observations")}
    try:
        object_value(tool, "tool identity")
        if not isinstance(backend, str) or backend not in PINS:
            raise ValueError("unsupported backend")
        pin = PINS[backend]
        verify_files(work, (*INPUTS, pin["deck"]), frozen_manifest)
        execution = execution_identity(work, pin, tool, raw_manifest)
        identity = load(work / "INPUT_IDENTITY.json")
        for field, name in (("source_sha256", "dut.va"), ("deck_sha256", pin["deck"]), ("requested_settings_sha256", "requested_settings.json")):
            if identity.get(field) != frozen_manifest[name]:
                raise ValueError("execution input identity mismatch: " + field)
        deck = (work / pin["deck"]).read_text(); log = (work / "simulate.log").read_text()
        controls = control_block(deck, backend); requested = load(work / "requested_settings.json")
        if controls != {k: requested.get(k) for k in controls}:
            raise ValueError("requested/deck controls mismatch")
        option_lines = [l.strip() for l in deck.splitlines() if l.strip().startswith(".options ")]
        if len(option_lines) != 1:
            raise ValueError("ambiguous deck options")
        options = option_lines[0].split()[1:]
        option_values = dict(item.split("=", 1) for item in options)
        expected_keys = {"reltol", "vntol", "abstol", "method", "trtol"}
        expected_keys |= {"chgtol", "itl4"} if backend == "openvaf_r_ngspice" else {"numdgt", "dtmin", "dtratio", "short"}
        if len(options) != len(option_values) or set(option_values) != expected_keys:
            raise ValueError("unreviewed deck option set")
        for source, key in (("reltol", "reltol"), ("vntol", "vabstol_V"), ("abstol", "iabstol_A")):
            if float(option_values[source]) != requested.get(key):
                raise ValueError("requested/deck tolerance mismatch")
        if option_values["method"] != "trap" or float(option_values["trtol"]) != 7:
            raise ValueError("unreviewed method/trtol")
        if backend == "openvaf_r_ngspice" and (float(option_values["chgtol"]) != 1e-14 or float(option_values["itl4"]) != 10):
            raise ValueError("unreviewed charge/iteration setting")
        output["identity"] = gate([], artifacts={n: raw_manifest[n] for n in raw_manifest}, frozen_inputs=dict(frozen_manifest))
        bad = re.findall(r"(?im)^.*(?:did not converge|convergence failure|giving up|timestep too small|error:|^\s*\^\s*\?).*$", log)
        output["diagnostics"] = gate(bad or ["diagnostic contract not approved"], matches=bad)
        if bad:
            raise ValueError("failed simulation diagnostic")
        if backend == "openvaf_r_ngspice":
            rb = ngspice(log, deck); actual = {k: v["value"] for k, v in rb["effective"].items()}
        else:
            rb = gnucap(log, gc_number); actual = {"reltol": rb["actual"]["reltol"], "vabstol_V": rb["actual"]["vabstol"], "iabstol_A": rb["actual"]["iabstol"]}
            method = re.findall(r"\bmethod=(\S+)", log)
            if not method or set(method) != {"trap"}:
                raise ValueError("missing/conflicting method readback")
            actual["method"] = "trap"
        mismatch = ["missing/mismatched " + k for k in ("reltol", "vabstol_V", "iabstol_A")
                    if not positive(requested.get(k)) or not math.isclose(actual[k], requested[k], rel_tol=1e-12, abs_tol=0)]
        if actual["method"] != "trap": mismatch.append("wrong integration method setting")
        if backend == "gnucap_modelgen":
            for name, expected in (("dtmin", 1e-16), ("dtratio", 1e9), ("trtol", 7)):
                actual[name] = gc_options(log, name)
                if not math.isclose(actual[name], expected, rel_tol=1e-12, abs_tol=0):
                    mismatch.append("mismatched extra " + name)
        else:
            final = log.split("* Current simulation options *")[-1]
            for name, expected in (("trtol", 7), ("chgtol", 1e-14), ("itl4", 10)):
                tokens = re.findall(r"(?m)^\s*" + name + r"(?:\s+\([^)]*\))?\s*=\s*(\S+)", final)
                if len(tokens) != 1 or not math.isclose(float(tokens[0]), expected, rel_tol=1e-12, abs_tol=0):
                    mismatch.append("missing/mismatched extra " + name)
                else: actual[name] = float(tokens[0])
        output["config"] = gate(mismatch, actual=actual)
        if not proof_path or evidence_root is None:
            raise ValueError("approved fixed mechanism proof bundle unavailable")
        proof = proof_bundle(proof_path, evidence_root, backend, approved_proof_sha256)
        environment = tool.get("environment_sha256")
        if not isinstance(environment, str) or not re.fullmatch(r"[0-9a-f]{64}", environment) or proof.get("environment_sha256") != environment:
            raise ValueError("missing or mismatched environment factory digest")
        # Exact argv, including mounts/wrapper/options, is explicitly approved per run.
        argv_hash = hashlib.sha256(json.dumps(execution["argv"], separators=(",", ":")).encode()).hexdigest()
        if argv_hash not in proof.get("argv_sha256", []):
            raise ValueError("complete argv outside reviewed scope")
        expected_scope = {"argv_sha256": argv_hash,
                          "frozen_manifest": {n: frozen_manifest[n] for n in (*INPUTS, pin["deck"])},
                          "compiled_sha256": raw_manifest[pin["compiled"]]}
        scopes = proof.get("run_scopes", [])
        if not isinstance(scopes, list) or scopes.count(expected_scope) != 1:
            raise ValueError("frozen inputs/loaded artifact outside reviewed per-run scope")
        claims = object_value(proof.get("claims", {}), "proof claims")
        runtime_issues = []
        mapped = dict(controls)
        if claims.get("runtime") != pin["mapping"]: runtime_issues.append("runtime parameter path not approved")
        if backend == "gnucap_modelgen":
            dtmin_option = gc_options(log, "dtmin")
            dtratio = gc_options(log, "dtratio")
            # Fixed grammar excludes hard transient dtmin/dtratio overrides.
            # s_tr_set.cc:176-191 selects the larger soft value.
            dtmin = max(dtmin_option, controls["maxstep_s"] / dtratio)
            quotient = controls["maxstep_s"] / dtmin
            if quotient >= 2**53:
                raise ValueError("TIME_t mapping exceeds calibrated integer range")
            ticks = int(quotient + 0.5)
            mapped["maxstep_s"] = ticks * dtmin
            mapped["dtmin_s"] = dtmin
            mapped["option_dtmin_s"] = dtmin_option
            mapped["dtratio"] = dtratio
            if mapped["maxstep_s"] != requested["maxstep_s"]:
                runtime_issues.append("quantized cap differs from exact requested cap")
        output["runtime"] = gate(runtime_issues, requested=controls, mapped_effective=mapped,
            limit="parameter application; not a proof of every floating time gap or exact save cutoff")
        native_issues = []
        required = ("startup", "export", "diagnostic_contract")
        complete = waveform_complete(work / "waveform.txt", backend, controls["stop_s"], log)
        native_issues.extend(complete["issues"])
        output["observations"] = complete
        if claims.get("diagnostic_contract") == "closed":
            output["diagnostics"] = gate([])
        if re.search(r"(?im)^.*(?:warning|fatal|aborted|interrupted).*$", log):
            native_issues.append("unclassified diagnostic")
        for claim in required:
            if claims.get(claim) != "closed": native_issues.append(claim + " mechanism proof unavailable")
        if claims.get("native") != ("ngspice-noninterpolated-wrdata-v1" if backend == "openvaf_r_ngspice" else "gnucap-converged-alltime-v1"):
            native_issues.append("native origin path not approved")
        if mismatch: native_issues.append("configuration is not qualified")
        output["native"] = gate(native_issues, waveform_sha256=raw_manifest["waveform.txt"],
            limit="saved accepted/forced values; not callback time, phase or model correctness")
        output["integrator"] = gate([] if claims.get("integrator") == "closed" else ["actual device integrator path unavailable"], setting=actual["method"])
    except EvidenceSchemaError as exc:
        issues.append(str(exc))
        output = {axis: gate([str(exc)]) for axis in output}
    except (ValueError, OSError, KeyError, ReadbackError) as exc:
        issues.append(str(exc))
    output["issues"] = issues
    output["proof_sha256"] = approved_proof_sha256
    return output
