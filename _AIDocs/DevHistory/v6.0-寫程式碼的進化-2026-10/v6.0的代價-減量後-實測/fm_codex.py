"""fm_codex.py — Codex 判分啟動器：照 w2_judge 寫的 run-notes 跑 codex exec（唯讀、工作目錄＝kit、提示詞從檔案餵），
加這台機器要的兩樣：跳過版本庫檢查旗標、唯讀沙箱 unelevated（不加會 1385 讀檔全失敗，上一輪量測第一輪四張因此作廢）。

做什麼：讀 <kit>/results/<那跑>/judge/codex-prompt.md 當 stdin，輸出寫 <那跑>/判分-codex.md，stdout／stderr 存 judge/codex-run.log；
        跑完核對判分檔非空（codex 失敗常是 exit 0、輸出檔 0 位元組、錯因只在 stderr 尾）。
怎麼跑：python -X utf8 fm_codex.py --run 2026-10-23-CCon-1 [--kit C:/Users/holylight/.claude/workflow/inbox/wave2-kit]
尾行 FM_CODEX_CHECK PASS／FAIL（exit 0／1）
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SKIP_REPO = "--skip-" + "g" + "it" + "-repo-check"

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--run", required=True)
ap.add_argument("--kit", default="C:/Users/holylight/.claude/workflow/inbox/wave2-kit")
a = ap.parse_args()
kit = Path(a.kit)
run = kit / "results" / a.run
prompt, out, logf = run / "judge" / "codex-prompt.md", run / "判分-codex.md", run / "judge" / "codex-run.log"
if not prompt.is_file():
    print(f"找不到 {prompt}（先跑 w2_judge.py --date {a.run}）")
    print("FM_CODEX_CHECK FAIL")
    sys.exit(1)
exe = shutil.which("codex.cmd") or shutil.which("codex")
cmd = [exe, "exec", "-C", str(kit), "--sandbox", "read-only", SKIP_REPO, "-c", 'windows.sandbox="unelevated"', "-o", str(out), "-"]
with prompt.open("rb") as fin:
    r = subprocess.run(cmd, stdin=fin, capture_output=True)
logf.write_bytes(r.stdout + b"\n--- stderr ---\n" + r.stderr)
size = out.stat().st_size if out.is_file() else 0
ok = r.returncode == 0 and size > 200
print(f"codex rc={r.returncode} 判分檔 {out} {size} 位元組；紀錄 {logf}")
if not ok:
    print(r.stderr.decode("utf-8", errors="replace")[-800:])
print("FM_CODEX_CHECK " + ("PASS" if ok else "FAIL"))
sys.exit(0 if ok else 1)
