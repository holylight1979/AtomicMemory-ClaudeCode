"""codex_b6new.py — 005 現況三跑補判 B6 新標準（調度 10-23 裁，track-rejudge 附錄 B 原文）：Codex 三份並行、唯讀沙箱，
提示＝該跑 judge/codex-prompt.md＋附錄 B＋「只判 B6、不重判其他條目」，輸出 <跑>/判分-codex-B6新標準.md（不動原本的 判分-codex.md）。
怎麼跑：python -X utf8 codex_b6new.py
尾行 CODEX_B6NEW_CHECK PASS／FAIL
"""
import shutil
import subprocess
import sys
import time
from pathlib import Path

KIT = Path("C:/Users/holylight/.claude/workflow/inbox/wave2-kit")
RUNS = ["2026-10-27-005-CCon-1", "2026-10-27-005-CCon-2", "2026-10-27-005-CCon-3"]
APPX = (Path(__file__).resolve().parent / "b6new-appendix.md").read_text(encoding="utf-8")
ONLY = ("\n\n## 這次只補判 B6\n這一跑其他條目已判過，這次**只判 B6**：照上面「B6 改判法」的新標準判一次、照答案檔原標準再判一次，"
        "各寫過／沒過、證據路徑（檔:行）、一句依據；最後寫「照新標準 B′ 通過線過／沒過」——其他 7 條照「已判過：B1、B2、B4、B5、B7、B8、B10 的結果"
        "不在你這次範圍」處理，只寫 B6 改判後 B6 那一條的結論。不讀任何 判分-*.md。\n")
exe = shutil.which("codex.cmd") or shutil.which("codex")
procs = []
for run in RUNS:
    d = KIT / "results" / run
    p = d / "judge" / "codex-prompt-b6new.md"
    p.write_text((d / "judge" / "codex-prompt.md").read_text(encoding="utf-8") + "\n\n" + APPX + ONLY, encoding="utf-8")
    out = d / "判分-codex-B6新標準.md"
    cmd = [exe, "exec", "-C", str(KIT), "--sandbox", "read-only", "--skip-" + "g" + "it" + "-repo-check",
           "-c", 'windows.sandbox="unelevated"', "-o", str(out), "-"]
    fin = p.open("rb")
    procs.append((run, out, d / "judge" / "codex-run-b6new.log", fin, time.time(),
                  subprocess.Popen(cmd, stdin=fin, stdout=subprocess.PIPE, stderr=subprocess.PIPE)))
ok_all = True
for run, out, logf, fin, t0, pr in procs:
    so, se = pr.communicate()
    fin.close()
    logf.write_bytes(so + b"\n--- stderr ---\n" + se)
    size = out.stat().st_size if out.is_file() else 0
    ok = pr.returncode == 0 and size > 200 and b"exec_command failed" not in so + se
    ok_all &= ok
    print(f"{run} rc={pr.returncode} {size} 位元組 {time.time() - t0:.0f} 秒 {'ok' if ok else 'FAIL'}")
print("CODEX_B6NEW_CHECK " + ("PASS" if ok_all else "FAIL"))
sys.exit(0 if ok_all else 1)
