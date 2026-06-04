#!/usr/bin/env python3
"""refile_classify.py — /refile 的 deterministic 引擎：輸入護欄 + 核心檔辨識 + 分類提議 + doc-ref 掃描。

設計：把「能用邏輯判定」的三段護欄全收進本檔（skill-creator「邏輯優先於語意」），
SKILL.md 只負責互動編排（取使用者確認、挑工具搬檔）。復用 realm 分類引擎：
  classify_realm（詞庫 + py-only learned）→ miss → llm_classify_realm（Ollama，Fail-safe 四態）。

子命令:
  classify <path>      分析單一 .md：回 verdict ∈
                         already_archived | not_found | core_file | classify
  docrefs  <old_rel>   搬移後掃人面向說明文件是否仍含舊 path/檔名引用（advisory）。

輸出 JSON 到 stdout (UTF-8)，錯誤到 stderr。exit 0 = 成功，1 = 業務失敗，2 = 內部錯誤。
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from pathlib import Path

# Windows Python 預設 cp950 stdout 中文會亂碼 → 強制 UTF-8（必備）
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

CLAUDE_DIR = Path.home() / ".claude"
for _p in (CLAUDE_DIR, CLAUDE_DIR / "tools"):  # lib.* + realm_llm_classify / ollama_client 可 import
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.atom_locations import (  # noqa: E402
    GLOBAL_MEMORY_DIR, LOCAL_ATOMS_REL,
    classify_realm, enumerate_local_paths, load_learned_lexicon,
)
from lib.atom_index_json import load_atom_index_json  # noqa: E402

# ─── 核心/設定檔辨識訊號（SoT；plan §2 核心檔辨識護欄）─────────────────────────
# 記憶系統 bootstrap / 設定集：命中即「不搬」。protected slug 與 bootstrap 鏈引用另判。
_CORE_EXACT_BASENAMES = frozenset({
    "CLAUDE.md", "MEMORY.md", "Architecture.md",
    "settings.json", "settings.local.json",
})
_CORE_GLOB_BASENAMES = ("IDENTITY*.md", "USER*.md", "SPEC_ATOM*.md")
# bootstrap 鏈：CLAUDE.md @import 鏈 + 自動載入規則（memory/ 內檔被這些引用＝核心）
_BOOTSTRAP_CHAIN_REL = (
    "CLAUDE.md", "IDENTITY.md", "USER.md", "memory/MEMORY.md", "rules/core.md",
)
# 報告用：掃這些索引文件找候選檔的關聯（agent 據此推導角色/子系統）
_INDEX_DOCS_REL = ("_AIDocs/_INDEX.md", "_AIDocs/DocIndex-System.md", "_AIDocs/Architecture.md")


def _rel(p: Path) -> str:
    """絕對/相對路徑 → 相對 CLAUDE_DIR 的 POSIX rel；不在樹下則回 resolve 後 POSIX。"""
    try:
        return p.resolve().relative_to(CLAUDE_DIR.resolve()).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8-sig")
    except OSError:
        return ""


def _index_entry_by_stem(stem: str) -> dict | None:
    try:
        data = load_atom_index_json(GLOBAL_MEMORY_DIR)
    except (OSError, ValueError):
        return None
    for a in data.get("atoms", []):
        if a.get("name") == stem:
            return a
    return None


def _core_file_signals(rel: str, basename: str, stem: str) -> list[str]:
    """回命中的核心檔訊號清單（空＝非核心檔）。多訊號可同時命中。"""
    sig: list[str] = []
    if basename in _CORE_EXACT_BASENAMES:
        sig.append(f"bootstrap/設定集精確檔名：{basename}")
    if any(fnmatch.fnmatch(basename, g) for g in _CORE_GLOB_BASENAMES):
        sig.append(f"bootstrap/設定集樣式檔名：{basename}")
    parts = rel.split("/")
    if "rules" in parts and basename.endswith(".md"):
        sig.append("rules/*.md（自動載入規則）")
    if "_meta" in parts and basename.endswith(".json"):
        sig.append("_meta/*.json（系統設定）")
    # protected slug（核心保護清單硬擋；先於 LLM）
    if classify_realm(stem, []).get("protected"):
        sig.append(f"核心保護清單命中 slug：{stem}")
    # memory/ 內被 bootstrap 鏈引用
    if rel.startswith("memory/"):
        for b in _BOOTSTRAP_CHAIN_REL:
            txt = _read(CLAUDE_DIR / b)
            if txt and basename in txt:
                sig.append(f"被 bootstrap 鏈引用：{b}")
                break
    return sig


def _index_doc_hits(basename: str, stem: str) -> list[str]:
    """掃索引文件找候選檔的提及（供 agent 推導關聯子系統）。回命中的 doc rel。"""
    hits: list[str] = []
    for rel in _INDEX_DOCS_REL:
        txt = _read(CLAUDE_DIR / rel)
        if txt and (basename in txt or stem in txt):
            hits.append(rel)
    return hits


def _extract_triggers(text: str) -> list[str]:
    """從 atom frontmatter 抽 `- Trigger:` 行（逗號分隔）；無則 []。"""
    m = re.search(r"^\s*-?\s*Trigger:\s*(.+)$", text, re.MULTILINE)
    if not m:
        return []
    return [t.strip() for t in m.group(1).split(",") if t.strip()]


def _looks_like_atom(text: str) -> bool:
    """atom 型知識（有 Trigger/Confidence frontmatter）vs TODO/transcript/散文。"""
    head = "\n".join(text.splitlines()[:40])
    return bool(re.search(r"^\s*-?\s*(Trigger|Confidence):", head, re.MULTILINE))


def _load_config() -> dict:
    try:
        return json.loads((CLAUDE_DIR / "workflow" / "config.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def classify(path_arg: str) -> dict:
    """單一 .md 分析 → verdict（plan §三段護欄的可程式化部分）。"""
    p = Path(path_arg).expanduser()
    if not p.is_absolute():
        p = (CLAUDE_DIR / path_arg).resolve()
    rel = _rel(p)
    basename = p.name
    stem = p.stem

    # 護欄 1：已在 atom 物理區 → 拒（已歸檔）
    if rel.startswith(LOCAL_ATOMS_REL + "/"):
        return {"status": "ok", "verdict": "already_archived", "rel": rel,
                "msg": f"已在 {LOCAL_ATOMS_REL}/ 下，無需 refile"}

    if not p.exists() or not p.is_file():
        return {"status": "ok", "verdict": "not_found", "rel": rel,
                "msg": f"檔案不存在或非檔案：{path_arg}"}

    text = _read(p)

    # 護欄 2：核心/設定檔辨識（關鍵；命中即不搬）
    sigs = _core_file_signals(rel, basename, stem)
    if sigs:
        return {"status": "ok", "verdict": "core_file", "rel": rel, "basename": basename,
                "stem": stem, "signals": sigs, "index_doc_hits": _index_doc_hits(basename, stem),
                "is_indexed_atom": _index_entry_by_stem(stem) is not None,
                "msg": "偵測為記憶系統核心/設定檔，不搬"}

    # 護欄 3：分類提議（詞庫 → miss → LLM；Fail-safe 四態）
    entry = _index_entry_by_stem(stem)
    triggers = entry.get("triggers", []) if entry else _extract_triggers(text)
    learned = load_learned_lexicon()
    lex = classify_realm(stem, triggers, extra_lexicon=learned or None)

    result = {
        "status": "ok", "verdict": "classify", "rel": rel, "basename": basename, "stem": stem,
        "is_indexed_atom": entry is not None,
        "indexed_realm": ("local" if (entry and entry.get("path", "").startswith(LOCAL_ATOMS_REL + "/"))
                          else "core") if entry else None,
        "looks_like_atom": _looks_like_atom(text),
        "triggers": triggers,
    }

    if lex.get("realm") == "local":  # 詞庫命中（deterministic，免 LLM）
        result.update({"classify_source": "lexicon", "proposed_realm": "local",
                       "proposed_domain": lex.get("domain"), "matched": lex.get("matched", []),
                       "confidence": 1.0, "reason": "詞庫命中實例專屬詞"})
        return result

    # 詞庫 miss（unknown core）→ 喚 LLM
    try:
        from realm_llm_classify import llm_classify_realm
        llm = llm_classify_realm(stem, triggers, text, enumerate_local_paths(), _load_config())
    except Exception as e:  # import/執行例外 → 視同基礎設施失敗（defer）
        result.update({"classify_source": "llm_error", "proposed_realm": "defer",
                       "reason": f"LLM 引擎不可用：{str(e)[:120]}"})
        return result

    realm = llm.get("realm")
    cfg = _load_config().get("realm", {}).get("llm_fallback", {})
    min_conf = cfg.get("min_confidence", 0.7)
    if realm == "error":
        proposed = "defer"  # 基礎設施失敗 → 留原地，下次再試（不誤降級）
    elif realm == "core":
        proposed = "core"
    elif realm == "local" and llm.get("confidence", 0.0) >= min_conf:
        proposed = "local"
    else:  # unsure / 低信心
        proposed = "else"
    result.update({
        "classify_source": "llm", "proposed_realm": proposed,
        "proposed_domain": llm.get("domain_path") if proposed in ("local", "else") else None,
        "confidence": llm.get("confidence", 0.0), "terms": llm.get("terms", []),
        "reason": llm.get("reason", ""), "llm_realm": realm, "min_confidence": min_conf,
    })
    return result


# ─── 移檔後 doc-ref 掃描（鏡像 wg_atoms._scan_doc_refs；單檔版）──────────────────


def _doc_scan_targets() -> list[Path]:
    """人面向說明文件：_AIDocs/（排除 atom 物理區 Failures/_atoms）＋根 README/TECH。"""
    docs: list[Path] = []
    aidocs = CLAUDE_DIR / "_AIDocs"
    if aidocs.is_dir():
        for p in aidocs.rglob("*.md"):
            rel = p.relative_to(CLAUDE_DIR).as_posix()
            if rel.startswith("_AIDocs/Failures/") or rel.startswith("_AIDocs/_atoms/"):
                continue
            docs.append(p)
    for fn in ("README.md", "TECH.md"):
        p = CLAUDE_DIR / fn
        if p.exists():
            docs.append(p)
    return docs


def docrefs(old_rel: str) -> dict:
    """搬移後掃舊 path/檔名殘留引用。回 {hits: [doc rel...]}（advisory only）。"""
    old_rel = old_rel.replace("\\", "/").lstrip("/")
    fname = old_rel.rsplit("/", 1)[-1] if old_rel else ""
    hits = sorted({
        p.relative_to(CLAUDE_DIR).as_posix()
        for p in _doc_scan_targets()
        if (old_rel and old_rel in _read(p)) or (fname and fname in _read(p))
    })
    return {"status": "ok", "old_rel": old_rel, "filename": fname, "hits": hits}


def main():
    p = argparse.ArgumentParser(description="/refile deterministic 引擎")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("classify", help="分析單一 .md → verdict")
    c.add_argument("path", help="目標 .md 路徑（絕對或相對 ~/.claude）")
    d = sub.add_parser("docrefs", help="搬移後掃舊 path/檔名引用")
    d.add_argument("old_rel", help="搬移前的 rel path（相對 ~/.claude）")
    args = p.parse_args()

    try:
        result = classify(args.path) if args.cmd == "classify" else docrefs(args.old_rel)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        sys.exit(0 if result.get("status") == "ok" else 1)
    except Exception as e:
        print(json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
