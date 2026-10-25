"""Native XSPICE build with an explicit, matching ngspice47 SDK.

The small subprocess probe validates a compiled model before exposing its final
library. Circuit execution/job orchestration remains with the circuit harness.
"""

from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

from ..errors import CompileError
from ..lint import decode_input, read_input_bytes


def _sha(path):
    return hashlib.sha256(read_input_bytes(path, "input_io")).hexdigest()


def _json(path):
    return json.loads(decode_input(read_input_bytes(path, "input_io"), "input_error"))


def _fail(message, code="xspice_toolchain"):
    raise CompileError(message, code=code)


def _tool(value, name):
    if not isinstance(value, str) or not value:
        _fail("SDK requires " + name)
    result = shutil.which(value)
    if not result or not Path(result).is_file():
        _fail("SDK executable unavailable: " + name)
    return Path(result).resolve()


def _sdk(config):
    if not isinstance(config, dict) or set(config) - {
        "sdk_version",
        "source_tree",
        "ngspice",
        "cc",
        "defines",
    }:
        _fail("SDK must contain only sdk_version, source_tree, ngspice, cc and defines")
    if type(config.get("sdk_version")) is not int or config.get("sdk_version") != 1:
        _fail("SDK requires sdk_version=1")
    tree = config.get("source_tree")
    if not isinstance(tree, str) or not Path(tree).is_absolute():
        _fail("SDK source_tree must be an absolute configured ngspice47 source path")
    tree = Path(tree).resolve()
    ng = _tool(config.get("ngspice"), "ngspice")
    cc = _tool(config.get("cc", "cc"), "cc")
    defines = config.get("defines", [])
    if (
        not isinstance(defines, list)
        or any(
            not isinstance(x, str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]*(?:=[0-9]+)?", x)
            for x in defines
        )
        or len(set(defines)) != len(defines)
    ):
        _fail("SDK defines must be distinct C macro names with optional integer values")
    required = [
        tree / "src/xspice/cmpp/cmpp",
        tree / "src/xspice/icm/dlmain.c",
        tree / "src/include/ngspice/cm.h",
        tree / "src/include/ngspice/config.h",
    ]
    if any(not p.is_file() for p in required) or not os.access(required[0], os.X_OK):
        _fail("SDK needs configured headers, executable cmpp and dlmain.c")
    if not re.search(r'^#define PACKAGE_VERSION "47"$', required[-1].read_text(), re.M):
        _fail("this backend is qualified only for the ngspice47 SDK")
    if sys.platform not in ("darwin", "linux"):
        _fail("native XSPICE build supports macOS/Linux only")
    try:
        version = subprocess.run(
            [str(ng), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        cc_version = subprocess.run(
            [str(cc), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as e:
        _fail("tool identity query failed: " + str(e))
    if not re.search(r"ngspice-47\b", version.stdout):
        _fail("the selected ngspice binary must report ngspice-47")
    return tree, ng, cc, defines, version.stdout, cc_version.stdout


def build_model(artifact, sdk, output=None):
    """Build an immutable source artifact and return a ready library receipt.

    SDK ``defines`` must match the selected binary's build configuration,
    including CIDER/WITH_PSS when applicable. They are never inferred from the
    operating system. A bounded DC/transient subprocess checks the actual ABI.
    ``output`` defaults to a new ``artifact/native`` directory.
    """
    artifact = Path(artifact).resolve()
    manifest = _json(artifact / "manifest.json")
    if manifest.get("artifact_version") != 1 or not isinstance(
        manifest.get("files"), dict
    ):
        _fail("unknown XSPICE source artifact version")
    required = {
        "cfunc.mod",
        "ifspec.ifs",
        "metadata.json",
        "ir.json",
        "source-inputs.json",
        "model.inc",
        "instance.cir",
    }
    if set(manifest["files"]) != required:
        _fail("source artifact manifest has an unexpected file set")
    for name, h in manifest["files"].items():
        if _sha(artifact / name) != h:
            _fail("source artifact changed after compilation: " + name)
    meta = _json(artifact / "metadata.json")
    tree, ng, cc, defines, ng_version, cc_version = _sdk(sdk)
    output = Path(output).resolve() if output is not None else artifact / "native"
    output.mkdir(parents=True, exist_ok=False)
    commands = []
    start = time.monotonic()
    receipt = {
        "status": "building",
        "artifact": str(artifact),
        "artifact_manifest_sha256": _sha(artifact / "manifest.json"),
        "sdk": dict(sdk),
        "ngspice": str(ng),
        "ngspice_sha256": _sha(ng),
        "ngspice_version": ng_version,
        "compiler": str(cc),
        "compiler_sha256": _sha(cc),
        "compiler_version": cc_version,
        "commands": commands,
        "sdk_files": {
            str(p.relative_to(tree)): _sha(p)
            for p in sorted((tree / "src/include/ngspice").rglob("*.h"))
        },
    }
    receipt["sdk_files"].update(
        {
            str(p.relative_to(tree)): _sha(p)
            for p in (tree / "src/xspice/cmpp/cmpp", tree / "src/xspice/icm/dlmain.c")
        }
    )

    def run(argv, cwd, label, timeout=30):
        argv = list(map(str, argv))
        log = output / (label + ".log")
        commands.append(
            {"argv": argv, "cwd": str(cwd), "timeout_s": timeout, "log": log.name}
        )
        with log.open("x") as stream:
            try:
                p = subprocess.run(
                    argv,
                    cwd=cwd,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    env=dict(os.environ, OMP_NUM_THREADS="1"),
                )
            except subprocess.TimeoutExpired:
                _fail(label + " timed out; see " + str(log), "xspice_build")
            if p.returncode:
                _fail(
                    label
                    + " failed with exit "
                    + str(p.returncode)
                    + "; see "
                    + str(log),
                    "xspice_build",
                )

    try:
        model = output / "model"
        model.mkdir()
        for name in ("cfunc.mod", "ifspec.ifs"):
            shutil.copy2(artifact / name, model / name)
        cmpp = tree / "src/xspice/cmpp/cmpp"
        run([cmpp, "-ifs"], model, "cmpp-interface")
        # ngspice47 cmpp serializes real defaults with %e (six decimals).
        # Restore the already verified specialized binary64 values before C
        # compilation, preserving both generated versions and their identities.
        generated = model / "ifspec.c"
        original = generated.read_text()
        shutil.copy2(generated, model / "ifspec.cmpp.c")
        text, restored = original, {}
        for name, value in meta["parameters"].items():
            pattern = (r"(static union Mif_Parse_Value\s+" + re.escape(name)
                       + r"_default\[\]\s*=\s*\{\s*\{\s*\.rvalue\s*=\s*)([-+0-9.eE]+)")
            matches = list(re.finditer(pattern, text))
            if len(matches) != 1:
                _fail("cmpp real default declaration differs: " + name, "xspice_build")
            previous = matches[0].group(2)
            text = re.sub(pattern, lambda m: m.group(1) + repr(float(value)), text)
            restored[name] = {"cmpp": previous, "specialized": repr(float(value))}
        generated.write_text(text)
        receipt["real_default_precision"] = {"cmpp_sha256": _sha(model / "ifspec.cmpp.c"),
            "compiled_sha256": _sha(generated), "parameters": restored}
        run([cmpp, "-mod"], model, "cmpp-model")
        (output / "modpath.lst").write_text("model\n")
        (output / "udnpath.lst").write_text("")
        run([cmpp, "-lst"], output, "cmpp-lists")
        objects = []
        for i, source in enumerate(
            (model / "ifspec.c", model / "cfunc.c", tree / "src/xspice/icm/dlmain.c")
        ):
            obj = output / (source.stem + ".o")
            run(
                [
                    cc,
                    "-fPIC",
                    "-O2",
                    "-fvisibility=hidden",
                    *("-D" + x for x in defines),
                    "-I" + str(tree / "src/include"),
                    "-I" + str(output),
                    "-I" + str(model),
                    "-c",
                    source,
                    "-o",
                    obj,
                ],
                output,
                "compile-" + str(i),
            )
            objects.append(obj)
        candidate = output / "candidate.cm"
        flags = (
            ["-dynamiclib", "-undefined", "dynamic_lookup"]
            if sys.platform == "darwin"
            else ["-shared"]
        )
        run([cc, *flags, *objects, "-o", candidate], output, "link")
        # Sources and host binary were verified before loading; a mismatch/crash
        # is contained in this child process, not the Python/compiler process.
        probe = output / "abi-probe"
        probe.mkdir()

        def startup(path):
            text = str(path)
            if any(c in text for c in ("\n", "\r", '"')):
                _fail("library path cannot contain quotes or newlines")
            return "codemodel " + text + "\n"

        (probe / ".spiceinit").write_text(startup(Path("../candidate.cm")))
        ir = _json(artifact / "ir.json")
        limits = [1e-9]
        limits.extend(
            e["trigger"]["start"] / 8
            for e in ir["events"]
            if e["trigger"]["kind"] == "timer" and e["trigger"]["start"] > 0
        )
        stop = min(limits)
        if not math.isfinite(stop) or stop <= 0:
            _fail("ABI probe time scale is unrepresentable")
        inputs = [p for p in meta["ports"] if meta["directions"][p] == "input"]
        text = "EVAS XSPICE ABI probe\n" + "".join(
            "v" + str(i) + " " + p + " 0 0\n" for i, p in enumerate(inputs)
        )
        text += (
            (artifact / "model.inc").read_text()
            + "a_probe "
            + " ".join(meta.get("instance_connections", meta["ports"]))
            + " "
            + meta["model_name"]
            + "\n"
        )
        text += f".tran {stop / 10} {stop} 0 {stop / 10}\n.control\nrun\nquit\n.endc\n.end\n"
        (probe / "probe.cir").write_text(text)
        run([ng, "-b", "probe.cir"], probe, "abi-probe", timeout=10)
        probe_log = (output / "abi-probe.log").read_text()
        if (
            "No. of Data Rows" not in probe_log
            or "Error" in probe_log
            or "fatal error" in probe_log.lower()
        ):
            _fail(
                "ABI/transient probe did not complete; see "
                + str(output / "abi-probe.log"),
                "xspice_build",
            )
        library = output / (meta["model_name"] + ".cm")
        candidate.rename(library)
        for name in ("model.inc", "instance.cir"):
            shutil.copy2(artifact / name, output / name)
        (output / ".spiceinit").write_text(startup(Path(library.name)))
        receipt.update(
            status="ready",
            library=str(library),
            library_sha256=_sha(library),
            startup_file=str(output / ".spiceinit"),
            model_include=str(output / "model.inc"),
            abi_probe_passed=True,
            wall_s=time.monotonic() - start,
        )
    except (CompileError, OSError) as e:
        receipt.update(status="failed", error=str(e), wall_s=time.monotonic() - start)
        (output / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
        raise
    (output / "build.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
