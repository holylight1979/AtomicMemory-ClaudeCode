"""verify_aec_hud_track_label.py — 收尾檢核 HUD 每則報告標「哪一軌」與「這則給誰看」。

背景：原設計者看到背景工作軌寫給總控台的收尾檢核「沒頭沒尾」——報告檔（workflow/aec-report/<sid>-t<turn>.json）
只有 session_id，HUD 卡片標頭只印時間與輪數。報告寫入端在 hooks/handlers（本案不動），由顯示端補推：
軌名＝那個 session 對話紀錄（projects/*/<sid>.jsonl）首則使用者訊息開頭的「track-<名>：」，其次 cwd 在
.claude-wt/<名> 底下就用資料夾名；讀者＝報告第一個非空欄位的首行寫了「給總控台」就標「給總控台」。
正例：API（/api/aec/reports、/api/aec/report/<sid>/<turn>）帶出 track／audience，卡片標頭與歷史格提示印出軌名與讀者；
反例：首行沒寫給總控台的不標、查不到對話紀錄的標頭退回 session 前 8 碼（仍有頭）。
node 不在則 skip；假資料全在 tmp（WG_CLAUDE_DIR 指 tmp），不碰 live。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_aec_hud_track_label.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent  # hooks/verify → hooks → .claude
LIB = ROOT / "tools" / "workflow-guardian-mcp" / "lib"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node not available")

SID_A = "aaaaaaaa-1111-2222-3333-444444444444"   # 開工句帶軌名、首行給總控台
SID_B = "bbbbbbbb-1111-2222-3333-444444444444"   # 沒有軌名開頭，cwd 在 worktree；首行不是給總控台
SID_C = "cccccccc-1111-2222-3333-444444444444"   # 查不到對話紀錄；第一個非空欄位（d）寫給總控台


def _jsonl(path: Path, recs) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in recs), encoding="utf-8")


def _report(sid: str, turn: int, **fields) -> dict:
    base = {"session_id": sid, "turn_seq": turn, "at": f"2026-10-21T1{turn}:00:00+08:00", "severity": "routine",
            "a": "無", "b": "無", "d": "無", "e": "無", "f": "無", "g": "無", "h": "可關閉", "i": "無",
            "j_evidence_path": "無", "k_followups": "無"}
    base.update(fields)
    return base


@pytest.fixture
def data_root(tmp_path):
    root = tmp_path / "data"
    rep = root / "workflow" / "aec-report"
    rep.mkdir(parents=True)
    reports = [
        _report(SID_A, 3, a="track-foo（索引小修），這輪做 X；這則給總控台看，你不需動作\n- x.py:1 — y"),
        _report(SID_B, 4, a="- y.py:2 — z", h="給總控台：合併"),
        _report(SID_C, 5, d="給總控台：請合併 001"),
    ]
    for r in reports:
        (rep / f"{r['session_id']}-t{r['turn_seq']}.json").write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8")
    _jsonl(root / "projects" / "C--Users-x--claude-wt-foo" / f"{SID_A}.jsonl", [
        {"type": "file-history-snapshot", "messageId": "m0"},
        {"type": "user", "cwd": "C:\\Users\\x\\.claude-wt\\foo", "sessionId": SID_A,
         "message": {"role": "user", "content": "track-foo：你是工作軌 track-foo，調度總控台是 claude-17。"}},
    ])
    _jsonl(root / "projects" / "C--Users-x--claude-wt-bar" / f"{SID_B}.jsonl", [
        {"type": "user", "cwd": "C:\\Users\\x\\.claude-wt\\bar", "sessionId": SID_B,
         "message": {"role": "user", "content": [{"type": "text", "text": "幫我看一下這個 bug"}]}},
    ])
    return root


_API = r"""
const ae = require(process.argv[1]);
const out = [];
const res = () => ({ writeHead() {}, end(s) { out.push(JSON.parse(s)); } });
ae.apiAecReports({}, res(), null);
ae.apiAecReport({}, res(), process.argv[2], "3");
console.log(JSON.stringify(out));
"""


def test_api_reports_carry_track_and_audience(data_root):
    env = dict(os.environ, WG_CLAUDE_DIR=str(data_root))
    r = subprocess.run([NODE, "-e", _API, str(LIB / "anti-evasion.js"), SID_A], capture_output=True, text=True,
                       encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    listing, single = json.loads(r.stdout.strip().splitlines()[-1])
    got = {x["session_id"]: (x.get("track"), x.get("audience")) for x in listing["reports"]}
    assert got == {SID_A: ("track-foo", "給總控台"), SID_B: ("bar", ""), SID_C: ("", "給總控台")}, got
    assert (single.get("track"), single.get("audience")) == ("track-foo", "給總控台")


_LATE = r"""
const fs = require("fs"), path = require("path");
const ae = require(process.argv[1]);
const [root, sid] = [process.argv[2], process.argv[3]];
const t0 = Date.now();
const first = ae.sessionTrack(sid, t0);                       // 對話紀錄還沒落檔
const dir = path.join(root, "projects", "C--x--claude-wt-late");
fs.mkdirSync(dir, { recursive: true });
fs.writeFileSync(path.join(dir, sid + ".jsonl"),
  JSON.stringify({ type: "user", isMeta: true, cwd: "C:\\x\\.claude-wt\\late",
                   message: { role: "user", content: "track-wrong：harness 插的說明" } }) + "\n" +
  JSON.stringify({ type: "user", cwd: "C:\\x\\.claude-wt\\late",
                   message: { role: "user", content: "track-late：你是工作軌 track-late" } }) + "\n");
