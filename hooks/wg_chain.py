"""wg_chain.py：連鎖斷路器的判定（純函式：不讀檔、不跑 git、不改 state）。

做什麼：同一個使用者回合裡，某道閘擋下或記欠 → AI 動手改了檔（改檔、寫卡、子代理；重跑、改目標樹這類沒改檔的動作照記、不算修補）
→ 又讓任一道閘擋下或記欠，就是一條連鎖邊「閘A→動作→閘B」；同一則回覆裡平行送出的呼叫算同一步（AI 那時還沒看到擋訊息）。
這裡把一個回合的帳（lib/chain_store.py 寫的 rows）
摺成連鎖狀態，判：這次觸發接不接上前一步、深度、要不要警報、警報後這一段其餘閘只記錄不擋、使用者三選一怎麼解讀、
改檔前要不要存快照、還原計畫，並產生給人看的連鎖過程表。
每一種情境是一條有名字的規則（RULES）；呼叫端（stop、pre_tool_use、post_tool_use）只蒐集事實交給 lib/chain_store.py，
判斷都在這裡。斷路器自己不逼修補、不要求任何宣告：它只在兩處擋——警報後 Stop 擋一次送經過表、
中止停手中擋下讀與問以外的工具呼叫（CHAIN_HALT_UNTIL_ANSWER）；兩者都不算閘觸發。
帳的一筆（row）：type＝gate｜action｜alarm｜notice｜answer｜reset｜snapshot｜restore，另帶 turn、agent（子代理 id，主 session 空字串）、
seq（同回合第幾筆）、ts（epoch 秒）、at（本地時間）；工具呼叫上的 gate／action 另帶 batch（哪一則回覆，CHAIN_SAME_BATCH）；
gate 另帶這次擋的對象：watched（擋的檔）、target（不是檔的對象，例如定位閘的部位），說不出就空（CHAIN_SAME_GATE_PER_OBJECT）；
工具呼叫上的 gate 再帶 call（被擋的呼叫逐字的雜湊，CHAIN_SAME_CALL_RETRY）。
怎麼跑案例：python -X utf8 -m pytest -q hooks/verify/verify_chain_breaker.py
"""
from __future__ import annotations

import difflib
import os
import re
import textwrap
import unicodedata
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

from wg_release import OPT_RELEASE, RELEASE_TAG
from wg_release_rules import canon_path, comment_only_change

