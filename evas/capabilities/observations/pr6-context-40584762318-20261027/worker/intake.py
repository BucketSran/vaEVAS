"""Stage 1 helper: start record, guard, and archive download for CI 40584762318 (E1) and CI 40569530278 (#274).

Usage: python3 -B intake.py start | metadata-old | download-e1 LO HI | download-old
Never executes anything inside an archive. Every download writes to a new path (exclusive create).
"""
import concurrent.futures
import datetime
import stat
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath

from common import *


def save(path, value):
    with Path(path).open("xb") as f:
        f.write(dump(value))


def download(args):
    a, zdir, adir, run, head = args
    name = a["name"]
    assert a["workflow_run"]["id"] == run and a["workflow_run"]["head_sha"] == head, name
    p = zdir / (name + ".zip")
    with p.open("xb") as f, (zdir / (name + ".stderr")).open("xb") as err:
        r = subprocess.run(["gh", "api", "repos/%s/actions/artifacts/%s/zip" % (REPO, a["id"])], env=ENV, stdout=f, stderr=err)
    assert r.returncode == 0, (name, r.returncode)
    h, n = sha_file(p)
    assert h == a["digest"].removeprefix("sha256:") and n == a["size_in_bytes"], name
    out = adir / name
    out.mkdir()
    rows, seen = [], set()
    with zipfile.ZipFile(p) as z:
        assert z.testzip() is None
        for m in z.infolist():
            rel = PurePosixPath(m.filename)
            mode = m.external_attr >> 16
            assert not rel.is_absolute() and ".." not in rel.parts and "\\" not in m.filename and m.filename not in seen, m.filename
            seen.add(m.filename)
            dest = out / m.filename
            assert dest.resolve().is_relative_to(out.resolve())
            if m.is_dir():
                continue
            assert stat.S_IFMT(mode) in (0, stat.S_IFREG), (m.filename, oct(mode))
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as src, dest.open("xb") as dst:
                for chunk in iter(lambda: src.read(1 << 20), b""):
                    dst.write(chunk)
            rows.append(dict(path=m.filename, bytes=m.file_size, sha256=sha_file(dest)[0], archive_mode=mode))
    save(zdir / (name + ".members.json"), rows)
    return dict(name=name, id=a["id"], sha256=h, bytes=n, file_count=len(rows))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "start":
        save(D / "guard-before.json", guard())
        save(D / "start.json", dict(started_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                    providerInstanceId="tclaude", model="claude-sonnet-5-5", options=[dict(id="effort", value="high")],
                                    task_id="unknown (delegation record not visible to the worker)", queue_time=None))
        (D / "zips").mkdir()
        (D / "artifacts").mkdir()
    elif cmd == "metadata-old":
        d = D / "ci-40569530278"
        d.mkdir()
        for name, route in (("run-initial.json", "repos/%s/actions/runs/%s" % (REPO, OLD_RUN)),
                            ("jobs-initial.json", "repos/%s/actions/runs/%s/jobs?per_page=100" % (REPO, OLD_RUN)),
                            ("artifacts-initial.json", "repos/%s/actions/runs/%s/artifacts?per_page=100" % (REPO, OLD_RUN))):
            with (d / name).open("xb") as f, (d / (name + ".stderr")).open("xb") as err:
                r = subprocess.run(["gh", "api", route], env=ENV, stdout=f, stderr=err)
            assert r.returncode == 0, (name, r.returncode)
    elif cmd == "download-e1":
        assets = load(C / "artifacts-initial.json")["artifacts"]
        lo, hi = int(sys.argv[2]), int(sys.argv[3])
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            rows = list(pool.map(download, [(a, D / "zips", D / "artifacts", RUN, HEAD) for a in assets[lo:hi]]))
        save(D / ("downloads-%d-%d.json" % (lo, hi)), rows)
        print(rows)
    elif cmd == "download-old":
        assets = [a for a in load(D / "ci-40569530278/artifacts-initial.json")["artifacts"] if a["name"] == "python-regression-timings"]
        assert len(assets) == 1
        (D / "zips-274").mkdir()
        (D / "artifacts-274").mkdir()
        rows = [download((a, D / "zips-274", D / "artifacts-274", OLD_RUN, OLD_HEAD)) for a in assets]
        save(D / "downloads-274.json", rows)
        print(rows)
