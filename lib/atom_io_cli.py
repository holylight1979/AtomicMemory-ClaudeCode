"""atom_io_cli.py — thin CLI bridge: stdin JSON → write_atom → stdout JSON

供 server.js 切 spawn 用：MCP toolAtomWrite/Promote 最終落檔
改 spawn `python -m lib.atom_io_cli`，stdin 餵 JSON 參數，stdout 讀 WriteResult。

Schema:
  stdin:  {"action": "write_atom"|"write_index"|"write_index_full"|"write_raw"
                    |"build"|"append", ...kwargs}
  stdout: WriteResult.to_dict()  (single-line JSON)
  exit code: 0=ok, 1=error

write_raw / write_index_full 額外參數：caller 端傳 file_path (str)、content (str)。

build / append：server.js toolAtomWrite 的內容構造
與 append 拼接統一走 py 單一實作（js buildAtomContent / 自拼 splice 退役為
test_13 parity fixture）：
  build:  build_atom_content kwargs → {ok, extra: {content}}（含 validate，不落檔）
  append: {file_path, knowledge, source} → 拼接+validate+write_raw 落檔

update_atom_field action 已移除（計數類欄位改走 lib/atom_access.py CLI
入口 `python -m lib.atom_access ...`，不再透過此 bridge）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .atom_io import (
    write_atom, write_index, write_index_full, write_raw,
    append_atom_file, WriteResult,
)
from .atom_access import init_access
from .atom_spec import build_atom_content, validate_atom_content


def create_atom(payload: dict) -> WriteResult:
    """合併 create funnel：build→write_raw→access init（first_seen+last_used 單寫）
    →write_index，單一 subprocess 取代 create 路徑原本的多次 spawn。

    落檔 .md / .access.json / index 三件 byte-identical
    （守 verify_atom_io_equivalence 對拍）。

    行為對拍逐一呼叫路徑：
      - build / validate 失敗 → 致命（ok=False）
      - write_raw 失敗 → 致命（ok=False）
      - access init → 不檢查結果（原 spawn 亦未檢查回傳）
      - write_index 失敗 → 非致命（原 appendToIndex 僅 crashLog）：ok 仍 True，
        index 狀態放 extra.index_ok / extra.index_error 供 caller 記錄。

    payload: {build: {...build_atom_content kwargs}, file_path, today,
              index: {base_dir, slug, rel_path, triggers}}
    """
    build_params = payload["build"]
    file_path = Path(payload["file_path"])
    today = payload["today"]
    index = payload["index"]

    # 1. build + validate（不落檔）
    try:
        content = build_atom_content(**build_params)
    except (TypeError, ValueError) as e:
        return WriteResult(ok=False, error=f"build: {e}")
    err = validate_atom_content(content)
    if err is not None:
        return WriteResult(ok=False, error=f"validate: {err}")

    # 2. write_raw（atomic write + audit；_atomic_write 自動 mkdir parent）
    wr = write_raw(file_path, content, source="mcp", op="atom_create")
    if not wr.ok:
        return WriteResult(ok=False, error=f"write_raw: {wr.error}")

    # 3. access.json：init 一次帶齊 first_seen + last_used（單寫，去冗餘雙寫）
    init_access(file_path, first_seen=today, last_used=today, source="mcp")

    # 4. index upsert（非致命，對拍 appendToIndex 的 crashLog-only）
    ir = write_index(
        base_dir=Path(index["base_dir"]), slug=index["slug"],
        rel_path=index["rel_path"], triggers=list(index["triggers"]), source="mcp",
    )
    return WriteResult(
        ok=True,
        extra={"content": content, "index_ok": ir.ok, "index_error": ir.error},
    )


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"ok": False, "error": f"invalid stdin JSON: {e}"}))
        return 1

    action = payload.pop("action", "write_atom")
    try:
        if action == "write_atom":
            result = write_atom(**payload)
        elif action == "write_index":
            payload["base_dir"] = Path(payload["base_dir"])
            result = write_index(**payload)
        elif action == "write_index_full":
            # JSON 不能傳 Path，caller 用 str；轉成 Path
            payload["index_path"] = Path(payload["index_path"])
            result = write_index_full(**payload)
        elif action == "write_raw":
            payload["file_path"] = Path(payload["file_path"])
            result = write_raw(**payload)
        elif action == "build":
            content = build_atom_content(**payload)
            err = validate_atom_content(content)
            result = WriteResult(ok=err is None, error=err,
                                 extra={"content": content})
        elif action == "append":
            payload["file_path"] = Path(payload["file_path"])
            result = append_atom_file(**payload)
        elif action == "create_atom":
            result = create_atom(payload)
        else:
            result = WriteResult(ok=False, error=f"unknown action: {action}")
    except TypeError as e:
        result = WriteResult(ok=False, error=f"bad params: {e}")
    except KeyError as e:
        result = WriteResult(ok=False, error=f"missing param: {e}")

    print(json.dumps(result.to_dict(), ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
