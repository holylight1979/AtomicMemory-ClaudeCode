"""prompts.py：第二意見的兩種視角提示詞與回覆解析。

兩種模式（介面凍結）：
  independent  同材料獨立作答：提示詞**不得**含己方草稿（帶 draft 直接拒），避免被帶偏。
  review       拿目標逐段評草稿：**必須**帶 draft（缺就拒），每段回「是這裡／不是這段」。
提示詞只引材料的相對路徑（materials/<rel>），絕對路徑由 replay-guard pre 擋。
回覆必須有三段：## 結論 / ## 證據 / ## 反例或未解；parse_three_sections 缺段回 None。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

MODES = ("independent", "review")
KINDS = ("diagnose", "evaluate", "stage-review")
SECTIONS = ("結論", "證據", "反例或未解")

SANDBOX_NOTE = """\
【環境】你跑在唯讀沙箱，可能連 shell 都 spawn 不起來。材料已附在本訊息「材料全文」段，每份也放在工作目錄 \
materials/ 下（相對路徑如下表）。不要執行任何修改型指令，不要讀工作目錄以外的檔，不要查 git/svn 歷史；\
材料不夠就在「反例或未解」寫明缺什麼，不要猜。
"""

OUTPUT_RULES = """\
【輸出】只用繁體中文，恰好三段、標題固定、順序固定，不加其他章節：
## 結論
一句話判定 + 最多五條要點。每條要能指到材料的位置（如 materials/diff.patch 第 N 行、materials/card.md「某節」）。
## 證據
每條結論對應的證據，格式「materials/<檔>:<行或節>｜看到了什麼｜所以」。沒有材料佐證的推論要標「推論」。
## 反例或未解
會推翻你結論的情況、材料裡查不到的事、以及你覺得出題者沒給夠的東西。沒有也要寫「無」並說為何沒有。
"""

INDEPENDENT_TMPL = """\
{sandbox_note}
【任務】{kind_text}。你是獨立的第二意見：出題方的看法不會給你，請只根據材料自己判斷。
部位：{part}
問題：{question}

【材料清單】（相對工作目錄）
{materials_table}

{output_rules}
【材料全文】
{materials_body}
"""

REVIEW_TMPL = """\
{sandbox_note}
【任務】{kind_text}。你拿著目標逐段評一份草稿：對草稿的每一段回「是這裡」（命中目標、證據在材料何處）\
或「不是這段」（為何不是、材料哪裡反駁），不要重寫整份草稿。
部位：{part}
目標／問題：{question}

【材料清單】（相對工作目錄；草稿在 materials/draft.md）
{materials_table}

{output_rules}
附加要求：「結論」段先給整體判定（可接受／需修／不接受），再逐段列「是這裡／不是這段」。

【材料全文】
{materials_body}
"""

_KIND_TEXT = {
    "diagnose": "診斷這段改動或這個部位的根因與風險",
    "evaluate": "評估這個做法是否達成目標、有無更簡單的等價寫法",
    "stage-review": "審查這一階段的交付是否完整、驗證是否真的覆蓋宣稱",
}


def _materials_table(manifest: Dict[str, Any]) -> str:
    rows = [f"- materials/{f['rel']}（{f['bytes']} bytes, sha256 {f['sha256'][:12]}…）" for f in manifest.get("files", [])]
    return "\n".join(rows) if rows else "- （無材料）"


def _materials_body(manifest: Dict[str, Any], texts: Dict[str, str], max_chars: int) -> str:
    parts: List[str] = []
    for f in manifest.get("files", []):
        body = texts.get(f["rel"], "")
        if len(body) > max_chars:
            body = body[:max_chars] + f"\n…（已截斷，原 {len(body)} 字；完整內容在 materials/{f['rel']}）\n"
        parts.append(f"### materials/{f['rel']}\n```\n{body.rstrip()}\n```")
    return "\n\n".join(parts)


def build_prompt(mode: str, manifest: Dict[str, Any], question: str, draft: Optional[str] = None,
                 kind: str = "diagnose", part: str = "", texts: Optional[Dict[str, str]] = None,
                 material_max_chars: int = 40000) -> str:
    """組提示詞。independent 帶 draft → ValueError；review 缺 draft → ValueError。"""
    if mode not in MODES:
        raise ValueError(f"mode 只收 {'|'.join(MODES)}：{mode!r}")
    if kind not in KINDS:
        raise ValueError(f"kind 只收 {'|'.join(KINDS)}：{kind!r}")
    if not (question or "").strip():
        raise ValueError("question 必填")
    has_draft = bool((draft or "").strip())
    if mode == "independent" and has_draft:
        raise ValueError("independent 模式不收 draft：獨立作答不能看到己方答案")
    if mode == "review" and not has_draft:
        raise ValueError("review 模式必須帶 draft：沒有草稿就沒有東西可逐段評")
    tmpl = INDEPENDENT_TMPL if mode == "independent" else REVIEW_TMPL
    return tmpl.format(
        sandbox_note=SANDBOX_NOTE,
        kind_text=_KIND_TEXT[kind],
        part=part or "（未指定）",
        question=question.strip(),
        materials_table=_materials_table(manifest),
        output_rules=OUTPUT_RULES,
        materials_body=_materials_body(manifest, texts or {}, material_max_chars),
    )


_SEC_RE = re.compile(r"^##\s*(結論|證據|反例或未解)\s*$", re.MULTILINE)


def parse_three_sections(text: str) -> Optional[Dict[str, str]]:
    """回 {結論, 證據, 反例或未解}；任一段缺或空 → None。"""
    if not text:
        return None
    hits = list(_SEC_RE.finditer(text))
    if len(hits) < 3:
        return None
    out: Dict[str, str] = {}
    for i, m in enumerate(hits):
        end = hits[i + 1].start() if i + 1 < len(hits) else len(text)
        body = text[m.end():end].strip()
        if m.group(1) in out:
            return None  # 同名段出現兩次 = 格式不合
        out[m.group(1)] = body
    if any(s not in out or not out[s] for s in SECTIONS):
        return None
    return out


def render_reply(sections: Dict[str, str]) -> str:
    return "\n\n".join(f"## {s}\n{sections[s].strip()}" for s in SECTIONS) + "\n"