const withinTtl = ae.sessionTrack(sid, t0 + 1000);
const afterTtl = ae.sessionTrack(sid, t0 + 61 * 1000);
console.log(JSON.stringify([first, withinTtl, afterTtl]));
"""


def test_track_missing_at_first_is_rechecked_and_meta_records_skipped(tmp_path):
    """codex 審查指出：第一次查不到就永久快取空值，之後對話紀錄出現也不再查。改成推不到的 60 秒後重查；
    首則使用者紀錄若是 harness 插的 isMeta 說明，跳過它看下一則。"""
    root = tmp_path / "data"
    (root / "projects").mkdir(parents=True)
    env = dict(os.environ, WG_CLAUDE_DIR=str(root))
    sid = "dddddddd-1111-2222-3333-444444444444"
    r = subprocess.run([NODE, "-e", _LATE, str(LIB / "anti-evasion.js"), str(root), sid], capture_output=True,
                       text=True, encoding="utf-8", env=env)
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == ["", "", "track-late"]


_CARD = r"""
const h = require(process.argv[1]);
const s = h.render().match(/<script>([\s\S]*?)<\/script>/)[1];
const el = () => ({ addEventListener() {}, style: {}, innerHTML: "", textContent: "", className: "", querySelectorAll: () => [] });
const document = { getElementById: el, querySelectorAll: () => [] };
const window = { confirm: () => true };
const fetch = () => new Promise(() => {});
const setInterval = () => 0;
function Worker() { throw new Error("no worker"); }
function EventSource() {}
const URL = { createObjectURL: () => "" };
function Blob() {}
const location = { origin: "http://x" };
eval(s);
const cases = JSON.parse(process.argv[2]);
console.log(JSON.stringify(cases.map((r) => ({ card: cardHtml(r), tip: tipOf(r) }))));
"""


def test_card_head_and_grid_tip_show_track_and_audience():
    cases = [
        _report(SID_A, 3, track="track-foo", audience="給總控台"),
        _report(SID_B, 4, track="bar", audience=""),
        _report(SID_C, 5, track="", audience=""),
    ]
    r = subprocess.run([NODE, "-e", _CARD, str(LIB / "aec-hud-html.js"), json.dumps(cases, ensure_ascii=False)],
                       capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    a, b, c = json.loads(r.stdout.strip().splitlines()[-1])
    head = lambda x: x["card"][:x["card"].index("<details")]   # noqa: E731
    assert "track-foo" in head(a) and "給總控台" in head(a)
    assert "bar" in head(b) and "給總控台" not in head(b)
    assert "session cccccccc" in head(c) and "給總控台" not in head(c)   # 查不到軌名：退回 session 前 8 碼
    assert "track-foo" in a["tip"] and "給總控台" in a["tip"] and "session cccccccc" in c["tip"]
