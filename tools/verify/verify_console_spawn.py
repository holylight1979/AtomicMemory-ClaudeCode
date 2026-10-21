"""verify_console_spawn.py：總控台開工作 session 腳本（tools/console-spawn.py）的驗收案例。subprocess 一律假的，不真打 claude。

正例：--method bg 組出的指令是 [claude, "--bg", <開工句>, "--permission-mode", <模式>]、cwd＝worktree、不經 shell；
開工句以 / 開頭原樣進參數；transcript 出現「<軌名> 收到開工」（SendMessage 正文或 assistant 文字）→ PASS、印短 id 與名字；
worktree 無信任而 live 根有 → 補正斜線鍵並印出；--help 有「怎麼跑」。
反例：--worktree 指 live 根／未登記 → FAIL 不起；--prompt-file 不存在 → FAIL；kill switch → FAIL 且訊息點名檔；
已 5 個活著 → 拒並列現有；逾時沒收到 → exit 1、stdout 有開工句 code block 與「退回人貼」；live 根也沒信任 → FAIL；
method=gui → 不起、印退路。
模型：--model 接在指令尾（bg 與 print 都接）；沒給 --model 也沒 config default_model → 指令不含 --model；--model 優先於
config；開工後讀 transcript 最近一則真回應的 message.model 印「模型＝…」，指定了卻對不上或讀不到 → FAIL 印「指定＝…／實際＝…」、
不殺 session；session 第一回合就回 API 錯誤（例：模型 id 不存在）→ 不等逾時、立刻 FAIL 並印 claude 回的錯。
信任寫回（~/.claude.json 其他 session 隨時在寫）：讀完到寫之間別人寫進的鍵寫回後仍在；寫暫存檔中途失敗 → 原檔一個位元組
都沒動、暫存檔與鎖都收掉；換行（LF／CRLF）與結尾有無換行照原檔；寫入在 Claude Code 同一把鎖（<設定檔>.lock 目錄）內、
寫完放掉；鎖被別人拿著 → 真的等到時限才 FAIL、不寫、不動別人的鎖；拿鎖後超過持鎖時限 → 不換上、不刪鎖（可能已換人）；
已信任 → 不拿鎖不寫；檔不存在／不是合法 JSON／格式不對（含 projects 某筆不是物件）→ 不寫、FAIL 印原因退人貼。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_console_spawn.py
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

CLAUDE = Path(__file__).resolve().parents[2]
TOOL = CLAUDE / "tools" / "console-spawn.py"
NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_spec = importlib.util.spec_from_file_location("console_spawn", TOOL)
cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cs)

TRACK = "track-demo"
PROMPT = f"{TRACK}：你是工作軌 {TRACK}，調度總控台是 claude-xx。第一步用 EnterWorktree 切進 …"


class Result:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


class FakeClaude:
    """假的 subprocess.run：記下每次呼叫；`agents --json` 回 self.agents；`--bg` 回短 id 並可觸發 on_bg。"""

    def __init__(self, short_id="abc12345", session_id="abc12345-0000-4000-8000-000000000000"):
        self.calls = []
        self.agents = []
        self.short_id, self.session_id = short_id, session_id
        self.on_bg = None
        self.bg_result = None

    def __call__(self, cmd, **kw):
        self.calls.append({"cmd": list(cmd), **kw})
        if cmd[1:3] == ["agents", "--json"]:
            return Result(0, json.dumps(self.agents))
        if "--bg" in cmd:
            if self.on_bg:
                self.on_bg()
            return self.bg_result or Result(0, f"backgrounded · {self.short_id}\n  claude attach {self.short_id}\n")
        if "-p" in cmd:
            return Result(0, json.dumps({"type": "result", "result": "ok"}))
        raise AssertionError(f"沒料到的指令 {cmd}")

    def bg_calls(self):
        return [c for c in self.calls if "--bg" in c["cmd"]]


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s


class World:
    """暫存的 live 根＋登記好的 worktree＋開工句檔＋信任檔＋資料根。"""

    def __init__(self, tmp: Path):
        self.live = tmp / "live"
        self.wt = tmp / "wt" / "track-demo"
        self.wt.mkdir(parents=True)
        reg = self.live / ".git" / "worktrees" / "track-demo"
        reg.mkdir(parents=True)
        (reg / "gitdir").write_text(str(self.wt / ".git") + "\n", encoding="utf-8")
        (self.wt / ".git").write_text(f"gitdir: {reg}\n", encoding="utf-8")
        (self.live / "workflow").mkdir()
        self.prompt_file = tmp / "kickoff.txt"
        self.prompt_file.write_text(PROMPT, encoding="utf-8")
        self.claude_bin = tmp / "claude.exe"
        self.claude_bin.write_text("", encoding="utf-8")
        self.config = tmp / "claude.json"
        self.config.write_text(json.dumps({"projects": {cs.trust_key(self.live): {"hasTrustDialogAccepted": True}}}),
                               encoding="utf-8")
        self.data = tmp / "data"
        (self.data / "projects").mkdir(parents=True)

    def argv(self, **over):
        base = {"--track": TRACK, "--worktree": str(self.wt), "--branch": TRACK, "--prompt-file": str(self.prompt_file),
                "--permission-mode": "bypassPermissions", "--claude-bin": str(self.claude_bin), "--timeout": "90",
                "--poll": "3"}
        base.update(over)
        return [x for k, v in base.items() for x in (k, v) if v is not None]

    def write_transcript(self, session_id: str, blocks, model=None, extra=()) -> Path:
        """blocks=None 就不寫那則 assistant、只寫 extra（例：第一回合只有 API 錯誤訊息的 session）。"""
        d = self.data / "projects" / cs.cwd_slug(self.wt)
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{session_id}.jsonl"
        lines = [json.dumps({"type": "user", "message": {"content": PROMPT}})]
        if blocks is not None:
            msg = {"content": blocks, **({"model": model} if model else {})}
            lines.append(json.dumps({"type": "assistant", "message": msg}, ensure_ascii=False))
        lines += [json.dumps(r, ensure_ascii=False) for r in extra]
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return p

    def write_spawn_config(self, **spawn) -> None:
        (self.live / "workflow" / "config.json").write_text(json.dumps({"console": {"spawn": spawn}}), encoding="utf-8")


@pytest.fixture
def world(tmp_path):
    return World(tmp_path)


def run(world: World, fake: FakeClaude, clock: Clock, capsys, **over):
    code = cs.main(world.argv(**over), run_fn=fake, sleep_fn=clock.sleep, now_fn=clock.now,
                   config_path=world.config, data_dir=world.data)
    return code, capsys.readouterr().out


def sendmessage_block(text: str) -> dict:
    return {"type": "tool_use", "name": "SendMessage", "input": {"to": "claude-xx", "message": text}}


def arm_kickoff(world: World, fake: FakeClaude, blocks, model=None, extra=()):
    """--bg 一跑就讓 agents 清單有它、transcript 寫好指定內容（模擬工作軌開工後的狀態）。"""
    def on_bg():
        fake.agents = [{"id": fake.short_id, "sessionId": fake.session_id, "kind": "background",
                        "name": "track-demo kickoff", "cwd": str(world.wt), "status": "busy"}]
        world.write_transcript(fake.session_id, blocks, model, extra)
    fake.on_bg = on_bg


# ─── 正例 ───────────────────────────────────────────────────────────────────────
def test_bg_command_shape_cwd_and_no_shell(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, [sendmessage_block(f"{TRACK} 收到開工")])
    code, out = run(world, fake, clock, capsys)
    assert code == 0 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK PASS")
    (bg,) = fake.bg_calls()
    assert bg["cmd"] == [str(world.claude_bin), "--bg", PROMPT, "--permission-mode", "bypassPermissions"]
    assert bg["cwd"] == str(world.wt)
    assert not bg.get("shell") and bg["stdin"] is subprocess.DEVNULL
    assert "abc12345" in out and "track-demo kickoff" in out and "收到開工（SendMessage）" in out


def test_slash_prompt_passes_verbatim(world, capsys):
    world.prompt_file.write_text(f"/continue {TRACK}", encoding="utf-8")
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, [sendmessage_block(f"{TRACK} 收到開工")])
    code, _ = run(world, fake, clock, capsys)
    assert code == 0
    assert fake.bg_calls()[0]["cmd"][2] == f"/continue {TRACK}"


def test_kickoff_in_assistant_text_counts(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, [{"type": "text", "text": f"{TRACK} 收到開工，開始核實路徑。"}])
    code, out = run(world, fake, clock, capsys)
    assert code == 0 and "收到開工（文字）" in out


def test_kickoff_of_other_track_does_not_count(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, [sendmessage_block("track-other 收到開工")])
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and "退回人貼" in out


def test_trust_added_with_forward_slash_key(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, [sendmessage_block(f"{TRACK} 收到開工")])
    code, out = run(world, fake, clock, capsys)
    assert code == 0
    projects = json.loads(world.config.read_text(encoding="utf-8"))["projects"]
    key = str(world.wt.resolve()).replace("\\", "/")
    assert projects[key]["hasTrustDialogAccepted"] is True
    assert "\\" not in key and "已替 worktree 補信任紀錄" in out


def test_help_has_how_to_run():
    r = subprocess.run([sys.executable, "-X", "utf8", str(TOOL), "--help"], capture_output=True, creationflags=NO_WINDOW)
    out = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0 and "怎麼跑" in out and "--permission-mode" in out and "--method" in out
    assert "--model" in out


# ─── 反例 ───────────────────────────────────────────────────────────────────────
def test_worktree_pointing_at_live_root_fails(world, capsys):
    fake, clock = FakeClaude(), Clock()
    (world.live / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    code, out = run(world, fake, clock, capsys, **{"--worktree": str(world.live)})
    assert code == 1 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK FAIL")
    assert "live 根" in out and fake.bg_calls() == []


def test_unregistered_worktree_fails(world, capsys):
    fake, clock = FakeClaude(), Clock()
    (world.live / ".git" / "worktrees" / "track-demo" / "gitdir").write_text("D:/elsewhere/.git\n", encoding="utf-8")
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and "未登記" in out and fake.bg_calls() == []


def test_missing_prompt_file_fails(world, capsys):
    fake, clock = FakeClaude(), Clock()
    code, out = run(world, fake, clock, capsys, **{"--prompt-file": str(world.prompt_file.with_name("nope.txt"))})
    assert code == 1 and "開工句檔不存在" in out and fake.calls == []


def test_kill_switch_refuses_and_names_file(world, capsys):
    fake, clock = FakeClaude(), Clock()
    kill = world.live / "workflow" / cs.KILL_SWITCH
    kill.write_text("", encoding="utf-8")
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and "kill switch" in out and str(kill) in out and fake.bg_calls() == []


def test_parallel_limit_lists_existing(world, capsys):
    fake, clock = FakeClaude(), Clock()
    rows = [{"id": f"id{i:06d}", "sessionId": f"id{i:06d}-sess", "track": f"track-{i}", "branch": f"b{i}",
             "worktree": f"C:/wt/{i}", "startedAt": "2026-10-20 10:00:00"} for i in range(5)]
    cs.save_state(world.live, rows)
    fake.agents = [{"id": r["id"], "sessionId": r["sessionId"], "kind": "background", "name": r["track"]} for r in rows]
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and "上限 5" in out and fake.bg_calls() == []
    assert all(r["track"] in out for r in rows)


def test_dead_sessions_do_not_count_toward_limit(world, capsys):
    fake, clock = FakeClaude(), Clock()
    rows = [{"id": f"id{i:06d}", "sessionId": f"id{i:06d}-sess", "track": f"track-{i}"} for i in range(5)]
    cs.save_state(world.live, rows)
    fake.agents = []          # 五個都不在 agents 清單＝都結束了
    arm_kickoff(world, fake, [sendmessage_block(f"{TRACK} 收到開工")])
    code, _ = run(world, fake, clock, capsys)
    assert code == 0 and len(fake.bg_calls()) == 1


def test_timeout_falls_back_to_human_paste(world, capsys):
    fake, clock = FakeClaude(), Clock()
    fake.on_bg = lambda: fake.agents.append({"id": fake.short_id, "sessionId": fake.session_id, "name": "quiet"})
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK FAIL")
    assert "退回人貼" in out and "90 秒內沒收到" in out
    assert f"```\n{PROMPT}\n```" in out
    assert f"claude stop {fake.short_id}" in out and clock.t >= 90


def test_live_root_untrusted_fails(world, capsys):
    fake, clock = FakeClaude(), Clock()
    world.config.write_text(json.dumps({"projects": {}}), encoding="utf-8")
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and "沒有信任紀錄" in out and fake.bg_calls() == []
    assert json.loads(world.config.read_text(encoding="utf-8")) == {"projects": {}}


def test_bg_refused_by_claude_fails(world, capsys):
    fake, clock = FakeClaude(), Clock()
    fake.bg_result = Result(1, "", "Workspace not trusted. Run `claude` in … once and accept the trust prompt, then retry.")
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and "claude --bg 起不來" in out and "Workspace not trusted" in out


def test_gui_method_only_prints_fallback(world, capsys):
    fake, clock = FakeClaude(), Clock()
    code, out = run(world, fake, clock, capsys, **{"--method": "gui"})
    assert code == 1 and "退回人貼" in out and PROMPT in out and fake.calls == []


# ─── 模型 ───────────────────────────────────────────────────────────────────────
OPUS, SONNET = "claude-opus-5-5", "claude-sonnet-5-5"
KICKOFF = [sendmessage_block(f"{TRACK} 收到開工")]
# Claude Code 自己補寫的訊息 model 欄是 "<synthetic>"；模型 id 不存在時第一回合只會有這一則（實測 2.1.304）
NO_RESPONSE = {"type": "assistant", "message": {"model": "<synthetic>",
                                                "content": [{"type": "text", "text": "No response requested."}]}}
BAD_MODEL_TEXT = ("There's an issue with the selected model (claude-nonexistent-9-9). It may not exist or you may "
                  "not have access to it. Run /model to pick a different model.")
BAD_MODEL_ERROR = {"type": "assistant", "isApiErrorMessage": True,
                   "message": {"model": "<synthetic>", "content": [{"type": "text", "text": BAD_MODEL_TEXT}]}}


def test_model_flag_goes_into_bg_cmd(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=OPUS)
    code, _ = run(world, fake, clock, capsys, **{"--model": OPUS})
    assert code == 0
    assert fake.bg_calls()[0]["cmd"] == [str(world.claude_bin), "--bg", PROMPT, "--permission-mode", "bypassPermissions",
                                         "--model", OPUS]


def test_no_model_flag_no_config_adds_nothing_and_reports_actual(world, capsys):
    assert not (world.live / "workflow" / "config.json").exists()      # 前置：config 沒有 default_model
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=OPUS)
    code, out = run(world, fake, clock, capsys)
    assert code == 0 and "--model" not in fake.bg_calls()[0]["cmd"]
    assert f"模型＝{OPUS}" in out                                       # 前置：真的讀到 transcript 的 model 欄


def test_config_default_model_used_without_flag(world, capsys):
    world.write_spawn_config(default_model=SONNET)
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=SONNET)
    code, out = run(world, fake, clock, capsys)
    assert code == 0 and fake.bg_calls()[0]["cmd"][-2:] == ["--model", SONNET] and f"模型＝{SONNET}" in out


def test_model_flag_beats_config_default_model(world, capsys):
    world.write_spawn_config(default_model=SONNET)
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=OPUS)
    code, _ = run(world, fake, clock, capsys, **{"--model": OPUS})
    cmd = fake.bg_calls()[0]["cmd"]
    assert code == 0 and cmd[-2:] == ["--model", OPUS] and SONNET not in cmd


def test_model_matches_transcript_passes(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=OPUS, extra=(NO_RESPONSE,))
    code, out = run(world, fake, clock, capsys, **{"--model": OPUS})
    assert code == 0 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK PASS")
    assert f"模型＝{OPUS}" in out and "<synthetic>" not in out          # 後面那則 <synthetic> 不算實際模型


def test_model_mismatch_fails_with_both_values_and_keeps_session(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=SONNET)
    code, out = run(world, fake, clock, capsys, **{"--model": OPUS})
    assert code == 1 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK FAIL")
    assert f"指定＝{OPUS}／實際＝{SONNET}" in out and f"claude stop {fake.short_id}" in out
    assert not any(c["cmd"][1:2] == ["stop"] for c in fake.calls)       # 不殺 session，交總控台決定
    assert "退回人貼" not in out                                        # 已開工，不叫人重貼


def test_model_specified_but_transcript_has_no_model_fails(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, KICKOFF, model=None)
    code, out = run(world, fake, clock, capsys, **{"--model": OPUS})
    assert code == 1 and f"指定＝{OPUS}／實際＝讀不到" in out


def test_api_error_fails_at_once_with_claude_message(world, capsys):
    fake, clock = FakeClaude(), Clock()
    arm_kickoff(world, fake, None, extra=(BAD_MODEL_ERROR,))
    code, out = run(world, fake, clock, capsys, **{"--model": "claude-nonexistent-9-9"})
    assert code == 1 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK FAIL")
    assert BAD_MODEL_TEXT in out and f"claude stop {fake.short_id}" in out
    assert "退回人貼" not in out                                        # 人貼救不了 API 錯誤，不叫人貼
    assert clock.t < 90                                                 # 不白等到逾時


def test_print_method_also_passes_model(world, capsys):
    fake, clock = FakeClaude(), Clock()
    code, out = run(world, fake, clock, capsys, **{"--method": "print", "--model": OPUS})
    (p,) = [c for c in fake.calls if "-p" in c["cmd"]]
    assert code == 0 and p["cmd"][-2:] == ["--model", OPUS] and "不核對實際模型" in out


# ─── 信任紀錄寫回（~/.claude.json 其他 session 隨時在寫）──────────────────────────────
def trust(world: World):
    logs = []
    ok = cs.ensure_trust(world.config, world.wt, world.live, logs.append)
    return ok, "\n".join(logs)


def config_lock(world: World) -> Path:
    return world.config.with_name(world.config.name + ".lock")


def leftovers(world: World):
    """設定檔旁邊的暫存檔與鎖（claude.json.*）。"""
    return sorted(p.name for p in world.config.parent.iterdir() if p.name.startswith(world.config.name + "."))


def test_key_written_by_other_session_between_read_and_write_survives(world, monkeypatch):
    real_loads, fired = json.loads, []

    def loads_then_other_session_writes(s, *a, **kw):
        data = real_loads(s, *a, **kw)
        if not fired:                     # 我們第一次讀完、還沒寫：另一個 session 寫進一個鍵
            fired.append(1)
            other = real_loads(world.config.read_bytes())
            other["numStartups"] = 42
            world.config.write_bytes(json.dumps(other, indent=2).encode("utf-8"))
        return data

    monkeypatch.setattr(cs.json, "loads", loads_then_other_session_writes)
    ok, _ = trust(world)
    monkeypatch.undo()
    assert fired                                                        # 前置：讀寫之間真的有人寫過
    data = json.loads(world.config.read_bytes())
    assert ok is True and data["numStartups"] == 42
    assert data["projects"][cs.trust_key(world.wt)]["hasTrustDialogAccepted"] is True
    assert data["projects"][cs.trust_key(world.live)]["hasTrustDialogAccepted"] is True


def test_write_failure_leaves_original_intact(world, monkeypatch):
    before, failed = world.config.read_bytes(), []

    def write_half_then_fail(self, data, *a, **kw):
        failed.append(self.name)
        blob = data.encode("utf-8") if isinstance(data, str) else data
        with open(self, "wb") as fh:
            fh.write(blob[: len(blob) // 2])
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(cs.Path, "write_text", write_half_then_fail)
    monkeypatch.setattr(cs.Path, "write_bytes", write_half_then_fail)
    try:
        ok, out = trust(world)
    except OSError:                       # 舊碼不攔：例外直接拋出，下面照樣檢查原檔
        ok, out = None, ""
    monkeypatch.undo()
    assert failed                                                       # 前置：真的寫到一半失敗過
    assert world.config.read_bytes() == before                          # 原檔一個位元組都沒動
    json.loads(before)
    assert ok is False and "原檔沒動" in out
    assert leftovers(world) == []                                       # 半截暫存檔與鎖都收掉


@pytest.mark.parametrize("nl,tail", [("\n", ""), ("\n", "\n"), ("\r\n", "\r\n")])
def test_newline_style_and_tail_kept(world, nl, tail):
    body = json.dumps(json.loads(world.config.read_bytes()), indent=2).replace("\n", nl)
    world.config.write_bytes((body + tail).encode("utf-8"))
    ok, _ = trust(world)
    raw = world.config.read_bytes().decode("utf-8")
    assert ok is True and cs.trust_key(world.wt) in raw and raw.count("\n") > 3     # 前置：真的寫回、是多行
    assert raw.count("\r\n") == (raw.count("\n") if nl == "\r\n" else 0)
    assert raw.endswith("}" + tail)


def test_write_happens_under_claude_lock_and_releases_it(world, monkeypatch):
    real_replace, lock_held = cs.os.replace, []

    def replace_and_look(src, dst):
        lock_held.append(config_lock(world).is_dir())
        return real_replace(src, dst)

    monkeypatch.setattr(cs.os, "replace", replace_and_look)
    ok, _ = trust(world)
    assert ok is True and lock_held == [True] and leftovers(world) == []


def test_lock_held_by_other_waits_then_fails_without_writing(world, monkeypatch):
    monkeypatch.setattr(cs, "CONFIG_LOCK_WAIT_SEC", 0.3)
    lock, before = config_lock(world), world.config.read_bytes()
    lock.mkdir()
    t0 = time.monotonic()
    ok, out = trust(world)
    assert time.monotonic() - t0 >= 0.3                                 # 真的等到時限，不是一看到鎖就放棄
    assert ok is False and str(lock) in out and world.config.read_bytes() == before
    assert lock.is_dir()                                                # 別人的鎖不動


def test_lock_held_too_long_does_not_replace_or_delete_lock(world, monkeypatch):
    monkeypatch.setattr(cs, "CONFIG_LOCK_HOLD_SEC", -1.0)               # 模擬拿鎖後卡住、已超過持鎖時限
    before = world.config.read_bytes()
    ok, out = trust(world)
    assert ok is False and "不換上" in out and world.config.read_bytes() == before
    assert leftovers(world) == [world.config.name + ".lock"]            # 暫存檔收掉；鎖可能已換人拿著，不刪


def test_already_trusted_takes_no_lock_and_writes_nothing(world, monkeypatch):
    data = json.loads(world.config.read_bytes())
    data["projects"][cs.trust_key(world.wt)] = {"hasTrustDialogAccepted": True}
    world.config.write_bytes(json.dumps(data).encode("utf-8"))
    before, replaced = world.config.read_bytes(), []
    monkeypatch.setattr(cs, "lock_config", lambda *a: pytest.fail("已信任不該拿鎖"))
    monkeypatch.setattr(cs.os, "replace", lambda *a: replaced.append(a))
    ok, _ = trust(world)
    assert ok is True and replaced == [] and world.config.read_bytes() == before and leftovers(world) == []


@pytest.mark.parametrize("content,reason", [
    ("{broken", "不是合法 JSON"), ("[]", "格式不對"), ('{"projects": []}', "格式不對"),
    ('{"projects": {"C:/x": "yes"}}', "格式不對"), (None, "不存在")])
def test_bad_or_missing_config_not_written_and_fails(world, capsys, content, reason):
    if content is None:
        world.config.unlink()
    else:
        world.config.write_text(content, encoding="utf-8")
    fake, clock = FakeClaude(), Clock()
    code, out = run(world, fake, clock, capsys)
    assert code == 1 and out.rstrip().endswith("CONSOLE_SPAWN_CHECK FAIL") and "退回人貼" in out
    assert reason in out and fake.bg_calls() == []
    assert (world.config.read_text(encoding="utf-8") if world.config.exists() else None) == content
