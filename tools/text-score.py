#!/usr/bin/env python3
"""text-score.py：照文字規格（text-specs/<代號>.md）逐條問開源免費的小模型裁判，產出評分表並留帳（G15）。

做什麼：
  讀規格（規格是資料：代號、適用、讀者、讀者目的、通過線、檢核項表、判例表；程式不寫死任何條目）
  → 去掉開頭 --- 檔頭、code 區塊與網址 → 每條檢核項各問裁判一次；判法欄寫了「程式切出…」「抓候選詞」的先由程式切範圍
  → 裁判回 {quote, reason, verdict}；程式校驗引用逐字在送去的那段原文裡，對不到、判否沒附引用、輸入被截斷 → 該條作廢
  → 分數由程式算（是＝過；不適用不算沒過、不進分母），印評分表與一行摘要 `評分 N/M｜沒過：…`，留帳 Logs/guard-text_score.jsonl。
  規格的 `- 目標: {{goal}}` 與條目問題裡的 {{goal}} 由 --goal 填當下的需求目標（收尾自動評時 hooks/wg_text_score 給：
  目標樹樹根，沒樹用本回合使用者原話）；規格用了 {{goal}} 卻沒給目標 → 印「不評」、不留帳。
裁判：照 tools/ollama_client 的 backend 優先序（內網 rdchat → 本地 ollama），每台用自己的裁判模型
  （text_score.judge_model_by_backend，沒列到的用 judge_model；--model 給了全部用它；那台沒裝就算不在，不換成別的模型）。
  都不在或逾時 → 印「裁判不在，未評」、記一筆未評，exit 0；不擋、不改用付費模型。
怎麼跑：
  python tools/text-score.py <檔> --spec reader-designer
  python tools/text-score.py - --json < 回覆.txt                 # 讀 stdin；--json 印一行 JSON（再接尾行）
  python tools/text-score.py <檔> --auto-kind docs               # 自動評的入口：enabled／auto_targets（種類與路徑樣式）／min_chars 不符就印「不評」
  python tools/text-score.py - --tail-line --auto-kind final_reply < 回覆.txt   # stdout 只有摘要一行（每則尾巴取用）；不評時什麼都不印
尾行（--tail-line 不印）：`TEXT_SCORE DONE spec=<代號> pass=<n> fail=<n> na=<n> void=<n> unscored=<n> secs=<秒> logged=<0|1>`（數字是尺不是判決；
  logged=0＝留帳沒寫進去，原因在 stderr）。
exit：0 完成（含裁判不在、不評）；2 規格或原文讀不到、規格格式錯、原文是空的。完整參數以 --help 為準；規格寫法見 text-specs/README.md。
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CODE_DIR = Path(__file__).resolve().parents[1]   # 程式碼根：lib.*、ollama_client、text-specs 從本樹載
for _p in (CODE_DIR, CODE_DIR / "tools"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
from lib.project_root import claude_data_dir  # noqa: E402
import ollama_client  # noqa: E402

CLAUDE_DIR = claude_data_dir()   # 使用者資料根（WG_CLAUDE_DIR 或 ~/.claude）：config 與留帳
CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"
LOG_PATH = CLAUDE_DIR / "Logs" / "guard-text_score.jsonl"
SPEC_DIR = CODE_DIR / "text-specs"

DEFAULTS: Dict[str, Any] = {
    "enabled": True,                  # 只管 --auto-kind（自動評）；手動指令照跑
    "default_spec": "reader-designer",
    "judge_model": "gemma4:e4b",      # judge_model_by_backend 沒列到的 backend 用它
    "judge_model_by_backend": {       # 每台 backend 各自的裁判（各台裝得下、判得準的那個）
        "rdchat-direct": "gemma4:e4b",
        "local": "qwen3:4b-instruct-2507-q4_K_M",
    },
    "timeout_sec": 120,               # 每次問裁判的逾時
    "num_ctx": 8192,                  # 每次明帶；Ollama 預設 4096 會從前面靜默截掉
    "min_chars": 300,                 # 自動評的最短字數（去掉檔頭、code 與網址，不算空白）
    "reply_scope": "code_change",     # 收尾自動評哪些回覆（hooks/wg_text_score._reply_in_scope 讀；本工具不用）
    "auto_targets": {                 # 自動評的種類 → 來源路徑樣式；空清單＝不比路徑
        "final_reply": [],
        "docs": ["memory/_staging/*checklist*.md", "_AIDocs/DevHistory/**/*提案*.md"],
    },
}

NUM_PREDICT = 512        # 一條的回答（引用＋一句理由）用不到這麼多；防裁判停不下來
TRUNCATE_RATIO = 0.95    # prompt_eval_count ≥ num_ctx×95% 就當輸入太長（實測內網 Ollama 超過時回報整段長度，不一定截到 num_ctx）
MAX_ITEMS = 8            # 一份規格最多 8 條：指令越長小裁判越差（提案 Q13）
GOAL_SLOT = "{{goal}}"   # 規格裡由程式填入當下需求目標的位置
MAX_CANDIDATES = 12      # 候選詞最多送幾個
MIN_QUOTE_CHARS = 4      # 引用正規化後至少幾個字，太短對不出是哪一句

REQUIRED_KEYS = ("規格代號", "適用", "讀者", "讀者目的", "通過線", "維護")
ITEM_COLS = ("代號", "問題", "判法", "必過", "沒過時", "來源")
EXAMPLE_COLS = ("代號", "會判「是」", "會判「否」")
ON_FAIL = ("記帳", "提醒", "擋")
VERDICTS = ("是", "否", "不適用")

SCHEMA = {   # 欄位順序固定 引用 → 理由 → 判定（先寫判定會拉偏，提案 2.2）
    "type": "object",
    "properties": {
        "quote": {"type": "string"},
        "reason": {"type": "string"},
        "verdict": {"type": "string", "enum": list(VERDICTS)},
    },
    "required": ["quote", "reason", "verdict"],
}

# 條目專屬的字放最前面、原文放最後：每條的開頭不同，Ollama 就不會拿上一條的快取接著算（提案 4.5：換了前一個呼叫判定會翻）
PROMPT = """你是文字評審，照一條檢核項判斷「原文」，只回一個 JSON 物件。

