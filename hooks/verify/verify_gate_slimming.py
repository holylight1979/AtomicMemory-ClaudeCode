"""verify_gate_slimming.py — 守門瘦身（少驗幾次、hook 少載、評分與收尾減量）的行為案例。

做什麼：每件一段，驗砍掉的重複真的不再發生（舊碼跑是紅的），同時驗原本在擋「需要判斷的事」的入口還在。
怎麼跑：python -X utf8 -m pytest -q hooks/verify/verify_gate_slimming.py
       python -X utf8 hooks/verify/verify_gate_slimming.py   （直接跑，尾行 GATE_SLIMMING_CHECK PASS／FAIL）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))


# ─── 文字評分手動叫 ─────────────────────────────────

def test_text_score_skill_is_callable():
    """skill text-score 存在、可叫、指向 text-score.py，而且每條指令都帶 --goal（預設規格要 {{goal}}，沒帶就永遠不評）。"""
    md = (HOOKS_DIR.parent / "skills" / "text-score" / "SKILL.md").read_text(encoding="utf-8")
    assert "user-invocable: true" in md and "tools/text-score.py" in md
    runs = [ln for ln in md.splitlines() if "python ~/.claude/tools/text-score.py" in ln]
    assert runs and all("--goal" in ln for ln in runs), runs


# ─── 收尾檢核、收割報告、交付信合成一份 ─────────────────────────────

def _aec_drive(monkeypatch, tmp_path, tool_input, tool_response=None):
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import verify_aec_emission_gate as vae
    from handlers import post_tool_use as pt
    if tool_response is not None:
        state = {"turn_seq": 7}
        for name, fn in (("_ensure_state", lambda *a, **k: state), ("write_state", lambda *a, **k: None),
                         ("_hud_alive", lambda *a, **k: (False, {"reason": "test"})),
                         ("append_guard_log", lambda *a, **k: None), ("_spawn_hud_edge", lambda *a, **k: None)):
            monkeypatch.setattr(pt, name, fn)
        monkeypatch.setattr(pt, "WORKFLOW_DIR", tmp_path)
        with pytest.raises(SystemExit):
            pt.handle_post_tool_use({"session_id": "sid", "tool_name": "mcp__workflow-guardian__anti_evasion_report",
                                     "tool_input": tool_input, "tool_response": tool_response},
                                    {"docdrift": {"enabled": False}, "aec": {}})
        return state
    return vae._drive_ptu(monkeypatch, tmp_path, tool_input)


_SKIP = [{"source": "decision", "summary": "這次的取捨寫在程式註解裡", "action": "skip", "reason": "讀程式就看得到"}]


def _aec_input(**over):
    base = {"a": "無", "b": "無", "d": "見收割報告", "h": "可關閉", "i": "無", "j_evidence_path": "無", "k_followups": "無",
            "report": "做了什麼：改了 x。驗了什麼：verify 全綠。沒做什麼：無。追蹤項：無。"}
    base.update(over)
    return base


def test_aec_carries_harvest_items_in_one_call(monkeypatch, tmp_path):
    """收割清單跟收尾檢核同一次交：核對過就算本回合收割，(d)「見收割報告」不再被當成欠寫
    （舊碼不認 harvest_items → (d) 欠著、要再呼叫 knowledge_harvest_report → 紅）。"""
    import wg_harvest
    state = _aec_drive(monkeypatch, tmp_path, _aec_input(harvest_items=_SKIP))
    aec = state["anti_evasion_report"]
    assert "d_pending" not in aec, aec.get("d_pending")
    assert wg_harvest.validated_this_turn(state, "sid", 7)
    assert aec["report"].startswith("做了什麼")


def test_aec_without_harvest_still_owes_see_harvest(monkeypatch, tmp_path):
    """反例：沒交 harvest_items 又寫「見收割報告」→ 照舊欠著（入口還在）。"""
    state = _aec_drive(monkeypatch, tmp_path, _aec_input())
    assert any("見收割報告" in x for x in state["anti_evasion_report"]["d_pending"])


def test_aec_rejected_by_mcp_is_not_recorded(monkeypatch, tmp_path):
    """MCP 端拒收的那次呼叫（isError）不當報告收（舊碼照收 → 紅）。"""
    state = _aec_drive(monkeypatch, tmp_path, _aec_input(), tool_response={"isError": True, "content": []})
    assert "anti_evasion_report" not in state


@pytest.mark.skipif(not __import__("shutil").which("node"), reason="node not available")
def test_aec_node_side_report_makes_efg_optional():
    """Node 端：給了 report → e／f／g 可省；沒給 report → e／f／g 照擋；harvest_items 形狀錯 → 擋；schema 不再把 e／f／g 列必填。"""
    import json
    import subprocess
    lib = HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib"
    script = ("const p=require('path');const lib=process.argv[1];const ae=require(p.join(lib,'anti-evasion.js'));"
              "const m=require(p.join(lib,'mcp.js'));const t=m.TOOL_DEFINITIONS.find(x=>x.name==='anti_evasion_report');"
              "console.log(JSON.stringify({req:t.inputSchema.required,props:Object.keys(t.inputSchema.properties),"
              "withReport:ae.aecArgErrors({report:'r'},true),noReport:ae.aecArgErrors({},true),"
              "v6off:ae.aecArgErrors({report:'r'},false),badItems:ae.aecArgErrors({report:'r',harvest_items:[{}]},true)}));")
    res = subprocess.run(["node", "-e", script, str(lib)], capture_output=True, text=True, encoding="utf-8")
    assert res.returncode == 0, res.stderr
    got = json.loads(res.stdout.strip().splitlines()[-1])
    assert not {"e", "f", "g"} & set(got["req"]) and {"report", "harvest_items"} <= set(got["props"])
    assert got["withReport"] == [] and len(got["noReport"]) == 3 and len(got["v6off"]) == 3 and got["badItems"]


def test_hud_card_shows_report():
    """HUD 卡片有 report 就顯示「收尾全文」（給了 report 省掉 e／f／g 時，人看得到那段內容；舊碼不顯示 → 紅）。
    內層瀏覽器 script 的語法由 verify_aec_hud_inner_js 驗。"""
    js = (HOOKS_DIR.parent / "tools" / "workflow-guardian-mcp" / "lib" / "aec-hud-html.js").read_text(encoding="utf-8")
    i = js.index("function cardHtml(r)")
    body = js[i:js.index("function renderCard", i)]
    assert "r.report" in body and "收尾全文" in body


def test_delivery_letter_is_the_closing_report():
    """交付信範本：同一份白話全文，寫法照「做了什麼／驗了什麼／沒做什麼／追蹤項」，不再預設一長串欄位。"""
    md = (HOOKS_DIR.parent / "skills" / "console" / "references" / "delivery.md").read_text(encoding="utf-8")
    for want in ("做了什麼", "驗了什麼", "沒做什麼", "追蹤項", "report"):
        assert want in md, want
    assert "盤點（改前 → 改後）" not in md


# ─── Codex 只審一輪（工作軌規矩：只寫在總控台 skill） ─────────────

def test_codex_one_round_is_console_only():
    """「Codex 只審一輪、只收弄壞資料／繞閘」是開發期的工作軌規矩：寫在 skills/console。"""
    md = (HOOKS_DIR.parent / "skills" / "console" / "SKILL.md").read_text(encoding="utf-8")
    assert "Codex 只審一輪" in md and "【弄壞資料】" in md


# ─── 總控台流程（文字規則，沒有程式閘） ───────────────────

_CONSOLE = HOOKS_DIR.parent / "skills" / "console"


def _template(md: str) -> str:
    i = md.index("## 派工單範本")
    return md[i:md.index("```", md.index("```markdown", i) + 3)]


def test_dispatch_template_has_only_four_parts():
    """派工單只寫四樣：做什麼、怎麼驗、不准碰什麼，加一句原始目標（舊範本另有定死／判斷入口／紅案例／做法 → 紅）。"""
    tpl = _template((_CONSOLE / "references" / "dispatch.md").read_text(encoding="utf-8"))
    heads = [ln[3:].strip() for ln in tpl.splitlines() if ln.startswith("## ") and ln[3:].strip() != "派工單範本"]
    assert heads == ["做什麼", "怎麼驗", "不准碰什麼"], heads
    assert "原始目標：" in tpl


def test_kickoff_says_no_history_snapshot():
    """工作軌開工句：不讀歷史快照（接續單、交接備忘、舊交付信）。"""
    md = (_CONSOLE / "references" / "kickoff.md").read_text(encoding="utf-8")
    sec = md[md.index("## 3. 工作軌"):md.index("### 3b.")]
    assert "不讀歷史快照" in sec


def test_merge_rules_fast_forward_and_no_third_run():
    """可快轉不補驗直接推；兩軌碰同一大檔，總控台不跑第三次（舊規則「解過衝突時補驗」→ 紅）。"""
    md = (_CONSOLE / "SKILL.md").read_text(encoding="utf-8")
    assert "可快轉（分支已含最新 main）不補驗、直接推" in md and "總控台不跑第三次" in md
    assert "補驗只在候選基底落後 main 或解過衝突時跑" not in md


# ─── worktree 根的一次性 git 啟動器不算改程式 ──────────────────────────

_LAUNCH_SRC = 'import subprocess' + chr(10) + 'subprocess.run(["git", "status"])' + chr(10)


@pytest.fixture()
def git_repo(tmp_path, monkeypatch):
    import subprocess
    import wg_verify_ledger as vl
    repo = tmp_path / "wt"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    monkeypatch.setattr(vl, "LAUNCHER_DIR", tmp_path / "markers")
    return vl, repo


def test_launcher_rejects_program_swaps():
    """codex 反例：清單首項留 git、用 executable／shell／env 換掉實際跑的程式，或 git 用 -c alias、submodule foreach 叫別的程式 → 不算啟動器。"""
    import wg_release_rules as rr
    nl = chr(10)
    bad = ['import subprocess' + nl + 'subprocess.run(["git", "x.py"], executable="python")' + nl,
           'import subprocess' + nl + 'subprocess.run(["git", "status", "&", "python", "x.py"], shell=True)' + nl,
           'import subprocess' + nl + 'subprocess.run(["git", "-c", "alias.x=!python x.py", "x"])' + nl,
           'import subprocess' + nl + 'subprocess.run(["git", "submodule", "foreach", "python x.py"])' + nl,
           'import subprocess' + nl + 'subprocess.run(["git", "rebase", "--exec", "python x.py", "main"])' + nl,
           'import subprocess' + nl + 'subprocess.run(["git", "status"], None, None, None, None, None, None, "python")' + nl]
    assert not any(rr.is_git_launcher_source(b) for b in bad)
    assert rr.is_git_launcher_source('import subprocess' + nl + 'subprocess.run(["git", "status"], capture_output=True, text=True, cwd="x")' + nl)


def test_note_git_launcher_root_untracked_only(git_repo):
    """版控根、沒追蹤、只跑 git → 記標記；子目錄裡的、已追蹤的、內容不只跑 git 的 → 不記（照算程式）。"""
    import subprocess
    vl, repo = git_repo
    root_l = repo / "_once.py"
    root_l.write_text(_LAUNCH_SRC, encoding="utf-8")
    assert vl.note_git_launcher(str(root_l)) is True and vl.git_launcher(str(root_l))
    sub = repo / "tools"
    sub.mkdir()
    (sub / "_once.py").write_text(_LAUNCH_SRC, encoding="utf-8")
    assert vl.note_git_launcher(str(sub / "_once.py")) is False and not vl.git_launcher(str(sub / "_once.py"))
    tracked = repo / "_kept.py"
    tracked.write_text(_LAUNCH_SRC, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "_kept.py"], check=True)
    assert vl.note_git_launcher(str(tracked)) is False


def test_note_git_launcher_edit_into_code_drops_marker_delete_keeps_it(git_repo):
    """改成不只跑 git → 拿掉標記；刪掉之後標記還在（刪除也不算改程式）；非 .py 不管。"""
    vl, repo = git_repo
    f = repo / "_once.py"
    f.write_text(_LAUNCH_SRC, encoding="utf-8")
    assert vl.note_git_launcher(str(f)) is True
    f.write_text(_LAUNCH_SRC + 'open("a", "w")' + chr(10), encoding="utf-8")
    assert vl.note_git_launcher(str(f)) is False and not vl.git_launcher(str(f))
    f.write_text(_LAUNCH_SRC, encoding="utf-8")
    vl.note_git_launcher(str(f))
    f.unlink()
    assert vl.note_git_launcher(str(f)) is None and vl.git_launcher(str(f))
    assert vl.note_git_launcher(str(repo / "run.sh")) is None


def test_console_skill_launcher_order_no_rerun():
    """工作軌守則：啟動器建、刪不算改程式，不再要求「刪啟動器 → 再跑一次 verify」。"""
    md = (HOOKS_DIR.parent / "skills" / "console" / "SKILL.md").read_text(encoding="utf-8")
    assert "LAUNCHER_NOT_CODE" in md and "刪啟動器 → 再跑一次 verify" not in md


# ─── hook 每次啟動只載入要用的部分 ─────────────────────────────────

def _loaded_after_import(module: str) -> set:
    """在乾淨的子行程 import module，回載進來的模組名。"""
    import json
    import subprocess
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import importlib; importlib.import_module(sys.argv[2]); "
            "print(json.dumps(sorted(sys.modules)))")
    r = subprocess.run([sys.executable, "-c", code, str(HOOKS_DIR), module], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return set(json.loads(r.stdout.strip().splitlines()[-1]))


@pytest.mark.parametrize("module, not_loaded", [
    ("dispatcher", {"dataclasses", "logging", "socket", "difflib"}),
    ("handlers.post_tool_use", {"ollama_client", "urllib.request", "wg_vcs_sync", "logging"}),
    ("handlers.stop", {"ollama_client", "urllib.request", "turn_metrics_cs", "reading_path_cs", "cs_roslyn", "logging"}),
    ("handlers.user_prompt_submit", {"ollama_client", "urllib.request", "logging"}),
])
def test_hook_import_on_use(module, not_loaded):
    """HOOK_IMPORT_ON_USE：每個事件 import handler 時，用不到的重模組不先載（舊碼每次都載 → 紅）。"""
    got = _loaded_after_import(module) & not_loaded
    assert not got, f"{module} 一 import 就載了 {sorted(got)}"


def test_lazy_names_still_patchable_and_callable():
    """改成惰性入口後，名字還在模組上（測試照換得掉），呼叫時才真的載。"""
    import wg_episodic as ep
    from handlers import post_tool_use as pt
    import wg_reading_path as rp
    for mod, name in ((ep, "write_raw"), (ep, "get_client"), (ep, "move_atom_pair"), (pt, "spawn_vcs_sync"),
                      (pt, "_trigger_incremental_index"), (rp, "metrics_for_files"), (rp, "parse_diff_ranges")):
        assert callable(getattr(mod, name)), name
    rp.parse_diff_ranges("")                         # 呼叫時才真的載 turn_metrics，載得到


def test_module_patterns_compiled_on_first_use():
    """模組層正規表示式第一次用到才編譯：import 完一條都還沒編（舊碼 import 時全編 → 紅）；用一次就編好、結果跟 re 一樣。"""
    import json
    import subprocess
    code = ("import sys, json; sys.path.insert(0, sys.argv[1]); import wg_release_rules as rr, wg_evasion as ev, wg_core as wc; "
            "from wg_lazy_re import LazyPattern; "
            "ps=[v for m in (rr, ev, wc) for v in vars(m).values() if isinstance(v, LazyPattern)]; "
            "print(json.dumps([len(ps), sum(1 for v in ps if v._rx is not None)]))")
    r = subprocess.run([sys.executable, "-c", code, str(HOOKS_DIR)], capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    total, compiled = json.loads(r.stdout.strip().splitlines()[-1])
    assert total >= 100 and compiled == 0, (total, compiled)
    import re
    from wg_lazy_re import lazy_re
    lz = lazy_re(r"(\d+)-(\w+)", re.I)
    assert lz.pattern == r"(\d+)-(\w+)" and lz._rx is None
    assert lz.search("x 12-AB").groups() == re.compile(r"(\d+)-(\w+)", re.I).search("x 12-AB").groups()
    assert lz.sub("#", "1-a 2-b") == "# #" and lz.flags & re.I


# ─── state 讀寫收斂 ────────────────────────────────────────────────

def test_state_written_compact_and_unchanged_not_rewritten(tmp_path, monkeypatch):
    """state 落檔不縮排；讀進來沒改就寫回 → 不重寫檔（舊碼每次都縮排重寫 → 紅）；有改照寫。"""
    import os
    import wg_core
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "state_path", lambda sid: tmp_path / f"state-{sid}.json")
    wg_core.write_state("s1", {"session": {"id": "s1"}, "turn_seq": 1, "modified_files": []})
    p = tmp_path / "state-s1.json"
    assert "\n" not in p.read_text(encoding="utf-8").strip()
    st = wg_core.read_state("s1")
    import time
    t = time.time_ns() - 10**10                      # 十秒前：還在協調窗口內，沒重寫的話 mtime 不會動
    os.utime(p, ns=(t, t))
    before = p.stat().st_mtime_ns
    wg_core.write_state("s1", st)
    assert p.stat().st_mtime_ns == before
    st["turn_seq"] = 2
    wg_core.write_state("s1", st)
    assert wg_core.read_state("s1")["turn_seq"] == 2 and p.stat().st_mtime_ns != before


def test_unchanged_state_still_touched_for_coordination(tmp_path, monkeypatch):
    """沒變的 state 不重寫，但檔快過跨 session 協調的掃描窗口時碰一下 mtime（別的 session 還看得到它活著）。"""
    import os
    import wg_core
    monkeypatch.setattr(wg_core, "WORKFLOW_DIR", tmp_path)
    monkeypatch.setattr(wg_core, "state_path", lambda sid: tmp_path / f"state-{sid}.json")
    wg_core.write_state("s2", {"session": {"id": "s2"}, "turn_seq": 1})
    p = tmp_path / "state-s2.json"
    st = wg_core.read_state("s2")
    old = p.stat().st_mtime - 3600
    os.utime(p, (old, old))
    wg_core.write_state("s2", st)
    assert p.stat().st_mtime > old + 3000


# ─── CHANGELOG 各軌寫自己的片段，合併時彙整 ─────────────────────────

_FOLD = HOOKS_DIR.parent / "skills" / "console" / "scripts" / "changelog-fold.py"


def _fold(*args):
    import subprocess
    return subprocess.run([sys.executable, "-X", "utf8", str(_FOLD), *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8")


def test_changelog_fold_inserts_fragments_newest_first(tmp_path):
    """兩軌各寫一個片段：收進主檔 --- 之後、新日期在前、同日依檔名，收完刪片段（舊流程沒有這支工具 → 紅）。"""
    main = tmp_path / "_CHANGELOG.md"
    main.write_text("# 變更記錄" + chr(10) + chr(10) + "---" + chr(10) + "## 2026-10-01 舊的" + chr(10) + "- 舊" + chr(10),
                    encoding="utf-8")
    d = tmp_path / "frags"
    d.mkdir()
    (d / "track-b-001.md").write_text("## 2026-10-22 B 的改動" + chr(10) + "- b" + chr(10), encoding="utf-8")
    (d / "track-a-002.md").write_text("## 2026-10-22 A 的改動" + chr(10) + "- a" + chr(10), encoding="utf-8")
    (d / "track-c-001.md").write_text("## 2026-10-21 C 的改動" + chr(10) + "- c" + chr(10), encoding="utf-8")
    r = _fold("--write", "--dir", d, "--changelog", main)
    assert r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "CHANGELOG_FOLD DONE folded=3", r.stdout + r.stderr
    heads = [ln for ln in main.read_text(encoding="utf-8").splitlines() if ln.startswith("## ")]
    assert heads == ["## 2026-10-22 B 的改動", "## 2026-10-22 A 的改動", "## 2026-10-21 C 的改動", "## 2026-10-01 舊的"]
    assert not list(d.glob("*.md"))


def test_changelog_fold_bad_fragment_touches_nothing(tmp_path):
    """片段第一行不是「## 日期 標題」→ --check FAIL、--write 一個都不動（exit 2）。"""
    main = tmp_path / "_CHANGELOG.md"
    main.write_text("# x" + chr(10) + "---" + chr(10), encoding="utf-8")
    d = tmp_path / "frags"
    d.mkdir()
    (d / "ok.md").write_text("## 2026-10-22 好的" + chr(10), encoding="utf-8")
    (d / "bad.md").write_text("沒有標題" + chr(10), encoding="utf-8")
    assert _fold("--check", "--dir", d, "--changelog", main).stdout.strip().endswith("CHANGELOG_FOLD_CHECK FAIL")
    r = _fold("--write", "--dir", d, "--changelog", main)
    assert r.returncode == 2 and (d / "ok.md").exists() and main.read_text(encoding="utf-8") == "# x" + chr(10) + "---" + chr(10)


def test_tracks_told_to_write_fragments():
    """開工句與總控台守則講：工作軌寫 _AIDocs/_changelog.d/<軌>-<NNN>.md，合併時跑 changelog-fold（多軌規矩，不寫進 rules）。"""
    kick = (HOOKS_DIR.parent / "skills" / "console" / "references" / "kickoff.md").read_text(encoding="utf-8")
    skill = (HOOKS_DIR.parent / "skills" / "console" / "SKILL.md").read_text(encoding="utf-8")
    assert "_changelog.d" in kick and "changelog-fold.py --write" in skill


if __name__ == "__main__":
    rc = pytest.main([__file__, "-q", "-p", "no:cacheprovider"])
    print("GATE_SLIMMING_CHECK PASS" if rc == 0 else "GATE_SLIMMING_CHECK FAIL")
    sys.exit(0 if rc == 0 else 1)
