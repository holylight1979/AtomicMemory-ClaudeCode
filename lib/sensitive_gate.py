"""sensitive_gate.py — 個人隱私敏感資訊的判定：寫到驗證或隱私資訊的記憶卡要進 memory/personal/<user>/secret/。

做什麼：
  secret/ 不進版控、不送向量、觸發詞照常注入；其他個人卡（工作偏好）照常進版控。程式分兩級把關：
  - 真實值（SECRET_VALUE_RE，機器格式的 token、私鑰）：判定不靠人，secret/ 以外一律不准寫、不准上版控。
  - 字眼（SENSITIVE_WORD_RE）：是不是個人敏感交給寫卡的 AI 判，一般技術知識也會提到，
    所以命中只要求宣告（secret=true 或 not_sensitive=<理由>），不直接擋死。
  - secret 側（check_secret_write）：secret=true 的卡整張沒命中隱私字眼不收；知識段只有部分行命中要拆成兩張；
    帶 secret_reason=<理由> 可整張收（留稽核）。
誰在用：atom_io（寫檔前）、atom_io_cli 的 sensitive_check（MCP atom_write）、wg_vcs_sync（commit 前）、
  extract-worker（背景萃取沒人能判，命中就不寫）、provenance（自動回填的使用者原話，命中就不填）、
  health-weekly（週掃）、atom-heal、indexer。
只依賴 stdlib：hooks 以頂層模組載入、tools 以 lib.sensitive_gate 載入都要能跑。
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

SECRET_DIR_NAME = "secret"

SECRET_VALUE_RE = re.compile(
    r"glpat-[A-Za-z0-9_-]{16,}"
    r"|gh[pousr]_[A-Za-z0-9]{30,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{24,}"
    r"|AKIA[0-9A-Z]{16}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----"
)
SENSITIVE_WORD_RE = re.compile(
    r"密碼|passwords?\b|passwd|私鑰|金鑰|憑證|credentials?\b|api[_ -]?key|access[_ -]?token|private[_ -]?token"
    r"|身分證|手機號碼|信用卡|銀行帳號|住家地址|薪資"
    r"|\\\\[A-Za-z0-9][\w.-]*\\[^\s\\]+"          # 內網共用資料夾 \\host\share；\\.\pipe 不算
    r"|(?<![:\w/])//[A-Za-z0-9][\w.-]*/[\w$.-]+"  # 同一條路徑的正斜線寫法；https://host/path 不算
    r"|\b(?:192\.168|10\.\d{1,3})\.\d{1,3}\.\d{1,3}\b",   # 內網 IP
    re.IGNORECASE,
)
_SECRET_PATH_RE = re.compile(rf"(^|/)personal/[^/]+/{SECRET_DIR_NAME}/")


def is_secret_path(path: Any) -> bool:
    """路徑（相對或絕對、Path 或字串）在 personal/<user>/secret/ 底下。"""
    return bool(_SECRET_PATH_RE.search(str(path).replace("\\", "/")))


def secret_value_found(text: str) -> bool:
    return bool(SECRET_VALUE_RE.search(text or ""))


def sensitive_words(text: str) -> List[str]:
    """命中的字眼（小寫去重保序）。"""
    return list(dict.fromkeys(m.group(0).lower() for m in SENSITIVE_WORD_RE.finditer(text or "")))


def _flatten(fields: Dict[str, Any], keys: Iterable[str]) -> str:
    parts: List[str] = []
    for key in keys:
        value = fields.get(key)
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, list):
            parts.extend(str(v) for v in value)
    return "\n".join(parts)


def write_fields_text(fields: Dict[str, Any]) -> str:
    return _flatten(fields, ("title", "triggers", "knowledge", "actions", "provenance", "quote"))


def _has_reason(why: Any) -> bool:
    """理由要有字：空白、純標點不算。"""
    return isinstance(why, str) and len(re.sub(r"[\W_]", "", why)) >= 2


def _line_hits(line: str) -> List[str]:
    words = sensitive_words(line)
    if secret_value_found(line):
        words.append("真實值")
    return words


def secret_lines_report(fields: Dict[str, Any]) -> Dict[str, Any]:
    """secret 卡的逐行體檢：knowledge 哪幾行命中隱私（1 起算）、哪幾行沒有；其他欄位（標題、觸發詞、行動、來源、原話）有沒有命中。"""
    knowledge = fields.get("knowledge")
    if isinstance(knowledge, list):
        lines = [str(x) for x in knowledge]
    elif knowledge:
        lines = [str(knowledge)]
    else:
        lines = []
    hit = [i for i, ln in enumerate(lines, 1) if _line_hits(ln)]
    miss = [i for i, ln in enumerate(lines, 1) if i not in hit and ln.strip()]
    other = _flatten(fields, ("title", "triggers", "actions", "provenance", "quote"))
    return {"hit": hit, "miss": miss, "words": sensitive_words(" ".join(lines[i - 1] for i in hit)),
            "other_hit": bool(_line_hits(other))}


def check_secret_write(fields: Dict[str, Any], secret_reason: Any = None) -> Optional[str]:
    """secret=true 的卡過閘：整張沒有隱私字眼不收、一張卡只有部分行是隱私要拆。帶 secret_reason=<理由> 可整張收。
    回擋下的原因；放行回 None。訊息不複述內容裡的值。"""
    if _has_reason(secret_reason):
        return None
    rep = secret_lines_report(fields)
    if not rep["hit"] and not rep["other_hit"]:
        return ("secret=true 但內容沒有命中任何隱私字眼（密碼、金鑰、憑證、個資、內網位址、token 真實值）。"
                "放進 secret 的卡不跨機、編輯工具在一般範圍找不到，放錯比放對貴。判斷後重送："
                "真的是不想公開的內容 → 帶 secret_reason=\"<哪一句、什麼資訊>\"；只是工作判準或技術知識 → 拿掉 secret 照常寫。")
    if rep["hit"] and rep["miss"]:
        return (f"secret=true 但知識段只有第 {'、'.join(map(str, rep['hit']))} 行命中（{'、'.join(rep['words'][:5])}），"
                f"第 {'、'.join(map(str, rep['miss']))} 行沒有隱私內容。隱私與非隱私要拆開：命中的行帶 secret=true 另寫一張，"
                "其餘照常寫（原 scope）；整張確實都該藏 → 帶 secret_reason=\"<理由>\" 重送。")
    return None


def check_write(fields: Dict[str, Any], not_sensitive: Any = None) -> Optional[str]:
    """寫進 secret/ 以外的卡片內容過閘：回擋下的原因；放行回 None。訊息不複述內容裡的值。"""
    text = write_fields_text(fields)
    if secret_value_found(text):
        return ("內容含密碼或 token 的真實值，這次不寫檔。值本身別寫進卡，只寫放在哪；"
                "真的要留 → 帶 secret=true，落 personal/<user>/secret/。")
    words = sensitive_words(text)
    if not words or _has_reason(not_sensitive):
        return None
    return (f"內容提到「{'、'.join(words[:5])}」，可能是個人驗證或隱私資訊，這次不寫檔。判斷後重送："
            "是個人敏感資訊（帳密、金鑰、個資、內網位址、不想公開的內容）→ 帶 secret=true，落 personal/<user>/secret/"
            "（不進版控、不送向量，觸發詞照常注入）；只是一般技術知識 → 帶 not_sensitive=\"<一句理由>\" 照原路徑寫。")


def _scan_cli() -> int:
    """python -m lib.sensitive_gate scan：列本機每張 secret 卡的逐行體檢（本機終端看，不進任何報告）。"""
    import json
    from .atom_index_json import load_personal_rows
    from .atom_locations import CLAUDE_DIR, GLOBAL_MEMORY_DIR
    rows = [a for a in load_personal_rows(GLOBAL_MEMORY_DIR) if isinstance(a, dict) and is_secret_path(a.get("path", ""))]
    for a in rows:
        text = (CLAUDE_DIR / str(a["path"])).read_text(encoding="utf-8", errors="ignore")
        body = text.split("## 知識", 1)[1].split("## 行動", 1)[0] if "## 知識" in text else ""
        lines = [ln[2:] if ln.startswith("- ") else ln for ln in body.splitlines() if ln.strip()]
        rep = secret_lines_report({"title": a.get("name", ""), "triggers": a.get("triggers"), "knowledge": lines})
        if not rep["hit"] and not rep["other_hit"]:
            verdict = "無隱私字眼"
        elif rep["hit"] and rep["miss"]:
            verdict = "混雜"
        else:
            verdict = "ok"
        print(json.dumps({"atom": a.get("name"), "verdict": verdict, "hit": rep["hit"], "miss": rep["miss"],
                          "words": rep["words"][:5]}, ensure_ascii=False))
    print(f"SENSITIVE_SCAN DONE secret_cards={len(rows)}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(_scan_cli() if len(sys.argv) > 1 and sys.argv[1] == "scan" else 2)
