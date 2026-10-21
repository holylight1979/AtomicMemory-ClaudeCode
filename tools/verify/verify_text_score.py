"""verify_text_score.py：tools/text-score.py 與 tools/text-score-weekly.py（G15 文字規格評分）。

做什麼：
- 規格是資料：真規格 reader-designer 解析出的條目與切法、條目一律正面問；另一份臨時規格（代號 Q1、Q2、切「前 2 句」）不改程式照樣跑；
  格式錯（缺鍵、代號≠檔名、沒過時亂寫、看不懂的程式切法、沒有模型判、超過 8 條、判例代號不存在、沒來源）→ exit 2、說哪裡錯、不問裁判。
- 切範圍：開頭 --- 檔頭、標題不算句子、去掉引用與清單符號、code 區塊與網址不送；前 N 句；候選詞只收像代號的字。
- 引用校驗：全半形、markdown 記號、空白不計，「…」分段依序；抄題目、順序顛倒、改寫、只在切範圍外 → 作廢；判否沒附引用 → 作廢。
- 分數由程式算：裁判多帶 score 欄也不看；是＋不適用＝過；必過「否」→ 不過；必過作廢 → 未定。
- 裁判：假 Ollama（127.0.0.1 的 HTTP 伺服器；回應形狀錄自真 gemma4:e4b 的 /api/chat）；--model 換模型時每台都送那個模型、
  第一台 404 換第二台；都不在 → 「裁判不在，未評」、exit 0、留帳記未評；程式裡沒有付費模型或子行程的路。
- 留帳欄位：時間、session、規格代號與雜湊、來源、每條結果、模型、秒數、token；prompt_eval_count 貼著 num_ctx → 該條作廢。
- 自動評入口：enabled=false、種類不在 auto_targets、來源路徑不符該類的路徑樣式（stdin 沒有路徑）、字數不到 min_chars
  → 「不評」且不問裁判（同案先跑一次會問的對照）。
- 尾巴一行（--tail-line）：stdout 只有摘要一行、照樣留帳；裁判不在印未評；不評時 stdout 空、原因走 stderr。
- 週彙總：每條每週過率、趨勢、作廢數、裁判不在數、壞行計數、尾行。
- config：workflow/config.json 的 text_score 段與工具 DEFAULTS 相同。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_text_score.py
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
import threading
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "text-score.py"
WEEKLY = ROOT / "tools" / "text-score-weekly.py"
SPEC_FILE = ROOT / "text-specs" / "reader-designer.md"
DONE_RE = re.compile(r"^[A-Z][A-Z0-9_]* DONE( \w+=\S+)*$")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


TS = _load("text_score_under_test", TOOL)

# 錄自真 gemma4:e4b（內網 Ollama /api/chat，2026-10-21）的回應；各案只換 model、content、prompt_eval_count
RECORDED = {
    "model": "gemma4:e4b",
    "created_at": "2026-10-21T07:48:59.155548494Z",
    "message": {"role": "assistant", "content": ""},
    "done": True,
    "done_reason": "stop",
    "total_duration": 4096222910,
    "load_duration": 3617387658,
    "prompt_eval_count": 339,
    "prompt_eval_duration": 101026000,
    "eval_count": 52,
    "eval_duration": 375431000,
}

GOOD = """# 全機殘留清理：結果

全機殘留清理做完了，你不需要動作。

- 結果（為了 G13）：暫存資料夾從 180 樣降到 89 樣（試過）。
- 留下的：一個叫 worker-1 的工作資料夾（看不出還有沒有人在用），先不刪。
"""

TWO_SPEC = """# 評分規格：測試用

- 規格代號: tmp-two
- 適用: 測試
- 讀者: 測試讀者
- 讀者目的: 測試目的
- 通過線: 必過項全部「是」或「不適用」，其餘「否」最多 1 個
- 維護: 測試

## 檢核項

| 代號 | 問題（答 是／否／不適用） | 判法 | 必過 | 沒過時 | 來源 |
|---|---|---|---|---|---|
| Q1 | 前兩句有講結論嗎？ | 程式切出前 2 句 → 模型判 | 必過 | 記帳 | 測試 |
| Q2 | 有說憑什麼嗎？ | 模型判 |  | 提醒 | 測試 |

## 判例

