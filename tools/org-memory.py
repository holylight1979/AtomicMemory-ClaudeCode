#!/usr/bin/env python3
"""org-memory.py — 公司層記憶（org）初始化與工具卡掃描。

做什麼：把一個已 checkout 的公司記憶 repo 根佈成「所有專案都看得到、都能寫」的記憶層：
  <root>/.claude/memory/{MEMORY.md（含 atom-catalog 區塊）, _atom_index.json, shared/, shared/_taxonomy.json}
  <root>/.claude/project-tree.json {"standalone": true}（專案往上尋根到此為止）
  種一顆工具卡 shared/工具/org-memory.md（索引非空，sync-memory-index --check 才能過）
  ~/.claude/workflow/config.json org_memory.enabled=true, roots=[{"id":"org","root":<root>}]
  ~/.claude/memory/project-registry.json 登錄條目（向量 indexer 據此建層 shared:<slug>）
全部冪等：已存在的檔不覆寫。
--scan-tools：把 skills/_skill_index.json、mcp-servers.template.json 的每個工具登記成 org shared/工具/ 一張卡
  （--project <root> 時另掃 <root>/.claude/tools/*.py 落該專案 shared/工具/）。只建缺的卡，既有卡一律不動；
  卡的進入點（Depends: path:）消失 → 把 Status 改 deprecated，不刪卡。
  卡名：skill → skill-<name>、MCP server → mcp-<name>（一眼看出種類、避開索引檔 MEMORY.md 撞名）、
  專案 tools/*.py → 檔名去副檔名（與 --init 種的 org-memory 一致）。
怎麼跑：
  python ~/.claude/tools/org-memory.py --init <公司記憶 repo 根>
  python ~/.claude/tools/org-memory.py --scan-tools [--project <專案根>] [--owner <AD 帳號>] [--dry-run]
  完整參數以 --help 為準。
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

CLAUDE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CLAUDE_DIR))
sys.path.insert(0, str(CLAUDE_DIR / "hooks"))

import wg_core  # noqa: E402
from wg_roles import get_current_user  # noqa: E402
from lib import atom_access  # noqa: E402
from lib.atom_io import locate_atom, write_index, write_raw  # noqa: E402
from lib.atom_spec import (  # noqa: E402
    TRIGGER_MIN, build_atom_content, parse_depends, resolve_depends_path, validate_atom_content,
)
from lib.atom_index_json import load_atom_index_json, upsert_atom  # noqa: E402

CONFIG_PATH = wg_core.CONFIG_PATH
SYNC_INDEX = CLAUDE_DIR / "tools" / "sync-memory-index.py"
TAXONOMY = {
    "domains": {
        "工具": {
            "desc": "工具卡：Author=負責人、Source=進入點、Status=production|deprecated、Depends=path:進入點",
        },
    },
}
SEED_NAME = "org-memory"
SEED_REL = f"memory/shared/工具/{SEED_NAME}.md"
SEED_TRIGGERS = ["org-memory", "公司層記憶", "org 初始化", "scope=org"]

# --scan-tools 來源（測試 monkeypatch 這三個）
SKILL_INDEX = CLAUDE_DIR / "skills" / "_skill_index.json"
SKILLS_DIR = CLAUDE_DIR / "skills"
MCP_TEMPLATE = CLAUDE_DIR / "mcp-servers.template.json"
TOOL_DOMAIN = "工具"
# audit source：VALID_SOURCES 內最貼切者——把外部 SoT（skills 索引／MCP 樣板／tools 目錄）同步進記憶
SCAN_SOURCE = "tool:sync-memory-index"
_STATUS_RE = re.compile(r"^- Status:\s*(.*)$", re.MULTILINE)
_DEPENDS_RE = re.compile(r"^- Depends:\s*(.+)$", re.MULTILINE)


def _write_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _sync_catalog(mem: Path) -> str:
    """MEMORY.md atom-catalog 區塊交給 sync-memory-index 專案模式（marker upsert）。"""
    r = subprocess.run(
        [sys.executable, str(SYNC_INDEX), "--write", "--memory-dir", str(mem)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(f"sync-memory-index --write 失敗（exit {r.returncode}）：{r.stderr.strip()}")
    return "MEMORY.md atom-catalog 區塊已同步"


def init_tree(root: Path, user: str) -> List[str]:
    """佈 <root>/.claude 記憶樹（純檔案系統，不碰 ~/.claude）。回逐項訊息。"""
    mem = root / ".claude" / "memory"
    done: List[str] = []

    decl = root / ".claude" / "project-tree.json"
    if not decl.exists():
        _write_lf(decl, json.dumps({"standalone": True}, ensure_ascii=False, indent=2) + "\n")
        done.append(f"建 {decl}")

    tax = mem / "shared" / "_taxonomy.json"
    if not tax.exists():
        _write_lf(tax, json.dumps(TAXONOMY, ensure_ascii=False, indent=2) + "\n")
        done.append(f"建 {tax}（Lv1：工具）")

    seed = mem / "shared" / "工具" / f"{SEED_NAME}.md"
    if not seed.exists():
        entry = str(Path(__file__).resolve())
        content = build_atom_content(
            title=SEED_NAME, scope="shared", confidence="[臨]", triggers=SEED_TRIGGERS,
            knowledge=[
                "[臨] 公司層記憶（org）＝這個 repo 的 .claude/memory；所有專案的 session 都看得到，"
                "寫入用 atom_write scope=org（落 shared/<Lv1>/，免 project_cwd）",
                "[臨] 工具卡四欄：Author=負責人、Source=進入點、Status=production|deprecated、"
                "Depends=path:進入點（進入點消失健檢自動標 stale）",
            ],
            actions=[
                "新機初始化：python ~/.claude/tools/org-memory.py --init <公司記憶 repo 的本機 checkout 路徑>",
                "查公司知識：python ~/.claude/tools/memory-search.py \"關鍵字\"",
            ],
            author=user, status="production", provenance=entry, depends=[f"path:{entry}"],
        )
        err = validate_atom_content(content)
        if err:
            raise RuntimeError(f"seed atom 不合規格：{err}")
        _write_lf(seed, content)
        atom_access.init_access(seed, source=SCAN_SOURCE)   # 與掃描器建卡一致：卡＋sidecar 一起落
        upsert_atom(mem, SEED_NAME, SEED_REL, SEED_TRIGGERS, scope="shared")
        done.append(f"種工具卡 {seed}")

    memory_md = mem / "MEMORY.md"
    if not memory_md.exists():
        _write_lf(memory_md, "# Atom Index — Org\n\n> 公司層記憶：所有專案看得到；寫入 `atom_write scope=org`。\n")
        done.append(f"建 {memory_md}")

    done.append(_sync_catalog(mem))
    return done


def register_in_config(root: Path) -> str:
    """config.json org_memory ← enabled=true, roots=[{id:org, root}]（其他鍵原位不動）。"""
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    org = cfg.get("org_memory") if isinstance(cfg.get("org_memory"), dict) else {}
    org["enabled"] = True
    org["roots"] = [{"id": "org", "root": str(root)}]
    cfg["org_memory"] = org
    _write_lf(CONFIG_PATH, json.dumps(cfg, ensure_ascii=False, indent=2) + "\n")
    return f"config.json org_memory.enabled=true roots=[{root}]"


def register_in_registry(root: Path) -> str:
    """project-registry.json 直接寫條目（不走 register_project：它要 cwd 已是專案）。"""
    slug = wg_core.cwd_to_project_slug(str(root))
    reg = wg_core._load_registry()
    entry = reg.setdefault("projects", {}).setdefault(slug, {})
    entry["root"] = str(root)
    entry["last_seen"] = wg_core._today()
    wg_core._save_registry(reg)
    return f"project-registry.json 登錄 {slug}"


def cmd_init(root_arg: str) -> int:
    root = Path(root_arg).expanduser().resolve()
    if not root.is_dir():
        print(f"[org-memory] 根目錄不存在：{root}（請先 checkout 公司記憶 repo）", file=sys.stderr)
        return 2
    if wg_core.find_vcs_root(root) is None:
        print(f"[org-memory] 警告：{root} 不在任何 git/svn 工作區內，記憶不會被 vcs-sync 自動上版控", file=sys.stderr)
    user = get_current_user()
    msgs = init_tree(root, user)
    msgs.append(register_in_config(root))
    msgs.append(register_in_registry(root))
    print("[org-memory] 完成：")
    for m in msgs:
        print(f"  - {m}")
    print("下一步：")
    print(f"  1. 把 {root / '.claude'} 提交上版控，其他同事 checkout 後各自跑同一行 --init")
    print("  2. 重啟 Claude Code（MCP 重載）；SessionStart 會多一行 [Org] 公司層 N 顆")
    print("  3. 寫公司知識：atom_write scope=org domain=<Lv1>；查：python ~/.claude/tools/memory-search.py \"關鍵字\"")
    return 0


# ─── --scan-tools：來源 → 卡片規格 ────────────────────────────────────────────

def _keywords(desc: str) -> List[str]:
    """說明文字按標點切段，取最多 3 段 2～20 字的片段當觸發關鍵字。"""
    out: List[str] = []
    for tok in re.split(r"[，,、/／（）()：:—;；\s\[\]「」。]+", desc or ""):
        tok = tok.strip()
        if 2 <= len(tok) <= 20 and tok not in out:
            out.append(tok)
        if len(out) == 3:
            break
    return out


def _card(name: str, kind: str, desc: str, *, entry: str, has_path: bool, run: str) -> Dict[str, object]:
    """卡名＝kind 前綴＋名稱（kind 為「工具」的專案腳本不加前綴）；觸發詞保留裸名，搜尋仍以工具名命中。"""
    card_name = name if kind == TOOL_DOMAIN else f"{kind}-{name}"
    triggers = [card_name, name, kind]
    triggers = [t for i, t in enumerate(triggers) if t not in triggers[:i]]
    triggers += [k for k in _keywords(desc) if k not in triggers]
    while len(triggers) < TRIGGER_MIN:
        triggers.append("工具卡")
    return {
        "name": card_name, "entry": entry, "has_path": has_path, "triggers": triggers,
        "desc": desc or "（來源未附說明）", "run": run,
    }


def _load_json(path: Path, label: str) -> Optional[dict]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"[org-memory] 略過 {label}：讀不到 {path}（{e}）", file=sys.stderr)
        return None


def collect_skill_cards() -> List[Dict[str, object]]:
    """skills/_skill_index.json 每個 skill 一張卡 skill-<name>；進入點＝skills/<dir>/SKILL.md。"""
    data = _load_json(SKILL_INDEX, "skills")
    if not data:
        return []
    cards = []
    for s in data.get("skills", []):
        name = s.get("name")
        if not name:
            continue
        entry = (SKILLS_DIR / (s.get("dir") or name) / "SKILL.md").resolve().as_posix()
        cards.append(_card(name, "skill", s.get("description", ""), entry=entry, has_path=True,
                           run=f"Claude Code 內呼叫 /{name}"))
    return cards


def collect_mcp_cards() -> List[Dict[str, object]]:
    """mcp-servers.template.json servers 每張卡 mcp-<name>；進入點＝entry_absolute 展開，否則 npm 套件名（無路徑 → 無 Depends）。"""
    data = _load_json(MCP_TEMPLATE, "mcp")
    if not data:
        return []
    cards = []
    for name, d in (data.get("servers") or {}).items():
        abs_entry = d.get("entry_absolute")
        if abs_entry:
            entry = Path(abs_entry.replace("{claude_dir}", str(CLAUDE_DIR))).resolve().as_posix()
        else:
            entry = d.get("npm_package") or name
        cards.append(_card(name, "mcp", d.get("description", ""), entry=entry, has_path=bool(abs_entry),
                           run=f"MCP server「{name}」由 hooks/ensure-mcp.py 依 mcp-servers.template.json 註冊，Claude Code 啟動即載入"))
    return cards


def _first_doc_paragraph(py: Path) -> str:
    try:
        doc = ast.get_docstring(ast.parse(py.read_text(encoding="utf-8-sig")))
    except (OSError, SyntaxError, ValueError):
        doc = None
    if not doc:
        return ""
    return " ".join(line.strip() for line in doc.strip().split("\n\n")[0].splitlines())


def collect_project_cards(root: Path) -> List[Dict[str, object]]:
    """<root>/.claude/tools/*.py 每檔一張卡；說明＝檔頭 docstring 第一段。"""
    cards = []
    for py in sorted((root / ".claude" / "tools").glob("*.py")):
        entry = py.resolve().as_posix()
        cards.append(_card(py.stem, TOOL_DOMAIN, _first_doc_paragraph(py), entry=entry, has_path=True,
                           run=f"python {entry} --help"))
    return cards


# ─── --scan-tools：寫卡（create-if-absent）與退役 ─────────────────────────────

def write_card(card: Dict[str, object], *, project_cwd: Path, owner: str, dry_run: bool) -> str:
    """缺卡才建；回一行訊息，「失敗」開頭表示該卡沒寫成（呼叫端據此 exit 1）。"""
    name = str(card["name"])
    triggers = list(card["triggers"])  # type: ignore[arg-type]
    loc = locate_atom(name, "shared", project_cwd=str(project_cwd), domain=TOOL_DOMAIN, mode="create",
                      allow_new_category=True, triggers=triggers)
    if not loc.ok and "Slug collision" in (loc.error or ""):
        # funnel 的撞名保護（例：專案 tools/memory.py 撞索引檔 MEMORY.md）：不是寫入失敗，改名要人拍板
        return f"略過 {name}：{loc.error.splitlines()[0]}（要登記請改名後重跑）"
    if not loc.ok:
        return f"失敗 {name}：{loc.error}"
    slug = loc.extra["slug"]
    if loc.path is not None:
        return f"已存在：{slug}"
    entry = str(card["entry"])
    content = build_atom_content(
        title=name, scope="shared", confidence="[臨]", triggers=triggers,
        knowledge=[f"[臨] {card['desc']}"], actions=[str(card["run"])],
        author=owner, status="production", provenance=entry,
        depends=[f"path:{entry}"] if card["has_path"] else None,
    )
    err = validate_atom_content(content)
    if err:
        return f"失敗 {slug}：{err}"
    target = Path(loc.extra["target_dir"]) / f"{slug}.md"
    if dry_run:
        return f"[dry-run] 將建立：{target}"
    res = write_raw(target, content, source=SCAN_SOURCE, op="tool-card")
    if not res.ok:
        return f"失敗 {slug}：{res.error}"
    idx = write_index(Path(loc.extra["index_dir"]), slug, loc.extra["create_rel_path"], triggers,
                      SCAN_SOURCE, scope="shared")
    if not idx.ok:
        return f"失敗 {slug}：索引 {idx.error}"
    atom_access.init_access(target, source=SCAN_SOURCE)
    return f"建立：{target}"


def deprecate_missing(mem_dir: Path, *, dry_run: bool) -> List[str]:
    """shared/工具/ 下 path 型 Depends 任一不存在的卡 → Status: deprecated（不刪卡；已 deprecated 不重寫）。"""
    msgs: List[str] = []
    for e in load_atom_index_json(mem_dir).get("atoms", []):
        rel = str(e.get("path") or "").replace("\\", "/")
        if f"/{TOOL_DOMAIN}/" not in rel:
            continue
        path = mem_dir.parent / rel  # index path 以 <root>/.claude 為根
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8-sig")
        dm = _DEPENDS_RE.search(text)
        if not dm:
            continue
        missing = [d["value"] for d in parse_depends(dm.group(1))
                   if d["type"] == "path" and d["value"] and not resolve_depends_path(d["value"]).exists()]
        if not missing:
            continue
        sm = _STATUS_RE.search(text)
        if sm and sm.group(1).strip() == "deprecated":
            continue
        if not sm:
            msgs.append(f"失敗 {e['name']}：無 Status 行，無法標 deprecated（進入點消失：{missing[0]}）")
            continue
        if dry_run:
            msgs.append(f"[dry-run] 將退役：{e['name']}（進入點消失：{missing[0]}）")
            continue
        res = write_raw(path, _STATUS_RE.sub("- Status: deprecated", text, count=1),
                        source=SCAN_SOURCE, op="meta-edit")
        msgs.append(f"退役：{e['name']}（進入點消失：{missing[0]}）" if res.ok else f"失敗 {e['name']}：{res.error}")
    return msgs


def cmd_scan_tools(project_arg: Optional[str], owner: Optional[str], dry_run: bool) -> int:
    owner = owner or get_current_user()
    jobs = []  # (標籤, 落點 root, 卡片清單)
    org_root = wg_core.org_memory_root()
    if org_root is not None and not (org_root / ".claude" / "memory").is_dir():
        print(f"[org-memory] org 根 {org_root} 尚未 --init，略過公司層", file=sys.stderr)
        org_root = None
    if org_root is not None:
        jobs.append(("org", org_root, collect_skill_cards() + collect_mcp_cards()))
    if project_arg:
        project = Path(project_arg).expanduser().resolve()
        if not (project / ".claude" / "memory").is_dir():
            print(f"[org-memory] --project {project} 沒有 .claude/memory，不是專案記憶根", file=sys.stderr)
            return 2
        jobs.append(("project", project, collect_project_cards(project)))
    if not jobs:
        print("[org-memory] 沒有可掃的落點：config 未啟用 org_memory，也沒給 --project", file=sys.stderr)
        return 2

    failed = 0
    for label, root, cards in jobs:
        tag = "；dry-run" if dry_run else ""
        print(f"[org-memory] scan-tools → {label} {root}（來源 {len(cards)} 個；owner={owner}{tag}）")
        msgs = [write_card(c, project_cwd=root, owner=owner, dry_run=dry_run) for c in cards]
        msgs += deprecate_missing(root / ".claude" / "memory", dry_run=dry_run)
        for m in msgs:
            print(f"  - {m}")
            if m.startswith("略過"):
                print(f"[org-memory] {m}", file=sys.stderr)
        failed += sum(1 for m in msgs if m.startswith("失敗"))
        changed = any(m.startswith(("建立", "退役")) for m in msgs)
        if changed:
            try:
                print(f"  - {_sync_catalog(root / '.claude' / 'memory')}")
            except RuntimeError as e:
                print(f"  - 失敗 catalog：{e}")
                failed += 1
    if failed:
        print(f"[org-memory] {failed} 項失敗（見上）", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="公司層記憶（org）初始化與工具卡掃描；完整參數以 --help 為準")
    ap.add_argument("--init", metavar="ROOT", help="把 ROOT（已 checkout 的公司記憶 repo 根）佈成公司層記憶並寫入 config／registry")
    ap.add_argument("--scan-tools", action="store_true",
                    help="掃 skills 索引與 MCP 樣板，缺的工具卡建到 org shared/工具/；進入點消失的卡標 deprecated")
    ap.add_argument("--project", metavar="ROOT", help="（搭 --scan-tools）另掃 ROOT/.claude/tools/*.py，卡落該專案 shared/工具/")
    ap.add_argument("--owner", metavar="USER", help="（搭 --scan-tools）卡的負責人 Author；預設目前登入的 AD 帳號")
    ap.add_argument("--dry-run", action="store_true", help="（搭 --scan-tools）只印會建／會退役哪些卡，不寫檔")
    args = ap.parse_args()
    if args.init:
        return cmd_init(args.init)
    if args.scan_tools:
        return cmd_scan_tools(args.project, args.owner, args.dry_run)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
