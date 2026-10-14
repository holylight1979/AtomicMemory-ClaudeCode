"""atom_io_cli.py — thin CLI bridge: stdin JSON → write_atom → stdout JSON

供 server.js 切 spawn 用：MCP toolAtomWrite/Promote 最終落檔
改 spawn `python -m lib.atom_io_cli`，stdin 餵 JSON 參數，stdout 讀 WriteResult。

Schema:
  stdin:  {"action": "write_atom"|"write_index"|"write_index_full"|"write_raw"
                    |"build"|"append"|"locate"|"check_supersedes"|"retire"|"realm_check"|"scrub", ...kwargs}
  預算：create（create_atom／build）走 _budget_check、append 走 _append_budget_check＋atom_io.append_atom_file；
  replace 走 build 的 _budget_check。直接呼叫 lib.atom_io.write_atom(mode="replace") 沒有預算檢查（既有差異，
  CLI／js 路徑都已預檢）。
  日期閘：create_atom／build 看建好的知識段＋行動段、append（atom_io.append_atom_file）看新增行，
  有敘事型日期就拒（KNOWLEDGE_LINE_NO_NARRATIVE_DATE，判式 lib/narrative_date，與 write_atom 同一份）。
  realm_check：{scope?, project_cwd, title, triggers, knowledge, actions, domain} → scope=org 走 check_org_write，
  shared 直接放行，其餘走 check_global_write。scrub：{text} → extra.text（去專案名／路徑／「此專案」）。
  stdout: WriteResult.to_dict()  (single-line JSON)
  exit code: 0=ok, 1=error

write_raw / write_index_full 額外參數：caller 端傳 file_path (str)、content (str)。

build / append：server.js toolAtomWrite 的內容構造
與 append 拼接統一走 py 單一實作（js buildAtomContent / 自拼 splice 退役為
test_13 parity fixture）：
  build:  build_atom_content kwargs（＋選填 existing_path：replace 的既有檔，檔頭以舊卡為底）→ {ok, extra: {content}}（含 validate，不落檔）
  append: {file_path, knowledge, source} → 拼接+validate+write_raw 落檔

locate：{title, scope, project_cwd, role, user, audience, realm, domain}
→ {ok, path, extra:{found, rel_path}}。append/replace 找不到扁平落點時，js 端
以此定位子夾內的實體檔（定位規則 py 單一來源，見 atom_io.locate_atom）。

check_supersedes：{targets, self_slug, index_dir} → {ok, error}。js 端 replace 走 build
前先問這裡（create_atom 內建呼叫）；可解析／非自指／無循環／非核心保護名四檢（py 單源）。

retire：{atom_name, scope, project_cwd, role, user, reason, dry_run}
→ {ok, error, path, extra:{op:"retire", atom, old_path, new_path, index_ok,
   steps_done, steps_failed, index_root, base_dir}}。先 locate_atom（與 atom_write 同契約）
取實體檔與 memory root，再呼叫 tools/memory-audit.py delete_atom(project_dir=…)。

search：{query, cwd?, user?, roles?, top_k?, use_vector?} → {ok, extra: <lib/memory_search.search 回傳>}。
唯讀；user/roles 缺省以現用身份（wg_roles）補；query 空 → error。

source：{atom, cwd?} → {ok, extra: <lib/provenance.atom_source 回傳>}。唯讀；
atom 找不到 → ok=False、error 同 extra.error。

update_atom_field action 已移除（計數類欄位改走 lib/atom_access.py CLI
入口 `python -m lib.atom_access ...`，不再透過此 bridge）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from .atom_io import (
    write_atom, write_index, write_index_full, write_raw,
    append_atom_file, locate_atom, check_supersedes, WriteResult,
    _canonical_supersedes, card_body_lines, narrative_date_error,
)
from .atom_access import init_access
from .atom_spec import (
    build_atom_content, validate_atom_content,
    knowledge_sections_bytes, knowledge_budget_error, KNOWLEDGE_BUDGET_BYTES,
    render_knowledge_lines,
)
from .hub_card import budget_limit_for, is_hub_card, route_doc_for, depends_paths


def _index_kwargs(index: dict) -> dict:
    """write_index 的選填鍵：depends 有給（含 []）才傳；None／缺鍵不傳＝索引沿用既有 depends。
    原型別透傳不轉 list：字串／dict 要讓 write_index（validate_depends）拒收，list("path:x") 會變逐字合法清單。"""
    out = {}
    if index.get("depends") is not None:
        out["depends"] = index["depends"]
    return out


def _budget_check(content: str, route_paths=None, kind_hint=None):
    """build 產物的 knowledge 區大小預算（create/replace 共用硬拒；append 走 _append_budget_check）。
    導讀卡（標題含導讀／kind_hint=hub／五段 ≥4）用 HUB_CARD_BUDGET，其餘 KNOWLEDGE_BUDGET_BYTES。
    超額回錯誤字串（附 kind／route_to），否則 None。"""
    limit = budget_limit_for(content, KNOWLEDGE_BUDGET_BYTES, kind_hint=kind_hint)
    err = knowledge_budget_error(knowledge_sections_bytes(content), limit)
    if err is None:
        return None
    kind = "hub" if limit != KNOWLEDGE_BUDGET_BYTES else "plain"
    return f"{err}｜kind={kind} route_to={route_doc_for(route_paths or [])}"


def _append_budget_check(existing: str, knowledge, file_path: str):
    """append 預檢：既有 knowledge 區＋新增行（render 後）≤ 既有卡的預算（hub 卡 4096、其餘 3072）。
    超額回錯誤字串（kind=complement、route_to 部位文件），否則 None。不截斷、不改內容。"""
    limit = budget_limit_for(existing, KNOWLEDGE_BUDGET_BYTES)
    existing_bytes = knowledge_sections_bytes(existing)
    rendered = "\n".join(render_knowledge_lines(list(knowledge or []))) + "\n"
    new_bytes = len(rendered.encode("utf-8"))
    total = existing_bytes + new_bytes
    if total <= limit:
        return None
    route = route_doc_for(depends_paths(_depends_of(existing)) + [file_path])
    return (f"knowledge 區 {total} bytes（既有 {existing_bytes}＋新增 {new_bytes}）超過預算 {limit} bytes；"
            f"不截斷：個案細節寫進 {route}；atom 只留結論一行＋路徑｜kind=complement route_to={route}")


def _depends_of(content: str):
    import re as _re
    m = _re.search(r"^- Depends:[ \t]*(.*)$", content or "", _re.MULTILINE)   # 不跨行：空 Depends 行不吃下一行
    return [x.strip() for x in _re.split(r"[,，]", m.group(1)) if x.strip()] if m else []


def _realm_check(payload: dict):
    """realm_check 依 scope 分派：org → check_org_write（公司層不得帶專案名／路徑）；
    其餘（global／personal 跨專案）→ check_global_write；shared 不在此閘（專案層本來就能寫專名）。"""
    scope = str(payload.get("scope") or "global")
    fields = {"title": payload.get("title", ""), "triggers": payload.get("triggers"),
              "knowledge": payload.get("knowledge"), "actions": payload.get("actions")}
    if scope == "shared":
        return None
    if scope == "org":
        from .realm_gate import check_org_write
        errs = check_org_write(fields)
        return "\n".join(errs) if errs else None
    from .realm_gate import check_global_write
    return check_global_write(
        payload.get("project_cwd"), title=payload.get("title", ""),
        triggers=payload.get("triggers"), knowledge=payload.get("knowledge"),
        actions=payload.get("actions"), domain=payload.get("domain"))


def _canonical_build_params(build_params: dict):
    """build / create_atom 共用：supersedes 先轉 canonical slug 再給 build_atom_content，
    驗證（check_supersedes 也是 slug 比對）、檔頭、receipt 用同一份清單——原字串落檔會讓
    "Old Atom" 寫進檔頭而注入端對不上 old-atom.md。回 (params, canonical_list, error)；
    空目標回錯誤（slugify("") 會變 "untitled"，不能放行）。key 缺省時不補、None/[] 不輸出。"""
    raw = build_params.get("supersedes")
    if not raw:
        return build_params, [], None
    canonical = _canonical_supersedes(raw)
    if "" in canonical:
        return build_params, canonical, "supersedes: empty target name"
    return {**build_params, "supersedes": canonical}, canonical, None


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
              index: {base_dir, slug, rel_path, triggers}, dry_run?: bool}
    dry_run=True：跑完範疇後盾＋build/validate/budget 即回（ok=True、path=預計落點、
    extra.dry_run=True），不落檔、不寫 access.json、不動 index。
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

    # 0b. Supersedes canonical 化 + 寫前檢查（py 單源）：index_root = base_dir 的上一層
    #     （全域 CLAUDE_DIR／專案根）；驗證、落檔、receipt 用同一份 slug 清單
    build_params, sup, sup_err = _canonical_build_params(build_params)
    if sup_err:
        return WriteResult(ok=False, error=sup_err)
    if sup:
        sup_err = check_supersedes(sup, self_slug=index["slug"], index_dir=Path(index["base_dir"]))
        if sup_err:
            return WriteResult(ok=False, error=sup_err)

    # 1. build + validate（不落檔）
    try:
        content = build_atom_content(**build_params)
    except (TypeError, ValueError) as e:
        return WriteResult(ok=False, error=f"build: {e}")
    err = validate_atom_content(content) or narrative_date_error(card_body_lines(content))
    if err is not None:
        return WriteResult(ok=False, error=f"validate: {err}")
    budget_err = _budget_check(content, depends_paths(build_params.get("depends")) + [str(file_path)],
                               kind_hint=payload.get("kind_hint"))
    if budget_err is not None:
        return WriteResult(ok=False, error=f"budget: {budget_err}")
    if payload.get("dry_run"):
        return WriteResult(ok=True, path=file_path,
                           extra={"content": content, "dry_run": True,
                                  "rel_path": str(index.get("rel_path") or ""),
                                  "index_ok": None, "index_error": None})

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
        scope=index.get("scope"), **_index_kwargs(index),
    )
    return WriteResult(
        ok=True, path=file_path,
        extra={"content": content, "index_ok": ir.ok, "index_error": ir.error,
               "op": "create", "atom": index["slug"], "path": str(file_path),
               "supersedes": list(sup)},
    )


def _load_memory_audit():
    """tools/memory-audit.py 檔名含 '-' 無法 import → 以路徑載入（延遲：只有 retire 需要）。"""
    import importlib.util
    script = Path(__file__).resolve().parent.parent / "tools" / "memory-audit.py"
    spec = importlib.util.spec_from_file_location("memory_audit", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {script}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def retire_atom(payload: dict) -> WriteResult:
    """退役：locate_atom（同 atom_write 契約，mode=append 只定位既有檔）→ 取 memory root →
    memory-audit.delete_atom(layer, project_dir, reason, atom_path=loc.path)。定位路徑直接
    傳入，delete_atom 不再遍歷整層找同名檔（shared 與 personal/<u> 同名時會退役錯顆）。
    護欄／冪等順序／結構化失敗全在 delete_atom；本函式只負責定位與契約轉換。
    scope=local ⇒ scope=global + realm=local。"""
    atom_name = str(payload.get("atom_name") or "").strip()
    scope = str(payload.get("scope") or "").strip()
    reason = str(payload.get("reason") or "").strip()
    dry_run = bool(payload.get("dry_run"))
    if not atom_name or not scope:
        return WriteResult(ok=False, error="retire: atom_name and scope are required")
    if not reason:
        return WriteResult(ok=False, error="retire: reason is required")
    realm = None
    if scope == "local":
        scope, realm = "global", "local"
    loc = locate_atom(
        atom_name, scope, project_cwd=payload.get("project_cwd"), role=payload.get("role"),
        user=payload.get("user"), realm=realm, mode="append",
    )
    base_extra = {"op": "retire", "atom": atom_name, "old_path": None, "new_path": None,
                  "index_ok": None, "steps_done": [], "steps_failed": []}
    if not loc.ok:
        return WriteResult(ok=False, error=f"retire locate: {loc.error}", extra=base_extra)
    if loc.path is None:
        return WriteResult(ok=False, error=f"retire: atom not found: {atom_name}.md (scope={scope})",
                           extra=base_extra)
    ex = loc.extra or {}
    index_dir = Path(ex["index_dir"])
    base_extra.update({"index_root": ex.get("index_root"), "base_dir": ex.get("base_dir")})
    try:
        from .atom_locations import GLOBAL_MEMORY_DIR
        is_global = index_dir.resolve() == GLOBAL_MEMORY_DIR.resolve()
    except OSError:
        is_global = False
    layer = "global" if is_global else "project"
    project_dir = None if is_global else index_dir
    try:
        ma = _load_memory_audit()
    except (ImportError, OSError, SyntaxError) as e:
        return WriteResult(ok=False, error=f"retire: memory-audit unavailable: {e}", extra=base_extra)
    slug = ex.get("slug") or Path(loc.path).stem
    ok, msg, info = ma.delete_atom(slug, layer, purge=False, dry_run=dry_run,
                                   project_dir=project_dir, reason=reason,
                                   atom_path=Path(loc.path))
    base_extra.update({
        "atom": slug, "old_path": info.get("old_path") or str(loc.path),
        "new_path": info.get("new_path"), "index_ok": info.get("index_ok"),
        "steps_done": list(info.get("steps_done") or []),
        "steps_failed": list(info.get("steps_failed") or []),
        "references": list(info.get("references") or []), "dry_run": dry_run,
        "message": msg,
    })
    return WriteResult(ok=ok, path=loc.path, error=None if ok else msg, extra=base_extra)


def search_atoms(payload: dict) -> WriteResult:
    """唯讀查詢（lib/memory_search 單源）；身份缺省取現用 OS 帳號與職能。"""
    from .memory_search import search, default_identity
    cwd = payload.get("cwd") or str(Path.cwd())
    user, roles = payload.get("user"), payload.get("roles")
    if user is None and roles is None:
        user, roles = default_identity(cwd)
    try:
        result = search(
            payload.get("query", ""), cwd, user=user, roles=roles,
            top_k=int(payload.get("top_k") or 8), use_vector=bool(payload.get("use_vector", True)),
        )
    except ValueError as e:
        return WriteResult(ok=False, error=str(e))
    return WriteResult(ok=True, extra=result)


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
            depends = payload.pop("depends", None)
            result = write_index(**payload, **_index_kwargs({"depends": depends}))
        elif action == "write_index_full":
            # JSON 不能傳 Path，caller 用 str；轉成 Path
            payload["index_path"] = Path(payload["index_path"])
            result = write_index_full(**payload)
        elif action == "write_raw":
            payload["file_path"] = Path(payload["file_path"])
            result = write_raw(**payload)
        elif action == "build":
            # existing_path：MCP replace 帶既有檔路徑 → 檔頭以舊卡為底（atom_io.carry_replace_header，與 py write_atom 同一份）
            existing_path = payload.pop("existing_path", None)
            payload, sup, err = _canonical_build_params(payload)
            content = None
            if err is None:
                content = build_atom_content(**payload)
                if existing_path:
                    from .atom_io import carry_replace_header, given_header_keys
                    old = Path(existing_path).read_text(encoding="utf-8-sig")
                    content = carry_replace_header(old, content, given_header_keys(payload))
                err = (validate_atom_content(content) or narrative_date_error(card_body_lines(content))
                       or _budget_check(content))
            result = WriteResult(ok=err is None, error=err,
                                 extra={"content": content, "supersedes": sup})
        elif action == "append":
            payload["file_path"] = Path(payload["file_path"])
            # 預算預檢（hub 卡 4096／其餘 3072；超額附 kind／route_to），再交 append_atom_file 拼接落檔
            try:
                existing = payload["file_path"].read_text(encoding="utf-8-sig")
            except OSError:
                existing = ""
            budget_err = _append_budget_check(existing, payload.get("knowledge"), str(payload["file_path"])) if existing else None
            result = (WriteResult(ok=False, error=f"budget: {budget_err}") if budget_err
                      else append_atom_file(**payload))
        elif action == "create_atom":
            result = create_atom(payload)
        elif action == "locate":
            result = locate_atom(**payload)
        elif action == "check_supersedes":
            sup_err = check_supersedes(
                payload.get("targets") or [], self_slug=payload["self_slug"],
                index_dir=Path(payload["index_dir"]),
                index_root=Path(payload["index_root"]) if payload.get("index_root") else None,
            )
            result = WriteResult(ok=sup_err is None, error=sup_err)
        elif action == "retire":
            result = retire_atom(payload)
        elif action == "realm_check":
            # 專案專屬內容不得落 global／org（lib/realm_gate.py 單源）。MCP js 對 scope=global
            # 與 scope=org（改寫成 shared 之前）的所有 mode 先問這裡；不受 skip_gate 影響。
            gate_err = _realm_check(payload)
            result = WriteResult(ok=gate_err is None, error=gate_err)
        elif action == "scrub":
            # 去專案細節：{text} → {extra:{text}}；candidate_global／org 改寫前用
            from .realm_gate import scrub_project_details
            result = WriteResult(ok=True, extra={"text": scrub_project_details(str(payload.get("text") or ""))})
        elif action == "search":
            result = search_atoms(payload)
        elif action == "source":
            from .provenance import atom_source
            src = atom_source(payload.get("atom", ""), cwd=payload.get("cwd"))
            result = WriteResult(ok="error" not in src, error=src.get("error"), extra=src)
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