RULES: Dict[str, str] = {
    "CHAIN_SAME_TURN": "連鎖只在同一個使用者回合、同一個對話者（主 session 或同一個子代理）裡算；換回合從零起，中止也只在警報那一回合有效。",
    "CHAIN_COUNT_TRIGGERS": "次數＝這一段（回合開頭、或選「繼續」之後）閘觸發總數減 1；觸發＝真的擋下或記欠，讓警報響的那一次也算；"
                            "警報之後只記錄的不算進次數與深度（表上照列、標只記錄）。",
    "CHAIN_GATE_NAME": "閘名取擋訊息裡第一個 [Guardian:名稱] 或 [名稱] 標記；認不出用呼叫端給的預設名。同一道閘每次擋訊息的標記相同，同閘次數才數得準。",
    "CHAIN_ACTION_FACTS": "哪些工具呼叫算 AI 動作：Edit／Write／MultiEdit／NotebookEdit＝改；Bash／PowerShell 有寫入目標（含判不出目標的寫入）＝改，"
                          "跑測試或驗證＝重跑，其餘不是唯讀的指令＝其他動作；atom_write／atom_retire＝寫卡；收尾檢核與收割回報＝重交報告；"
                          "need_goal＝改目標樹；Agent／Task＝其他動作。讀檔（Read、唯讀指令）不算動作。"
                          "動作都照記、照列進經過表；接不接成邊、算不算同閘次數只看有沒有改到檔（CHAIN_NO_EDIT_NO_EDGE）。",
    "CHAIN_EDGE_TIME_ORDER": "同一段裡閘B接在閘A之後觸發、中間 AI 有改到檔的動作 → 記一條邊 A→B；深度＝連續邊的長度。沒記到改檔動作、A 與 B 是不同的閘時，"
                             "Stop 接 Stop 算改寫回覆、閘B在工具呼叫上算 AI 接著的那次呼叫。",
    "CHAIN_SAME_GATE_NO_ACTION": "同一道閘接連觸發、中間沒記到 AI 動作（重試同一個呼叫、只改寫回覆）→ 不接成邊、也不算同閘次數，交回那道閘自己的擋次上限處理。"
                                 "中間有動作但都沒改到檔，同樣不接（CHAIN_NO_EDIT_NO_EDGE）。",
    "CHAIN_NO_EDIT_NO_EDGE": "兩次觸發之間 AI 的動作都沒改到檔 → 不算修補：同一道閘不接成邊、不讓同閘次數加 1（帳上記這條規則）；"
                             "不同的閘照「沒記到動作」那樣判（CHAIN_EDGE_TIME_ORDER 後半、CHAIN_NO_FIX_NO_EDGE）。改到檔（changes_files）＝"
                             "改（Edit／Write／MultiEdit／NotebookEdit、Bash／PowerShell 有寫入目標，含判不出目標的寫入）、寫卡（atom_write／atom_retire "
                             "改的是卡片檔）、子代理（Agent／Task：它改了什麼主 session 的帳看不到，照改檔算）；沒改到檔＝重跑測試、其他沒有寫入目標的指令"
                             "（建刪暫存工作樹這類）、重交收尾報告、改目標樹（只動 session 的 state）。原樣重送被擋的呼叫照 CHAIN_SAME_CALL_RETRY。",
    "CHAIN_SAME_CALL_RETRY": "同一道閘擋同一個對象，這次被擋的工具呼叫跟這道閘這個對象上一次被擋的逐字相同（工具名＋參數，帳上 call）"
                             "→ 原樣重試：不接成邊、不讓同閘次數加 1，中間做了別的動作（回應別的提示）也一樣，交回那道閘自己的擋次上限處理。"
                             "改了內容、補進宣告（呼叫變了）照舊算；有一邊沒記 call（收尾閘、舊帳）照舊只看中間有沒有動作。",
    "CHAIN_SAME_EVENT": "同一個 hook 事件裡先後觸發的兩道閘不接成邊（不是 AI 動作造成的）。",
    "CHAIN_SAME_BATCH": "同一則 assistant 回覆裡平行送出的工具呼叫算同一步：送出前就決定好，中間 AI 沒看到任何擋訊息。"
                        "這一批之間的閘觸發不接成邊、不讓同閘次數加 1；呼叫之間放過的改動也不算 AI 看過擋訊息之後的動作，"
                        "下一則回覆裡的呼叫才算。這一批的觸發接在前一批裡深度最深的那一步。"
                        "同一則＝兩筆帳的 batch 相同（chain_store 從 transcript 取這次呼叫所在那則回覆之前最後一則 assistant 的 message.id）。"
                        "這一筆記不出是哪一則（子代理、transcript 讀不到或找不到，帳上記 batch_why）就不跳過任何一步；前面記得出批次的步驟照用"
                        "（跟那一步同一批送出的動作不算反應）。收尾不是工具呼叫、一定在所有工具呼叫那幾則之後，不帶 batch。",
    "CHAIN_NO_FIX_NO_EDGE": "前一步是工具上的閘、之後 AI 沒有改到檔的動作就收尾 → 收尾的閘不接上前一步。",
    "CHAIN_EDGE_PREVIEWED": "閘B已列在閘A擋下時的「後面還會擋」預覽裡（A 擋的時候 B 就欠著）→ 不是 A 之後的動作造成的，不接成邊。",
    "CHAIN_EDGE_FILES_DISJOINT": "閘B說了它看哪些檔、A 之後 AI 的每個動作都說得出改了哪些檔、兩邊沒有交集 → 不接成邊；"
                                 "B 沒說看哪些檔、或有改檔動作說不出改了哪些檔（寫卡、判不出目標的 Bash、子代理），照接；沒改到檔的動作不算進來。",
    "CHAIN_ALARM_DEPTH": "深度照算、照列進經過表（閘→修→閘→修→第三次閘＝深度 2），預設不警報：要擋的是繞回原點的修不停，"
                         "那是同一道閘第 2 次（CHAIN_ALARM_SAME_GATE）；三道各管各的閘各擋一次不是連鎖。"
                         "設定 depth_alarm=true 才在深度 ≥ max_depth（預設 2）時也警報。",
    "CHAIN_ALARM_SAME_GATE": "同一道閘擋同一個對象（CHAIN_SAME_GATE_PER_OBJECT）同一段第 max_same_gate 次觸發（預設 2）→ 警報；"
                             "只數跟這道閘這個對象上一次觸發之間 AI 有記到改到檔的動作的那幾次（中間的動作接在別道閘、別的對象後面也算；"
                             "沒改到檔的不算，CHAIN_NO_EDIT_NO_EDGE）。",
    "CHAIN_SAME_GATE_PER_OBJECT": "同閘次數照「閘＋擋的對象」數：要擋的是修了又欠、繞回原點，繞回同一個對象才算同閘第 2 次；"
                                  "同一道閘擋不同對象，各要各的證據，第 1 次補的沒讓第 2 次多欠什麼，各算各的第 1 次。"
                                  "對象＝呼叫端報的 target（不是檔的對象：定位閘報部位表那一列，表外的檔報同頂層目錄那一組），"
                                  "沒報 target 就看 watched（擋的檔：動資料檔、改舊測試報這次要寫的檔）；兩次都報 target 比 target、"
                                  "都只報檔就有交集算同一個；有一邊說不出對象（收尾閘、版控口令這類只看閘名的、判不出的），"
                                  "或一邊報 target 一邊只報檔，照舊只看閘名。中間沒動作不算（CHAIN_SAME_GATE_NO_ACTION）、"
                                  "同一則回覆算一步（CHAIN_SAME_BATCH）照舊疊在上面；經過表每一筆列出擋的對象。",
    "CHAIN_ABORT_RECORD_ONLY": "警報一響（含讓它響的那一次），這一段其餘所有閘只記錄、不擋、不記欠（同一道閘這一段只記一筆）；"
                               "使用者選之前不逼任何修補。呼叫端在閘擋或記欠之前問，只記錄就跳過那道閘的擋與記欠、照往下走。"
                               "沒人能答時會改使用者資料的那幾道照擋（CHAIN_HEADLESS_KEEPS_DATA_GATES）。",
    "CHAIN_HALT_UNTIL_ANSWER": "能互動的 session 中止就是停手：警報後到使用者選「繼續」或「放行」之前（選還原或答別的也停到換回合）；沒人能答的不停手（CHAIN_HEADLESS_NO_ASK），"
                               "除了讀（HALT_ALLOW 與 readonly_shell 判定唯讀的指令）和 AskUserQuestion，工具呼叫一律先擋下、附經過表與該問的題目。"
                               "這不是閘觸發、不進次數，也不逼修補；讓警報響不會換到被擋的動作過關。"
                               "唯讀指令只認白名單裡的讀檔指令、沒有寫檔重導向與指令替換；判不出一律當成會動手。",
    "CHAIN_STOP_NOTICE_ONCE": "警報後 Stop 只擋一次，送連鎖過程表（能互動就附三選項）；使用者在那之前已答就不擋、附結果與表；之後的 Stop 不再擋，只附提醒。",
    "CHAIN_ABORT_SHOWS_REPLACED_BLOCK": "警報在哪一次響，那道閘原本要送的擋訊息（含附註，例如紅測閘的基底紅缺哪一件）就照附在取代它的中止訊息最後"
                                        "（收尾的中止通知、工具上的停手訊息），超過 REPLACED_CAP 字留開頭：經過表只列第一行，AI 照原文才知道缺什麼、"
                                        "該問使用者什麼。之後的停手訊息與提醒不再附（那時沒有被換掉的擋）。",
    "CHAIN_HEADLESS_NO_ASK": "沒人能答（headless／SDK、子代理、裁判子 session；判法 wg_release.non_interactive_reason，警報那一刻判）→ 不叫 AI 問、"
                             "不停手：這一回合其餘閘只記錄、留帳，AI 照常把工作做完；讓警報響的那次工具呼叫照放，收尾擋一次要 AI 把經過表寫進收尾報告。"
                             "不還原也不繼續。會改使用者資料的那幾道閘例外，照擋（CHAIN_HEADLESS_KEEPS_DATA_GATES）。",
    "CHAIN_HEADLESS_KEEPS_DATA_GATES": "沒人能答、警報之後（通知記下不能互動），擋的是改使用者資料的閘照擋（KEEP_BLOCKING，閘名取擋訊息標記）："
                                       "動資料檔（DataFileAsk）、改舊測試（OldTestDeclare）、commit 前的版控口令（CommitOrder）與隱私檔"
                                       "（GitPrivacy）與 svn 測試路徑（SvnTestBlock）、專案 session 改根層核心或全域 MCP 設定"
                                       "（CrossRealmWriteBlock／CrossRealmBashBlock／CrossRealmMcpBlock）——這些放掉就是沒人看著改了使用者的資料檔、"
                                       "既有測試、版本庫歷史或根層設定，事後看帳也收不回。讓警報響的那一次也照擋；每一次都記一筆（帳上 kept），"
                                       "不算進次數與深度、不再警報。其餘閘（定位、目標樹、對帳、病形、繞閘、記憶寫入路徑這類管做法與品質的）照"
                                       "CHAIN_ABORT_RECORD_ONLY 只記錄。能互動的 session 不變：警報後本來就停手到使用者選，選「放行這一回合」照放。",
    "CHAIN_ANSWER_BY_TOOL_USE_ID": "使用者答案只認中止通知之後、tool_use_id 對得上 AskUserQuestion 的結果（wg_release._answers_after），"
                                   "題目逐字等於通知記下的那一題（含【收尾放行確認】【連鎖中止】；NFKC、空白正規化後比）、答案逐字是三選項之一；"
                                   "其他工具輸出、AI 文字印出同樣的字、AI 自己改寫題意另出的題都不算。",
    "CHAIN_CONTINUE_RESETS": "選「信任後續 AI 審查，繼續」→ 開新的一段：次數、深度、同閘次數歸零，閘照常擋，同樣額度再超再問。",
    "CHAIN_RELEASE_TURN": "選「放行這一回合」→ 這一回合其餘閘照舊只記錄，換回合才恢復。",
    "CHAIN_RESTORE_SEGMENT": "選「還原連鎖改動」→ 只還原這一段的快照（連鎖前的改動不動）：原本存在的檔寫回快照、原本不存在的刪掉，"
                             "還原後重讀比雜湊、比不上重試；沒快照到的改動列出來、不還原。動手前先核對：實際路徑（連結、掛載點）沒變、"
                             "檔案現在的內容等於這一段最後一次寫入後記下的內容（沒寫入過就等於快照）——對不上表示連鎖之後被別處改過，不覆寫、不刪，列出來。"
                             "之後這一回合其餘閘只記錄。",
    "CHAIN_SNAPSHOT_WINDOW": "這一段第一道閘觸發起（選「繼續」的那一段從選的那刻起）到使用者答案之前，每個要被改的檔這一段第一次改之前存快照"
                             "（原本不存在就記不存在）；超過 snapshot_max_bytes、不是一般檔、讀不到、這一段已存滿 snapshot_max_files 的不存、記原因；"
                             "斷路器自己的快照與帳不存。",
    "CHAIN_COMMENT_ONLY_RECORDED": "每筆編輯記 comment_only：去掉註解與空白後兩邊相同＝true、不同＝false、判不了（Bash 改檔、二進位、"
                                   "認不出註解語法、掃到結尾還在字串裡）＝unknown；只記錄，不影響邊、次數、深度與門檻。",
}

