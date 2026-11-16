#!/usr/bin/env python3
"""Build a ready-to-install Elyx archive without external tooling.

Elyx archives are ZIP files with ``refmap.yml`` at the root. This script does the
same job that ``elyb build`` does for a source build: validate the Python files,
exclude caches and VCS folders, write real directory entries (the installer checks
for them) and report the archive size.

Usage:
    python3 tools/elyx_pack.py                 # → builds/custom_extra_ayu-<version>.elyx
    python3 tools/elyx_pack.py --out build/x   # custom output directory
    python3 tools/elyx_pack.py --compile       # also embed Python 3.11 bytecode
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IGNORE_DIRS = {
    ".git",
    ".github",
    ".elyx",
    "builds",
    "dist",
    "tools",
    "docs",
    "__pycache__",
    ".venv",
    "node_modules",
}
# User documentation and CI config stay in the repository, not in the archive.
IGNORE_FILES = {".gitignore", ".DS_Store", "README.md"}
# Never pack previously built archives back into a new one.
IGNORE_SUFFIXES = (".elyx", ".eaf")
ARCHIVE_SUFFIX = ".elyx"


def read_metainfo() -> dict:
    path = os.path.join(ROOT, "metainfo.yml")
    meta: dict = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            value = value.strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            meta[key.strip()] = value
    return meta


def iter_files() -> list:
    collected = []
    for current, dirs, names in os.walk(ROOT):
        dirs[:] = sorted(
            name for name in dirs if name not in IGNORE_DIRS and not name.startswith(".")
        )
        for name in sorted(names):
            if name in IGNORE_FILES or name.endswith(".pyc"):
                continue
            if name.endswith(IGNORE_SUFFIXES):
                continue
            full = os.path.join(current, name)
            relative = os.path.relpath(full, ROOT).replace(os.sep, "/")
            collected.append((full, relative))
    return collected


def check_python(files: list) -> list:
    problems = []
    for full, relative in files:
        if not relative.endswith(".py"):
            continue
        try:
            with open(full, "r", encoding="utf-8") as handle:
                compile(handle.read(), relative, "exec")
        except SyntaxError as error:
            problems.append("%s: %s" % (relative, error))
    return problems


def required_paths() -> list:
    """Every path declared in refmap must exist in the archive."""
    refmap = os.path.join(ROOT, "refmap.yml")
    declared = []
    if not os.path.exists(refmap):
        return declared
    with open(refmap, "r", encoding="utf-8") as handle:
        for line in handle:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            if key.strip() in ("metainfo", "main", "strings", "assets", "wheels"):
                target = value.strip()
                if target:
                    declared.append(target)
    return declared


def build(output_dir: str, compile_bytecode: bool) -> str:
    meta = read_metainfo()
    plugin_id = meta.get("id") or "plugin"
    version = meta.get("version") or "dev"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")

    files = iter_files()
    problems = check_python(files)
    if problems:
        for problem in problems:
            print("syntax error: %s" % problem, file=sys.stderr)
        raise SystemExit(1)

    names = {relative for _full, relative in files}
    for required in required_paths():
        if required not in names and not any(name.startswith(required + "/") for name in names):
            raise SystemExit("refmap points to a missing path: %s" % required)
    for mandatory in ("refmap.yml", "metainfo.yml"):
        if mandatory not in names:
            raise SystemExit("archive root must contain %s" % mandatory)

    os.makedirs(output_dir, exist_ok=True)
    archive_name = "%s-%s-%s%s" % (plugin_id, version, stamp, ARCHIVE_SUFFIX)
    archive_path = os.path.join(output_dir, archive_name)

    directories = set()
    for relative in names:
        parts = relative.split("/")[:-1]
        for index in range(1, len(parts) + 1):
            directories.add("/".join(parts[:index]))

    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for directory in sorted(directories):
            info = zipfile.ZipInfo(directory + "/")
            info.external_attr = (0o40755 << 16) | 0x10
            info.date_time = datetime.now().timetuple()[:6]
            archive.writestr(info, b"")
        for full, relative in files:
            with open(full, "rb") as handle:
                archive.writestr(relative, handle.read())
            if compile_bytecode and relative.endswith(".py"):
                source = open(full, "r", encoding="utf-8").read()
                code = compile(source, relative, "exec", optimize=2)
                path = os.path.join(ROOT, relative)
                cache = os.path.join(os.path.dirname(path), "__pycache__")
                os.makedirs(cache, exist_ok=True)
                pyc_name = os.path.splitext(os.path.basename(relative))[0] + ".pyc"
                pyc_path = os.path.join(cache, pyc_name)
                import importlib.util

                with open(pyc_path, "wb") as handle:
                    handle.write(importlib.util.MAGIC_NUMBER)
                    handle.write(b"\0" * 12)
                    import marshal

                    marshal.dump(code, handle)
                with open(pyc_path, "rb") as handle:
                    archive.writestr(relative[:-3] + ".pyc", handle.read())
                os.remove(pyc_path)

    size = os.path.getsize(archive_path)
    report = {
        "plugin_id": plugin_id,
        "version": version,
        "files": len(files),
        "bytes": size,
        "archive": archive_path,
        "compiled": bool(compile_bytecode),
    }
    print(json.dumps(report, indent=2))
    return archive_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Pack the plugin into an .elyx archive")
    parser.add_argument("--out", default=os.path.join(ROOT, "builds"), help="output directory")
    parser.add_argument("--compile", action="store_true", help="embed Python 3.11 bytecode")
    arguments = parser.parse_args()
    output = arguments.out
    if not os.path.isabs(output):
        output = os.path.join(ROOT, output)
    build(output, arguments.compile)


if __name__ == "__main__":
    main()
