"""fm_nc.py — 非改 code 題（B5 題四「三份上線文件整併」）比照題 B′ 的跑法：建受測專案、無頭代打、收材料。

做什麼
  build：在 <dest> 建 qn4-release-guide\（B5 題四的五個檔逐字照抄，git init＋commit init）與 qn4-release-guide-root\
         （複製同一次 w2_build_env 剛建好、還沒跑過的 qa2-pricing-root：同一份 config.json、詞表與卡集；卡集清單一起複製改名）。
         要先跑完 w2_build_env --selfcheck（PASS）再跑這步。
  run：用 w2_run_all 的 call_claude／patch_turn（同一支 claude.exe、bypassPermissions、WG_CLAUDE_DIR／WG_TEST_LOGS_DIR 指資料根、
       入口讓 claude 自設 sdk-cli，同題 B′）送題句；AI 最後一則像在問問題就回「照你的判斷做」，最多兩次；不打交材料句（本題不判分）。
       回合 JSON 落 <kit>/results/<日期>/turns/N-1-t<n>.json，跑完用 w2_collect 收到 <kit>/results/<日期>/N-1/。
怎麼跑（放在 w2_run_all.py、w2_collect.py 同一個目錄）
  python -X utf8 fm_nc.py build [--dest C:/w4]
  python -X utf8 fm_nc.py run --date <results 底下的資料夾> [--hooks-off] [--dest C:/w4] [--kit …]
尾行 FM_NC DONE step=<build|run> …；失敗印 FM_NC FAIL reason=…（exit 1）
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w2_collect  # noqa: E402
import w2_run_all as ra  # noqa: E402

NAME = "qn4-release-guide"
SEED_ROOT = "qa2-pricing-root"   # 這組串跑不跑 A′，它的資料根建好後沒被用過
PROMPT = "請把 ops/docs 中互有重複的三份上線文件整併成 ops/docs/release.md，移除原來那三份，每個必要步驟都要保留。"
FILES = {
    "ops/deploy.py": '"""部署腳本（CI 呼叫的重啟步驟）。"""\nimport subprocess\n\n\ndef restart():\n'
                     '    subprocess.run(["systemctl", "restart", "orderhub"], check=True)\n',
    "ops/README.md": "# ops\n\n- 上線步驟見 `docs/rollout-sequence.md`，環境備註見 `docs/runtime-memo.md`；"
                     "`docs/release-legacy.md` 是舊版，留著對照。\n- CI 的重啟步驟呼叫 `deploy.py` 的 `restart()`。\n",
    "ops/docs/runtime-memo.md": "# 執行環境備註\n\n- 從 2027-03 開始，服務使用 9121；9120 已交給監控使用，仍標示服務使用 9120 的文件已過時。\n"
                                "- 必須先完成 migrate 才能重啟，顛倒順序會回應 500。\n"
                                "- 服務重啟完成後，執行 `curl -f http://localhost:9121/health` 檢查。\n",
    "ops/docs/release-legacy.md": "# 上線操作（歷史版本）\n\n1. `git pull`\n2. `pip install -r requirements.txt`\n"
                                  "3. 執行 `systemctl restart orderhub` 重啟服務（監聽埠為 9120）\n",
    "ops/docs/rollout-sequence.md": "# 發布流程\n\n1. 動手部署前先備份資料庫：`pg_dump orderhub > snapshots/$(date +%Y%m%d).sql`\n"
                                    "2. `git pull`\n3. `pip install -r requirements.txt`\n4. `python manage.py migrate`\n"
                                    "5. `systemctl restart orderhub`\n",
}
VC = "g" + "it"


def fail(reason):
    print(f"FM_NC FAIL reason={reason}")
    sys.exit(1)


def vc(root, *args):
    r = subprocess.run([VC, "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        fail(f"{VC} {' '.join(args)} 失敗於 {root}: {r.stderr[-300:]}")
    return r.stdout


def build(dest):
    proj, root, seed = dest / NAME, dest / f"{NAME}-root", dest / SEED_ROOT
    if not seed.is_dir() or any((seed / "Logs").iterdir()):
        fail(f"{seed} 不在或 Logs 不是空的（要先跑 w2_build_env、而且這個資料根沒被用過）")
    for p in (proj, root):
        if p.exists():
            # 上一跑留下的 .git 物件檔是唯讀，Windows 上 rmtree 刪不掉：遇到就先改可寫再刪
            shutil.rmtree(p, onexc=lambda fn, path, exc: (os.chmod(path, 0o666), fn(path)))
    for rel, text in FILES.items():
        f = proj / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")
    vc(proj, "init", "-q")
    vc(proj, "add", "-A")
    vc(proj, "-c", "user.name=b5", "-c", "user.email=b5@local", "commit", "-q", "-m", "init")
    shutil.copytree(seed, root)
    manifest = dest / f"{SEED_ROOT}.cards.json"
    if manifest.is_file():
        d = json.loads(manifest.read_text(encoding="utf-8"))
        d["root"] = str(root)
        (dest / f"{NAME}-root.cards.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    cards = len(w2_collect.card_hashes(root / "memory"))
    status = vc(proj, "status", "--short").strip()
    if status:
        fail(f"受測專案 init 後不乾淨：{status}")
    print(f"FM_NC DONE step=build project={proj} files={len(FILES)} root_cards={cards} manifest={manifest.is_file()}")


def run(a):
    kit, dest = Path(a.kit), Path(a.dest)
    proj, root = dest / NAME, dest / f"{NAME}-root"
    if not proj.is_dir() or not root.is_dir():
        fail(f"找不到 {proj} 或 {root}（先跑 build）")
    turns_dir = kit / "results" / a.date / "turns"
    turns_dir.mkdir(parents=True, exist_ok=True)
    sid, n, last, cost = "", 0, None, 0.0

    def send(prompt, label):
        nonlocal sid, n, last, cost
        n += 1
        d = ra.call_claude(prompt, proj, root, "sdk", sid, a.max_turns, a.timeout_min, a.hooks_off)
        d["_meta"].update({"q": "N", "seg": "1", "n": n, "id": label})
        if d.get("session_id"):
            ra.patch_turn(d, proj, prompt)
        (turns_dir / f"N-1-t{n}.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
        cost = max(cost, float(d.get("total_cost_usd") or 0))
        ok = bool(d.get("session_id")) and d["_meta"]["rc"] == 0
        print(f"  N-1-t{n} [{label}] session={str(d.get('session_id', '?'))[:8]} turns={d.get('num_turns', '?')} "
              f"stop={d.get('stop_reason', '?')} denials={len(d.get('permission_denials') or [])} rc={d['_meta']['rc']}", flush=True)
        if ok:
            sid, last = d["session_id"], d
        return ok

    ok = send(PROMPT, "first")
    auto = 2
    while ok and auto > 0 and last and ra.asks_question(last):
        auto -= 1
        ok = send(ra.AUTO, "auto")
    w2_collect.PROJECTS["N"] = NAME
    sys.argv = ["w2_collect.py", "--q", "N", "--seg", "1", "--date", a.date, "--kit", str(kit), "--dest", str(dest)]
    w2_collect.main()
    print(f"FM_NC DONE step=run date={a.date} turns={n} failed={int(not ok)} cost_usd={cost:.2f} hooks={'off' if a.hooks_off else 'on'}")
    return ok


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=["build", "run"])
    ap.add_argument("--dest", default="C:/w4")
    ap.add_argument("--kit", default=ra.DEFAULT_KIT)
    ap.add_argument("--date")
    ap.add_argument("--hooks-off", action="store_true")
    ap.add_argument("--max-turns", type=int, default=120)
    ap.add_argument("--timeout-min", type=int, default=45)
    a = ap.parse_args()
    if a.step == "build":
        build(Path(a.dest))
    else:
        if not a.date:
            fail("run 要 --date")
        sys.exit(0 if run(a) else 1)


if __name__ == "__main__":
    main()
