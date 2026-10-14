"""harness_text.py：從一則訊息取出「使用者本人打的字」（純函式；hooks 的權威判斷、UserPromptSubmit 入口剔 IDE 區塊、
Quote 與來源補填都用這一支，hooks 端 wg_core 只轉呼叫，不另存一份）。

harness 區塊＝下列標籤成對包住的內容：
- 標籤名完整比對（`<task-notification-example>` 不算），不分大小寫；標籤在引號外的 `>` 才結束，屬性值裡的 `>`、`/` 不算。
- 其他 Claude session 用 SendMessage 送來的 `<cross-session-message …>`：從開頭到第一個原樣 `</cross-session-message>`
  全部是同伴內容，裡面不解析任何標籤。依據（總控台 claude-2c 2026-10-12 實測）：Claude Code 只把同伴正文裡的
  `</cross-session-message>` 轉成 `<\\/cross-session-message>`，其他標籤（`</system-reminder>`、`<system-reminder>`、
  `</task-notification>`）原樣保留；所以第一個原樣閉合一定是真邊界，正文裡沒閉合的標籤也不能讓外層吃到字串尾。
- 其餘標籤巢狀照深度算；閉合標籤只結束和最內層同名的那一層，和最內層不同名的閉合標籤當內容（保守：不提早結束任何區塊）。
- 閉合標籤允許空白（`</task-notification >`）；自閉合標籤（引號外結尾是 `/`）只剔標籤本身。
- 沒閉合的區塊吃到字串尾：分不出後面哪段是使用者打的，寧可不認。
- 區塊外的孤立閉合標籤當普通文字留著（user_typed_text 會因為殘留標籤字樣整則不認）。
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

HARNESS_TAG_NAMES = (r"system-reminder|task-notification|cross-session-message|ide_[a-z_]+|command-name|"
                     r"command-message|command-args|local-command-stdout|browser_instruction")
IDE_TAG_NAMES = r"ide_[a-z_]+"
_PEER_TAG = "cross-session-message"
_TAG_RE = re.compile(r"<\s*(/?)\s*(" + HARNESS_TAG_NAMES + r")(?=[\s/>])", re.IGNORECASE)
_PEER_CLOSE_RE = re.compile(r"<\s*/\s*cross-session-message\s*>", re.IGNORECASE)
# 清理後還殘留的 harness 標籤字樣（開、閉，含同伴正文轉義的 `<\/名稱>`）：代表有區塊邊界被提早結束而漏出內容
_RESIDUE_TAG_RE = re.compile(r"<\s*\\?/?\s*(?:" + HARNESS_TAG_NAMES + r")(?=[\s/>])", re.IGNORECASE)
# 沒有標籤包住的系統通知標記行：這行起到訊息尾都是 harness 的說明與通知。只認自成一行的完整標記（不分大小寫，前後可空白）。
_SYSTEM_NOTIFICATION_RE = re.compile(r"^[ \t]*\[SYSTEM NOTIFICATION - NOT USER INPUT\][ \t]*\r?$",
                                     re.IGNORECASE | re.MULTILINE)
# hook 注入殘渣行（[Guardian:*] / [Atom:*] / [Session:Context] / [JIT:*] / [WG:*] 等 additionalContext 前綴，
# 允許行首空白、不分大小寫）：在空白折疊前逐行整行剔除，清理後的文字不會再被當成殘渣行。
HOOK_RESIDUE_LINE_RE = re.compile(
    r"^[ \t]*\[(?:Guardian|Atom|JIT|Session|Parallel|Workflow Guardian|WG|Role|AIDocs|"
    r"Context budget)[^\]]*\].*$",
    re.MULTILINE | re.IGNORECASE,
)


def _tag_end(text: str, i: int) -> Tuple[int, bool]:
    """從 i 往後找標籤結尾（引號外的 `>`）→ (結尾後一格, 是否自閉合)；找不到 → (字串長度, False)。"""
    quote, last = "", ""
    for j in range(i, len(text)):
        c = text[j]
        if quote:
            if c == quote:
                quote, last = "", c
        elif c in "\"'":
            quote = c
        elif c == ">":
            return j + 1, last == "/"
        elif not c.isspace():
            last = c
    return len(text), False


def strip_harness_blocks(text: str, repl: str = " ", only: Optional[str] = None) -> str:
    """剔掉 harness 區塊（規則見模組說明），每個區塊換成 repl。
    only：只剔最外層標籤名完整符合這個正則的區塊，其餘區塊原樣留著；巢狀與交錯照樣看所有 harness 標籤判斷，
    所以先用 only 剔一部分、再整則清理，和直接整則清理結果相同。"""
    if not text:
        return ""
    keep_re = re.compile(r"(?:" + only + r")\Z", re.IGNORECASE) if only else None
    out: List[str] = []
    stack: List[str] = []
    pos = 0          # 區塊外文字從哪裡開始
    seen_to = 0      # 已讀過的位置（標籤屬性、同伴正文裡的字不再當標籤）
    start, outer = 0, ""

    def block(end: int) -> str:
        return repl if keep_re is None or keep_re.match(outer) else text[start:end]

    for m in _TAG_RE.finditer(text):
        if m.start() < seen_to:
            continue
        closing, name = m.group(1) == "/", m.group(2).lower()
        end, self_closing = _tag_end(text, m.end())
        if name == _PEER_TAG and not closing and not self_closing:
            close = _PEER_CLOSE_RE.search(text, end)           # 同伴正文不解析：直接跳到第一個原樣閉合
            end = close.end() if close else len(text)
            seen_to = end
            if not stack:
                out.append(text[pos:m.start()])
                start, outer = m.start(), name
                out.append(block(end))
                pos = end
            continue
        seen_to = end
        if not stack:
            if closing:
                continue                              # 區塊外的孤立閉合標籤：普通文字
            out.append(text[pos:m.start()])
            start, outer = m.start(), name
            if self_closing:
                out.append(block(end))
                pos = end
            else:
                stack.append(name)
            continue
        if self_closing:
            continue
        if not closing:
            stack.append(name)
        elif name == stack[-1]:
            stack.pop()
            if not stack:
                out.append(block(end))
                pos = end
    out.append(block(len(text)) if stack else text[pos:])   # 沒閉合 → 吃到字串尾
    return "".join(out)


def peer_message_bodies(text: str) -> List[str]:
    """其他 session 用 SendMessage 送來的每個 `<cross-session-message …>…</cross-session-message>` 區塊的正文（去頭尾空白）。
    正文不解析標籤（同 strip_harness_blocks：直接跳到第一個原樣閉合）；沒閉合就吃到字串尾。給「派工訊息開回合」的判定用。"""
    out: List[str] = []
    if not text:
        return out
    for m in _TAG_RE.finditer(text):
        if m.group(1) == "/" or m.group(2).lower() != _PEER_TAG:
            continue
        end, self_closing = _tag_end(text, m.end())
        if self_closing:
            continue
        close = _PEER_CLOSE_RE.search(text, end)
        body = text[end:close.start()] if close else text[end:]
        if body.strip():
            out.append(body.strip())
    return out


def user_typed_text(prompt: str, keep_lines: bool = False) -> str:
    """使用者本人打的字：剔掉 harness 區塊、系統通知標記行之後的內容、hook 殘渣行，空白折一格
    （keep_lines=True 時保留換行、只折行內空白，給要逐句看的萃取與 Quote 用）。
    清理後若還殘留任何 harness 標籤字樣（含 `<\\/名稱>`）→ 整則不認，回空字串：代表有區塊被提早結束而漏出內容，
    使用者自己打了標籤字樣也一併不認（要他單獨重打）。空字串＝這則不是使用者的話。
    口令、糾正、豁免、使用者決策、不要記、停用、失敗萃取、Quote 只吃這個結果（先清理、再截長）。清兩次結果不變。"""
    if not prompt:
        return ""
    text = strip_harness_blocks(prompt)
    m = _SYSTEM_NOTIFICATION_RE.search(text)
    text = HOOK_RESIDUE_LINE_RE.sub(" ", text[:m.start()] if m else text)
    if _RESIDUE_TAG_RE.search(text):
        return ""
    if not keep_lines:
        return re.sub(r"\s+", " ", text).strip()
    lines = (re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines())
    return "\n".join(ln for ln in lines if ln)


# ─── 開工句（一次性 session 指示）樣板 ─────────────────────────────────────────
# 派給「這個 session」的角色、工作步驟、派工單路徑只在這次有效，不是跨專案知識，也不是哪張卡片的「使用者原話」。
# 兩個用途、兩種嚴格度（同一套樣板）：
#   session_directive_reason：萃取器用（hooks/user-extract-worker.py）。整則每個子句都整句對上樣板才算，
#     有一個子句對不上就交 LLM，因為開工句裡夾的真決策不能被丟掉。
#   is_kickoff_prompt：Quote 自動填用（hooks/wg_provenance.py）。上面那條成立就算；或第一個子句整句是角色句
#     （「你是…工作 session <名>」，後面可帶任何括號說明），而且後面至少還有一個子句整句對上其他樣板
#     （總控台、第一步 EnterWorktree、派工 prompt 位置…）。角色句的括號說明（全形半形）與「對人總控台是 X、
#     調度總控台是 Y」這類變體不在嚴格樣板裡，這裡容許；以引號開頭的引用討論（「『你是工作 session x，總控台是 y。』
#     這兩句是範本」）只認嚴格判定、問句（「你是工作 session x 嗎？」）不算，照填 Quote。
# 子句界：句號、逗號、分號、問號、驚嘆號、換行、英文句點加空白；頓號不切；括號裡的逗號不切（樣板含括號註記）。
# 樣板以 skills/console/references/kickoff.md 的實際句型為底（角色、總控台、第一步 EnterWorktree、派工 prompt 位置、
# 讀完照做、讀寫範圍、交付、只跑目標 verify、開工前先 SendMessage），可擴充；名稱與路徑是欄位，不綁 v6 專名。
# 欄位（路徑、名稱、分支）只收 ASCII：吃不下的字（中文、頓號後的另一段話）留在子句裡，整句就對不上、交 LLM，
# 不會被欄位吞掉。兩個例外是原設計者的一般開工句型：角色句「接手「<名稱>」的（根層）總控端／總控台」名稱收中文與全形引號，
# 派工子句「先讀 <路徑> 全文」路徑收中文字（接續單檔名多是中文），兩者仍整句比對。
# 角色句後面的括號說明只認 _ROLE_NOTES 這份固定完整句型（從實際開過的開工句收集）；清單外的括號內容當未匹配的殘餘，
# 整則交 LLM（不靠字數、不靠決策關鍵字）。新的派工說明要被攔，就把那句加進清單。
_PATH = r"(?:[A-Za-z]:[\\/]|~[\\/]|/)[A-Za-z0-9_.~:\\/-]*"
_PATH_WIDE = r"(?:[A-Za-z]:[\\/]|~[\\/]|/)[\w.~:\\/-]*"          # 「先讀 <路徑> 全文」專用：\w 含中文字，仍不收空白與標點
_NAME = r"[A-Za-z0-9_.-]+"
_QUOTED_NAME = r"「[^「」\n]{1,40}」"                               # 「接手「<名稱>」的總控端」專用：名稱收中文
_ROLE_NOTES = (
    re.escape("需求目標核心流程設計單，只設計不寫程式"),   # track-goal
    re.escape("閱讀路徑掃描器"),                           # track-g12
    re.escape("獨立實跑驗證"),                             # track-verify
    r"接手，前一個\s*" + _NAME + r"\s*session\s*已滿",     # 接手 session
)
_ROLE_NOTE = r"(?:\s*（(?:" + "|".join(_ROLE_NOTES) + r")）)?"
_BRANCH_NOTE = r"(?:\s*（(?:分支\s*[A-Za-z0-9_./-]+|detached)(?:，\s*已存在)?(?:，\s*不要新建)?）?)?"
# 角色開場（不含括號說明）：嚴格樣板的 role 句與 Quote 端的開場判定共用
_ROLE_OPENERS = (
    r"(?:你是|妳是)\s*(?:v[0-9A-Za-z.]+\s*的\s*)?工作\s*session(?:\s*" + _NAME + r")?",
    r"請接手\s*(?:本次\s*)?(?:的\s*)?工作\s*session(?:\s*" + _NAME + r")?",
    r"for this session|act as\s+" + _NAME + r"|you are (?:the |a )?" + _NAME + r"\s+session",
    r"接手\s*" + _QUOTED_NAME + r"\s*的\s*(?:根層\s*)?(?:總控端|總控台)",
)
KICKOFF_CLAUSES = tuple((name, re.compile(pat, re.IGNORECASE)) for name, pat in (
    ("role", _ROLE_OPENERS[0] + _ROLE_NOTE),
    ("role", _ROLE_OPENERS[1]),
    ("role", _ROLE_OPENERS[2]),
    ("role", _ROLE_OPENERS[3]),
    ("controller", r"(?:總控台|主控台)\s*(?:是|為)\s*" + _NAME),
    ("step", r"第一步(?:用|先)?\s*EnterWorktree\s*切進\s*(?:worktree\s*)?(?:" + _PATH + r")?" + _BRANCH_NOTE),
    ("step", r"worktree\s*" + _PATH + _BRANCH_NOTE),
    ("dispatch", r"派工(?:單|\s*prompt)\s*(?:在|:|：)\s*" + _PATH),
    ("dispatch", r"(?:用絕對路徑)?讀完(?:全文)?照做"),
    ("dispatch", r"先讀\s*" + _PATH_WIDE + r"\s*全文"),
    ("dispatch", r"read the task at\s+" + _PATH),
    ("scope", r"(?:本次)?(?:一律)?只(?:讀|讀寫|在)\s*" + _PATH + r"(?:\s*(?:裡|內))?(?:\s*(?:讀寫|工作))?"),
    ("scope", r"you must work only in\s+" + _PATH),
    ("scope", r"(?:切進去之後)?所有讀寫一律用\s*worktree\s*(?:的\s*)?絕對路徑(?:、\s*不碰\s*live(?:\s*" + _PATH + r")?)?"),
    ("deliver", r"交付(?:信)?(?:用\s*SendMessage\s*(?:全文)?(?:\s*給\s*" + _NAME + r")?)?(?:\s*附\s*live\s*未動證明)?"),
    ("verify", r"只跑目標\s*verify(?:（直接在\s*worktree\s*根跑\s*pytest，\s*不加\s*cd）)?(?:、\s*不跑全量)?"
               r"(?:、\s*不重掛\s*Monitor)?(?:、\s*不輪詢)?"),
    ("ack", r"開工前先\s*SendMessage\s*" + _NAME + r"\s*一句「\s*" + _NAME + r"?\s*收到開工\s*」?"),
))
# 角色句整句（後面可帶任一個不巢狀的括號說明，全形半形都認）
_ROLE_OPENER_RE = re.compile(r"(?:" + "|".join(_ROLE_OPENERS) + r")(?:\s*[（(][^（）()]*[）)])?", re.IGNORECASE)
_QUOTE_OPENERS = "「『“\"'"
_CLAUSE_BREAKS = "。，,；;！？!?\n"
_CLAUSE_PAD = " \t\r\n「」『』“”\"'…"


def kickoff_clauses(text: str) -> List[str]:
    """切子句（括號裡的逗號不切；英文句點後接空白才切），去掉頭尾空白與引號。"""
    parts, buf, depth = [], [], 0
    for i, c in enumerate(text):
        if c in "（(":
            depth += 1
        elif c in "）)" and depth:
            depth -= 1
        period = c == "." and i + 1 < len(text) and text[i + 1].isspace()
        if depth == 0 and (c in _CLAUSE_BREAKS or period):
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    parts.append("".join(buf))
    stripped = (p.strip(_CLAUSE_PAD) for p in parts)
    return [p for p in stripped if p]


def kickoff_clause_kind(clause: str) -> Optional[str]:
    return next((name for name, pat in KICKOFF_CLAUSES if pat.fullmatch(clause)), None)


def session_directive_reason(prompt: str) -> Optional[str]:
    """每個子句都整句對上一次性派工樣板 → 對上的樣板名（"role+controller+step" 這種）；有任何子句對不上 → None（交 LLM）。"""
    kinds: List[str] = []
    for clause in kickoff_clauses(prompt or ""):
        kind = kickoff_clause_kind(clause)
        if kind is None:
            return None
        if kind not in kinds:
            kinds.append(kind)
    return "+".join(kinds) if kinds else None


def is_kickoff_prompt(prompt: str) -> bool:
    """Quote 自動填用：這則是開工句 → 不當使用者原話。session_directive_reason 成立；或第一個子句整句是角色句
    （可帶括號說明）且後面至少一個子句整句對上非角色樣板。"""
    if session_directive_reason(prompt):
        return True
    if (prompt or "").lstrip()[:1] in _QUOTE_OPENERS:
        return False   # 以引號開頭＝在引用開工句（例：「『你是…』這句不該填」）；整則都是樣板才算，上面嚴格判定已管
    clauses = kickoff_clauses(prompt or "")
    if not clauses or not _ROLE_OPENER_RE.fullmatch(clauses[0]):
        return False
    return any(kickoff_clause_kind(c) not in (None, "role") for c in clauses[1:])
