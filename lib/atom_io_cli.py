"""atom_io_cli.py — thin CLI bridge: stdin JSON → write_atom → stdout JSON

供 server.js 切 spawn 用：MCP toolAtomWrite/Promote 最終落檔
改 spawn `python -m lib.atom_io_cli`，stdin 餵 JSON 參數，stdout 讀 WriteResult。

Schema:
  stdin:  {"action": "write_atom"|"write_index"|"write_index_full"|"write_raw"
                    |"build"|"append"|"locate", ...kwargs}
  stdout: WriteResult.to_dict()  (single-line JSON)
  exit code: 0=ok, 1=error

write_raw / write_index_full 額外參數：caller 端傳 file_path (str)、content (str)。

build / append：server.js toolAtomWrite 的內容構造
與 append 拼接統一走 py 單一實作（js buildAtomContent / 自拼 splice 退役為
test_13 parity fixture）：
  build:  build_atom_content kwargs → {ok, extra: {content}}（含 validate，不落檔）
  append: {file_path, knowledge, source} → 拼接+validate+write_raw 落檔

locate：{title, scope, project_cwd, role, user, audience, realm, domain}
→ {ok, path, extra:{found, rel_path}}。append/replace 找不到扁平落點時，js 端
以此定位子夾內的實體檔（定位規則 py 單一來源，見 atom_io.locate_atom）。

update_atom_field action 已移除（計數類欄位改走 lib/atom_access.py CLI
入口 `python -m lib.atom_access ...`，不再透過此 bridge）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .atom_io import (
    write_atom, write_index, write_index_full, write_raw,
    append_atom_file, locate_atom, WriteResult,
)
from .atom_access import init_access
from .atom_spec import (
    build_atom_content, validate_atom_content,
    knowledge_sections_bytes, knowledge_budget_error,
)


def _budget_check(content: str):
    """build 產物的 knowledge 區大小預算（create/replace 共用硬拒；append 在
    atom_io.append_atom_file 內檢）。超額回錯誤字串，否則 None。"""
    return knowledge_budget_error(knowledge_sections_bytes(content))


def _core_layout_gate_error(base_dir: Path, rel_path: str):
    """核心層 create 落點後盾：gate 開且 index 在全域 memory/ 時，rel_path 必須帶範疇段。
    回錯誤字串或 None。專案層 index（非全域）不在此檢。"""
    from . import atom_io as _aio
    from .atom_locations import (
        FAILURES_ROOT_NAME, core_category_segments, is_flat_core_path,
        is_legacy_failures_path, unclassified_error,
    )
    try:
        if base_dir.resolve() != _aio.GLOBAL_MEMORY_DIR.resolve():
            return None
    except OSError:
        return None
    if not _aio._category_gate_enabled():
        return None
    rel = rel_path.replace("\\", "/")
    segs = core_category_segments(rel)
    if is_legacy_failures_path(rel) or is_flat_core_path(rel) or segs == [FAILURES_ROOT_NAME]:
        try:
            from .atom_taxonomy import core_categories
            cats = core_categories()
        except Exception:  # noqa: BLE001 — taxonomy 缺時仍要拒、只是列不出清單
            cats = []
        layer = "failures" if (segs and segs[0] == FAILURES_ROOT_NAME) or is_legacy_failures_path(rel) else "core"
        return ("category gate: create landing spot must be memory/<Lv1>[/<Lv2>]/ "
                f"(got {rel!r}); " + unclassified_error(None, cats, layer))
    return None


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

    # 0. 範疇寫入閘後盾（py 單源）：js 端算好 file_path 才 spawn 本 action，不經 write_atom；
    #    若 rel_path 仍是核心層平鋪（memory/<slug>.md）、Failures 根平鋪、或舊址 _AIDocs/Failures/
    #    → 拒（舊碼 MCP 實例／繞路呼叫都攔得住）。專案層由 locate(mode=create) 閘 + js 預檢負責。
    gate_err = _core_layout_gate_error(Path(index["base_dir"]), str(index.get("rel_path") or ""))
    if gate_err:
        return WriteResult(ok=False, error=gate_err)

    # 1. build + validate（不落檔）
    try:
        content = build_atom_content(**build_params)
    except (TypeError, ValueError) as e:
        return WriteResult(ok=False, error=f"build: {e}")
    err = validate_atom_content(content)
    if err is not None:
        return WriteResult(ok=False, error=f"validate: {err}")
    budget_err = _budget_check(content)
    if budget_err is not None:
        return WriteResult(ok=False, error=f"budget: {budget_err}")

    # 2. write_raw（atomic write + audit；_atomic_write 自動 mkdir parent）
    wr = write_raw(file_path, content, source="mcp", op="atom_create")
    if not wr.ok:
        return WriteResult(ok=False, error=f"write_raw: {wr.error}")

    # 3. access.json：init 一次帶齊 first_seen + last_used（單寫，去冗餘雙寫）
    init_access(file_path, first_seen=today, last_used=today, source="mcp")

    # 4. index upsert（非致命，對拍 appendToIndex 的 crashLog-only）
    # scope：js 端 create 傳 scopeLabel（與 frontmatter 一致）；缺省 None → 沿用既有/global
    ir = write_index(
        base_dir=Path(index["base_dir"]), slug=index["slug"],
        rel_path=index["rel_path"], triggers=list(index["triggers"]), source="mcp",
        scope=index.get("scope"),
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
            err = validate_atom_content(content) or _budget_check(content)
            result = WriteResult(ok=err is None, error=err,
                                 extra={"content": content})
        elif action == "append":
            payload["file_path"] = Path(payload["file_path"])
            result = append_atom_file(**payload)
        elif action == "create_atom":
            result = create_atom(payload)
        elif action == "locate":
            result = locate_atom(**payload)
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
