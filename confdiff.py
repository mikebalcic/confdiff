#!/usr/bin/env python3
"""confdiff —— 比对两份配置文件，只把"有意义的变化"列出来。

支持 JSON / YAML(简化) / .env / INI 四种格式。
差异分级：新增、删除、改动、空白差异。

用法:
    python confdiff.py old.json new.json
    python confdiff.py old.yaml new.yaml --ignore "^debug\\."
    python confdiff.py old.env new.env --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Change:
    key: str
    kind: str          # added | removed | changed | whitespace
    old: str | None
    new: str | None

    def render(self) -> str:
        symbol = {"added": "+", "removed": "-", "changed": "~", "whitespace": "·"}[self.kind]
        if self.kind == "added":
            return f"{symbol} {self.key}: {self.new!r}"
        if self.kind == "removed":
            return f"{symbol} {self.key}: {self.old!r}"
        return f"{symbol} {self.key}: {self.old!r} -> {self.new!r}"


def _stringify(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _unquote(value: str) -> str:
    """去掉包裹整串的引号，但保留首尾空白——空白差异需要被 diff 看见。"""
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in "\"'":
        return stripped[1:-1]
    return value


def flatten(data: dict, prefix: str = "") -> dict[str, str]:
    """把嵌套字典拍平成点号路径。列表按索引展开。"""
    flat: dict[str, str] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, path + "."))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                item_path = f"{path}[{index}]"
                if isinstance(item, dict):
                    flat.update(flatten(item, item_path + "."))
                else:
                    flat[item_path] = _stringify(item)
        else:
            flat[path] = _stringify(value)
    return flat


def _parse_simple_yaml(text: str) -> dict:
    """够用的 YAML 子集：key: value，支持缩进嵌套与 # 注释。"""
    root: dict = {}
    stack: list[tuple[int, dict]] = [(-1, root)]
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.split(" #")[0].strip().strip('"').strip("'")
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value == "":
            child: dict = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = value
    return root


def _parse_env(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].strip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = _unquote(value)
    return result


def _parse_ini(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(("[", "#", ";")):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
        elif ":" in line:
            key, _, value = line.partition(":")
        else:
            continue
        result[key.strip()] = _unquote(value)
    return result


def load(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    name = path.name.lower()
    if suffix == ".json":
        return flatten(json.loads(text))
    if suffix in (".yaml", ".yml"):
        return flatten(_parse_simple_yaml(text))
    if suffix == ".env" or name.endswith(".env"):
        return _parse_env(text)
    if suffix in (".ini", ".cfg", ".conf"):
        return _parse_ini(text)
    try:
        return flatten(json.loads(text))
    except json.JSONDecodeError:
        return _parse_env(text)


def diff(old: dict[str, str], new: dict[str, str]) -> list[Change]:
    changes: list[Change] = []
    for key in sorted(set(old) | set(new)):
        in_old, in_new = key in old, key in new
        if in_old and not in_new:
            changes.append(Change(key, "removed", old[key], None))
        elif in_new and not in_old:
            changes.append(Change(key, "added", None, new[key]))
        elif old[key] != new[key]:
            if old[key].strip() == new[key].strip():
                changes.append(Change(key, "whitespace", old[key], new[key]))
            else:
                changes.append(Change(key, "changed", old[key], new[key]))
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="confdiff",
        description="比对两份配置文件，列出有意义的变化（支持 JSON / YAML / .env / INI）",
    )
    parser.add_argument("old", help="旧版本文件")
    parser.add_argument("new", help="新版本文件")
    parser.add_argument("--ignore", action="append", default=[],
                        help="要忽略的键名正则（可多次传入）")
    parser.add_argument("--json", action="store_true", help="以 JSON 输出")
    args = parser.parse_args(argv)

    patterns = [re.compile(p) for p in args.ignore]

    old_path, new_path = Path(args.old), Path(args.new)
    for path in (old_path, new_path):
        if not path.exists():
            print(f"confdiff: 找不到文件 {path}", file=sys.stderr)
            return 2

    changes = diff(load(old_path), load(new_path))
    if patterns:
        changes = [c for c in changes if not any(p.search(c.key) for p in patterns)]

    if args.json:
        print(json.dumps(
            [{"key": c.key, "kind": c.kind, "old": c.old, "new": c.new} for c in changes],
            ensure_ascii=False, indent=2))
    else:
        for change in changes:
            print(change.render())
        print(f"\n共 {len(changes)} 处变化。")
    return 1 if changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