| 代號 | 會判「是」 | 會判「否」 |
|---|---|---|
| Q1 | 做完了。 | 因為以前… |
"""


class Fake:
    """假 Ollama：GET /api/tags 回 200；POST /api/chat 依題目裡的「檢核項 <代號>：」回 answers[代號]。"""

    def __init__(self, chat_status: int = 200):
        self.answers: Dict[str, Any] = {}
        self.prompt_counts: Dict[str, int] = {}
        self.overrides: Dict[str, Dict[str, Any]] = {}   # 代號 → 直接蓋掉回應欄位（送型別怪異的回應）
        self.requests: List[Dict[str, Any]] = []
        self.chat_status = chat_status
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _send(self, code: int, obj: Dict[str, Any]) -> None:
                body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                self._send(200, {"models": []})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)))
                fake.requests.append(payload)
                if fake.chat_status != 200:
                    self._send(fake.chat_status, {"error": "model not found"})
                    return
                iid = item_of(payload)
                ans = fake.answers.get(iid, {"quote": "", "reason": "沒問題", "verdict": "是"})
                resp = copy.deepcopy(RECORDED)
                resp["model"] = payload["model"]
                resp["message"]["content"] = ans if isinstance(ans, str) else json.dumps(ans, ensure_ascii=False)
                resp["prompt_eval_count"] = fake.prompt_counts.get(iid, RECORDED["prompt_eval_count"])
                resp.update(fake.overrides.get(iid, {}))
                self._send(200, resp)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def asked(self) -> List[str]:
        return [item_of(p) for p in self.requests]


def item_of(payload: Dict[str, Any]) -> str:
    return re.search(r"檢核項 (\S+?)：", payload["messages"][0]["content"]).group(1)


def body_of(payload: Dict[str, Any]) -> str:
    return payload["messages"][0]["content"].split("=====原文開始=====\n", 1)[1].split("\n=====原文結束=====", 1)[0]


@pytest.fixture
def fake():
    f = Fake()
    yield f
    f.close()


def closed_url() -> str:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    return f"http://127.0.0.1:{port}"


def backend(url: str, priority: int = 1, model: str = "gemma4:e4b") -> Dict[str, Any]:
    return {"base_url": url, "llm_model": model, "priority": priority}


def data_root(tmp_path: Path, backends: Dict[str, Any], text_score: Dict[str, Any] = None) -> Path:
    root = tmp_path / "data"
    (root / "workflow").mkdir(parents=True, exist_ok=True)
    cfg: Dict[str, Any] = {"vector_search": {"ollama_backends": backends}}
    if text_score is not None:
        cfg["text_score"] = text_score
    (root / "workflow" / "config.json").write_text(json.dumps(cfg, ensure_ascii=False), encoding="utf-8")
    return root


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def run(root: Path, *args: Any, tool: Path = TOOL) -> subprocess.CompletedProcess:
    env = {**os.environ, "WG_CLAUDE_DIR": str(root)}
    return subprocess.run([sys.executable, "-X", "utf8", str(tool), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env, cwd=str(root), timeout=120)


def records(root: Path) -> List[Dict[str, Any]]:
    log = root / "Logs" / "guard-text_score.jsonl"
    return [json.loads(x) for x in log.read_text(encoding="utf-8").splitlines()] if log.exists() else []


def tail(out: str) -> str:
    last = out.strip().splitlines()[-1]
    assert DONE_RE.match(last), last
    return last


# ─── 規格是資料 ───────────────────────────────────────────────────────────────

def test_real_spec_parses_items_scopes_and_hash():
    spec = TS.load_spec("reader-designer")
    rows = [line.split("|")[1].strip() for line in SPEC_FILE.read_text(encoding="utf-8").split("## 判例")[0].splitlines()
            if re.match(r"^\| [A-Z]\d", line)]
    assert [it.id for it in spec.items] == rows and len(rows) == 7
    assert [it.scope for it in spec.items[:3]] == [("first", 1), ("first", 3), ("candidates", 0)]
    assert all(it.scope == ("full", 0) for it in spec.items[3:])
    assert all(it.must and it.on_fail == "記帳" and it.source for it in spec.items)   # 七條同一等級、沒過時＝記帳
    assert [it.id for it in spec.items if it.good and it.bad] == rows[:4]
    assert spec.sha == hashlib.sha256(SPEC_FILE.read_bytes()).hexdigest()[:16]
    assert spec.allow_fail == 0
    assert not any("找得到" in it.question for it in spec.items) and "找得到" not in TS.PROMPT   # 一律正面問：通過＝答「是」


def test_other_spec_runs_without_code_change(tmp_path, fake):
    spec_file = write(tmp_path, "tmp-two.md", TWO_SPEC)
    src = write(tmp_path, "t.md", "# 標題\n\n做完了。缺一件。第三句不該送給 Q1。\n")
    fake.answers = {"Q1": {"quote": "做完了。", "reason": "有結論", "verdict": "是"},
                    "Q2": {"quote": "缺一件。", "reason": "沒證據", "verdict": "否"}}
    p = run(data_root(tmp_path, {"a": backend(fake.url)}), src, "--spec", spec_file)
    assert p.returncode == 0, p.stderr
    assert fake.asked() == ["Q1", "Q2"]
    q1, q2 = fake.requests
    assert body_of(q1) == "做完了。\n缺一件。" and "第三句" in body_of(q2)
    assert "會判「是」的例子：做完了。" in q1["messages"][0]["content"]
    assert "| Q2 | 否 |" in p.stdout and "R1" not in p.stdout
    assert "評分 1/2｜沒過：Q2" in p.stdout and "｜過｜" in p.stdout     # 非必過的否在容許的 1 個以內
    assert tail(p.stdout).startswith("TEXT_SCORE DONE spec=tmp-two pass=1 fail=1 na=0 void=0 unscored=0 secs=")


BAD_SPECS = [
    ("缺讀者目的", lambda s: s.replace("- 讀者目的: 測試目的\n", ""), "缺"),
    ("代號不等於檔名", lambda s: s.replace("規格代號: tmp-two", "規格代號: other"), "要跟檔名"),
    ("沒過時亂寫", lambda s: s.replace("| 記帳 |", "| 警告 |"), "沒過時只能是"),
    ("看不懂的切法", lambda s: s.replace("程式切出前 2 句", "程式切出最後一句"), "看不懂"),
    ("沒有模型判", lambda s: s.replace("| 模型判 |", "| 程式判 |"), "沒有「模型判」"),
    ("超過八條", lambda s: s.replace("| Q2 |", "\n".join(f"| X{i} | 問？ | 模型判 |  | 記帳 | 測試 |" for i in range(8))
                                    + "\n| Q2 |"), "超過上限"),
    ("判例代號不存在", lambda s: s.replace("| Q1 | 做完了。", "| Q9 | 做完了。"), "不在檢核項表"),
    ("沒來源", lambda s: s.replace("| 提醒 | 測試 |", "| 提醒 |  |"), "沒有來源"),
    ("判法沒有箭頭", lambda s: s.replace("程式切出前 2 句 → 模型判", "程式切出前 2 句，再模型判"), "看不懂"),
    ("前零句", lambda s: s.replace("程式切出前 2 句", "程式切出前 0 句"), "看不懂"),
    ("通過線寫錯", lambda s: s.replace("其餘「否」最多 1 個", "其餘否最多兩個"), "通過線要寫成"),
]


@pytest.mark.parametrize("label,mutate,needle", BAD_SPECS, ids=[b[0] for b in BAD_SPECS])
def test_bad_spec_exits_2_without_asking_judge(tmp_path, fake, label, mutate, needle):
    root = data_root(tmp_path, {"a": backend(fake.url)})
    src = write(tmp_path, "t.md", "做完了。缺一件。\n")
    ok = run(root, src, "--spec", write(tmp_path, "tmp-two.md", TWO_SPEC))   # 對照：好規格會問裁判
    assert ok.returncode == 0 and len(fake.requests) == 2
    (tmp_path / "bad").mkdir()
    bad = write(tmp_path / "bad", "tmp-two.md", mutate(TWO_SPEC))
    p = run(root, src, "--spec", bad)
    assert p.returncode == 2 and needle in p.stderr, (p.returncode, p.stderr)
    assert len(fake.requests) == 2


# ─── 切範圍 ───────────────────────────────────────────────────────────────────

def test_sentences_skip_headings_markers_code_and_urls():
    text = ("# 大標\n\n> **狀態**：做完了。你不需要動作！\n\n## 小標\n\n- 第三句在清單裡\n1. 第四句？\n"
            "```\nprint('程式裡的句子。')\n```\n看 https://example.com/a。最後一句\n|---|---|\n")
    sents = TS.sentences(text)
    assert sents[:4] == ["**狀態**：做完了。", "你不需要動作！", "第三句在清單裡", "第四句？"]
    assert sents[-1] == "最後一句"                       # 網址後面直接接中文，網址拿掉、中文留著
    assert not any("程式裡" in s or "example.com" in s or "標" in s for s in sents)
    item = TS.Item("X", "q", "m", True, "記帳", "s", ("first", 3))
    body, note = TS.scope_for(item, TS.clean_text(text), sents)
    assert body == "**狀態**：做完了。\n你不需要動作！\n第三句在清單裡" and "前 3 句" in note


def test_sentences_quoted_heading_and_english_periods():
    assert TS.sentences("> # 引用裡的標題\n> 結論在這。\n")[0] == "結論在這。"
    assert TS.sentences("Done. No action needed. See tools/text-score.py for v6.0 details.\n") == [
        "Done.", "No action needed.", "See tools/text-score.py for v6.0 details."]


LETTER = "---\nto: track-x\nseq: 002\n---\n# 交付\n\n做完了，你不需要動作。\n"


@pytest.mark.parametrize("text,first", [
    (LETTER, "做完了，你不需要動作。"),
    (LETTER.replace("\n", "\r\n"), "做完了，你不需要動作。"),          # stdin 進來的 CRLF
    ("---\n\n開頭是水平線的正文。\n\n---\n結尾。\n", "開頭是水平線的正文。"),   # 不是「鍵: 值」開頭就不是檔頭
    ("---\nhttps://example.com\n這段正文不能消失。\n---\n結論。\n", "這段正文不能消失。"),   # https: 不算鍵
    ("---\n注意: 此版本尚未完成\n付款流程仍會失敗。\n---\n請暫緩發布。\n", "注意: 此版本尚未完成"),   # 框裡有一行正文就不是檔頭
    ("---\n注意: 此版本尚未完成\n# 付款流程仍會失敗\n---\n請暫緩發布。\n", "注意: 此版本尚未完成"),   # 標題不是檔頭
    ("---\n注意: 此版本尚未完成\n  付款流程仍會失敗。\n---\n請暫緩發布。\n", "注意: 此版本尚未完成"),  # 縮排正文也不是
    ("---\nto: track-x\nfiles:\n  - a.md\n  - b.md\n---\n做完了。\n", "做完了。"),                      # 巢狀清單照樣是檔頭
])
def test_frontmatter_is_not_reader_text(text, first):
    assert TS.sentences(text)[0] == first
    body = TS.clean_text(text)
    assert "track-x" not in body and "track-x" not in TS.candidates(body)
    assert "seq" not in "".join(TS.sentences(text))


def test_candidates_only_code_like_words():
    text = "改用 `list --all --json` 逐 key 判，gemma4:e4b 與 worker-1、HEAD、R1，以及 hook 和 session 跟 text-score.py。"
    cands = TS.candidates(text)
    assert cands == ["list --all --json", "gemma4:e4b", "worker-1", "HEAD", "R1", "text-score.py"]


# ─── 引用校驗 ─────────────────────────────────────────────────────────────────

SOURCE = "**結論**：全機殘留清理做完了，你不需要動作。\n改用 `list --all --json` 逐 key 判，刪了 100 項。"


@pytest.mark.parametrize("quote,ok", [
    ("全機殘留清理做完了，你不需要動作。", True),
    ("結論：全機殘留清理做完了,你不需要動作", True),                   # markdown 記號、半形逗號、少句號
    ("「改用 list --all --json 逐 key 判」", True),                     # 外加引號、inline code 記號拿掉
    ("全機殘留清理…你不需要動作", True),
    ("全機殘留清理...刪了 100 項", True),
    ("你不需要動作…全機殘留清理", False),                               # 順序顛倒
    ("全機殘留清理已經完成，不需要你動作。", False),                     # 改寫
    ("英文代號、指令旗標、設定鍵、檔名", False),                         # 抄題目
])
def test_quote_found(quote, ok):
    assert TS.quote_found(quote, SOURCE) is ok


@pytest.mark.parametrize("quote,source,ok", [
    ("數值abcd", "數值ab>cd", False),                       # 行中間的 > 是原文的字，不能刪
    ("第 1 行結論。第 2 行接著講", "> 第 1 行結論。\n> 第 2 行接著講", True),   # 跨行的引用：行首引用符號不算字
    ("結果：降到 89 樣", "- **結果**：降到 89 樣", True),
    ("……", SOURCE, False),                                    # 只有省略號＝沒有引用
])
def test_quote_found_structure_only_at_line_start(quote, source, ok):
    assert TS.quote_found(quote, source) is ok


def _item(iid: str = "R9", must: bool = True) -> Any:
    return TS.Item(iid, "q", "模型判", must, "記帳", "s", ("full", 0))


def _resp(content: Any) -> Dict[str, Any]:
    r = copy.deepcopy(RECORDED)
    r["message"]["content"] = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
    return r


@pytest.mark.parametrize("answer,truncated,status,verdict,why", [
    ({"quote": "", "reason": "x", "verdict": "否"}, False, "作廢", "否", "判否沒附引用"),
    ({"quote": "", "reason": "x", "verdict": "是"}, False, "判定", "是", ""),
    ({"quote": "", "reason": "x", "verdict": "不適用"}, False, "判定", "不適用", ""),
    ({"quote": "題目裡的字不在原文", "reason": "x", "verdict": "不適用"}, False, "作廢", "不適用", "引用對不到原文"),   # 附了就要對得到
    ({"quote": "全機殘留清理做完了", "reason": "x", "verdict": "大概"}, False, "作廢", None, "判定不是 是／否／不適用"),
    ({"quote": "", "reason": "x", "verdict": None}, False, "作廢", None, "判定不是 是／否／不適用"),
    ({"quote": "", "reason": "x", "verdict": "NONE"}, False, "作廢", None, "判定不是 是／否／不適用"),
    ({"quote": "……", "reason": "x", "verdict": "是"}, False, "作廢", "是", "引用太短，對不出是哪一句"),
    ({"quote": "做完", "reason": "x", "verdict": "否"}, False, "作廢", "否", "引用太短，對不出是哪一句"),
    ({"quote": "全…作。", "reason": "x", "verdict": "否"}, False, "作廢", "否", "引用太短，對不出是哪一句"),   # 省略號不算字
    ({"quote": "完全不在原文的句子", "reason": "x", "verdict": "否"}, False, "作廢", "否", "引用對不到原文"),
    ("我覺得是", False, "作廢", None, "裁判回的不是 JSON"),
    ({"R9": {"quote": "刪了 100 項", "reason": "x", "verdict": "否"}}, False, "判定", "否", ""),   # 另一種形狀
    ({"quote": "刪了 100 項", "reason": "x", "verdict": "No"}, False, "判定", "否", ""),
    ({"quote": "刪了 100 項", "reason": "x", "verdict": "否"}, True, "作廢", "否", "輸入太長，可能被截斷（prompt_eval_count ≥ num_ctx 的 95%）"),
])
def test_check_answer_rules(answer, truncated, status, verdict, why):
    res = TS.check_answer(_item(), _resp(answer), SOURCE, truncated)
    assert (res.status, res.verdict, res.why) == (status, verdict, why)


def test_quote_outside_cut_scope_is_void(tmp_path, fake):
    src = write(tmp_path, "t.md", GOOD)
    fake.answers = {"R1": {"quote": "暫存資料夾從 180 樣降到 89 樣", "reason": "x", "verdict": "是"}}   # 原文有，但不在第一句
    p = run(data_root(tmp_path, {"a": backend(fake.url)}), src)
    assert p.returncode == 0, p.stderr
    assert body_of(fake.requests[0]) == "全機殘留清理做完了，你不需要動作。"
    assert "| R1 | 作廢：引用對不到原文（裁判判是） |" in p.stdout
    assert "評分 6/7｜作廢：R1" in p.stdout and "｜未定｜" in p.stdout      # 必過項作廢＝未定


# ─── 分數由程式算 ─────────────────────────────────────────────────────────────

def test_score_is_computed_by_program(tmp_path, fake):
    src = write(tmp_path, "t.md", GOOD)
    fake.answers = {
        "R1": {"quote": "全機殘留清理做完了", "reason": "x", "verdict": "否", "score": "7/7", "total": 99},
        "R5": {"quote": "", "reason": "x", "verdict": "不適用", "score": 0},
    }
    p = run(data_root(tmp_path, {"a": backend(fake.url)}), src)
    assert p.returncode == 0, p.stderr
    assert "評分 6/7｜沒過：R1" in p.stdout and "｜不過｜" in p.stdout
    assert tail(p.stdout).startswith("TEXT_SCORE DONE spec=reader-designer pass=5 fail=1 na=1 void=0 unscored=0 secs=")
    rec = records(tmp_path / "data")[0]
    assert (rec["score"], rec["total"], rec["overall"]) == (6, 7, "不過")


def test_tally_overall_rules():
    spec = TS.Spec("s", Path("s.md"), "x", {}, [], allow_fail=1)
    R = TS.Result
    must_void = [R("A", True, "作廢", "是", why="引用對不到原文"), R("B", False, "判定", "是")]
    assert TS.tally(spec, must_void)["overall"] == "未定"
    one_other_fail = [R("A", True, "判定", "是"), R("B", False, "判定", "否")]
    assert TS.tally(spec, one_other_fail)["overall"] == "過"
    two_other_fail = one_other_fail + [R("C", False, "判定", "否")]
    assert TS.tally(spec, two_other_fail)["overall"] == "不過"
    all_absent = [R("A", True, "未評", why="裁判不在"), R("B", False, "未評", why="裁判不在")]
    t = TS.tally(spec, all_absent)
    assert (t["overall"], t["summary"]) == ("未評", "評分 未評｜裁判不在")


# ─── 裁判 ─────────────────────────────────────────────────────────────────────

def test_judge_absent_does_not_block_and_is_logged(tmp_path):
    root = data_root(tmp_path, {"rdchat-direct": backend(closed_url()), "local": backend(closed_url(), 3, "qwen3:1.7b")})
    p = run(root, write(tmp_path, "t.md", GOOD))
    assert p.returncode == 0, p.stderr
    assert "裁判不在，未評" in p.stdout and "rdchat-direct、local" in p.stdout
    assert tail(p.stdout).startswith("TEXT_SCORE DONE spec=reader-designer pass=0 fail=0 na=0 void=0 unscored=7 ")
    rec = records(root)[0]
    assert rec["overall"] == "未評" and {(i["status"], i["why"]) for i in rec["items"]} == {("未評", "裁判不在")}


def test_model_override_and_failover_use_same_judge_model(tmp_path):
    down, up = Fake(chat_status=404), Fake()
    try:
        root = data_root(tmp_path, {"rdchat-direct": backend(down.url, 1), "local": backend(up.url, 3, "qwen3:1.7b")})
        p = run(root, write(tmp_path, "t.md", GOOD), "--model", "gemma4:26b")
        assert p.returncode == 0, p.stderr
        assert down.requests and all(r["model"] == "gemma4:26b" for r in down.requests)
        assert len(up.requests) == 7 and {r["model"] for r in up.requests} == {"gemma4:26b"}   # 不換成本機設定的 qwen3:1.7b
        assert records(root)[0]["models_used"] == ["gemma4:26b"]
    finally:
        down.close()
        up.close()


def test_each_backend_uses_its_own_judge_model(tmp_path):
    rd, loc, other = Fake(chat_status=404), Fake(chat_status=404), Fake()
    try:
        root = data_root(tmp_path, {"rdchat-direct": backend(rd.url, 1), "local": backend(loc.url, 2, "qwen3:1.7b"),
                                    "other": backend(other.url, 3, "qwen3:1.7b")},
                         {"judge_model": "fallback:1b",
                          "judge_model_by_backend": {"rdchat-direct": "gemma4:e4b", "local": "qwen3:4b-instruct-2507-q4_K_M"}})
        p = run(root, write(tmp_path, "t.md", GOOD))
        assert p.returncode == 0, p.stderr
        assert rd.requests and {r["model"] for r in rd.requests} == {"gemma4:e4b"}
        assert loc.requests and {r["model"] for r in loc.requests} == {"qwen3:4b-instruct-2507-q4_K_M"}
        assert len(other.requests) == 7 and {r["model"] for r in other.requests} == {"fallback:1b"}   # 沒列到的退到頂層
        rec = records(root)[0]
        assert rec["models_used"] == ["fallback:1b"] and rec["judges"] == {
            "rdchat-direct": "gemma4:e4b", "local": "qwen3:4b-instruct-2507-q4_K_M", "other": "fallback:1b"}
    finally:
        for f in (rd, loc, other):
            f.close()


def test_judge_absent_lists_each_backend_judge(tmp_path):
    root = data_root(tmp_path, {"rdchat-direct": backend(closed_url()), "local": backend(closed_url(), 3, "qwen3:1.7b")})
    p = run(root, write(tmp_path, "t.md", GOOD))   # 沒有 text_score 段 → 照 DEFAULTS 的對照表
    assert "各台裁判：rdchat-direct=gemma4:e4b、local=qwen3:4b-instruct-2507-q4_K_M" in p.stdout, p.stdout
    assert records(root)[0]["judges"] == TS.DEFAULTS["judge_model_by_backend"]


def test_payload_settings_and_no_paid_path(tmp_path, fake):
    root = data_root(tmp_path, {"a": backend(fake.url)}, {"num_ctx": 4096, "judge_model": "gemma4:e4b"})
    assert run(root, write(tmp_path, "t.md", GOOD)).returncode == 0
    r = fake.requests[0]
    assert (r["model"], r["stream"], r["think"]) == ("gemma4:e4b", False, False)
    assert r["options"]["temperature"] == 0 and r["options"]["num_ctx"] == 4096
    assert list(r["format"]["properties"]) == ["quote", "reason", "verdict"]
    assert r["messages"][0]["content"].index("檢核項 R1") < r["messages"][0]["content"].index("=====原文開始=====")
    src = TOOL.read_text(encoding="utf-8")
    assert not re.search(r"anthropic|openai|codex|claude\s+-p|subprocess|urllib|requests|http\.client|socket", src, re.I)
    assert "import ollama_client" in src     # 對外連線只有 ollama_client 這一條


def test_odd_response_types_do_not_crash(tmp_path, fake):
    fake.overrides = {"R2": {"message": {"role": "assistant", "content": {"quote": "x", "verdict": "是"}}},
                      "R3": {"prompt_eval_count": "很多", "eval_count": None}}
    root = data_root(tmp_path, {"a": backend(fake.url)})
    p = run(root, write(tmp_path, "t.md", GOOD))
    assert p.returncode == 0, p.stderr
    item = {i["id"]: i for i in records(root)[0]["items"]}
    assert (item["R2"]["status"], item["R2"]["why"]) == ("作廢", "裁判回的不是 JSON")
    assert (item["R3"]["status"], item["R3"]["prompt_tokens"], item["R3"]["answer_tokens"]) == ("判定", 0, 0)


def test_log_write_failure_is_visible_not_blocking(tmp_path, fake):
    root = data_root(tmp_path, {"a": backend(fake.url)})
    (root / "Logs").write_text("這裡是檔案，不是資料夾", encoding="utf-8")   # 留帳目錄建不起來
    p = run(root, write(tmp_path, "t.md", GOOD))
    assert p.returncode == 0 and len(fake.requests) == 7
    assert "留帳寫不進" in p.stderr and tail(p.stdout).endswith(" logged=0")


# ─── 留帳 ─────────────────────────────────────────────────────────────────────

def test_log_record_fields(tmp_path, fake):
    root = data_root(tmp_path, {"a": backend(fake.url)})
    src = write(tmp_path, "t.md", GOOD)
    p = run(root, src, "--session", "sess-123")
    assert p.returncode == 0, p.stderr
    assert tail(p.stdout).endswith(" logged=1")
    [rec] = records(root)
    datetime.fromisoformat(rec["ts"])
    assert (rec["session"], rec["kind"], rec["spec"]) == ("sess-123", "manual", "reader-designer")
    assert rec["spec_sha"] == hashlib.sha256(SPEC_FILE.read_bytes()).hexdigest()[:16]
    assert rec["source"] == str(src.resolve()) and rec["chars"] == len(GOOD)
    assert rec["model"] == "gemma4:e4b" and rec["judges"] == {"a": "gemma4:e4b"} and rec["secs"] >= 0   # a 不在對照表 → 頂層
    assert (rec["prompt_tokens"], rec["answer_tokens"]) == (7 * 339, 7 * 52)
    assert [i["id"] for i in rec["items"]] == ["R1", "R2", "R3", "R4", "R5", "R6", "R7"]
    assert all({"status", "verdict", "quote", "reason", "why", "secs", "prompt_tokens"} <= set(i) for i in rec["items"])


def test_truncated_input_voids_that_item(tmp_path, fake):
    root = data_root(tmp_path, {"a": backend(fake.url)}, {"num_ctx": 8192})
    fake.prompt_counts = {"R4": 8000, "R6": 9500}   # 實測內網 Ollama 超過 num_ctx 時回報整段長度（比 num_ctx 大）
    assert run(root, write(tmp_path, "t.md", GOOD)).returncode == 0
    item = {i["id"]: i for i in records(root)[0]["items"]}
    assert item["R4"]["status"] == item["R6"]["status"] == "作廢" and "截斷" in item["R4"]["why"]
    assert item["R5"]["status"] == "判定"


def test_json_output_is_one_line_matching_log(tmp_path, fake):
    root = data_root(tmp_path, {"a": backend(fake.url)})
    p = run(root, write(tmp_path, "t.md", GOOD), "--json")
    lines = p.stdout.strip().splitlines()
    assert len(lines) == 2 and DONE_RE.match(lines[1])
    assert json.loads(lines[0]) == records(root)[0]


@pytest.mark.parametrize("answers,line", [
    ({}, "評分 7/7｜全過"),
    ({"R1": {"quote": "全機殘留清理做完了，你不需要動作。", "reason": "", "verdict": "否"},
      "R4": {"quote": "先不刪。", "reason": "", "verdict": "否"}}, "評分 5/7｜沒過：R1、R4"),
    ({"R3": {"quote": "不在原文裡的一句話", "reason": "", "verdict": "是"}}, "評分 6/7｜作廢：R3"),   # 作廢不算全過
])
def test_tail_line_prints_only_the_summary(tmp_path, fake, answers, line):
    fake.answers = answers
    root = data_root(tmp_path, {"a": backend(fake.url)})
    p = run(root, write(tmp_path, "t.md", GOOD), "--tail-line")
    assert p.returncode == 0, p.stderr
    assert p.stdout.splitlines() == [line] and records(root)[0]["summary"] == line   # 照樣留帳


def test_tail_line_judge_absent_and_auto_skip(tmp_path, fake):
    gone = data_root(tmp_path / "gone", {"a": backend(closed_url())})
    p = run(gone, write(tmp_path, "t.md", GOOD), "--tail-line")
    assert p.returncode == 0 and p.stdout.splitlines() == ["評分 未評｜裁判不在"]
    root = data_root(tmp_path / "on", {"a": backend(fake.url)}, {"min_chars": 300})
    p = run(root, write(tmp_path, "t.md", GOOD), "--tail-line", "--auto-kind", "final_reply")
    assert p.returncode == 0 and p.stdout == "" and "不評：" in p.stderr   # 不評：尾巴不加東西，原因走 stderr
    assert fake.requests == [] and records(root) == []


# ─── 自動評入口 ───────────────────────────────────────────────────────────────

LONG = GOOD + "\n" + "這一段是補字數用的白話說明，讓文字超過三百字。" * 15 + "\n"


@pytest.mark.parametrize("cfg,kind,text,why", [
    ({"enabled": False}, "final_reply", LONG, "text_score.enabled=false"),
    ({}, "subagent_reply", LONG, "subagent_reply 不在 text_score.auto_targets"),
    ({"min_chars": 300}, "final_reply", GOOD + "```\n" + "x" * 500 + "\n```\n", "少於 text_score.min_chars=300"),
    ({"min_chars": 300}, "final_reply", "---\nnote: " + "很長的檔頭" * 100 + "\n---\n" + GOOD, "少於 text_score.min_chars=300"),
])
def test_auto_kind_skips_without_asking(tmp_path, fake, cfg, kind, text, why):
    on = data_root(tmp_path / "on", {"a": backend(fake.url)}, {"min_chars": 300})
    assert run(on, write(tmp_path, "long.md", LONG), "--auto-kind", "final_reply").returncode == 0   # 對照：會評
    assert len(fake.requests) == 7 and records(on)[0]["kind"] == "final_reply"
    root = data_root(tmp_path / "off", {"a": backend(fake.url)}, cfg)
    p = run(root, write(tmp_path, "t.md", text), "--auto-kind", kind)
    assert p.returncode == 0 and "不評：" in p.stdout and why in p.stdout, p.stdout
    assert len(fake.requests) == 7 and records(root) == []
    assert tail(p.stdout).startswith("TEXT_SCORE DONE spec=reader-designer pass=0 ") and tail(p.stdout).endswith(" logged=0")


DOC_TARGETS = {"final_reply": [], "docs": ["memory/_staging/*checklist*.md", "_AIDocs/DevHistory/**/*提案*.md"]}


@pytest.mark.parametrize("rel,kind,scored", [
    ("memory/_staging/g15-checklist.md", "docs", True),
    ("_AIDocs/DevHistory/v6.0-x/G15-研究與提案.md", "docs", True),
    ("_AIDocs/DevHistory/提案.md", "docs", True),                        # ** 也可以是零層
    ("notes/g15-checklist.md", "docs", False),
    ("memory/_staging/sub/g15-checklist.md", "docs", False),            # * 不跨資料夾
    ("xmemory/_staging/g15-checklist.md", "docs", False),               # 資料夾名要整段對上
    ("notes/隨手記.md", "final_reply", True),                            # 空清單＝這類不比路徑
])
def test_auto_kind_filters_by_path_patterns(tmp_path, fake, rel, kind, scored):
    root = data_root(tmp_path, {"a": backend(fake.url)}, {"auto_targets": DOC_TARGETS})
    src = tmp_path / "proj" / rel
    src.parent.mkdir(parents=True)
    src.write_text(LONG, encoding="utf-8")
    p = run(root, src, "--auto-kind", kind)
    assert p.returncode == 0, p.stderr
    assert (len(fake.requests), len(records(root))) == ((7, 1) if scored else (0, 0)), p.stdout
    if not scored:
        assert f"不符 text_score.auto_targets.{kind} 的路徑樣式" in p.stdout


@pytest.mark.parametrize("targets", [DOC_TARGETS, {"docs": ["*"]}])   # 「*」也不能比中 stdin
def test_auto_kind_docs_from_stdin_has_no_path(tmp_path, fake, targets):
    root = data_root(tmp_path, {"a": backend(fake.url)}, {"auto_targets": targets})
    env = {**os.environ, "WG_CLAUDE_DIR": str(root)}
    p = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "-", "--auto-kind", "docs"], input=LONG,
                       capture_output=True, text=True, encoding="utf-8", env=env, timeout=120)
    assert p.returncode == 0 and "不評：來源是 stdin、沒有路徑" in p.stdout and fake.requests == []


def test_auto_kind_old_list_config_matches_kind_only(tmp_path, fake):
    root = data_root(tmp_path, {"a": backend(fake.url)}, {"auto_targets": ["final_reply", "docs"]})
    p = run(root, write(tmp_path, "隨手記.md", LONG), "--auto-kind", "docs")
    assert p.returncode == 0, p.stderr
    assert len(fake.requests) == 7 and records(root)[0]["kind"] == "docs"


@pytest.mark.parametrize("path,pattern,ok", [
    (r"C:\Proj\Memory\_Staging\G15-CHECKLIST.MD", "memory/_staging/*checklist*.md", True),   # 不分大小寫
    ("/a/_AIDocs/DevHistory/x/y/z提案.md", "_AIDocs/DevHistory/**/*提案*.md", True),          # ** 多層
    ("/a/docs/[x]+.md", "docs/[x]+.md", True),                                                # 方括號、加號照字面
    ("/a/docs/x.md", "docs/[x].md", False),
    ("/a/docs/ab.md", "docs/a?.md", True),
    ("/a/docs/a/b.md", "docs/a?b.md", False),                                                 # ? 不跨資料夾
])
def test_path_matches(path, pattern, ok):
    assert TS.path_matches(path, [pattern]) is ok


# ─── 週彙總 ───────────────────────────────────────────────────────────────────

def _rec(ts: datetime, verdicts: Dict[str, str], overall: str = "過", sha: str = "a") -> str:
    items = [{"id": k, "status": "判定" if v in ("是", "否", "不適用") else v, "verdict": v if v in ("是", "否", "不適用") else None}
             for k, v in verdicts.items()]
    return json.dumps({"ts": ts.isoformat(timespec="seconds"), "spec": "reader-designer", "spec_sha": sha,
                       "overall": overall, "items": items}, ensure_ascii=False)


def test_weekly_rates_trend_void_and_bad_lines(tmp_path):
    now, before = datetime.now(), datetime.now() - timedelta(days=7)
    log = write(tmp_path, "log.jsonl", "\n".join([
        _rec(before, {"R1": "否", "R2": "是"}),
        _rec(before, {"R1": "是", "R2": "是"}),
        _rec(now, {"R1": "是", "R2": "否", "R3": "作廢"}),
        _rec(now, {"R1": "是", "R2": "是", "R3": "不適用"}, sha="b"),
        _rec(now, {"R1": "未評", "R2": "未評", "R3": "未評"}, overall="未評"),
        "壞掉的一行",
        json.dumps({"ts": now.isoformat(), "spec": "reader-designer", "items": "不是清單"}),
        json.dumps({"ts": now.isoformat(), "spec": "reader-designer", "items": [{"status": "判定"}]}),   # 條目沒 id
        _rec(now - timedelta(days=60), {"R1": "否"}),          # 期間外
    ]) + "\n")
    p = run(tmp_path, "--log", log, "--weeks", "2", "--json", tool=WEEKLY)
    assert p.returncode == 0, p.stderr
    data = json.loads(p.stdout.strip().splitlines()[0])
    s = data["specs"]["reader-designer"]
    assert (s["records"], s["unscored"], s["spec_versions"]) == (5, 1, 2)
    rows = {r["id"]: r for r in s["items"]}
    assert rows["R1"]["rates"] == [0.5, 1.0] and rows["R1"]["trend"] == 50
    assert rows["R2"]["rates"] == [1.0, 0.5] and rows["R2"]["trend"] == -50
    assert rows["R3"]["rates"] == [None, None] and rows["R3"]["void"] == 1 and rows["R3"]["counts"]["不適用"] == 1
    assert tail(p.stdout) == "TEXT_SCORE_WEEKLY DONE weeks=2 records=5 unscored=1 void=1 bad=3"
    assert "讀不懂" in p.stderr
    md = run(tmp_path, "--log", log, "--weeks", "2", tool=WEEKLY).stdout
    assert "| R1 | 50% | 100% | ↑50 | 0 |" in md and "| R2 | 100% | 50% | ↓50 |" in md and "規格改過" in md


# ─── config ───────────────────────────────────────────────────────────────────

def test_config_section_matches_defaults():
    section = json.loads((ROOT / "workflow" / "config.json").read_text(encoding="utf-8"))["text_score"]
    assert {k: v for k, v in section.items() if not k.startswith("_")} == TS.DEFAULTS
