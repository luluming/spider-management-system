#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从 Cursor 导出的 JSON（如 Untitled-1.json）中读取 items 与 mob_params，并导出字段：

- items[*]: ugc_item.content, user_info.nickname（含 user_info.user_basic_info.nickname）, published_time_ms
  （兼容 nickname / published_time_ms 写在 item 根或 ugc_item 内）
- mob_params: poi_id（整份文件通常一份，会附加到每一行导出）

用法:
  python scripts/extract_untitled_json.py "C:\\Users\\zm\\AppData\\Local\\Programs\\cursor\\Untitled-1.json"
  python scripts/extract_untitled_json.py path/to/file.json -o out.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _as_dict(obj: Any) -> Dict[str, Any]:
    return obj if isinstance(obj, dict) else {}


def _nickname_from_user_info(ui: Dict[str, Any]) -> Optional[str]:
    """兼容 user_info.nickname 与 user_info.user_basic_info.nickname。"""
    n = ui.get("nickname")
    if n is not None and str(n).strip() != "":
        return str(n)
    ubi = _as_dict(ui.get("user_basic_info"))
    n = ubi.get("nickname")
    if n is not None and str(n).strip() != "":
        return str(n)
    return None


def _pick_nickname(item: Dict[str, Any], ugc: Dict[str, Any]) -> Optional[str]:
    for src in (item, ugc):
        ui = _as_dict(src.get("user_info"))
        n = _nickname_from_user_info(ui)
        if n is not None:
            return n
    return None


def _pick_published_time_ms(item: Dict[str, Any], ugc: Dict[str, Any]) -> Optional[Any]:
    for key in ("published_time_ms", "publish_time_ms", "publishedTimeMs"):
        if key in item and item[key] is not None:
            return item[key]
        if key in ugc and ugc[key] is not None:
            return ugc[key]
    return None


def _pick_content(ugc: Dict[str, Any]) -> Optional[str]:
    c = ugc.get("content")
    if c is None:
        return None
    return str(c)


def _pick_poi_id(root: Dict[str, Any]) -> Optional[str]:
    mp = _as_dict(root.get("mob_params"))
    for key in ("poi_id", "poiId", "poiID"):
        v = mp.get(key)
        if v is not None and str(v).strip() != "":
            return str(v)
    return None


def _iter_items(root: Any) -> List[Any]:
    if isinstance(root, dict):
        items = root.get("items")
        if isinstance(items, list):
            return items
        # 有时整包在 data 里
        data = root.get("data")
        if isinstance(data, dict):
            inner = data.get("items")
            if isinstance(inner, list):
                return inner
    return []


def extract_rows(root: Dict[str, Any]) -> List[Dict[str, Any]]:
    poi_id = _pick_poi_id(root)
    rows: List[Dict[str, Any]] = []
    for raw in _iter_items(root):
        item = _as_dict(raw)
        ugc = _as_dict(item.get("ugc_item"))
        rows.append(
            {
                "content": _pick_content(ugc),
                "nickname": _pick_nickname(item, ugc),
                "published_time_ms": _pick_published_time_ms(item, ugc),
                "poi_id": poi_id,
            }
        )
    return rows


def dump_csv(rows: Iterable[Dict[str, Any]], path: Path) -> None:
    fieldnames = ["content", "nickname", "published_time_ms", "poi_id"]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r[k]) for k in fieldnames})


def main() -> int:
    default_win = r"C:\Users\zm\AppData\Local\Programs\cursor\Untitled-1.json"
    p = argparse.ArgumentParser(description="从 Untitled-1.json 提取 items / mob_params 字段")
    p.add_argument(
        "json_path",
        nargs="?",
        default=default_win,
        help=f"JSON 文件路径（默认: {default_win}）",
    )
    p.add_argument("-o", "--output", type=Path, help="输出 CSV 路径；省略则打印 JSON 到 stdout")
    args = p.parse_args()

    path = Path(args.json_path)
    if not path.is_file():
        print(f"文件不存在: {path}", file=sys.stderr)
        return 1

    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8-sig")

    try:
        root = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"JSON 解析失败: {e}", file=sys.stderr)
        return 1

    if not isinstance(root, dict):
        print("根节点必须是 JSON 对象（字典）", file=sys.stderr)
        return 1

    rows = extract_rows(root)
    if args.output:
        dump_csv(rows, args.output)
        print(f"已写入 {args.output}，共 {len(rows)} 行", file=sys.stderr)
    else:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
