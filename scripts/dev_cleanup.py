#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
API_DIR = ROOT / "api"
DEV_PORTS = (8000, 3001, 3002)
DEFAULT_NEXT_ENV = """/// <reference types="next" />
/// <reference types="next/image-types/global" />

// NOTE: This file should not be edited
// see https://nextjs.org/docs/app/api-reference/config/typescript for more information.
"""


def run(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=check)


def read_process_table() -> tuple[dict[int, str], dict[int, set[int]]]:
    proc_map: dict[int, str] = {}
    children: dict[int, set[int]] = {}
    result = run(["ps", "-axo", "pid=,ppid=,command="], check=True)
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split(None, 2)
        if len(parts) < 3:
            continue
        pid = int(parts[0])
        ppid = int(parts[1])
        command = parts[2]
        proc_map[pid] = command
        children.setdefault(ppid, set()).add(pid)
    return proc_map, children


def listener_pids() -> set[int]:
    pids: set[int] = set()
    result = run(
        [
            "lsof",
            "-nP",
            "-ti",
            "tcp:8000",
            "-iTCP:3001",
            "-iTCP:3002",
            "-sTCP:LISTEN",
        ]
    )
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.isdigit():
            pids.add(int(line))
    return pids


def cwd_for_pid(pid: int) -> str | None:
    result = run(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"])
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def is_repo_next_server(pid: int, command: str) -> bool:
    if not command.startswith("next-server (v"):
        return False
    cwd = cwd_for_pid(pid)
    return cwd == str(WEB_DIR)


def direct_dev_match(command: str) -> bool:
    web_path = str(WEB_DIR)
    api_path = str(API_DIR)
    return any(
        pattern in command
        for pattern in (
            f"{web_path}/node_modules/.bin/next",
            f"{web_path}/.next",
            f"{web_path}/.next-",
            f"{web_path}/.next-runs",
            f"{api_path}/.venv/bin/python -m uvicorn",
            "uvicorn app.main:app --reload",
        )
    )


def descendant_pids(root_pids: set[int], children: dict[int, set[int]]) -> set[int]:
    seen = set(root_pids)
    stack = list(root_pids)
    while stack:
        parent = stack.pop()
        for child in children.get(parent, set()):
            if child in seen:
                continue
            seen.add(child)
            stack.append(child)
    return seen


def collect_dev_pids() -> set[int]:
    proc_map, children = read_process_table()
    seed_pids = listener_pids()
    for pid, command in proc_map.items():
        if direct_dev_match(command) or is_repo_next_server(pid, command):
            seed_pids.add(pid)
    return descendant_pids(seed_pids, children)


def pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def terminate_pids(pids: set[int]) -> None:
    if not pids:
        print("No repo-scoped dev processes found.")
        return

    ordered = sorted(pids, reverse=True)
    print(f"Stopping {len(ordered)} repo-scoped dev process(es).")
    for pid in ordered:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            continue

    deadline = time.time() + 4
    while time.time() < deadline:
        remaining = {pid for pid in ordered if pid_exists(pid)}
        if not remaining:
            print("All repo-scoped dev processes exited cleanly.")
            return
        time.sleep(0.2)

    remaining = {pid for pid in ordered if pid_exists(pid)}
    if remaining:
        print(f"Force-killing {len(remaining)} stubborn process(es).")
        for pid in sorted(remaining, reverse=True):
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                continue


def prune_web_build_dirs() -> None:
    removed: list[str] = []
    for entry in WEB_DIR.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == ".next" or entry.name == ".next-runs" or entry.name.startswith(".next-"):
            shutil.rmtree(entry, ignore_errors=True)
            removed.append(entry.name)
    if removed:
        print("Removed generated Next build dirs:", ", ".join(sorted(removed)))
    else:
        print("No generated Next build dirs found.")


def normalize_next_env() -> None:
    next_env_path = WEB_DIR / "next-env.d.ts"
    next_env_path.write_text(DEFAULT_NEXT_ENV, encoding="utf-8")
    print("Normalized web/next-env.d.ts")


def run_git_gc() -> None:
    print("Running git gc --prune=now")
    subprocess.run(["git", "gc", "--prune=now"], cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stop repo-scoped dev processes and cleanup generated artifacts.")
    parser.add_argument("--reset", action="store_true", help="Stop dev processes and delete generated Next build directories.")
    parser.add_argument("--git-gc", action="store_true", help="Run git gc --prune=now after process cleanup.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    terminate_pids(collect_dev_pids())
    normalize_next_env()
    if args.reset:
        prune_web_build_dirs()
    if args.git_gc:
        run_git_gc()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
