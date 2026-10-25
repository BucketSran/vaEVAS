"""Prepare same-source Spectre inputs for these finite circuits; never execute."""

import hashlib
import json
from pathlib import Path
import re


def prepare_reference(directory, artifacts):
    directory = Path(directory)
    output = directory / "spectre-inputs"
    output.mkdir(exist_ok=False)
    models, sources = {}, {}
    for artifact in map(Path, artifacts):
        meta = json.loads((artifact / "metadata.json").read_text())
        models[meta["model_name"]] = meta
        for name, text in json.loads((artifact / "source-inputs.json").read_text()).items():
            name = Path(name).name
            if name in sources and sources[name] != text:
                raise ValueError("reference source basename collision")
            sources[name] = text
    deck = (directory / "tb.cir").read_text()
    aliases = dict(re.findall(r"(?im)^\.model\s+(\S+)\s+([a-zA-Z_][a-zA-Z0-9_]*)", deck))
    text = "simulator lang=spectre\nglobal 0\n"
    for name, source in sources.items():
        (output / name).write_text(source)
        text += 'ahdl_include "' + name + '"\n'
    text += "simulatorOptions options reltol=1e-10 vabstol=1e-13 iabstol=1e-16\n"
    in_control = False
    for line in deck.splitlines()[1:]:
        line = line.strip()
        if line.startswith(".control"):
            in_control = True
        if in_control or not line or line.startswith(("*", ".model", ".options", ".end")):
            continue
        if line.startswith(".save"):
            nodes = re.findall(r"v\(([^)]+)\)", line)
            text += "save " + " ".join(nodes) + "\n"
            continue
        if line.startswith(".tran"):
            tokens = line.split()
            text += f"tran tran stop={tokens[2]} maxstep={tokens[4]} errpreset=conservative\n"
            continue
        kind = line[0].lower()
        if kind == "a":
            refs = re.findall(r"%vd\((\S+)\s+(\S+)\)", line)
            tokens = re.sub(r"%vd\((\S+)\s+(\S+)\)", r"\1", line).split()
            meta = models[aliases[tokens[-1]]]
            pins = tokens[1:-1]
            if len(pins) != len(meta["ports"]):
                raise ValueError("reference VA pin count differs")
            connection = dict(zip(meta["ports"], pins))
            for port, reference in meta.get("output_references", {}).items():
                if reference != "0" and (connection[port], connection[reference]) not in refs:
                    raise ValueError("reference VA connection differs from differential model")
            parameters = " ".join(k + "=" + repr(v) for k, v in meta["parameters"].items())
            text += "x" + tokens[0][1:] + " (" + " ".join(pins) + ") " + meta["module"] + " " + parameters + "\n"
            continue
        tokens = line.split()
        if kind in ("r", "c"):
            primitive, parameter = ("resistor", "r") if kind == "r" else ("capacitor", "c")
            text += f"{tokens[0]} ({tokens[1]} {tokens[2]}) {primitive} {parameter}={tokens[3]}\n"
        elif kind == "v":
            match = re.fullmatch(r"(\S+)\s+(\S+)\s+(\S+)\s+(.+)", line)
            name, positive, negative, source = match.groups()
            text += f"{name} ({positive} {negative}) vsource "
            if source.lower().startswith("pulse("):
                values = source[6:-1].split()
                if len(values) != 7:
                    raise ValueError("pulse source shape outside reference preparer")
                text += "type=pulse " + " ".join(k + "=" + v for k, v in zip(
                    ("val0", "val1", "delay", "rise", "fall", "width", "period"), values))
            elif source.lower().startswith("pwl("):
                text += "type=pwl wave=[" + source[4:-1] + "]"
            else:
                text += "type=dc dc=" + source
            text += "\n"
        elif kind == "e" and len(tokens) == 6:
            text += tokens[0] + " (" + " ".join(tokens[1:5]) + ") vcvs gain=" + tokens[5] + "\n"
        else:
            raise ValueError("unhandled circuit line: " + line)
    (output / "tb.scs").write_text(text)
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in output.iterdir() if p.is_file()}
    (output / "preparation.json").write_text(json.dumps({
        "status": "prepared_not_executed", "native_syntax_validation": "pending authorized Spectre run",
        "same_source": True, "requested_reltol": 1e-10, "requested_vabstol": 1e-13,
        "requested_iabstol": 1e-16, "effective_settings": None, "files": files,
        "new_spectre_runs": 0, "command_after_authorization": "spectre tb.scs -format psfascii +log spectre.log"}, indent=2) + "\n")
    return output
