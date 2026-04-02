#!/usr/bin/env python3
"""Set MYSQL_PASSWORD (and optionally MYSQL_NAME) in a .env file. Safe for special characters."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _quote_env_value(value: str) -> str:
    if re.search(r'[\s#"\']', value) or value.startswith(("'", '"')):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def update_key(lines: list[str], key: str, new_value: str) -> list[str]:
    prefix = f"{key}="
    out: list[str] = []
    found = False
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or not stripped:
            out.append(line)
            continue
        if stripped.startswith(prefix):
            out.append(f"{key}={_quote_env_value(new_value)}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={_quote_env_value(new_value)}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("env_file", type=Path, help="Path to .env")
    p.add_argument("password", help="New MYSQL_PASSWORD value")
    p.add_argument("--name", dest="db_name", help="Optional MYSQL_NAME to set")
    args = p.parse_args()
    path = args.env_file
    if not path.is_file():
        print(f"Not found: {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    lines = update_key(lines, "MYSQL_PASSWORD", args.password)
    if args.db_name:
        lines = update_key(lines, "MYSQL_NAME", args.db_name)
    path.write_text(newline.join(lines) + newline, encoding="utf-8")
    print(f"Updated {path} (MYSQL_PASSWORD" + (", MYSQL_NAME" if args.db_name else "") + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
