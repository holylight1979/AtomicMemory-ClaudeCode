#!/usr/bin/env python3
"""realm_llm_classify.py — 詞庫 miss 時喚本地 LLM 判 realm + 階層 domain（計畫 Phase B）。

複用 atom-heal 的 Ollama 樣板（_extract_json + get_client().generate(format="json")）。
**僅由 SessionEnd sweep（非熱路徑）與 /refile skill 呼叫；永不掛 server.js 寫入熱路徑。**

回傳 realm ∈ {local, core, unsure, error}：
  - error  ＝基礎設施失敗（連不到 backend / 空回應）→ caller **defer 留原地**（不誤降級）。
  - unsure ＝LLM 跑了但判不出 / 低信心 → caller 落 _AIDocs/_atoms/Else（catch-all）。
  - core   ＝LLM 確信跨專案核心 → caller 留 core。
  - local  ＝LLM 判本地範疇 → caller 搬 domain_path（已 canon）。

紅線：核心保護硬擋（protected name）由 caller 在喚 LLM 前先擋，故本模組不重判 protected。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

CLAUDE_DIR = Path.home() / ".claude"
for _p in (CLAUDE_DIR, CLAUDE_DIR / "tools"):  # lib.* + ollama_client 都要可 import
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from lib.atom_locations import (  # noqa: E402
    LOCAL_REALM_DEFAULT_DOMAIN, LOCAL_REALM_MAX_DEPTH,
    classify_realm, normalize_domain_path,
)

# 系統通用詞黑名單：learned 詞庫**絕不收**（核心 atom 滿是這些詞，收了會把核心誤殺成 local）。
_GENERIC_TERMS = (
    "server.js", "wg_", "hook", "atom_", "記憶系統", "memory", "guardian",
    "sweep", "index", "classify", "realm", "scope", "session", "config",
    "mcp", "trigger", "frontmatter", "atom",
)
_TERM_MIN_LEN = 2
_TERM_MAX = 5


def _extract_json(s: str) -> str:
    """剝 ```json``` 圍欄 + 取首個 {…}（本地 crack 模型常無視 format=json 而加圍欄）。
    對拍 atom-heal.py:_extract_json。"""
    s = (s or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    i, j = s.find("{"), s.rfind("}")
    return s[i:j + 1] if (i != -1 and j > i) else s


def _validate_terms(terms: Any) -> List[str]:
    """剔系統通用詞 / 過短 / 會誤殺 protected 的詞 → 回乾淨實例詞（lowercase，≤5）。"""
    out: List[str] = []
    for t in (terms or []):
        tl = str(t).strip().lower()
        if len(tl) < _TERM_MIN_LEN:
            continue
        if any(g in tl for g in _GENERIC_TERMS):
            continue
        # 不收「自身當 name 即命中核心保護」的詞（避免 learned 反過來把核心判 local）
        if classify_realm(tl, []).get("protected"):
            continue
        if tl not in out:
            out.append(tl)
        if len(out) >= _TERM_MAX:
            break
    return out


def _build_prompt(name: str, triggers: List[str], content_excerpt: str,
                  existing_paths: List[str]) -> str:
    paths_str = "\n".join(f"  - {p}" for p in existing_paths) or "  （目前無既有 local 路徑）"
    trig = ", ".join(triggers or [])
    excerpt = (content_excerpt or "").strip()[:800]
    return (
        "判斷一個記憶 atom 屬「core（跨專案通用知識）」或「local（只在 ~/.claude 內有用："
        "記憶系統開發 / 特定外部工具 / 腦內世界 / 特定 OS·環境踩坑）」。\n\n"
        f"atom 名稱：{name}\n"
        f"觸發詞：{trig}\n"
        f"內容摘要：{excerpt}\n\n"
        "現有 local 階層路徑（**請優先複用既有層**，避免 OS/Win vs OS/Windows 分歧）：\n"
        f"{paths_str}\n\n"
        f"若判 local，給一條由粗到細的階層 domain 路徑（slash 分隔，最深 {LOCAL_REALM_MAX_DEPTH} 層）：\n"
        "- Lv1 最廣（如 OS / Tools / World / MemDev），逐層收斂到最具體。\n"
        "- **深 = 內容『量』多需細分，非內容細節多、非範疇廣**。新領域 / 上方路徑清單顯示該範疇"
        "還沒幾顆 atom → 給**較淺路徑（Lv2–3 足矣，如 OS/Windows/WSL）**；唯當既有路徑已顯示"
        "該窄範疇累積多顆 atom 才加深。寧淺勿深、預留長大空間。\n"
        "- 可複用上方既有層、或提議新層。\n"
        "再抽 2–5 個「實例專屬詞」（綁定該 atom 特定工具/環境的詞，"
        "**勿用 server.js/hook/記憶系統 等系統通用詞**）。\n\n"
        '只回 JSON：{"realm":"local|core|unsure",'
        '"domain_path":"<如 OS/Windows/WSL；core/unsure 給 null>",'
        '"terms":["..."],"confidence":0.0,"reason":"<簡短>"}'
    )


def llm_classify_realm(name: str, triggers: Optional[List[str]] = None,
                       content_excerpt: str = "", existing_paths: Optional[List[str]] = None,
                       config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """喚 LLM 判 realm + 階層 domain。回 {realm, domain_path, confidence, terms, reason}。

    realm="error"（基礎設施失敗）→ caller defer；其餘見模組 docstring。
    domain_path 於 realm=local 時已過 normalize_domain_path（canon 對既有樹 snap）。
    """
    triggers = list(triggers or [])
    existing_paths = list(existing_paths or [])
    prompt = _build_prompt(name, triggers, content_excerpt, existing_paths)

    try:
        from ollama_client import get_client
        raw = get_client().generate(prompt, timeout=60, format="json")
    except Exception as e:  # 連不到 backend / 模型錯誤 → 基礎設施失敗
        return {"realm": "error", "domain_path": None, "confidence": 0.0,
                "terms": [], "reason": f"LLM 不可用：{str(e)[:120]}"}
    if not (raw or "").strip():
        return {"realm": "error", "domain_path": None, "confidence": 0.0,
                "terms": [], "reason": "LLM 空回應"}

    try:
        obj = json.loads(_extract_json(raw))
        if not isinstance(obj, dict):
            raise ValueError("non-object")
    except (ValueError, TypeError) as e:
        # 有回應但解析不出 → unsure（非 error；歸 Else 而非 defer）
        return {"realm": "unsure", "domain_path": None, "confidence": 0.0,
                "terms": [], "reason": f"JSON 解析失敗：{str(e)[:100]}"}

    realm = str(obj.get("realm", "")).strip().lower()
    if realm not in ("local", "core", "unsure"):
        realm = "unsure"
    try:
        confidence = max(0.0, min(1.0, float(obj.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    terms = _validate_terms(obj.get("terms", []))
    reason = str(obj.get("reason", ""))[:200]

    domain_path = None
    if realm == "local":
        raw_dom = str(obj.get("domain_path") or "").strip()
        domain_path = (normalize_domain_path(raw_dom, existing_paths)
                       if raw_dom else LOCAL_REALM_DEFAULT_DOMAIN)

    return {"realm": realm, "domain_path": domain_path, "confidence": confidence,
            "terms": terms, "reason": reason}


# ─── CLI（手動 dogfood：對 index 內某 slug 跑分類，不落檔）────────────────────


def _classify_slug(slug: str) -> Dict[str, Any]:
    """讀 index 取 triggers/path + 讀內文摘要 → llm_classify_realm（dogfood/QA 用）。"""
    from lib.atom_index_json import load_atom_index_json
    from lib.atom_locations import GLOBAL_MEMORY_DIR, enumerate_local_paths
    data = load_atom_index_json(GLOBAL_MEMORY_DIR)
    entry = next((a for a in data.get("atoms", []) if a.get("name") == slug), None)
    if not entry:
        return {"realm": "error", "reason": f"atom not in index: {slug}"}
    md = CLAUDE_DIR / (entry.get("path") or "")
    excerpt = ""
    try:
        excerpt = md.read_text(encoding="utf-8-sig")
    except OSError:
        pass
    cfg = {}
    cfg_path = CLAUDE_DIR / "workflow" / "config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return llm_classify_realm(slug, entry.get("triggers", []), excerpt,
                              enumerate_local_paths(), cfg)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python tools/realm_llm_classify.py <atom-slug>", file=sys.stderr)
        return 2
    print(json.dumps(_classify_slug(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ─── 核心層範疇分類（閉合清單）— 程式寫手的 LLM fallback（lib.atom_locations.classify_category 喚）──

def _build_category_prompt(name: str, triggers: List[str], content_excerpt: str,
                           categories: List[str], layer: str) -> str:
    cats_str = "\n".join(f"  - {c}" for c in categories)
    trig = ", ".join(triggers or [])
    excerpt = (content_excerpt or "").strip()[:800]
    what = "失敗紀錄的主題範疇" if layer == "failures" else "記憶 atom 的範疇"
    return (
        f"判斷一則{what}。**只能從下列閉合清單選一個**，清單外一律回 unsure：\n"
        f"{cats_str}\n\n"
        f"atom 名稱：{name}\n"
        f"觸發詞：{trig}\n"
        f"內容摘要：{excerpt}\n\n"
        "再抽 2–5 個「實例專屬詞」（綁定該 atom 特定工具/環境的詞，"
        "**勿用 server.js/hook/記憶系統 等系統通用詞**）。\n\n"
        '只回 JSON：{"category":"<清單內正名或 unsure>","terms":["..."],'
        '"confidence":0.0,"reason":"<簡短>"}'
    )


def llm_classify_category(name: str, triggers: Optional[List[str]] = None,
                          content_excerpt: str = "", categories: Optional[List[str]] = None,
                          *, layer: str = "core",
                          config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """喚本地 LLM 從閉合清單選範疇。回 {status: hit|unsure|error, category, confidence, terms, reason}。

    status=error＝基礎設施失敗（連不到 backend／空回應）→ caller 拒寫並標 error（可延後重試）；
    unsure＝LLM 跑了但清單外／判不出／低信心 → caller 拒寫；hit＝category 在清單內
    （casefold 比對，回正名）；信心門檻由 caller（classify_category）依 config 裁。
    """
    triggers = list(triggers or [])
    categories = [str(c) for c in (categories or []) if str(c).strip()]
    if not categories:
        return {"status": "error", "category": None, "confidence": 0.0, "terms": [],
                "reason": "empty category list"}
    prompt = _build_category_prompt(name, triggers, content_excerpt, categories, layer)
    try:
        from ollama_client import get_client
        raw = get_client().generate(prompt, timeout=60, format="json")
    except Exception as e:  # 連不到 backend / 模型錯誤 → 基礎設施失敗
        return {"status": "error", "category": None, "confidence": 0.0, "terms": [],
                "reason": f"LLM 不可用：{str(e)[:120]}"}
    if not (raw or "").strip():
        return {"status": "error", "category": None, "confidence": 0.0, "terms": [],
                "reason": "LLM 空回應"}
    try:
        obj = json.loads(_extract_json(raw))
        if not isinstance(obj, dict):
            raise ValueError("non-object")
    except (ValueError, TypeError) as e:
        return {"status": "unsure", "category": None, "confidence": 0.0, "terms": [],
                "reason": f"JSON 解析失敗：{str(e)[:100]}"}
    try:
        confidence = max(0.0, min(1.0, float(obj.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    terms = _validate_terms(obj.get("terms", []))
    reason = str(obj.get("reason", ""))[:200]
    raw_cat = str(obj.get("category") or "").strip()
    canon = next((c for c in categories if c.casefold() == raw_cat.casefold()), None)
    if canon is None:
        return {"status": "unsure", "category": None, "confidence": confidence, "terms": terms,
                "reason": f"清單外：{raw_cat!r}" if raw_cat and raw_cat.lower() != "unsure" else (reason or "unsure")}
    return {"status": "hit", "category": canon, "confidence": confidence, "terms": terms,
            "reason": reason}