{goal_block}檢核項 {id}：{question}
{extras}讀者：{reader}
讀者目的：{purpose}

作答規則：
1. quote：從原文區塊逐字抄出支撐判定的那一句（不改字、不加字、繁體不改成簡體；太長可用「…」省略中間）。只能抄原文區塊，不能抄檢核項或例子。判「否」一定要引用沒做到的那一句；判「不適用」留空字串。
2. reason：一句話說為什麼。
3. verdict：只能是「是」「否」「不適用」其中之一。
格式：{{"quote": "…", "reason": "…", "verdict": "是"}}

=====原文開始=====
{body}
=====原文結束====="""


class SpecError(ValueError):
    """規格檔讀不到或格式不對；訊息直接給人看。"""


@dataclass
class Item:
    id: str
    question: str
    method: str
    must: bool
    on_fail: str
    source: str
    scope: Tuple[str, int]          # ("full", 0)｜("first", N)｜("candidates", 0)
    good: str = ""
    bad: str = ""


@dataclass
class Spec:
    code: str
    path: Path
    sha: str
    keys: Dict[str, str]
    items: List[Item]
    allow_fail: int                 # 非必過項最多幾個「否」仍算過


@dataclass
class Result:
    id: str
    must: bool
    status: str                     # 判定｜作廢｜未評
    verdict: Optional[str] = None
    quote: str = ""
    reason: str = ""
    why: str = ""                   # 作廢／未評的原因
    secs: float = 0.0
    prompt_tokens: int = 0
    answer_tokens: int = 0


# ─── 規格 ─────────────────────────────────────────────────────────────────────

KEY_RE = re.compile(r"^-\s*([^:：]+?)\s*[:：]\s*(.+)$")
ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
SEP_CELL_RE = re.compile(r"^:?-+:?$")
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _cells(line: str) -> List[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _table(lines: List[str], cols: Tuple[str, ...], where: str) -> List[Dict[str, str]]:
    """表頭每欄以 cols 的字開頭就認；缺欄 → SpecError。回傳每列 {欄名: 值}。"""
    if not lines:
        raise SpecError(f"{where}：找不到表格")
    head = _cells(lines[0])
    idx = {}
    for col in cols:
        hit = [i for i, h in enumerate(head) if h.startswith(col)]
        if not hit:
            raise SpecError(f"{where}：表頭缺「{col}」欄（表頭是 {' | '.join(head)}）")
        idx[col] = hit[0]
    rows = []
    for line in lines[1:]:
        cells = _cells(line)
        if all(SEP_CELL_RE.match(c) for c in cells if c):
            continue
        cells += [""] * (len(head) - len(cells))
        rows.append({col: cells[i] for col, i in idx.items()})
    return rows


FIRST_N_RE = re.compile(r"程式切出前\s*([0-9]+|[一二三四五六七八九十])\s*句")
PASS_LINE_RE = re.compile(r"必過項全部「是」或「不適用」(?:，其餘「否」最多\s*(\d+)\s*個)?")


def parse_scope(method: str, where: str) -> Tuple[str, int]:
    """判法欄 → 程式先切的範圍；只認 README 列的四種寫法，其他一律 SpecError（寫錯不能默默變成整份）。"""
    bad = f"{where}：判法「{method}」看不懂；認得的寫法見 text-specs/README.md"
    if "模型判" not in method:
        raise SpecError(f"{where}：判法「{method}」沒有「模型判」；本工具只跑要問裁判的條目")
    if "→" not in method:
        if not method.startswith("模型判"):
            raise SpecError(bad + "（程式切法要寫在「→」前面，整份給裁判就寫「模型判」）")
        return ("full", 0)
    head, tail = (s.strip() for s in method.split("→", 1))
    if not tail.startswith("模型判"):
        raise SpecError(bad + "（「→」後面要是「模型判…」）")
    if head == "程式切出標題後的第一句":
        return ("first", 1)
    if head == "程式先抓候選詞":
        return ("candidates", 0)
    m = FIRST_N_RE.fullmatch(head)
    if not m:
        raise SpecError(bad)
    n = int(m.group(1)) if m.group(1).isdigit() else CN_NUM[m.group(1)]
    if n < 1:
        raise SpecError(bad)
    return ("first", n)


def parse_pass_line(line: str, where: str) -> int:
    m = PASS_LINE_RE.fullmatch(line.strip())
    if not m:
        raise SpecError(f"{where}：通過線要寫成「必過項全部「是」或「不適用」」，可加「，其餘「否」最多 K 個」；現在是「{line}」")
    return int(m.group(1)) if m.group(1) else 0


def parse_spec(path: Path) -> Spec:
    raw = path.read_bytes()
    keys: Dict[str, str] = {}
    sections: Dict[str, List[str]] = {}
    cur: Optional[str] = None
    for line in raw.decode("utf-8-sig").splitlines():
        s = line.strip()
        if s.startswith("## "):
            cur = s[3:].strip()
            sections[cur] = []
        elif cur is None:
            m = KEY_RE.match(s)
            if m:
                keys[m.group(1)] = m.group(2).strip()
        elif s.startswith("|"):
            sections[cur].append(s)
    name = path.name
    missing = [k for k in REQUIRED_KEYS if not keys.get(k)]
    if missing:
        raise SpecError(f"{name}：開頭缺「- 鍵: 值」：{'、'.join(missing)}")
    if keys["規格代號"] != path.stem:
        raise SpecError(f"{name}：規格代號「{keys['規格代號']}」要跟檔名 {path.stem} 相同")

    items: List[Item] = []
    for row in _table(sections.get("檢核項", []), ITEM_COLS, f"{name} 檢核項"):
        where = f"{name} {row['代號'] or '(空代號)'}"
        if not ID_RE.match(row["代號"]):
            raise SpecError(f"{where}：代號要是英文字母開頭的英數字")
        if any(it.id == row["代號"] for it in items):
            raise SpecError(f"{where}：代號重複")
        if not row["問題"]:
            raise SpecError(f"{where}：問題是空的")
        if row["必過"] not in ("必過", ""):
            raise SpecError(f"{where}：必過欄只能寫「必過」或留空，現在是「{row['必過']}」")
        if row["沒過時"] not in ON_FAIL:
            raise SpecError(f"{where}：沒過時只能是 {'／'.join(ON_FAIL)}，現在是「{row['沒過時']}」")
        if not row["來源"]:
            raise SpecError(f"{where}：沒有來源的條目不收（原話或 Failures 卡）")
        items.append(Item(row["代號"], row["問題"], row["判法"], row["必過"] == "必過", row["沒過時"], row["來源"],
                          parse_scope(row["判法"], where)))
    if not items:
        raise SpecError(f"{name}：檢核項表沒有任何一條")
    if len(items) > MAX_ITEMS:
        raise SpecError(f"{name}：檢核項 {len(items)} 條，超過上限 {MAX_ITEMS} 條")

    by_id = {it.id: it for it in items}
    if "判例" in sections:
        for row in _table(sections["判例"], EXAMPLE_COLS, f"{name} 判例"):
            it = by_id.get(row["代號"])
            if it is None:
                raise SpecError(f"{name} 判例：代號「{row['代號']}」不在檢核項表裡")
            it.good, it.bad = row["會判「是」"], row["會判「否」"]
    return Spec(keys["規格代號"], path, hashlib.sha256(raw).hexdigest()[:16], keys, items,
                parse_pass_line(keys["通過線"], name))


def spec_path(name: str) -> Path:
    if name.endswith(".md") or re.search(r"[\\/]", name):   # 給的是路徑就照路徑
        return Path(name)
    return SPEC_DIR / f"{name}.md"


def needs_goal(spec: Spec) -> bool:
    """規格有沒有用 {{goal}}（目標欄或任一條問題）。"""
    return GOAL_SLOT in str(spec.keys.get("目標") or "") or any(GOAL_SLOT in it.question for it in spec.items)


def with_goal(spec: Spec, goal: str) -> Spec:
    """把 {{goal}} 換成當下的需求目標，回新的規格（不動原物件）。"""
    import copy
    out = copy.deepcopy(spec)
    out.keys["目標"] = str(out.keys.get("目標") or "").replace(GOAL_SLOT, goal)
    for it in out.items:
        it.question = it.question.replace(GOAL_SLOT, goal)
    return out


def load_spec(name: str) -> Spec:
    path = spec_path(name)
    if not path.is_file():
        have = "、".join(sorted(p.stem for p in SPEC_DIR.glob("*.md")    # README 與 <規格>-說明.md 不是規格
                                if p.stem != "README" and not p.stem.endswith("-說明"))) or "（沒有）"
        raise SpecError(f"找不到規格 {path}；text-specs/ 現有：{have}")
    return parse_spec(path)


# ─── 原文：清理、切句、候選詞 ─────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)^---[ \t]*\r?$\n?", re.M | re.S)
KEY_LINE_RE = re.compile(r"[\w-]+[ \t]*:(?:[ \t]|$)")      # 「鍵: 值」：冒號後接空白或行尾（https:// 不算）
HEAD_LINE_RE = re.compile(r"[ \t]*(?:[\w-]+[ \t]*:(?:[ \t]|$)|-[ \t])")   # （可縮排的）鍵值或清單項；標題、縮排正文都不算
FENCE_RE = re.compile(r"^[ \t]*(```|~~~)[^\n]*\n.*?^[ \t]*\1[^\n]*$", re.M | re.S)
URL_RE = re.compile(r"https?://[A-Za-z0-9\-._~:/?#\[\]@!$&'*+,;=%]+")   # 只吃網址字元：中文句子裡網址後面常直接接「。」
LINE_PREFIX_RE = re.compile(r"^\s*(?:>\s*)*(?:#+\s+|[-*+]\s+|\d+[.)]\s+)?")   # 行首的引用、標題、清單符號
RULE_LINE_RE = re.compile(r"[|:\-\s]+")
SENT_RE = re.compile(r"[^。！？!?]*[。！？!?]+[」』”’）)]*|[^。！？!?]+$")
EN_STOP_RE = re.compile(r"(?<=[A-Za-z0-9)\]])\.\s+(?=[A-Z])")   # 英文句點後接空白與大寫才算句界；檔名、版本號裡的點不算
INLINE_RE = re.compile(r"`([^`\n]+)`")
_A = "A-Za-z0-9_"
CODE_TOKEN_RE = re.compile(   # 像代號的字：旗標、帶 . / : _ - 的名字、全大寫縮寫、字母夾數字；一般英文單字不算
    rf"(?<![{_A}./-])(--?[A-Za-z][{_A}-]*|[A-Za-z][{_A}]*(?:[./:_-][{_A}]+)+|[A-Z][A-Z0-9]+|[A-Za-z]+[0-9][{_A}]*)")


def strip_frontmatter(text: str) -> str:
    """去掉開頭的 --- 檔頭（信件的 to:／seq: 不是給讀者的話）：第一行是「鍵: 值」、框裡每一行都像檔頭才算；
    有一行正文就整段留著，寧可多評幾行也不吃掉正文。"""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return text
    lines = [ln.rstrip("\r") for ln in m.group(1).splitlines() if ln.strip()]
    if lines and KEY_LINE_RE.match(lines[0]) and all(HEAD_LINE_RE.match(ln) for ln in lines):
        return text[m.end():]
    return text


def clean_text(text: str) -> str:
    """去掉開頭的檔頭、code 區塊與網址（裁判不評程式碼）；inline code 留著，R3 這類條目要看它。"""
    return URL_RE.sub(" ", FENCE_RE.sub(" ", strip_frontmatter(text)))


def sentences(text: str) -> List[str]:
    """標題、表格分隔線、水平線不算句子；去掉引用符號與清單符號；句號、問號、驚嘆號與換行都是句界。"""
    out: List[str] = []
    for line in clean_text(text).splitlines():
        s = re.sub(r"^\s*(?:>\s*)*", "", line).strip()
        if not s or s.startswith("#") or RULE_LINE_RE.fullmatch(s):
            continue
        s = LINE_PREFIX_RE.sub("", s).strip()
        for part in EN_STOP_RE.sub(".\n", s).split("\n"):
            out.extend(p.strip() for p in SENT_RE.findall(part) if p.strip())
    return out


def candidates(text: str) -> List[str]:
    """inline code 整段＋其他地方像代號的字，依第一次出現排序、不分大小寫去重。"""
    found: List[Tuple[int, str]] = [(m.start(), m.group(1).strip()) for m in INLINE_RE.finditer(text)]
    rest = INLINE_RE.sub(lambda m: " " * len(m.group(0)), text)
    found += [(m.start(), m.group(1)) for m in CODE_TOKEN_RE.finditer(rest)]
    seen, out = set(), []
    for _, word in sorted(found):
        if word and word.lower() not in seen:
            seen.add(word.lower())
            out.append(word)
    return out[:MAX_CANDIDATES]


def scope_for(item: Item, body: str, sents: List[str]) -> Tuple[str, str]:
    """回傳 (送給裁判的原文, 加在題目後面的說明)。引用只對這段原文校驗。"""
    kind, n = item.scope
    if kind == "first":
        where = "標題後的第一句" if n == 1 else f"前 {n} 句"
        return "\n".join(sents[:n]), f"原文只給了程式切出的範圍：{where}（標題不算句子）。\n"
    if kind == "candidates":
        cands = candidates(body)
        if not cands:
            return body, "程式沒抓到像代號的詞；清單外的英文代號與自創名詞仍要看。\n"
        listed = "、".join(f"「{c}」" for c in cands)
        return body, f"程式從原文抓到這些像代號的詞（依第一次出現排序；清單外的英文代號與自創名詞也要看）：{listed}\n"
    return body, ""


def build_prompt(spec: Spec, item: Item, text: str, extras: str) -> str:
    examples = "".join(f"{label}的例子：{ex}\n" for label, ex in (("會判「是」", item.good), ("會判「否」", item.bad)) if ex)
    goal = str(spec.keys.get("目標") or "").strip()
    goal_block = (f"當下的需求目標：{goal}\n針對這個目標，下面這一條過不過？跟這個目標或這種回覆無關的條目答「不適用」"
                  "（不算沒過）。\n\n") if goal and GOAL_SLOT not in goal else ""
    return PROMPT.format(id=item.id, question=item.question, extras=extras + examples, goal_block=goal_block,
                         reader=spec.keys["讀者"], purpose=spec.keys["讀者目的"], body=text)


# ─── 裁判回答：解析、引用校驗 ─────────────────────────────────────────────────

MARK_RE = re.compile(r"[*`]")   # 粗體、斜體、inline code 記號；其他符號（> # | 等）在行中間就是原文的字
ELLIPSIS_RE = re.compile(r"\.{2,}|⋯+")
QUOTE_EDGE = "「」『』\"“”'‘’"
VERDICT_ALIASES = {
    "是": "是", "yes": "是", "y": "是", "true": "是", "pass": "是",
    "否": "否", "no": "否", "n": "否", "false": "否", "fail": "否",
    "不適用": "不適用", "n/a": "不適用", "na": "不適用", "not applicable": "不適用",
}


def _norm(s: str) -> str:
    """NFKC（全半形統一，「…」變成 ...，① 這類相容字也會變成 1）→ 每行去掉行首的引用、標題、清單符號
    → 去掉 * 與反引號 → 拿掉所有空白。引用與原文兩邊都這樣比。"""
    lines = (LINE_PREFIX_RE.sub("", ln) for ln in unicodedata.normalize("NFKC", s).splitlines())
    return re.sub(r"\s+", "", MARK_RE.sub("", "".join(lines)))


def quote_segments(quote: str) -> List[str]:
    """引用用省略號切段、各段正規化，去掉空段；字數、比對都用這組段。"""
    segs = ELLIPSIS_RE.split(unicodedata.normalize("NFKC", quote.strip().strip(QUOTE_EDGE)))
    return [s for s in (_norm(seg) for seg in segs) if s]


def quote_found(quote: str, text: str) -> bool:
    """引用逐字在原文裡：每段依序出現。不做相似度比對——裁判改寫過的句子就失去『指得回原文』的用處。"""
    hay, pos = _norm(text), 0
    segs = quote_segments(quote)
    for seg in segs:
        at = hay.find(seg, pos)
        if at < 0:
            return False
        pos = at + len(seg)
    return bool(segs)


def _first_json(content: str) -> Optional[Dict[str, Any]]:
    content = content.strip()
    start = content.find("{")
    if start < 0:
        return None
    try:
        obj, _ = json.JSONDecoder().raw_decode(content[start:])
    except json.JSONDecodeError:
        return None
    if isinstance(obj, dict) and len(obj) == 1 and isinstance(next(iter(obj.values())), dict):
        obj = next(iter(obj.values()))   # 另一種形狀：{"R3": {...}}
    return obj if isinstance(obj, dict) else None


def _pick(obj: Dict[str, Any], *names: str) -> Any:
    return next((obj[n] for n in names if n in obj), "")


def check_answer(item: Item, resp: Dict[str, Any], sent_text: str, truncated: bool) -> Result:
    """有附引用就一定要對得到（不分判定）；只有「否」非附引用不可。"""
    msg = resp.get("message")
    content = msg.get("content") if isinstance(msg, dict) else msg
    obj = _first_json(content if isinstance(content, str) else "")
    res = Result(item.id, item.must, "作廢")
    if obj is None:
        res.why = "裁判回的不是 JSON"
        return res
    res.quote = str(_pick(obj, "quote", "引用", "evidence") or "").strip()
    res.reason = str(_pick(obj, "reason", "理由", "explanation") or "").strip()
    res.verdict = VERDICT_ALIASES.get(str(_pick(obj, "verdict", "判定", "answer")).strip().lower())
    if truncated:
        res.why = "輸入太長，可能被截斷（prompt_eval_count ≥ num_ctx 的 95%）"
    elif res.verdict is None:
        res.why = "判定不是 是／否／不適用"
    elif not res.quote:
        res.status, res.why = ("作廢", "判否沒附引用") if res.verdict == "否" else ("判定", "")
    elif sum(map(len, quote_segments(res.quote))) < MIN_QUOTE_CHARS:   # 省略號不算字
        res.why = "引用太短，對不出是哪一句"
    elif not quote_found(res.quote, sent_text):
        res.why = "引用對不到原文"
    else:
        res.status = "判定"
    return res


# ─── 裁判呼叫 ─────────────────────────────────────────────────────────────────

def make_client(config: Dict[str, Any], section: Dict[str, Any],
                override: Optional[str]) -> Tuple[ollama_client.OllamaClient, Dict[str, str]]:
    """沿用 ollama_client 的 backend 設定與退避，但每台的 llm_model 換成那台的裁判：
    --model 給了全部用它；否則 judge_model_by_backend 有列的照列，沒列的用 judge_model。
    ollama_client 不指定模型時會把 model 換成每台自己的 llm_model，退到下一台也用那台的裁判；
    那台沒裝這個模型就算不在，不換成它原本設定的模型。回 (client, {backend: 裁判})。"""
    backends = [b for b in ollama_client._build_backends_from_config(config) if b.llm_model]
    by_backend = section.get("judge_model_by_backend") or {}
    judges = {b.name: override or by_backend.get(b.name) or section.get("judge_model", DEFAULTS["judge_model"])
              for b in backends}
    client = ollama_client.OllamaClient([dataclasses.replace(b, llm_model=judges[b.name]) for b in backends])
    return client, judges


def ask_judge(client: ollama_client.OllamaClient, prompt: str, timeout: int, num_ctx: int) -> Optional[Dict[str, Any]]:
    """回完整回應（要 prompt_eval_count／eval_count）；所有 backend 都失敗回 None。"""
    payload = {
        "model": "",                  # ollama_client 送出前換成那台的裁判（make_client）
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": SCHEMA,
        "options": {"temperature": 0, "num_ctx": num_ctx, "num_predict": NUM_PREDICT},
    }
    resp = client._request_with_failover("llm", "/api/chat", payload, timeout)
    return resp if isinstance(resp, dict) else None


# ─── 評分 ─────────────────────────────────────────────────────────────────────

def _count(v: Any) -> int:
    """回應裡的 token 數；不是整數就當 0（只拿來記帳與判截斷，壞值不讓整份當掉）。"""
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0

def score(spec: Spec, text: str, *, config: Dict[str, Any], section: Dict[str, Any], override: Optional[str],
          source: str, session: Optional[str], kind: str) -> Dict[str, Any]:
    body = clean_text(text)
    sents = sentences(text)
    num_ctx = int(section.get("num_ctx", DEFAULTS["num_ctx"]))
    timeout = int(section.get("timeout_sec", DEFAULTS["timeout_sec"]))
    client, judges = make_client(config, section, override)
    results: List[Result] = []
    models_used: List[str] = []
    absent = False
    t_all = time.time()
    for item in spec.items:
        if absent:
            results.append(Result(item.id, item.must, "未評", why="裁判不在"))
            continue
        sent_text, extras = scope_for(item, body, sents)
        if not sent_text.strip():
            results.append(Result(item.id, item.must, "作廢", why="程式切不出範圍"))
            continue
        t0 = time.time()
        why = "裁判不在"
        try:
            resp = ask_judge(client, build_prompt(spec, item, sent_text, extras), timeout, num_ctx)
        except Exception as e:   # ollama_client 自己會吞網路錯誤；這裡接的是沒料到的例外，記未評、不讓整份當掉
            resp, why = None, f"裁判呼叫出錯：{type(e).__name__}: {e}"
            print(f"text-score：{item.id} {why}", file=sys.stderr)
        if resp is None:
            absent = True
            results.append(Result(item.id, item.must, "未評", why=why, secs=round(time.time() - t0, 2)))
            continue
        pe, ev = _count(resp.get("prompt_eval_count")), _count(resp.get("eval_count"))
        res = check_answer(item, resp, sent_text, pe >= TRUNCATE_RATIO * num_ctx)
        res.secs, res.prompt_tokens, res.answer_tokens = round(time.time() - t0, 2), pe, ev
        used = resp.get("model")
        if isinstance(used, str) and used and used not in models_used:
            models_used.append(used)
        results.append(res)
    secs = round(time.time() - t_all, 2)
    return build_record(spec, results, judges=judges, models_used=models_used, secs=secs, text=text,
                        source=source, session=session, kind=kind)


def tally(spec: Spec, results: List[Result]) -> Dict[str, Any]:
    """分數只由程式算：過＝是；不適用不算沒過、也不進分母；裁判回答裡的任何分數欄都不看。"""
    def by(status: str, verdict: Optional[str] = None) -> List[Result]:
        return [r for r in results if r.status == status and (verdict is None or r.verdict == verdict)]

    def ids(rs: List[Result]) -> str:
        return "、".join(r.id for r in rs)

    yes, no, na, voids, unscored = by("判定", "是"), by("判定", "否"), by("判定", "不適用"), by("作廢"), by("未評")
    passed = len(yes)
    counted = len(results) - len(na)
    other_fail = [r for r in no if not r.must]
    open_other = [r for r in voids + unscored if not r.must]
    if len(unscored) == len(results):
        overall = "未評"
    elif any(r.must for r in no) or len(other_fail) > spec.allow_fail:
        overall = "不過"
    elif any(r.must for r in voids + unscored) or len(other_fail) + len(open_other) > spec.allow_fail:
        overall = "未定"
    else:
        overall = "過"
    if overall == "未評":
        summary = f"評分 未評｜{unscored[0].why}"
    else:
        parts = [f"評分 {passed}/{counted}"]
        if no:
            parts.append(f"沒過：{ids(no)}")
        elif not voids and not unscored:
            parts.append("全過")
        if voids:
            parts.append(f"作廢：{ids(voids)}")
        if unscored:
            parts.append(f"未評：{ids(unscored)}")
        summary = "｜".join(parts)
    return {"pass": len(yes), "fail": len(no), "na": len(na), "void": len(voids), "unscored": len(unscored),
            "score": passed, "total": counted, "overall": overall, "summary": summary}


def build_record(spec: Spec, results: List[Result], *, judges: Dict[str, str], models_used: List[str], secs: float,
                 text: str, source: str, session: Optional[str], kind: str) -> Dict[str, Any]:
    return {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session": session,
        "kind": kind,
        "spec": spec.code,
        "spec_sha": spec.sha,
        "source": source,
        "text_sha": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        "chars": len(text),
        "model": "、".join(dict.fromkeys(judges.values())),   # 這次排定的裁判（不重複）；實際回答的看 models_used
        "judges": judges,
        "models_used": models_used,
        "backends": list(judges),
        "secs": secs,
        "prompt_tokens": sum(r.prompt_tokens for r in results),
        "answer_tokens": sum(r.answer_tokens for r in results),
        **tally(spec, results),
        "items": [dataclasses.asdict(r) for r in results],
    }


# ─── 輸出與留帳 ───────────────────────────────────────────────────────────────

def _cell(s: str) -> str:
    return (s or "").replace("|", "｜").replace("\n", " ").strip() or "（無）"


def render_table(rec: Dict[str, Any]) -> str:
    used = "、".join(rec["models_used"]) or rec["model"]
    lines = [f"評分表｜規格 {rec['spec']}｜{rec['overall']}｜裁判 {used} {rec['secs']:.1f} 秒｜作廢 {rec['void']} 條",
             "", "| 代號 | 判定 | 原文證據 | 理由 |", "|---|---|---|---|"]
    for it in rec["items"]:
        verdict = it["verdict"] if it["status"] == "判定" else f"{it['status']}：{it['why']}"
        if it["status"] == "作廢" and it["verdict"]:
            verdict += f"（裁判判{it['verdict']}）"
        lines.append(f"| {it['id']} | {verdict} | {_cell(it['quote'])} | {_cell(it['reason'])} |")
    return "\n".join(lines)


def done_line(spec_code: str, rec: Optional[Dict[str, Any]], logged: bool = False) -> str:
    r = rec or {}
    return (f"TEXT_SCORE DONE spec={spec_code} pass={r.get('pass', 0)} fail={r.get('fail', 0)} na={r.get('na', 0)} "
            f"void={r.get('void', 0)} unscored={r.get('unscored', 0)} secs={r.get('secs', 0.0):.1f} logged={int(logged)}")


def write_log(rec: Dict[str, Any]) -> bool:
    """寫不進去不擋（exit 照 0），但 stderr 說原因、尾行 logged=0。"""
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError as e:
        print(f"text-score：留帳寫不進 {LOG_PATH}：{e}", file=sys.stderr)
        return False


def load_config() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"text-score：{CONFIG_PATH} 讀不到，text_score 用預設、沒有裁判 backend：{e}", file=sys.stderr)
        return {}
    return config if isinstance(config, dict) else {}


def path_matches(path: str, patterns: List[str]) -> bool:
    """路徑樣式從任何一層資料夾起算都可以（樣式寫相對路徑，不管資料根或專案在哪）；
    `*`、`?` 不跨資料夾，`**/` 是零或多層資料夾，其他字元照字面；不分大小寫（樣式判的是命名慣例）。"""
    posix = path.replace("\\", "/")
    for pat in patterns:
        rx = (re.escape(pat.replace("\\", "/")).replace(r"\*\*/", "\0").replace(r"\*", "[^/]*")
              .replace(r"\?", "[^/]").replace("\0", "(?:.*/)?"))
        if re.search(rf"(?:^|/){rx}$", posix, re.I):
            return True
    return False


def auto_skip_reason(kind: str, text: str, section: Dict[str, Any], path: Optional[str]) -> str:
    """自動評（之後由收尾背景呼叫）要不要評這段：回空字串＝要評。path＝來源檔路徑，stdin 是 None。
    auto_targets 是 {種類: 路徑樣式清單}，清單空的種類不比路徑（例 final_reply 從 stdin 進來）；
    寫成種類清單的舊設定照舊只比種類。"""
    if not section.get("enabled", DEFAULTS["enabled"]):
        return "text_score.enabled=false"
    targets = section.get("auto_targets", DEFAULTS["auto_targets"])
    if kind not in targets:
        return f"{kind} 不在 text_score.auto_targets"
    patterns = targets[kind] if isinstance(targets, dict) else []
    rule = f"text_score.auto_targets.{kind} 的路徑樣式（{'、'.join(patterns)}）"
    if patterns and path is None:
        return f"來源是 stdin、沒有路徑，不符 {rule}"
    if patterns and not path_matches(path, patterns):
        return f"來源 {path} 不符 {rule}"
    n = len(re.sub(r"\s", "", clean_text(text)))
    floor = int(section.get("min_chars", DEFAULTS["min_chars"]))
    return f"文字 {n} 字，少於 text_score.min_chars={floor}" if n < floor else ""


def read_source(src: str) -> Tuple[str, str]:
    if src == "-":
        return sys.stdin.buffer.read().decode("utf-8-sig", errors="replace"), "stdin"
    path = Path(src)
    return path.read_text(encoding="utf-8-sig"), str(path.resolve())


def main(argv: Optional[List[str]] = None) -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="照文字規格逐條問開源免費的小模型裁判，印評分表並留帳（G15）")
    ap.add_argument("source", help="要評的文字檔；- 讀 stdin")
    ap.add_argument("--spec", help="規格代號（text-specs/<代號>.md）或規格檔路徑；預設 text_score.default_spec")
    ap.add_argument("--model", help="裁判模型（只走 Ollama），每台 backend 都用它；"
                                    "預設每台照 text_score.judge_model_by_backend，沒列到的用 judge_model")
    ap.add_argument("--json", action="store_true", help="改印一行 JSON（留帳同一筆），再接尾行")
    ap.add_argument("--session", help="留帳記的 session id（有的話）")
    ap.add_argument("--goal", default="", help="當下的需求目標（填規格裡的 {{goal}}）；規格用了 {{goal}} 卻沒給 → 不評")
    ap.add_argument("--auto-kind", help="自動評的文字種類（final_reply／docs）：照 enabled、auto_targets（種類與路徑樣式）、"
                                        "min_chars 決定評不評")
    ap.add_argument("--tail-line", action="store_true",
                    help="stdout 只印一行摘要（評分 N/M｜沒過：…，或「全過」），給每則回覆的尾巴取用；照樣留帳；"
                         "不評時 stdout 什麼都不印、原因寫 stderr")
    args = ap.parse_args(argv)

    config = load_config()
    section = {**DEFAULTS, **(config.get("text_score") or {})}
    try:
        spec = load_spec(args.spec or section.get("default_spec", DEFAULTS["default_spec"]))
        text, source = read_source(args.source)
    except (SpecError, OSError, UnicodeDecodeError) as e:
        print(f"text-score：{e}", file=sys.stderr)
        return 2
    if not clean_text(text).strip():
        print("text-score：原文是空的（去掉 code 與網址之後）", file=sys.stderr)
        return 2
    if args.auto_kind:
        why = auto_skip_reason(args.auto_kind, text, section, None if args.source == "-" else source)
        if why and args.tail_line:
            print(f"不評：{why}", file=sys.stderr)
            return 0
        if why:
            print(f"不評：{why}")
            print(done_line(spec.code, None))
            return 0

    if needs_goal(spec):
        goal = " ".join(str(args.goal or "").split())
        if not goal:
            print("不評：沒有當下的需求目標（目標樹樹根或本回合使用者原話）可以對", file=sys.stderr if args.tail_line else sys.stdout)
            if not args.tail_line:
                print(done_line(spec.code, None))
            return 0
        spec = with_goal(spec, goal[:300])
    rec = score(spec, text, config=config, section=section, override=args.model, source=source,
                session=args.session, kind=args.auto_kind or "manual")
    logged = write_log(rec)
    if args.tail_line:   # 尾巴就這一行，不接評分表與尾行
        print(rec["summary"])
        return 0
    if args.json:
        print(json.dumps(rec, ensure_ascii=False))
    elif rec["overall"] == "未評":
        judges = "、".join(f"{name}={judge}" for name, judge in rec["judges"].items())
        print(f"裁判不在，未評（試過 backend：{'、'.join(rec['backends']) or '沒有設定'}；各台裁判：{judges or '無'}）")
        print(rec["summary"])
    else:
        print(render_table(rec))
        if rec["unscored"]:
            first = next(it["id"] for it in rec["items"] if it["status"] == "未評")
            print(f"\n裁判中途不在：{first} 起未評")
        print("\n" + rec["summary"])
    print(done_line(spec.code, rec, logged))
    return 0


if __name__ == "__main__":
    sys.exit(main())
