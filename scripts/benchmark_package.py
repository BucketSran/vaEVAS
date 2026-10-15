"""Stage-specific structural checks; no execution, grading or human approval."""

import json
import math
from pathlib import Path, PurePosixPath
import re
import tomllib
from urllib.parse import unquote, urlsplit


LEVELS = ("contract", "implementation", "calibration", "accepted")
STAGE_LEVEL = {
    "source-screening": "contract", "design-draft": "contract", "deferred": "contract",
    "implementation": "implementation", "calibration": "calibration",
    "frozen": "calibration", "model-trials": "calibration",
}
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+[^)]*)?\)")
INCLUDE = re.compile(r'^\s*(?:`include|ahdl_include|include)\s+"([^"]+)"', re.M)
LEGACY_REGISTRIES = (
    "experiments/benchmark_v2/task-source-map.json",
    "experiments/benchmark_next/ota/calibration-plan.json",
    "experiments/benchmark_next/ldo/manifest.json",
    "experiments/benchmark_next/filter/manifest.json",
    "experiments/benchmark_next/calibration/manifest.json",
    "experiments/benchmark_next/converter/manifest.json",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def checked_path(root, relative, *, kind=None):
    """Check literal package files without following symlinks or escaping roots."""
    path = root / relative
    current = path
    while current != root:
        require(not current.is_symlink(), f"{path}: symlink is not a package asset")
        current = current.parent
    require(path.resolve().is_relative_to(root.resolve()), f"{path}: path escapes {root}")
    require(path.exists(), f"missing {path}")
    if kind == "file":
        require(path.is_file() and path.stat().st_size > 0, f"{path}: expected nonempty file")
    elif kind == "directory":
        require(path.is_dir(), f"{path}: expected directory")
    return path


def read_config(task):
    config = tomllib.loads(checked_path(task, "task.toml", kind="file").read_text())
    require(isinstance(config.get("metadata"), dict), f"{task}: missing metadata table")
    return config


def selected_level(config, explicit=None, *, formal=False):
    stage = config["metadata"].get("stage")
    require(stage in STAGE_LEVEL, f"metadata.stage: unknown or missing stage {stage!r}")
    inferred = "accepted" if formal else STAGE_LEVEL[stage]
    if explicit is not None:
        require(LEVELS.index(explicit) >= LEVELS.index(inferred),
                f"--stage {explicit}: cannot select a lower check level than {inferred}")
    return explicit or inferred


def legacy_task_ids(repo):
    """Reuse preserved construction identities, never infer legacy status from a new ID."""
    identities = set()

    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if (key in {"task", "task_id"} and isinstance(child, str)
                        and re.fullmatch(r"(?:benchmark/tasks/)?v[23]-[a-z0-9-]+", child)):
                    identities.add(child.rsplit("/", 1)[-1])
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for name in LEGACY_REGISTRIES:
        collect(json.loads(checked_path(repo, name, kind="file").read_text()))
    return identities


def prose(text):
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    return re.sub(r"^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text, flags=re.M | re.S)


def local_links(text, page, task, repo, *, public):
    """Resolve inline Markdown file targets; remote URLs/anchors are not fetched."""
    links = []
    starter = task / "environment/starter"
    for match in LINK.finditer(prose(text)):
        value = match[1].strip("<>")
        parsed = urlsplit(value)
        require(parsed.scheme.lower() != "file", f"{page}: file: link is not portable public material")
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        value = unquote(parsed.path)
        if value.startswith("/app/"):
            target = starter / value[5:]
        elif public and page == task / "instruction.md":
            # Relative solver links are resolved from /app, not the author directory.
            target = starter / value
        else:
            require(not Path(value).is_absolute(), f"{page}: nonportable link {value}")
            target = page.parent / value
        boundary = starter if public else repo
        require(target.resolve().is_relative_to(boundary.resolve()),
                f"{page}: link leaves {'public materials' if public else 'repository'}: {value}")
        if public:
            require(target.exists(), f"{page}: missing link in public materials: {value}")
        else:
            require(target.exists(), f"{page}: missing link {value}")
        links.append(value)
    return links


def check_instruction(task, text, artifacts):
    visible = prose(text)
    headings = re.findall(r"^##\s+(.+?)\s*$", visible, flags=re.M)
    require(headings == ["Spec", "Deliverable"],
            f"{task}/instruction.md: use Spec then Deliverable as the two main sections")
    require(not re.search(r"[\u3400-\u9fff]", text),
            f"{task}/instruction.md: solver instructions must be English")
    require(not re.search(r"(?m)^\s*<[^>]+>\s*$", visible)
            and not re.search(r"(?m)^#\s+<[^>]+>", visible),
            f"{task}/instruction.md: unresolved template placeholder")
    require(not re.search(r"(?m)^\s*module\s+\w+\s*(?:#\s*\(|\()", text),
            f"{task}/instruction.md: keep the module interface in starter source")
    deliverable = visible.split("## Deliverable", 1)[1]
    named_paths = set(re.findall(r"`([^`\n]+)`", deliverable))
    named_paths.update(unquote(urlsplit(m[1].strip("<>")).path) for m in LINK.finditer(deliverable))
    plain = LINK.sub("", re.sub(r"`[^`\n]*`", "", deliverable))
    named_paths.update(p.rstrip(".,;:") for p in re.findall(r"(?<![\w/.-])/app/[^\s`<>\"'()]+", plain))
    for artifact in artifacts:
        require(artifact in named_paths,
                f"{task}/instruction.md: Deliverable does not name {artifact}")


def check_artifacts(task, config):
    artifacts = config.get("artifacts")
    require(isinstance(artifacts, list) and artifacts,
            f"{task}/task.toml: artifacts must be a nonempty list")
    relative = []
    for value in artifacts:
        require(isinstance(value, str) and value.startswith("/app/") and value != "/app/",
                f"{task}: artifacts must be paths below /app/")
        name = value[5:].removesuffix("/")
        require(all(p not in {"", ".", ".."} for p in name.split("/"))
                and not any(c in name for c in "\\\0*?[]"),
                f"{task}: artifact is not a canonical literal path: {value}")
        path = checked_path(task / "environment/starter", name)
        require(path.is_file() or path.is_dir(), f"{path}: expected file or directory")
        require(not value.endswith("/") or path.is_dir(), f"{value}: directory artifact is a file")
        relative.append(name)
    require(len(set(relative)) == len(relative), f"{task}: duplicate artifacts")
    for name in relative:
        require(not any(other.startswith(name + "/") for other in relative),
                f"{task}: artifact scopes overlap at {name}")
    return artifacts, relative


def check_public_files(task, repo):
    starter = checked_path(task, "environment/starter", kind="directory")
    for item in starter.rglob("*"):
        checked_path(starter, item.relative_to(starter))
        if item.suffix == ".md" and item.is_file():
            local_links(item.read_text(), item, task, repo, public=True)
        if item.suffix not in {".va", ".vams", ".scs", ".spi", ".sp", ".inc"} or not item.is_file():
            continue
        content = re.sub(r"/\*.*?\*/", "", item.read_text(), flags=re.S)
        for name in INCLUDE.findall(content):
            if name in {"constants.vams", "disciplines.vams"} or "$" in name:
                continue  # Backend libraries and variable expansion require runtime validation.
            if name.startswith("/app/"):
                target = starter / name[5:]
            elif PurePosixPath(name).is_absolute():
                continue  # PDK/system mounts are checked by the execution environment.
            else:
                target = item.parent / name
            require(target.resolve().is_relative_to(starter.resolve()),
                    f"{item}: include leaves public materials: {name}")
            require(target.is_file(), f"{item}: missing public include: {name}")


def result_object(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"{path}: duplicate JSON key {key}")
            result[key] = value
        return result

    def finite(value):
        if isinstance(value, float):
            require(math.isfinite(value), f"{path}: nonfinite JSON number")
        elif isinstance(value, dict):
            for item in value.values():
                finite(item)
        elif isinstance(value, list):
            for item in value:
                finite(item)

    try:
        value = json.loads(path.read_text(), object_pairs_hook=unique)
        require(isinstance(value, dict) and value, f"{path}: expected nonempty JSON object")
        finite(value)
    except json.JSONDecodeError as error:
        raise ValueError(f"{path}: invalid JSON: {error.msg}") from error


def validate_package(task, repo, *, level=None, formal=False):
    task, repo = Path(task).absolute(), Path(repo).resolve()
    require(not task.is_symlink(), f"{task}: symlink package")
    require(SLUG.fullmatch(task.name), f"{task}: invalid task ID")
    config = read_config(task)
    selected = selected_level(config, level, formal=formal)
    metadata = config["metadata"]
    if selected == "accepted":
        require(metadata.get("review_status") == "accepted", f"{task}: requires explicit accepted review")
    require(config.get("schema_version") == "1.4", f"{task}: expected task schema_version = '1.4'")
    require(metadata.get("name") == task.name, f"{task}: metadata.name mismatch")
    for field in ("engineering_action", "source_group"):
        require(isinstance(metadata.get(field), str) and metadata[field].strip(), f"{task}: missing {field}")
    source = checked_path(task, "SOURCE.md", kind="file")
    instruction = checked_path(task, "instruction.md", kind="file")
    artifacts, relative = check_artifacts(task, config)
    check_instruction(task, instruction.read_text(), artifacts)
    local_links(instruction.read_text(), instruction, task, repo, public=True)
    local_links(source.read_text(), source, task, repo, public=False)
    check_public_files(task, repo)
    if LEVELS.index(selected) >= LEVELS.index("implementation"):
        for name in ("environment/Dockerfile", "solution/solve.sh", "tests/test.sh", "tests/verify.py"):
            checked_path(task, name, kind="file")
        public_bench = checked_path(task, "environment/starter/testbench", kind="directory")
        require(any(p.is_file() for p in public_bench.rglob("*")), f"{public_bench}: empty public testbench")
        require("testbench/" in instruction.read_text(),
                f"{instruction}: missing public testbench entry or usage link")
        for name in relative:
            starter = task / "environment/starter" / name
            checked_path(task / "solution", name, kind="directory" if starter.is_dir() else "file")
    if LEVELS.index(selected) >= LEVELS.index("calibration"):
        for name in ("reference", "calibration"):
            result_object(checked_path(task, f"results/{name}.json", kind="file"))
    if selected == "accepted":
        # A record can be inline in SOURCE.md or linked. Neither authenticates approval.
        body = prose(source.read_text())
        lines = [line for line in body.splitlines()
                 if re.search(r"review|审核", line, re.I) and LINK.search(line)]
        section = re.search(r"(?im)^##\s+[^\n]*(?:review|审核)[^\n]*\n(.*?)(?=^##\s|\Z)", body, re.S)
        require(lines or (section and section[1].strip()), f"{source}: missing review record")
    return selected
