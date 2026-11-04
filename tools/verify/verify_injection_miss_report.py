"""verify_injection_miss_report.py — tools/injection-miss-report.py 的回合切法與計數。

做什麼：用小型假 transcript 斷言：注入卡數只算行首 `[Atom:`、同回合 memory_search 有算到、
isMeta 不切回合、queued_command 算使用者回合、背景通知／peer 另計、Claude 沒回覆的回合不進比例、
isSidechain 與 subagents 子目錄略過、壞行計數、--sessions 取最近的檔、搜尋詞切法、尾行 DONE 格式。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_injection_miss_report.py
       或 python -X utf8 tools/verify/verify_injection_miss_report.py（印 INJECTION_MISS_REPORT_CHECK PASS/FAIL）
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "injection_miss_report", Path(__file__).resolve().parents[1] / "injection-miss-report.py")
imr = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(imr)


def _user(text, entry="claude-vscode", **extra):
    return {"type": "user", "entrypoint": entry, "message": {"role": "user", "content": text}, **extra}


def _ups(*lines):
    return {"type": "attachment", "attachment": {"type": "hook_additional_context", "hookEvent": "UserPromptSubmit",
                                                 "content": ["\n".join(lines)]}}


def _say(text="ok", **extra):
    return {"type": "assistant", "message": {"content": [{"type": "text", "text": text}]}, **extra}


def _search(query, **extra):
    return {"type": "assistant", "message": {"content": [
        {"type": "tool_use", "name": imr.SEARCH_TOOL, "input": {"query": query, "top_k": 5}}]}, **extra}


def _tool_result():
    return {"type": "user", "message": {"content": [{"type": "tool_result", "content": "hits=0"}]}}


def _write(path: Path, records, mtime: float):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in records:
            fh.write((r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)) + "\n")
    os.utime(path, (mtime, mtime))


SESSION_A = [
    # 回合 1：注入 2 張（行中的 [Atom: 不算），沒搜
    _user("第一題", origin={"kind": "human"}),
    _ups("[Atom:a] 內容", "[Atom:b] 內容", "參見 [Atom:c] 行中引用不算"),
    _say(),
    # 回合 2：注入 0 張；isMeta 技能內文不切回合；之後補搜
    _user("第二題"),
    _ups("[Context budget: 10/1000 tokens]"),
    _user("Base directory for this skill", isMeta=True),
    _search("gitlab ssh 金鑰 金鑰 a"),
    _tool_result(),
    _say(),
    # 回合 3：hook 沒輸出，沒搜
    _user("好"),
    _say(),
    # 回合 4：Claude 忙時排隊送進來的提示（queued_command）；注入 1 張仍搜
    {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "第四題", "commandMode": "prompt",
                                          "origin": {"kind": "human"}}},
    _ups("[Atom:d] 內容"),
    _search("windows heredoc"),
    # 回合 5：背景任務通知（另計）裡的搜尋
    _user("<task-notification>done</task-notification>", origin={"kind": "task-notification"}),
    _search("foo bar"),
    # 回合 6：其他 session 傳來的訊息（isMeta 但 origin=peer 仍切回合，另計）
    _user("Another Claude session sent a message", isMeta=True, origin={"kind": "peer"}),
    _say(),
    # 回合 7：本地指令，Claude 沒回覆 → 不進比例
    _user("<command-name>/model</command-name>"),
    # 子代理混在主檔的 sidechain 紀錄略過
    _search("sidechain 不算", isSidechain=True),
    "{壞掉的一行",
]
SESSION_B_HEADLESS = [_user("reply OK", entry="sdk-cli"), _say("OK", entrypoint="sdk-cli")]


def _projects(tmp_path: Path) -> Path:
    root = tmp_path / "projects"
    _write(root / "proj" / "sess-b.jsonl", SESSION_B_HEADLESS, 1_000_000)
    _write(root / "proj" / "sess-a.jsonl", SESSION_A, 2_000_000)
    _write(root / "proj" / "sess-a" / "subagents" / "agent-x.jsonl", [_user("子代理"), _search("子代理的搜尋")], 3_000_000)
    return root


def test_counts(tmp_path):
    files, turns, bad = imr.scan(_projects(tmp_path), 150)
    assert [p.name for p in files] == ["sess-a.jsonl", "sess-b.jsonl"]  # subagents 略過、新的在前
    assert bad == 1
    s = imr.summarize(turns)
    assert (s["turns"], s["unanswered"]) == (5, 1)
    assert (s["zero_inject"], s["zero_then_search"]) == (3, 1)
    assert (s["injected"], s["inject_then_search"], s["cards_total"]) == (2, 1, 3)
    assert (s["other_turns"], s["search_calls_user"], s["search_calls_other"]) == (2, 2, 1)
    assert s["by_entry"]["headless"] == {"turns": 1, "zero": 1, "zero_search": 0, "inj": 0, "inj_search": 0}
    assert s["by_entry"]["interactive"]["turns"] == 4


def test_sessions_limit_takes_newest(tmp_path):
    files, turns, _bad = imr.scan(_projects(tmp_path), 1)
    assert [p.name for p in files] == ["sess-a.jsonl"]
    assert imr.summarize(turns)["by_entry"]["headless"]["turns"] == 0


def test_search_terms(tmp_path):
    assert imr.split_terms("GitLab ssh 金鑰 金鑰 a，/memory") == ["gitlab", "ssh", "金鑰", "memory"]
    _files, turns, _bad = imr.scan(_projects(tmp_path), 150)
    terms = imr.search_terms(turns)
    assert terms == {"gitlab": 1, "ssh": 1, "金鑰": 1, "windows": 1, "heredoc": 1, "foo": 1, "bar": 1}


def test_render_tail_line(tmp_path):
    files, turns, bad = imr.scan(_projects(tmp_path), 150)
    out = imr.render(files, bad, imr.summarize(turns), imr.search_terms(turns))
    tail = out.splitlines()[-1]
    assert tail == "INJECTION_MISS DONE turns=5 zero_inject=3 zero_then_search=1 inject_then_search=1"
    assert re.fullmatch(r"[A-Z][A-Z0-9_]* DONE( \w+=\S+)*", tail)
    assert "注入 0 張的回合：3（60.0%），其中同回合自己 memory_search 補位：1（33.3%）" in out


if __name__ == "__main__":
    import subprocess  # 另開 pytest 行程，跟 tools/verify 其他案例同樣受 conftest 隔離
    rc = subprocess.call([sys.executable, "-X", "utf8", "-m", "pytest", "-q", "-p", "no:cacheprovider", __file__])
    print("INJECTION_MISS_REPORT_CHECK " + ("PASS" if rc == 0 else "FAIL"))
    sys.exit(1 if rc else 0)
