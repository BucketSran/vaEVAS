#!/usr/bin/env python3
"""Ask before a shell command writes a large artifact into internal runs/."""

import json
import os
import re
import sys

T7_RUNS = "/Volumes/T7/vaEVAS/current/runs"
INTERNAL_MARK = "TsingProject/research/vaEVAS"
BULK = re.compile(
    r"(?:^|[;&|]\s*)(?:rsync|ditto|unzip|tar)\b"
    r"|\bgit\s+archive\b"
    r"|\bcargo\s+(?:build|test|bench)\b"
    r"|\bcp\b[^\n]*\s-[^\n]*[aRr]"
)


def emit(payload):
    json.dump(payload, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def local_runs_path(command, cwd):
    internal_cwd = INTERNAL_MARK in cwd and not cwd.startswith("/Volumes/T7")
    relative_runs = bool(re.search(r"(?:^|[\s=])(?:\./)?runs(?:/|\s|$)", command))
    absolute_internal = INTERNAL_MARK in command and "/runs/" in command
    cwd_is_runs = internal_cwd and "/runs/" in cwd
    if absolute_internal or cwd_is_runs or (internal_cwd and relative_runs):
        return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        emit({"permission": "allow"})
        return 0
    command = str(data.get("command") or "")
    cwd = str(data.get("cwd") or "")
    if not local_runs_path(command, cwd) or not BULK.search(command):
        emit({"permission": "allow"})
        return 0
    mounted = os.path.ismount("/Volumes/T7")
    if mounted:
        where = f"T7 已挂载，大产物应写到 {T7_RUNS}，并在原路径留下符号链接。"
    else:
        where = "T7 当前没挂上。先接上磁盘再继续；不要先写进内置盘。"
    emit(
        {
            "permission": "ask",
            "user_message": (
                "这条命令会往内置盘的 runs/ 写入大量实验产物（整树复制、归档或 cargo 构建）。"
                + where
            ),
            "agent_message": (
                "Large run output needs the user's choice before it touches the internal disk. "
                + where
            ),
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