DEFAULTS: Dict[str, Any] = {"enabled": False, "depth_alarm": False, "max_depth": 2, "max_same_gate": 2,
                            "snapshot_max_bytes": 5_000_000, "snapshot_max_files": 200, "restore_retries": 3}

GATE = "ChainBreaker"
CHAIN_TAG = "【連鎖中止】"
OPT_RESTORE = "還原連鎖改動（不符本批目標）"
OPT_CONTINUE = "信任後續 AI 審查，繼續"
CHOICES: Dict[str, str] = {OPT_RESTORE: "restore", OPT_CONTINUE: "continue", OPT_RELEASE: "release"}
STOP_HOOKS = ("Stop", "SubagentStop")
HALT_ALLOW = ("Read", "Grep", "Glob", "AskUserQuestion", "TodoWrite", "ToolSearch")
# CHAIN_HEADLESS_KEEPS_DATA_GATES：沒人能答時警報後照擋的閘（擋訊息的標記名）
KEEP_BLOCKING = frozenset(("DataFileAsk", "OldTestDeclare", "CommitOrder", "GitPrivacy", "SvnTestBlock",
                           "CrossRealmWriteBlock", "CrossRealmBashBlock", "CrossRealmMcpBlock"))


def settings(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """workflow/config.json 的 chain_breaker 段蓋過 DEFAULTS；型別不對、數字小於 1 的照預設。
    設定裡沒寫 enabled＝不開（出廠 config.json 寫了開）：只帶部分設定的呼叫端（各閘自己的案例）照各閘原本的擋法。"""
    sec = (config or {}).get("chain_breaker")
    sec = sec if isinstance(sec, dict) else {}
    out = dict(DEFAULTS)
    for key in ("enabled", "depth_alarm"):
        if isinstance(sec.get(key), bool):
            out[key] = sec[key]
    for key in ("max_depth", "max_same_gate", "snapshot_max_bytes", "snapshot_max_files", "restore_retries"):
        v = sec.get(key)
        if isinstance(v, int) and not isinstance(v, bool) and v >= 1:
            out[key] = v
    return out


def is_stop(hook: Any) -> bool:
    return str(hook or "") in STOP_HOOKS


def one_line(text: Any, cap: int = 120) -> str:
    line = next((ln.strip() for ln in str(text or "").splitlines() if ln.strip()), "")
    return line if len(line) <= cap else line[:cap - 1] + "…"


# ─── 把帳摺成連鎖狀態 ─────────────────────────────────────────────────────

class Link(NamedTuple):
    linked: bool
    rule: str
    why: str


class Hit(NamedTuple):
    rule: str
    why: str


class Step:
    """一次閘觸發，加上它之後、下一次觸發之前 AI 做的動作。muted＝警報之後才觸發、只記錄（不算進次數與深度）。"""
    __slots__ = ("row", "actions", "link", "depth", "muted")

    def __init__(self, row: Dict[str, Any], muted: bool = False):
        self.row = row
        self.actions: List[Dict[str, Any]] = []
        self.link: Optional[Link] = None
        self.depth = 0
        self.muted = muted


class Chain:
    """一個回合、一個對話者目前這一段的連鎖狀態（選「繼續」就開新的一段）。"""

    def __init__(self, segment: int = 0):
        self.segment = segment
        self.steps: List[Step] = []
        self.lead: List[Dict[str, Any]] = []     # 選「繼續」之後、這一段第一次觸發之前的動作
        self.snaps: Dict[str, Dict[str, Any]] = {}
        self.alarm: Optional[Dict[str, Any]] = None
        self.notice: Optional[Dict[str, Any]] = None     # 警報那一刻記：答案從這之後才算、該問的題目、能不能互動
        self.shown: Optional[Dict[str, Any]] = None      # Stop 已擋過那一次、送過經過表
        self.answer: Optional[Dict[str, Any]] = None
        self.restored: Optional[Dict[str, Any]] = None
        self.halted = 0                                  # 中止中擋下的工具呼叫次數

    @property
    def open(self) -> bool:
        """CHAIN_SNAPSHOT_WINDOW：連鎖段開了沒（第 0 段要等第一道閘觸發，之後的段從選「繼續」那刻就開）。"""
        return self.segment > 0 or bool(self.steps)

    @property
    def count(self) -> int:
        """CHAIN_COUNT_TRIGGERS：警報之後只記錄的不算。"""
        return max(0, sum(1 for s in self.steps if not s.muted) - 1)

    @property
    def depth(self) -> int:
        return max((s.depth for s in self.steps if not s.muted), default=0)

    @property
    def record_only(self) -> bool:
        return self.alarm is not None

    def actions(self) -> List[Dict[str, Any]]:
        return self.lead + [a for s in self.steps for a in s.actions]


_SLOT = {"alarm": "alarm", "notice": "notice", "shown": "shown", "answer": "answer", "restore": "restored"}


def fold(rows: Iterable[Dict[str, Any]], turn: int, agent: str = "") -> Chain:
    """CHAIN_SAME_TURN：只摺這一回合、這個對話者的帳；遇到 reset（選「繼續」）就從新的一段重算。"""
    ch = Chain()
    for r in rows:
        if not isinstance(r, dict) or _int(r.get("turn")) != int(turn) or str(r.get("agent") or "") != agent:
            continue
        kind = r.get("type")
        if kind == "reset":
            ch = Chain(ch.segment + 1)
        elif kind == "gate":
            step = Step(r, muted=ch.alarm is not None)
            step.link, step.depth = attach(ch.steps, r)
            ch.steps.append(step)
        elif kind == "action":
            (ch.steps[-1].actions if ch.steps else ch.lead).append(r)
        elif kind == "snapshot":
            ch.snaps.setdefault(canon_path(r.get("path")), r)
        elif kind == "halted":
            ch.halted += 1
        elif kind in _SLOT:
            setattr(ch, _SLOT[kind], r)
    return ch


def _int(v: Any) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return -1


def same_batch(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """CHAIN_SAME_BATCH：兩筆帳（閘觸發或動作）是同一則 assistant 回覆裡送出的工具呼叫；有一邊記不出是哪一則就不算。"""
    key = str(a.get("batch") or "")
    return bool(key) and key == str(b.get("batch") or "")


def same_call(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """CHAIN_SAME_CALL_RETRY：兩次觸發擋的是逐字相同的工具呼叫；有一邊沒記 call 就不算。"""
    key = str(a.get("call") or "")
    return bool(key) and key == str(b.get("call") or "")


def attach(steps: Sequence[Step], row: Dict[str, Any]) -> Tuple[Optional[Link], int]:
    """新的一次觸發 row 接不接、深度多少（fold 與 judge 共用）。和前一步同一個 hook 事件 → 不接（CHAIN_SAME_EVENT）；
    前面跟 row 同一批的觸發整批跳過（CHAIN_SAME_BATCH）；原封不動重送這道閘這個對象上一次擋下的呼叫 → 不接（CHAIN_SAME_CALL_RETRY，
    中間夾了別道閘也一樣）；其餘跟前一批裡深度最深的那一步比，動作只算 AI 看過那一步擋訊息之後送出的。"""
    if not steps:
        return None, 0
    if row.get("event") and row.get("event") == steps[-1].row.get("event"):
        return Link(False, "CHAIN_SAME_EVENT", "和前一步是同一個 hook 事件"), 0
    i = len(steps) - 1
    while i >= 0 and same_batch(steps[i].row, row):
        i -= 1
    if i < 0:
        return Link(False, "CHAIN_SAME_BATCH", "和前面的觸發在同一則回覆裡一起送出（AI 還沒看到擋訊息）"), 0
    last = next((s for s in reversed(steps) if s.row.get("gate") == row.get("gate") and same_object(s.row, row)), None)
    if last is not None and same_call(last.row, row):
        return Link(False, "CHAIN_SAME_CALL_RETRY", "同一道閘、同一個對象，原封不動重送上一次被擋的呼叫"), 0
    j = i
    while j > 0 and same_batch(steps[j - 1].row, steps[i].row):
        j -= 1
    k = max(range(j, i + 1), key=lambda n: (steps[n].depth, n))
    prev = steps[k]
    acts = [a for s in steps[k:] for a in s.actions if not same_batch(prev.row, a)]
    lk = link(prev, row, acts)
    return lk, (prev.depth + 1 if lk.linked else 0)


def link(prev: Step, row: Dict[str, Any], acts: Sequence[Dict[str, Any]]) -> Link:
    """閘B（row）接不接上前一步 prev（acts＝prev 之後、AI 看過 prev 擋訊息才送出的動作，見 attach）：照 CHAIN_EDGE_PREVIEWED →
    CHAIN_SAME_GATE_NO_ACTION → CHAIN_NO_FIX_NO_EDGE → CHAIN_EDGE_FILES_DISJOINT 依序排除，都不中就照時間先後接上（CHAIN_EDGE_TIME_ORDER）。"""
    gate, hook = str(row.get("gate") or ""), row.get("hook")
    if gate != prev.row.get("gate") and gate in (prev.row.get("later") or ()):
        return Link(False, "CHAIN_EDGE_PREVIEWED", f"前一步擋的時候 {gate} 就列在後面還會擋")
    edits = [a for a in acts if changes_files(a)]
    if not edits:
        if gate == prev.row.get("gate"):
            return (Link(False, "CHAIN_NO_EDIT_NO_EDGE", "同一道閘、中間 AI 的動作都沒改到檔") if acts
                    else Link(False, "CHAIN_SAME_GATE_NO_ACTION", "同一道閘、中間 AI 沒有動作"))
        if is_stop(hook) and not is_stop(prev.row.get("hook")):
            return Link(False, "CHAIN_NO_FIX_NO_EDGE", "前一步之後 AI 沒改檔就收尾")
        return Link(True, "CHAIN_EDGE_TIME_ORDER", "改寫回覆" if is_stop(hook) else "AI 接著的工具呼叫")
    watched = _watched(row)
    if watched and all(_files(a) for a in edits):
        changed = {canon_path(f.get("path")) for a in edits for f in _files(a)}
        if not changed & watched:
            return Link(False, "CHAIN_EDGE_FILES_DISJOINT", "前一步之後改的檔不在它看的範圍")
    return Link(True, "CHAIN_EDGE_TIME_ORDER", "前一步之後 AI 動了手")


def _files(action: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [f for f in action.get("files") or () if isinstance(f, dict) and f.get("path")]


def changes_files(action: Dict[str, Any]) -> bool:
    """CHAIN_NO_EDIT_NO_EDGE：這筆動作有沒有改到檔——改、寫卡、子代理算；重跑、其他沒寫入目標的指令、重交報告、改目標樹不算。"""
    kind = str(action.get("kind") or "")
    return kind in ("edit", "card") or (kind == "other" and str(action.get("tool") or "") in ("Agent", "Task"))


class Judge(NamedTuple):
    record_only: bool          # 這次觸發只記錄、不擋（CHAIN_ABORT_RECORD_ONLY）
    alarm: Tuple[Hit, ...]     # 這次讓警報響的規則；空＝沒響（或這一段早就響過）
    link: Optional[Link]
    depth: int
    same: int                  # 同一道閘、同一個對象這一段第幾次（只數跟上一次之間 AI 有動作的）


def _watched(row: Dict[str, Any]) -> set:
    return {canon_path(p) for p in row.get("watched") or () if p}


def same_object(a: Dict[str, Any], b: Dict[str, Any]) -> bool:
    """CHAIN_SAME_GATE_PER_OBJECT：同一道閘的兩次觸發擋的是不是同一個對象。都報 target 比 target；都只報檔，有交集就是同一個；
    有一邊說不出對象、或一邊報 target 一邊只報檔 → 比不了，照舊算同一個（只看閘名）。"""
    ta, tb = str(a.get("target") or ""), str(b.get("target") or "")
    if ta and tb:
        return ta == tb
    fa, fb = _watched(a), _watched(b)
    if ta or tb or not fa or not fb:
        return True
    return bool(fa & fb)


def target_label(row: Dict[str, Any]) -> str:
    """經過表與警報句裡的「擋的對象」：target 取最後一個 | 之後（定位閘的部位名）；只報檔列檔名；說不出回空字串。"""
    t = str(row.get("target") or "")
    if t:
        return t.rsplit("|", 1)[-1]
    files = [short_path(p) for p in dict.fromkeys(str(p) for p in row.get("watched") or () if p)]
    return "、".join(files[:3]) + (f" 等 {len(files)} 個檔" if len(files) > 3 else "")


def same_count(steps: Sequence[Step], row: Dict[str, Any]) -> int:
    """CHAIN_ALARM_SAME_GATE：這一次觸發 row 是這道閘、這個對象這一段第幾次——第一次算 1，之後只在跟這道閘這個對象上一次觸發之間
    有記到 AI 看過那次擋訊息才送出、改到檔的動作（跟那次不同一批）、而且這次擋的不是原封不動的同一個呼叫才加 1（CHAIN_SAME_GATE_PER_OBJECT、
    CHAIN_SAME_GATE_NO_ACTION、CHAIN_NO_EDIT_NO_EDGE、CHAIN_SAME_BATCH、CHAIN_SAME_CALL_RETRY）。step 的 actions 是它之後、下一次觸發之前的動作。"""
    gate = row.get("gate")
    n, last, acted = 0, None, False
    for s in steps:
        if s.row.get("gate") == gate and same_object(s.row, row):
            if last is None or (acted and not same_call(last, s.row)):
                n += 1
            last, acted = s.row, False
        acted = acted or (last is not None and any(changes_files(a) and not same_batch(last, a) for a in s.actions))
    return n + 1 if last is None or (acted and not same_call(last, row)) else n


def judge(ch: Chain, row: Dict[str, Any], cfg: Dict[str, Any]) -> Judge:
    """一次新的閘觸發（row 還沒進帳）：接不接上前一步、深度、同閘同對象第幾次、要不要警報。"""
    lk, depth = attach(ch.steps, row)
    gate = str(row.get("gate") or "")
    same = same_count(ch.steps, row)
    if ch.record_only:
        return Judge(True, (), lk, depth, same)
    hits = []
    if same >= cfg["max_same_gate"]:
        obj = target_label(row)
        hits.append(Hit("CHAIN_ALARM_SAME_GATE", f"{gate}（擋 {obj}）這一段第 {same} 次觸發" if obj else f"{gate} 這一段第 {same} 次觸發"))
    if cfg["depth_alarm"] and depth >= cfg["max_depth"]:
        hits.append(Hit("CHAIN_ALARM_DEPTH", f"連鎖深度 {depth}"))
    return Judge(bool(hits), tuple(hits), lk, depth, same)


def muted_again(ch: Chain, gate: str) -> bool:
    """CHAIN_ABORT_RECORD_ONLY：警報後同一道閘這一段已經記過一筆只記錄 → 這次不再記。"""
    return ch.record_only and any(s.muted and s.row.get("gate") == gate for s in ch.steps)


def keeps_blocking(ch: Chain, gate: str) -> bool:
    """CHAIN_HEADLESS_KEEPS_DATA_GATES：警報了、通知記下沒人能答，而這道閘擋的是改使用者資料 → 照擋（不只記錄）。"""
    return ch.alarm is not None and (ch.notice or {}).get("interactive") is False and str(gate) in KEEP_BLOCKING


_TAG_RE = re.compile(r"\[(?:Guardian:)?([A-Za-z][\w-]*)\]")


def gate_name(reason: Any, default: str) -> str:
    """CHAIN_GATE_NAME：擋訊息第一個 [Guardian:名稱]／[名稱] 標記；沒有就用 default。"""
    m = _TAG_RE.search(str(reason or ""))
    return m.group(1) if m else default


def stop_step(ch: Chain) -> Optional[str]:
    """CHAIN_STOP_NOTICE_ONCE：收尾該做什麼——"notice"（擋一次送經過表）／"remind"（不擋、附提醒）／None（不介入）。"""
    if ch.alarm is None:
        return None
    if ch.shown is None:
        return "notice"
    if ch.answer is None and (ch.notice or {}).get("interactive"):
        return "remind"
    return None


def halted(ch: Chain) -> bool:
    """CHAIN_HALT_UNTIL_ANSWER：現在是不是中止停手中（能互動的 session 警報後，使用者還沒選繼續或放行）。
    沒人能答的不停手（CHAIN_HEADLESS_NO_ASK）。"""
    return (ch.alarm is not None and bool((ch.notice or {}).get("interactive", True))
            and (ch.answer or {}).get("choice") != "release")


def _nfkc(s: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(s or "")).split())


def choice_of(pairs: Iterable[Tuple[str, str]], asked: str) -> Optional[Tuple[str, str]]:
    """CHAIN_ANSWER_BY_TOOL_USE_ID：pairs＝wg_release._answers_after 判讀出的 (題目, 答案)；asked＝通知記下的題目。
    取最後一題逐字等於 asked 的，回 (restore｜continue｜release｜other, 原答案)；沒有這一題回 None。"""
    want = _nfkc(asked)
    for q, a in reversed(list(pairs)):
        if CHAIN_TAG not in str(q) or _nfkc(q) != want:
            continue
        ans = _nfkc(a)
        for opt, key in CHOICES.items():
            if ans == _nfkc(opt):
                return key, str(a)
        return "other", str(a)
    return None


def snapshot_need(ch: Chain, path: Any, cfg: Dict[str, Any]) -> Optional[str]:
    """CHAIN_SNAPSHOT_WINDOW：這個檔改之前要不要存快照——"take"／"full"（這一段已存滿，記原因不存）／None（不用）。"""
    if not ch.open or ch.answer is not None or canon_path(path) in ch.snaps:
        return None
    return "full" if len(ch.snaps) >= cfg["snapshot_max_files"] else "take"


class RestoreItem(NamedTuple):
    path: str
    how: str                   # write＝寫回快照｜delete＝連鎖中新建、刪掉｜skip＝沒快照到
    snap: Dict[str, Any]
    why: str
    expect: Optional[str]      # 動手前檔案現在該是什麼：雜湊｜"absent"｜None（判不出 → 不動手）


def restore_plan(ch: Chain) -> Tuple[List[RestoreItem], List[Dict[str, str]]]:
    """CHAIN_RESTORE_SEGMENT：這一段的快照 → 逐檔還原步驟；第二個回傳是這一段改過、卻沒有快照的改動（只列出，不還原）：
    {"path": 檔} 或說不出改了哪些檔的 {"what": 工具與指令}。
    每檔的 expect＝這一段最後一次寫入後記下的內容（action 的 after）；沒寫入過就是快照本身（原本不存在就是 absent）。"""
    last: Dict[str, Any] = {}
    for a in ch.actions():
        for f in _files(a):
            if "after" in f:
                last[canon_path(f["path"])] = f.get("after")
    items = []
    for key, r in ch.snaps.items():
        p = str(r.get("path") or "")
        if r.get("skipped"):
            items.append(RestoreItem(p, "skip", r, str(r["skipped"]), None))
            continue
        base = r.get("sha256") if r.get("existed") else "absent"
        items.append(RestoreItem(p, "write" if r.get("existed") else "delete", r, "", last.get(key, base)))
    missed: List[Dict[str, str]] = []
    for a in ch.actions():
        if a.get("kind") != "edit":
            continue
        files = _files(a)
        if not files:
            missed.append({"what": f"{a.get('tool') or '工具'}：{one_line(a.get('what'), 80)}"})
        missed.extend({"path": str(f["path"])} for f in files if canon_path(f["path"]) not in ch.snaps)
    return items, [dict(t) for t in dict.fromkeys(tuple(m.items()) for m in missed)]


# ─── 給人看的經過表與訊息 ──────────────────────────────────────────────────

_KIND = {"edit": "改", "rerun": "重跑", "card": "寫卡", "relocate": "重交定位", "goal": "改目標樹", "report": "重交報告"}


def short_path(path: Any) -> str:
    parts = [p for p in str(path or "").replace("\\", "/").split("/") if p]
    return "/".join(parts[-3:]) or str(path or "")


def describe_action(a: Dict[str, Any]) -> str:
    """一筆 AI 動作的白話：改 hooks/x.py（+3/−1 行）（只改註解）；說不出改了哪些檔就帶指令。"""
    label = _KIND.get(str(a.get("kind") or ""), "動作")
    files = _files(a)
    if not files:
        what = one_line(a.get("what"), 60) or str(a.get("tool") or "")
        return f"{label}（改了哪些檔判不出）{what}" if a.get("kind") == "edit" else f"{label} {what}".strip()
    parts = []
    for f in files:
        s = short_path(f["path"])
        add, rem = f.get("added"), f.get("removed")
        if isinstance(add, int) and isinstance(rem, int):
            s += f"（+{add}/−{rem} 行）"
        elif isinstance(add, int):
            s += f"（+{add} 行，原內容不明）"
        if f.get("comment_only") is True:
            s += "（只改註解）"
        parts.append(s)
    return f"{label} " + "、".join(parts)


def _cell(text: Any, cap: int = 80) -> str:
    return one_line(text, cap).replace("|", "／")


def _dur(seconds: Any) -> str:
    try:
        s = max(0, int(round(float(seconds))))
    except (TypeError, ValueError):
        return "—"
    return f"{s} 秒" if s < 60 else f"{s // 60} 分 {s % 60:02d} 秒"


def report(ch: Chain, now: float) -> str:
    """連鎖過程表：第幾步、哪道閘、擋的對象（CHAIN_SAME_GATE_PER_OBJECT；說不出寫 —）、擋了什麼、AI 接著做了什麼改動、
    這一步耗時（到下一次觸發或現在）；最後一句總次數與深度。"""
    lines = ["| 步 | 閘 | 擋的對象 | 擋了什麼 | AI 接著做了什麼改動 | 耗時 |", "|---|---|---|---|---|---|"]
    if ch.lead:
        lines.append("| 0 | （選繼續之後） | — | — | " + "；".join(describe_action(a) for a in ch.lead) + " | — |")
    for i, s in enumerate(ch.steps):
        nxt = ch.steps[i + 1] if i + 1 < len(ch.steps) else None
        what = _cell(s.row.get("what"))
        if s.link is not None and not s.link.linked:
            what += f"（沒接上前一步：{s.link.why}）"
        if s.row.get("kept"):
            what += "（沒人能答，會改使用者資料照擋）"
        elif s.muted:
            what += "（只記錄）"
        elif s.row.get("record_only"):
            what += "（這一次讓警報響：改送中止）"
        acts = "；".join(describe_action(a) + ("（跟這一步同一則回覆送出）" if same_batch(s.row, a) else "")
                         for a in s.actions)
        if not acts:
            acts = f"（沒記到改動：{nxt.link.why}）" if nxt is not None and nxt.link and nxt.link.linked else "—"
        end = nxt.row.get("ts") if nxt is not None else now
        lines.append(f"| {i + 1} | {_cell(s.row.get('gate'), 40)} | {_cell(target_label(s.row), 60) or '—'} | {what} | {acts} | "
                     f"{_dur(_float(end) - _float(s.row.get('ts')))} |")
    lines.append(f"總共連鎖 {ch.count} 次、深度 {ch.depth}")
    return "\n".join(lines)


def _float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _reason(ch: Chain) -> str:
    hits = (ch.alarm or {}).get("hits") or []
    return "、".join(f"{h[1]}（{h[0]}）" for h in hits if isinstance(h, (list, tuple)) and len(h) >= 2) or "連鎖超過門檻"


def question(ch: Chain) -> str:
    """該問的題目：通知記下的那一題（警報那一刻定），還沒有通知就照現在的次數與深度組。"""
    asked = (ch.notice or {}).get("question")
    return str(asked) if asked else f"{RELEASE_TAG}{CHAIN_TAG}本回合閘連鎖 {ch.count} 次、深度 {ch.depth}，要怎麼處理？"


def _ask_line(ch: Chain) -> str:
    return (f"\n把上表貼給使用者，用 AskUserQuestion 問一題（單選），題目照抄「{question(ch)}」，"
            f"選項固定三個：「{OPT_RESTORE}」「{OPT_CONTINUE}」「{OPT_RELEASE}」。")


def _headless_tail(no_ask: str) -> str:
    return (f"\n無法互動（{no_ask}）：不問使用者、不還原。照常把工作做完，收尾報告附上上表，"
            "寫明「連鎖中止：連鎖改動沒有還原，等使用者決定」。")


def _abort_head(ch: Chain, lead: str) -> str:
    no_ask = (ch.notice or {}).get("why") or ""
    stop = ("閘要的東西不用再補；動資料檔、改舊測試、commit 前、專案改根層核心這幾道會改使用者資料的閘照擋，照它的擋訊息補宣告"
            if no_ask else "使用者選之前，除了讀檔與 AskUserQuestion，其他工具一律先停手")
    return f"[Guardian:{GATE}] {lead}：{_reason(ch)}。這一回合其餘閘只記錄不擋，不用再修補；{stop}。\n"


REPLACED_CAP = 2000


def _replaced_tail(replaced: str) -> str:
    """CHAIN_ABORT_SHOWS_REPLACED_BLOCK：被中止換掉的那次擋，原擋訊息（含附註）照附在最後；超過 REPLACED_CAP 字留開頭（缺什麼、附註在前段）。"""
    text = str(replaced or "").strip()
    if not text:
        return ""
    if len(text) > REPLACED_CAP:
        text = f"{text[:REPLACED_CAP]}…（後面略，原文共 {len(text)} 字）"
    return f"\n\n這一次讓警報響、被中止訊息換掉的擋，原本說：\n{text}"


def notice_text(ch: Chain, now: float, replaced: str = "") -> str:
    """CHAIN_STOP_NOTICE_ONCE／CHAIN_HEADLESS_NO_ASK：警報後 Stop 擋那一次的訊息（能不能互動看通知記下的 why）。
    replaced＝讓警報響、被這則換掉的那次擋的原擋訊息（CHAIN_ABORT_SHOWS_REPLACED_BLOCK；警報不在這次響就不給）。"""
    no_ask = (ch.notice or {}).get("why") or ""
    return (_abort_head(ch, "連鎖中止") + report(ch, now) + (_headless_tail(no_ask) if no_ask else _ask_line(ch))
            + _replaced_tail(replaced))


def halt_text(ch: Chain, now: float, replaced: str = "") -> str:
    """CHAIN_HALT_UNTIL_ANSWER：中止停手中擋下工具呼叫的訊息；replaced 同 notice_text（讓警報響的那次工具呼叫才給）。"""
    no_ask = (ch.notice or {}).get("why") or ""
    choice = (ch.answer or {}).get("choice")
    if choice:
        did = "已選還原" if choice == "restore" else "沒選三選項之一"
        return (f"[Guardian:{GATE}] 連鎖中止：使用者{did}，這一回合不再動手，只能讀檔與回報，等使用者下一則指示。"
                f"總共連鎖 {ch.count} 次、深度 {ch.depth}")
    return (_abort_head(ch, "連鎖中止中") + report(ch, now) + (_headless_tail(no_ask) if no_ask else _ask_line(ch))
            + _replaced_tail(replaced))


def remind_text(ch: Chain) -> str:
    return (f"[Guardian:{GATE}] 連鎖中止中，還沒收到使用者三選一（題目照抄「{question(ch)}」）；"
            f"這一回合其餘閘只記錄，改檔先停手。總共連鎖 {ch.count} 次、深度 {ch.depth}")


def answer_text(choice: str, raw: str, results: Sequence[Dict[str, Any]] = (), missed: Sequence[Dict[str, str]] = ()) -> str:
    """照使用者答案做完之後給模型與使用者看的一段。"""
    if choice == "restore":
        ok = [r for r in results if r.get("ok")]
        bad = [r for r in results if not r.get("ok")]
        n_del = sum(1 for r in ok if r.get("how") == "delete")
        text = (f"[Guardian:{GATE}] 已照使用者選擇還原連鎖改動：寫回 {len(ok) - n_del} 檔、刪掉連鎖中新建的 {n_del} 檔"
                f"（重讀比對過）；連鎖前的改動沒動。")
        if bad:
            text += "\n沒還原成功：" + "；".join(f"{short_path(r.get('path'))}（{r.get('why')}）" for r in bad)
        if missed:
            text += "\n改過但沒快照、沒還原：" + "；".join(
                short_path(m["path"]) if m.get("path") else f"{m.get('what')}（改了哪些檔判不出）" for m in missed)
        return text + "\n這一回合其餘閘只記錄。"
    if choice == "continue":
        return (f"[Guardian:{GATE}] 使用者選繼續：連鎖次數歸零，閘照常擋；同樣額度（深度、同一道閘次數）再超會再問。")
    if choice == "release":
        return f"[Guardian:{GATE}] 使用者選放行這一回合：這一回合其餘閘只記錄不擋。"
    return f"[Guardian:{GATE}] 使用者沒選三選項之一（答：{one_line(raw, 60)}）：維持中止，這一回合其餘閘只記錄。"


# ─── 工具呼叫的事實：算不算 AI 動作、是不是唯讀指令 ───────────────────────

_EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
_SHELL_TOOLS = ("Bash", "PowerShell")


def action_of(tool_name: Any, tool_input: Any, tool_response: Any, writes: Sequence[str] = (), unknown_write: bool = False,
              ran_tests: bool = False) -> Optional[Tuple[str, List[Dict[str, Any]], str]]:
    """CHAIN_ACTION_FACTS：PostToolUse 的一次工具呼叫 → (kind, files, what)；不算動作回 None。
    writes＝呼叫端算出的寫入目標（絕對路徑）、unknown_write＝有寫入訊號但算不出目標、ran_tests＝這次是跑測試或驗證。"""
    tool = str(tool_name or "")
    ti = tool_input if isinstance(tool_input, dict) else {}
    if tool in _EDIT_TOOLS:
        return "edit", edit_facts(tool, ti, tool_response), ""
    if tool in _SHELL_TOOLS:
        cmd = str(ti.get("command") or "")
        if writes or unknown_write:
            return "edit", [{"path": str(p), "added": None, "removed": None, "comment_only": None} for p in writes], cmd
        if ran_tests:
            return "rerun", [], cmd
        return None if readonly_shell(tool, cmd) else ("other", [], cmd)
    if tool.endswith(("atom_write", "atom_retire")):
        return "card", [], tool.rsplit("__", 1)[-1]
    if tool.endswith(("anti_evasion_report", "knowledge_harvest_report")):
        return "report", [], tool.rsplit("__", 1)[-1]
    if tool.endswith("need_goal"):
        return "goal", [], f"need_goal {ti.get('action') or ''}".strip()
    if tool in ("Agent", "Task"):
        return "other", [], f"{tool}：{one_line(ti.get('description') or ti.get('prompt'), 60)}"
    return None


_READ_CMDS = frozenset(("cat", "head", "tail", "grep", "egrep", "fgrep", "rg", "ls", "dir", "wc", "pwd", "cd", "echo", "printf",
                        "type", "file", "stat", "du", "df", "which", "where", "cut", "tr", "diff", "cmp", "basename", "dirname",
                        "realpath", "readlink", "true", "nl", "jq", "sort"))
_RUNS_PROGRAM = ("--pre", "--compress-program")          # rg 前處理、sort 壓縮程式：會跑別的程式
_GIT_RUNS = ("--output", "--ext-diff", "-O", "--open-files-in-pager", "--exec-path")
_SED_OPTS = frozenset(("-n", "--quiet", "--silent", "-E", "-r", "--regexp-extended"))
_PS_READ = frozenset(("get-content", "gc", "get-childitem", "gci", "get-item", "gi", "select-string", "sls", "test-path",
                      "get-location", "resolve-path", "measure-object", "select-object", "where-object", "sort-object",
                      "format-list", "format-table", "write-output", "ls", "dir", "cat", "type", "pwd", "cd", "set-location"))
_VCS_READ = {"git": frozenset(("status", "log", "diff", "show", "blame", "ls-files", "rev-parse", "grep", "cat-file", "describe")),
             "svn": frozenset(("status", "st", "log", "diff", "info", "cat", "list", "ls", "blame"))}
_FIND_WRITES = frozenset(("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"))
_SED_PRINT = re.compile(r"^(?:\d+|\d+,\d+|\$)?p$")
_NULL_SINKS = ("/dev/null", "$null", "nul")


def readonly_shell(tool_name: Any, command: Any) -> bool:
    """CHAIN_HALT_UNTIL_ANSWER 的唯讀指令：每一段（; && || | 換行切）都是白名單裡的讀檔指令、沒有寫檔重導向（> /dev/null、2>&1 除外）、
    沒有指令替換 $( ) 與反引號、沒有 <( ) >( )。git／svn 只認查詢子指令（git 不准 -c 設定覆寫與會叫外部程式、寫檔的參數）；
    find 不准 -exec／-delete 這類；sed 只認 `-n` 加一段印行腳本（不准 -e／-f）；sort 不准 -o（含黏著寫）；rg、sort 不准叫別的程式；
    PowerShell 只認讀取 cmdlet、不准括號與大括號（裡面能執行任何命令）。判不出（引號沒收尾、拆不開）回 False。
    這是停手的護欄，不是沙箱：白名單外的一律當成會動手。"""
    segs = _shell_segments(str(command or ""))
    if segs is None:
        return False
    ps = str(tool_name or "") == "PowerShell"
    return all(_readonly_segment(seg, ps) for seg in segs)


def _shell_segments(cmd: str) -> Optional[List[str]]:
    """引號外依 ; & | 換行切段；遇到指令替換、行程替換、寫檔重導向回 None。"""
    segs: List[str] = []
    buf: List[str] = []
    quote = ""
    i, n = 0, len(cmd)
    while i < n:
        c = cmd[i]
        if quote:
            if c == quote:
                quote = ""
            elif c == "\\" and quote == '"' and i + 1 < n:
                buf.append(c)
                i += 1
                c = cmd[i]
            elif c == "$" and quote == '"' and cmd.startswith("$(", i):
                return None
            elif c == "`" and quote == '"':
                return None
            buf.append(c)
            i += 1
            continue
        if c in "'\"":
            quote = c
        elif c == "`" or cmd.startswith(("$(", "<(", ">("), i):
            return None
        elif c == ">":
            j = i + 1 + (cmd[i + 1:i + 2] == ">")
            target = re.match(r"\s*(&\d|[^\s;&|<>]+)", cmd[j:])
            if not target or not (target.group(1).startswith("&") or target.group(1).lower() in _NULL_SINKS):
                return None
            i = j + target.end()
            continue
        elif c in ";&|\n":
            segs.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if quote:
        return None
    segs.append("".join(buf))
    return [s for s in (x.strip() for x in segs) if s]


def _readonly_segment(seg: str, ps: bool) -> bool:
    toks = seg.split()
    while toks and re.match(r"^[A-Za-z_]\w*=", toks[0]):
        toks = toks[1:]
    if not toks:
        return True
    name = os.path.basename(toks[0].strip("'\"")).lower()
    name = name[:-4] if name.endswith(".exe") else name
    args = [t.strip("'\"") for t in toks[1:]]
    if ps:
        return name in _PS_READ and not any(c in seg for c in "(){}")
    if any(a.startswith(_RUNS_PROGRAM) for a in args):
        return False
    if name in _VCS_READ:
        if "-c" in args or any(a.startswith(_GIT_RUNS) for a in args):
            return False
        sub = next((a for k, a in enumerate(args) if not a.startswith("-") and (k == 0 or args[k - 1] != "-C")), "")
        return sub in _VCS_READ[name]
    if name == "find":
        return not _FIND_WRITES & set(args)
    if name == "sed":
        opts, rest = [a for a in args if a.startswith("-")], [a for a in args if not a.startswith("-")]
        return "-n" in opts and set(opts) <= _SED_OPTS and bool(rest) and bool(_SED_PRINT.match(rest[0]))
    if name == "sort" and any(a.startswith("--output") or (a.startswith("-") and not a.startswith("--") and "o" in a)
                              for a in args):
        return False
    return name in _READ_CMDS


# ─── 編輯的事實：行數與 comment_only ─────────────────────────────────────

_PY = (".py", ".pyw")
_JS = (".js", ".mjs", ".cjs", ".jsx", ".ts", ".tsx")
_CLIKE = _JS + (".cs", ".java", ".c", ".h", ".cc", ".cpp", ".hpp")
_SH = (".sh", ".bash", ".zsh")
_DIFF_MAX_LINES = 20000


def edit_facts(tool_name: str, tool_input: Dict[str, Any], tool_response: Any) -> List[Dict[str, Any]]:
    """PostToolUse 的 Edit／MultiEdit／Write／NotebookEdit → 每個改到的檔 {path, added, removed, comment_only}。
    行數：Edit 用 old_string／new_string 片段逐行比，Write 用前後全文；comment_only 用前後全文
    （tool_response.originalFile 套上這次的改動），拿不到全文才退回片段。其他工具回空清單
    （Bash 改檔由呼叫端給 files 或空清單，comment_only 記 unknown）。"""
    ti = tool_input if isinstance(tool_input, dict) else {}
    tr = tool_response if isinstance(tool_response, dict) else {}
    orig = tr.get("originalFile") if isinstance(tr.get("originalFile"), str) else None
    if tool_name == "NotebookEdit":
        path = ti.get("notebook_path")
        return [{"path": str(path), "added": None, "removed": None, "comment_only": None}] if path else []
    path = ti.get("file_path")
    if not path:
        return []
    if tool_name == "Write":
        after = str(ti.get("content") or "")
        before = orig if orig is not None else ("" if tr.get("type") == "create" else None)
        add, rem = line_delta(before, after) if before is not None else (len(after.splitlines()), None)
        return [{"path": str(path), "added": add, "removed": rem, "comment_only": comment_only(before, after, path)}]
    if tool_name == "Edit":
        edits = [ti]
    elif tool_name == "MultiEdit":
        edits = [e for e in ti.get("edits") or () if isinstance(e, dict)]
    else:
        return []
    add = rem = 0
    full: Optional[str] = orig
    for e in edits:
        old, new = str(e.get("old_string") or ""), str(e.get("new_string") or "")
        a, r = line_delta(old, new)
        add, rem = add + a, rem + r
        if full is not None and old and old in full:
            full = full.replace(old, new) if e.get("replace_all") else full.replace(old, new, 1)
        else:
            full = None
    if orig is not None and full is not None:
        co = comment_only(orig, full, path)
    elif len(edits) == 1:
        co = comment_only(str(edits[0].get("old_string") or ""), str(edits[0].get("new_string") or ""), path)
    else:
        co = None
    return [{"path": str(path), "added": add, "removed": rem, "comment_only": co}]


def line_delta(a: str, b: str) -> Tuple[int, int]:
    """兩段文字逐行比：(新增行數, 刪除行數)。先剝掉頭尾相同的行，中間太大就整段算。"""
    al, bl = str(a).splitlines(), str(b).splitlines()
    i = 0
    while i < min(len(al), len(bl)) and al[i] == bl[i]:
        i += 1
    j = 0
    while j < min(len(al), len(bl)) - i and al[-1 - j] == bl[-1 - j]:
        j += 1
    am, bm = al[i:len(al) - j], bl[i:len(bl) - j]
    if len(am) + len(bm) > _DIFF_MAX_LINES:
        return len(bm), len(am)
    add = rem = 0
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, am, bm, autojunk=False).get_opcodes():
        if op in ("replace", "delete"):
            rem += i2 - i1
        if op in ("replace", "insert"):
            add += j2 - j1
    return add, rem


def comment_only(before: Optional[str], after: Optional[str], path: Any) -> Optional[bool]:
    """CHAIN_COMMENT_ONLY_RECORDED：True＝兩邊去掉註解與空白後相同；False＝改到程式；None＝判不了。
    Python 沿用 COMMENT_ONLY_CHANGE 的 ast 比法（docstring 也算註解；片段先 dedent 再試）；JS／TS、C#、Java、C／C++
    與 bash 用下面的掃描器（字串、樣板字串、JS 正規式、C# @"…"、C#／Java \"\"\"…\"\"\" 裡的註解記號不算）；
    其他副檔名（Go 的反引號原始字串、Rust 的 'a 生命週期這類掃描器會讀錯的也在內）、二進位、掃到結尾還在字串或區塊註解裡 → None。"""
    if before is None or after is None or "\x00" in before or "\x00" in after:
        return None
    ext = os.path.splitext(str(path))[1].lower()
    if ext in _PY:
        got = comment_only_change(before, after, "x.py")
        return got if got is not None else comment_only_change(textwrap.dedent(before), textwrap.dedent(after), "x.py")
    if ext in _CLIKE:
        a, b = _strip_clike(before, ext), _strip_clike(after, ext)
    elif ext in _SH:
        a, b = _strip_sh(before), _strip_sh(after)
    else:
        return None
    return None if a is None or b is None else a == b


def _clike_pattern(js: bool, triple: bool, verbatim: bool) -> "re.Pattern[str]":
    alts = [r"(?P<lc>//[^\n]*)", r"(?P<bc>/\*[\s\S]*?\*/)"]
    if triple:
        alts.append(r'(?P<raw>"""[\s\S]*?""")')
    if verbatim:
        alts.append(r'(?P<verb>@"(?:[^"]|"")*")')
    alts.append(r"""(?P<str>"(?:[^"\\\n]|\\[\s\S])*"|'(?:[^'\\\n]|\\[\s\S])*')""")
    if js:
        alts.append(r"(?P<tpl>`(?:[^`\\]|\\[\s\S])*`)")
    alts += [r"(?P<ws>\s+)", r"""(?P<run>[^\s"'`/@]+)""", r"(?P<one>[\s\S])"]
    return re.compile("|".join(alts))


_CLIKE_RE = {key: _clike_pattern(*key) for key in ((False, False, False), (True, False, False),
                                                    (False, True, True), (False, True, False))}
_JS_REGEX = re.compile(r"/(?![*/])(?:[^/\\\n\[]|\\.|\[(?:[^\]\\\n]|\\.)*\])+/[A-Za-z]*")
_JS_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
_JS_REGEX_KW = re.compile(r"(?:^|[^\w$])(?:return|typeof|case|do|else|in|of|new|delete|void|throw|yield|await)$")
_WORD = re.compile(r"[\w$]")


def _strip_clike(src: str, ext: str) -> Optional[str]:
    """C 系語法：去掉 // 與 /* */ 註解、字串外的空白（兩個字詞中間留一格）；字串原樣留。沒收尾的字串或區塊註解 → None。"""
    js = ext in _JS
    pat = _CLIKE_RE[(js, ext in (".cs", ".java"), ext == ".cs")]
    out: List[str] = []
    gap = False
    i, n = 0, len(src)
    while i < n:
        m = pat.match(src, i)
        kind, tok = m.lastgroup, m.group()
        if kind in ("lc", "bc", "ws"):
            gap, i = True, m.end()
            continue
        if kind == "one":
            if tok in "\"'" or (tok == "`" and js) or src.startswith("/*", i):
                return None
            if js and tok == "/" and (not out or out[-1][-1] in _JS_REGEX_AFTER or _JS_REGEX_KW.search(out[-1])):
                rm = _JS_REGEX.match(src, i)
                if rm:
                    tok = rm.group()
        if gap and out and _WORD.match(out[-1][-1]) and _WORD.match(tok[0]):
            out.append(" ")
        out.append(tok)
        gap, i = False, i + len(tok)
    return "".join(out)


_SH_RE = re.compile(r"""(?P<sq>'[^']*')|(?P<dq>"(?:[^"\\]|\\[\s\S])*")|(?P<esc>\\[\s\S])|(?P<nl>\n)|(?P<ws>[ \t\r]+)"""
                    r"""|(?P<meta>[;|&()<>])|(?P<run>[^\s'"\\#;|&()<>]+)|(?P<one>[\s\S])""")
_SH_HEREDOC = re.compile(r"(?<!<)<<(?!<)(-?)\s*(['\"]?)([A-Za-z_]\w*)\2")


def _strip_sh(src: str) -> Optional[str]:
    """bash：字詞開頭的 # 到行尾是註解（$#、${#x}、a#b 不是）；引號內原樣；空白縮成一格、去空行；
    heredoc 內文原樣留到結束標記。沒收尾的引號 → None。"""
    lines: List[str] = []
    cur: List[str] = []
    word_start = True
    i, n = 0, len(src)
    while i < n:
        m = _SH_RE.match(src, i)
        kind, tok = m.lastgroup, m.group()
        i = m.end()
        if kind == "one" and tok == "#" and word_start:
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if kind == "one" and tok in "'\"":
            return None
        if kind == "nl":
            line = "".join(cur).strip()
            cur, word_start = [], True
            if line:
                lines.append(line)
            hd = _SH_HEREDOC.search(line)
            if hd:
                i = _copy_heredoc(src, i, hd.group(3), bool(hd.group(1)), lines)
            continue
        if kind == "ws":
            if cur and cur[-1] != " ":
                cur.append(" ")
            word_start = True
            continue
        cur.append(tok)
        word_start = kind == "meta"
    line = "".join(cur).strip()
    if line:
        lines.append(line)
    return "\n".join(lines)


def _copy_heredoc(src: str, i: int, delim: str, dash: bool, lines: List[str]) -> int:
    """heredoc 內文逐行原樣收進 lines，回結束標記那一行之後的位置（沒有結束標記就收到檔尾）。"""
    while i < len(src):
        j = src.find("\n", i)
        end = len(src) if j < 0 else j
        body = src[i:end]
        i = end + 1
        if (body.lstrip("\t") if dash else body).rstrip("\r") == delim:
            break
        lines.append("\x01" + body)
    return i
