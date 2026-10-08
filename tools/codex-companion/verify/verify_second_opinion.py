"""verify_second_opinion.py：第二意見工具（tools/second-opinion）單元測試；subprocess 全 monkeypatch，不打 codex。

正例：同材料兩次 pack 雜湊相同（含 CRLF 與亂序輸入）；manifest 無沙箱外路徑；prepare 印三行；全流程 done 三段齊；
      兩 job 目錄互不含對方 reply。
反例：independent 帶 draft 被拒；review 缺 draft 被拒；pre FAIL → blocked 且沒有 codex 子程序被啟動；
      探針失敗（餵 1385 stderr）status 必 failed 不得 done；post FAIL 不 done；逾時後 failed 且 kill 被呼叫；
      缺反例段 → failed；材料含封存關鍵字 → blocked；config 開 allow_claude_fallback 也不生效。
怎麼跑：python -X utf8 -m pytest -q tools/codex-companion/verify/verify_second_opinion.py
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]  # tools/codex-companion/verify/ → repo 根（worktree 或 live）
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
FIX = ROOT / "hooks" / "verify" / "fixtures" / "v6" / "second-opinion"
RUN_PY = ROOT / "tools" / "second-opinion" / "run.py"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


os.environ.pop("WG_CLAUDE_DIR", None)  # run.py 以檔案相對位置定 CLAUDE_DIR（＝本 repo 根），不吃 live 覆蓋
run = _load("so_run", RUN_PY)
pack = run.pack
so_prompts = run.so_prompts

THREE = "## 結論\n改動正確。\n\n## 證據\nmaterials/diff.patch:3；等號補上；所以邊界對了。\n\n## 反例或未解\n無，材料裡沒有 cap=0 的案例。\n"
TWO = "## 結論\n改動正確。\n\n## 證據\nmaterials/diff.patch:3；等號補上。\n"


# ─── fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def env(tmp_path, monkeypatch):
    """config／job_root 導到 tmp；models_cache 給假檔；guard 與 codex 都由 fake subprocess 代替。"""
    cache = tmp_path / "models_cache.json"
    cache.write_text(json.dumps({"models": [{"slug": "gpt-6-astra"}, {"slug": "gpt-5.6-sol"}]}),
                     encoding="utf-8", newline="\n")
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({
        "second_opinion": {"model": "gpt-6-astra", "models_cache": str(cache), "timeout_s": 300, "probe_timeout_s": 20,
                           "allow_claude_fallback": True},
        "codex_companion": {"codex_binary": "codex", "codex_extra_args": ["-c", "x=1"]},
    }), encoding="utf-8", newline="\n")
    monkeypatch.setattr(run, "CONFIG_PATH", cfg)
    monkeypatch.setattr(run, "JOB_ROOT", tmp_path / "jobs")
    monkeypatch.setattr(run.judge_backend, "resolve_codex_bin", lambda _cfg: "C:/fake/codex.cmd")

    plan = {"pre": "PASS", "post": "PASS", "probe": {"stdout": "CODEX_OK\n", "stderr": "", "rc": 0},
            "exec": {"reply": THREE, "stderr": "", "rc": 0, "timeout": False}, "popen": [], "kills": 0,
            "post_reasons": []}

    class CP:
        def __init__(self, stdout="", stderr="", rc=0):
            self.stdout, self.stderr, self.returncode = stdout, stderr, rc

    def fake_run(cmd, **kw):
        plan.setdefault("runs", []).append(list(cmd))
        joined = " ".join(str(c) for c in cmd)
        if "replay-guard.py" in joined:
            which = "pre" if " pre " in f" {joined} " else "post"
            verdict = plan[which]
            reasons = plan["post_reasons"] if which == "post" else ["提示詞含封存答案關鍵字（出題者洩題）：x"]
            body = "".join(f"  - {r}\n" for r in (reasons if verdict == "FAIL" else []))
            return CP(stdout=body + f"REPLAY_GUARD_CHECK {verdict}\n", rc=0 if verdict == "PASS" else 1)
        if cmd[:2] == ["git", "diff"] or (cmd[0] == "git" and "diff" in cmd):
            return CP(stdout=(FIX / "diff.patch").read_text(encoding="utf-8"))
        if cmd[0] == "git":
            return CP(stdout=".git\n")
        return CP(stdout="", rc=1)

    class FakePopen:
        def __init__(self, cmd, stdin=None, stdout=None, stderr=None, cwd=None, env=None, creationflags=0):
            self.cmd = list(cmd)
            plan["popen"].append(self.cmd)
            joined = " ".join(self.cmd)
            assert "claude" not in Path(self.cmd[0]).name.lower(), "第二意見不得退 claude"
            self._timeout = False
            if "Reply CODEX_OK" in self.cmd:
                p = plan["probe"]
                stdout.write(p["stdout"].encode("utf-8"))
                stderr.write(p["stderr"].encode("utf-8"))
                self._rc = p["rc"]
            else:
                e = plan["exec"]
                self._timeout = e["timeout"]
                stderr.write(e["stderr"].encode("utf-8"))
                stdout.write(e.get("stdout", "").encode("utf-8"))
                if not self._timeout and "-o" in self.cmd:
                    out = Path(self.cmd[self.cmd.index("-o") + 1])
                    out.write_text(e["reply"], encoding="utf-8", newline="\n")
                self._rc = e["rc"]
                assert "-s" in self.cmd and self.cmd[self.cmd.index("-s") + 1] == "read-only"
                assert "--ephemeral" in self.cmd and "--skip-git-repo-check" in self.cmd and joined.endswith(" -")

        def wait(self, timeout=None):
            if self._timeout and timeout and timeout > 15:
                raise subprocess.TimeoutExpired(self.cmd, timeout)
            return self._rc

        def kill(self):
            plan["kills"] += 1
            self._timeout = False

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", FakePopen)
    return {"tmp": tmp_path, "plan": plan, "cache": cache}


def _req(**over):
    base = {"kind": "diagnose", "part": "排程器", "cwd": str(FIX), "mode": "independent",
            "question": "這段 diff 修對了嗎？", "session_id": "abcdef1234",
            "materials": {"card": str(FIX / "card.md"), "defects": str(FIX / "defects.md"),
                          "diff": str(FIX / "diff.patch"), "ledger": str(FIX / "ledger.jsonl")}}
    base.update(over)
    return base


def _prepare(env, **over):
    so_cfg, _ = run.load_config()
    return run.prepare(_req(**over), so_cfg, run.JOB_ROOT)


def _execute(env, job_dir):
    so_cfg, cc_cfg = run.load_config()
    return run.execute(Path(job_dir), so_cfg, cc_cfg)


# ─── 雜湊與 manifest ──────────────────────────────────────────────────────────


def test_same_materials_same_hash_crlf_and_order(tmp_path):
    items = [("card.md", (FIX / "card.md").read_text(encoding="utf-8")),
             ("diff.patch", (FIX / "diff.patch").read_text(encoding="utf-8")),
             ("ledger.jsonl", (FIX / "ledger.jsonl").read_text(encoding="utf-8"))]
    m1 = pack.pack_materials(tmp_path / "a", items, "independent", "gpt-6-astra")
    crlf = [(rel, text.replace("\n", "\r\n")) for rel, text in reversed(items)]  # 亂序＋CRLF
    m2 = pack.pack_materials(tmp_path / "b", crlf, "review", "gpt-5.6-sol")
    assert m1["hash"] == m2["hash"], "同材料不同行尾／順序／模式／模型，hash 必同"
    assert [f["rel"] for f in m2["files"]] == sorted(f["rel"] for f in m2["files"])
    assert "\r" not in (tmp_path / "b" / "materials" / "card.md").read_bytes().decode("utf-8")
    assert pack.manifest_outside_paths(m1) == [] and pack.manifest_outside_paths(m2) == []
    # 反例：改一個字元 hash 就變
    m3 = pack.pack_materials(tmp_path / "c", items[:-1] + [("ledger.jsonl", items[-1][1] + "x")], "independent", "m")
    assert m3["hash"] != m1["hash"]


def test_pack_rejects_absolute_and_parent_paths(tmp_path):
    with pytest.raises(pack.PackError):
        pack.pack_materials(tmp_path / "x", [("C:/abs/x.md", "x")], "independent", "m")
    with pytest.raises(pack.PackError):
        pack.pack_materials(tmp_path / "y", [("../escape.md", "x")], "independent", "m")
    assert pack.manifest_outside_paths({"files": [{"rel": "C:\\Users\\x\\a.md"}]}) == ["C:\\Users\\x\\a.md"]


def test_top_n_sections_and_tail():
    text = (FIX / "defects.md").read_text(encoding="utf-8")
    top = pack.top_n_sections(text, 5)
    assert "病灶五" in top and "病灶六" not in top and "只取前 5 節" in top
    tail = pack.tail_lines((FIX / "ledger.jsonl").read_text(encoding="utf-8"), 20)
    assert tail.count("\n") == 20 and '"seq": 6' in tail and '"seq": 5' not in tail


# ─── 模式守門 ─────────────────────────────────────────────────────────────────


def test_independent_with_draft_rejected(env):
    with pytest.raises(ValueError):
        so_prompts.build_prompt("independent", {"files": []}, "q", draft="我方結論")
    res = _prepare(env, draft="我方結論")
    assert res["status"] == "failed" and "independent" in res["reason"] and "draft" in res["reason"]
    assert not run.JOB_ROOT.exists(), "拒收發生在建 job 目錄之前"
    assert env["plan"]["popen"] == []


def test_review_without_draft_rejected(env):
    with pytest.raises(ValueError):
        so_prompts.build_prompt("review", {"files": []}, "q")
    res = _prepare(env, mode="review")
    assert res["status"] == "failed" and "review" in res["reason"]
    res2 = _prepare(env, mode="review", draft="第一段：…\n第二段：…")
    assert res2["status"] == "started"
    prompt = (Path(res2["job_dir"]) / "prompt.md").read_text(encoding="utf-8")
    assert "materials/draft.md" in prompt and "是這裡" in prompt
    assert (Path(res2["job_dir"]) / "materials" / "draft.md").is_file()


def test_independent_prompt_has_no_draft_and_only_relative_paths(env):
    res = _prepare(env)
    assert res["status"] == "started"
    prompt = (Path(res["job_dir"]) / "prompt.md").read_text(encoding="utf-8")
    assert "draft" not in prompt.lower()
    assert "materials/card.md" in prompt and "materials/diff.patch" in prompt
    assert "C:\\" not in prompt.split("【材料全文】")[0] and "C:/" not in prompt.split("【材料全文】")[0]


# ─── 閘：pre / sealed ─────────────────────────────────────────────────────────


def test_pre_fail_blocks_and_never_spawns_codex(env):
    env["plan"]["pre"] = "FAIL"
    res = _prepare(env)
    assert res["status"] == "blocked" and "replay-guard pre FAIL" in res["reason"]
    st = json.loads((Path(res["job_dir"]) / "status.json").read_text(encoding="utf-8"))
    assert st["status"] == "blocked"
    assert env["plan"]["popen"] == [], "pre FAIL 不得啟動任何 codex 子程序"
    # 就算有人硬叫 execute，blocked 的 job 也不跑
    st2 = _execute(env, res["job_dir"])
    assert st2["status"] == "blocked" and env["plan"]["popen"] == []


def test_sealed_keyword_in_materials_blocked(env):
    sealed = [w for w in (FIX / "sealed.txt").read_text(encoding="utf-8").splitlines() if w and not w.startswith("#")]
    ok = _prepare(env, sealed=sealed)
    assert ok["status"] == "started", "fixture 材料本身不含封存關鍵字"
    assert (run.JOB_ROOT / "_sealed" / f"{ok['job_id']}.txt").is_file()
    assert not (Path(ok["job_dir"]) / "sealed.txt").exists(), "封存檔不放 job 目錄（codex 工作目錄）"
    leaked = _prepare(env, sealed=sealed, materials={**_req()["materials"], "diff": {"text": "修法：歸還早標完成要改順序"}})
    assert leaked["status"] == "blocked" and "封存答案關鍵字" in leaked["reason"]
    assert env["plan"]["popen"] == []


# ─── execute：探針 / codex / post / 解析 ─────────────────────────────────────


def test_probe_failure_1385_is_failed_not_done(env):
    env["plan"]["probe"] = {"stdout": "", "stderr": (FIX / "stderr_fail.log").read_text(encoding="utf-8"), "rc": 1}
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and st["stage"] == "probe" and "沙箱" in st["reason"]
    assert len(env["plan"]["popen"]) == 1 and "Reply CODEX_OK" in env["plan"]["popen"][0]
    assert not (Path(res["job_dir"]) / "reply.md").exists()


def test_probe_timeout_is_failed_and_killed(env):
    class Hang(subprocess.Popen):  # type: ignore[misc]
        pass
    plan = env["plan"]
    orig = subprocess.Popen

    class Probe(orig):  # type: ignore[misc]
        def wait(self, timeout=None):
            if "Reply CODEX_OK" in self.cmd:
                raise subprocess.TimeoutExpired(self.cmd, timeout)
            return super().wait(timeout)
    subprocess.Popen = Probe
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and "探針逾時" in st["reason"] and plan["kills"] == 1
    assert len(plan["popen"]) == 1, "探針失敗後不得再跑 codex exec，也不得退 claude"


def test_post_fail_not_done(env):
    env["plan"]["post"] = "FAIL"
    env["plan"]["post_reasons"] = ["指令命中禁區樣式：\\.claude[/\\\\]memory"]
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and st["stage"] == "post-guard" and "replay-guard post FAIL" in st["reason"]
    assert (Path(res["job_dir"]) / "reply.raw.md").is_file() and not (Path(res["job_dir"]) / "reply.md").exists()


def test_exec_timeout_is_failed_and_killed(env):
    env["plan"]["exec"]["timeout"] = True
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and "逾時" in st["reason"] and "kill" in st["reason"]
    assert env["plan"]["kills"] == 1
    assert not (Path(res["job_dir"]) / "reply.md").exists()


def test_missing_section_is_failed(env):
    env["plan"]["exec"]["reply"] = TWO
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and st["stage"] == "parse" and "缺段" in st["reason"]
    assert so_prompts.parse_three_sections(TWO) is None
    assert so_prompts.parse_three_sections(THREE + "\n## 結論\n又一次\n") is None, "同名段兩次＝格式不合"
    assert so_prompts.parse_three_sections("## 結論\n\n## 證據\nx\n## 反例或未解\ny\n") is None, "空段算缺"


def test_full_run_done_three_sections_and_jobs_isolated(env):
    a = _prepare(env)
    sa = _execute(env, a["job_dir"])
    assert sa["status"] == "done"
    reply_a = (Path(a["job_dir"]) / "reply.md").read_text(encoding="utf-8")
    assert reply_a.startswith("## 結論") and "## 證據" in reply_a and "## 反例或未解" in reply_a
    env["plan"]["exec"]["reply"] = THREE.replace("改動正確。", "第二個 job 的結論。")
    b = _prepare(env, session_id="zzzz9999", question="另一題")
    sb = _execute(env, b["job_dir"])
    assert sb["status"] == "done" and a["job_id"] != b["job_id"]
    assert a["hash"] == b["hash"], "同材料兩個 job hash 相同（Q9 正例）"
    reply_b = (Path(b["job_dir"]) / "reply.md").read_text(encoding="utf-8")
    assert "第二個 job" in reply_b and "第二個 job" not in reply_a
    for root, other in ((Path(a["job_dir"]), "第二個 job"), (Path(b["job_dir"]), "改動正確。")):
        for p in root.rglob("*"):
            if p.is_file():
                assert other not in p.read_text(encoding="utf-8", errors="replace"), f"{p} 含對方回覆"
    # job 目錄八檔齊
    for name in ("request.json", "manifest.json", "prompt.md", "codex.stderr.log", "reply.raw.md", "reply.md", "status.json"):
        assert (Path(a["job_dir"]) / name).is_file(), name
    assert (Path(a["job_dir"]) / "materials").is_dir()
    # codex exec 指令形狀
    ex = [c for c in env["plan"]["popen"] if "Reply CODEX_OK" not in c][0]
    assert ex[ex.index("-m") + 1] == "gpt-6-astra" and ex[ex.index("-C") + 1] == a["job_dir"]
    assert "-c" in ex and "x=1" in ex, "codex_extra_args 要帶上"


def test_post_no_command_lines_pass_only_when_log_clean(env):
    """保留裁決：post FAIL 只因「找不到指令行」（codex 純推理）→ 整份紀錄掃乾淨才算過；有命中仍 failed。"""
    env["plan"]["post"] = "FAIL"
    env["plan"]["post_reasons"] = ["紀錄裡找不到任何指令行（格式變了？），無法判定"]
    env["plan"]["exec"]["stderr"] = "model: gpt-6-astra\ncodex\n## 結論\n"
    a = _prepare(env)
    sa = _execute(env, a["job_dir"])
    assert sa["status"] == "done" and "純推理" in sa["guard_note"]
    env["plan"]["exec"]["stderr"] = "model: gpt-6-astra\nread C:\\Users\\x\\.claude\\memory\\a.md\n"
    b = _prepare(env, session_id="bbbbbbbb")
    sb = _execute(env, b["job_dir"])
    assert sb["status"] == "failed" and "post FAIL" in sb["reason"]


# ─── 設定與 CLI 形狀 ──────────────────────────────────────────────────────────


def test_claude_fallback_is_always_off(env):
    so_cfg, _ = run.load_config()
    assert so_cfg["allow_claude_fallback"] is False, "config 寫 true 也不理"
    assert run.DEFAULTS["allow_claude_fallback"] is False


def test_model_not_in_cache_is_failed(env):
    cfg = json.loads(run.CONFIG_PATH.read_text(encoding="utf-8"))
    cfg["second_opinion"]["model"] = "gpt-6-astra-900K"
    run.CONFIG_PATH.write_text(json.dumps(cfg), encoding="utf-8", newline="\n")
    res = _prepare(env)
    assert res["status"] == "failed" and "不在 models_cache" in res["reason"] and env["plan"]["popen"] == []


def test_prepare_cli_prints_three_lines(env, capsys, tmp_path):
    req = tmp_path / "req.json"
    req.write_text(json.dumps(_req()), encoding="utf-8", newline="\n")
    rc = run.main(["prepare", "--request", str(req)])
    out = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert out[0].startswith("job_id: ") and out[1].startswith("hash: ") and out[2] == "status: started"
    assert any(l.startswith("job_dir: ") for l in out)


# ─── 退回修正（總控台 BLOCK 2／3）：狀態機與整份掃描 ─────────────────────────


def test_probe_spawn_oserror_writes_failed(env):
    """探針的 Popen 直接拋 OSError（codex 路徑錯／權限）→ status 必 failed、stage=probe，不得留 running。"""
    def boom(*a, **k):
        raise OSError(5, "codex.cmd: access denied")
    import subprocess as sp
    sp.Popen = boom
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and st["stage"] == "probe" and "OSError" in st["reason"]
    on_disk = json.loads((Path(res["job_dir"]) / "status.json").read_text(encoding="utf-8"))
    assert on_disk["status"] == "failed", "status.json 不可卡在 running"


def test_terminal_status_not_overwritten(env):
    """failed／blocked／done 之後任何 write_status 都不寫：並行 execute 的 A 寫 failed、B 不能蓋成 done。"""
    res = _prepare(env)
    job = Path(res["job_dir"])
    run.write_status(job, "failed", stage="probe", reason="A 探針失敗")
    after = run.write_status(job, "done", stage="done", reason="")
    assert after["status"] == "failed" and "不可覆寫" in after["rejected_write"]
    on_disk = json.loads((job / "status.json").read_text(encoding="utf-8"))
    assert on_disk["status"] == "failed" and on_disk["reason"] == "A 探針失敗" and "rejected_write" not in on_disk
    # 同終態重寫允許（補 reason 之類），不同終態互蓋不允許
    same = run.write_status(job, "failed", reason="A 探針失敗（補充）")
    assert same["status"] == "failed" and same["reason"].endswith("（補充）")
    env["plan"]["pre"] = "FAIL"
    blocked = _prepare(env, session_id="bbbbbbbb")
    assert run.write_status(Path(blocked["job_dir"]), "done")["status"] == "blocked"


def test_execute_on_terminal_job_keeps_original_reason(env):
    """退回修正第二輪（BLOCK 2）：failed／blocked／done／running 的 job 再 execute → 只回傳不寫檔，原始 reason 與 updated_at 原樣。"""
    env["plan"]["probe"] = {"stdout": "", "stderr": "CreateProcessWithLogonW failed: 1385\n", "rc": 1}
    res = _prepare(env)
    job = Path(res["job_dir"])
    first = _execute(env, str(job))
    assert first["status"] == "failed" and "沙箱" in first["reason"]
    before = (job / "status.json").read_bytes()
    import time as _t
    _t.sleep(1.1)  # 讓 updated_at 若被重寫一定會變
    again = _execute(env, str(job))
    assert again["status"] == "failed" and again["reason"] == first["reason"]
    assert "只接 started" in again["rejected_execute"] and "重新 prepare" in again["rejected_execute"]
    assert (job / "status.json").read_bytes() == before, "拒絕路徑不得動 status.json（reason／updated_at 都要原樣）"
    assert len([c for c in env["plan"]["popen"]]) == 1, "拒絕路徑不 spawn"
    # blocked 的 job 同樣只回傳不寫
    env["plan"]["pre"] = "FAIL"
    b = _prepare(env, session_id="bbbbbbbb")
    bb = Path(b["job_dir"]) / "status.json"
    raw_b = bb.read_bytes()
    rb = _execute(env, b["job_dir"])
    assert rb["status"] == "blocked" and bb.read_bytes() == raw_b


def test_second_execute_on_same_job_rejected(env):
    """同一 job 已有 executor（execute.lock 存在）→ 第二個 execute 直接拒、不 spawn、不改 status。"""
    res = _prepare(env)
    job = Path(res["job_dir"])
    assert run._acquire_executor_lock(job) is True, "第一個 executor 拿鎖"
    st = _execute(env, str(job))
    assert "已有 executor" in st.get("rejected_execute", "") and st["status"] == "started"
    assert env["plan"]["popen"] == [], "被拒的 execute 不得啟動任何子程序"
    on_disk = json.loads((job / "status.json").read_text(encoding="utf-8"))
    assert on_disk["status"] == "started" and "rejected_execute" not in on_disk
    # 正常單一 executor 拿鎖後整段跑完 → done，且 lock 檔留著（一次性 job）
    res2 = _prepare(env, session_id="cccccccc")
    st2 = _execute(env, res2["job_dir"])
    assert st2["status"] == "done" and (Path(res2["job_dir"]) / "execute.lock").is_file()


def test_post_no_cmd_scan_sees_early_outside_read(env):
    """反例（codex 構造）：stderr 無指令行；stdout 前段有一次成功的出界讀取，後接一千萬個換行。整檔掃描要抓到 → failed。"""
    env["plan"]["post"] = "FAIL"
    env["plan"]["post_reasons"] = ["紀錄裡找不到任何指令行（格式變了？），無法判定"]
    env["plan"]["exec"]["stderr"] = "model: gpt-6-astra\n"
    env["plan"]["exec"]["stdout"] = (
        'exec\n"C:\\Program Files\\PowerShell\\7\\pwsh.exe" -Command "Get-Content C:\\outside\\secret.txt" in C:\\jobs\\job1\n'
        " succeeded in 12ms:\n外部檔案的實際內容\n" + "\n" * 10_000_001)
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and st["stage"] == "post-guard" and "outside" in st["reason"].lower()
    assert not (Path(res["job_dir"]) / "reply.md").exists()


def test_post_oversize_log_is_failed(env, monkeypatch):
    """紀錄合計超過上限 → 直接 failed「過大無法判定」，不掃尾段、不放行。"""
    monkeypatch.setattr(run, "MAX_LOG_BYTES", 1000)
    env["plan"]["post"] = "FAIL"
    env["plan"]["post_reasons"] = ["紀錄裡找不到任何指令行（格式變了？），無法判定"]
    env["plan"]["exec"]["stderr"] = "model: gpt-6-astra\n"
    env["plan"]["exec"]["stdout"] = "clean\n" * 400  # 2400 bytes，內容乾淨但超過上限
    res = _prepare(env)
    st = _execute(env, res["job_dir"])
    assert st["status"] == "failed" and "過大" in st["reason"]
    assert not (Path(res["job_dir"]) / "reply.md").exists()
