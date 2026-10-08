"""R4 基線：每個 session「第一次 Edit/Write 之前讀了幾個檔、跨幾個頂層目錄」。
跑法：python r4_baseline.py <projects/<slug> 目錄> [N=10] [--skip <session_id>]
讀檔算法：Read 工具的 file_path，加上 Bash 裡 cat/sed -n/head/tail 後面的路徑（bypass 模式讀檔走 Bash）。
頂層目錄＝檔案路徑去掉 cwd 後的第一段；cwd 外的檔以磁碟根起算第一段。
"""
import json, re, sys, os
from pathlib import Path

READ_CMD = re.compile(r'(?:^|[;&|]\s*)(?:cat|head|tail|sed\s+-n\s+\S+|less)\s+(?:-[a-zA-Z0-9]+\s+)*"?([^"\s;|&]+)"?')
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

def norm(p): return p.replace("\\", "/").rstrip("/").lower()

def is_abs(p): return p.startswith("/") or p.startswith("~") or re.match(r"^[a-z]:/", p) is not None

def top_dir(path, cwd):
    p, c = norm(path), norm(cwd)
    if not is_abs(p):
        p = c + "/" + p.lstrip("./")
    if p.startswith(c + "/"):
        rel = p[len(c) + 1:]
        return rel.split("/")[0] if "/" in rel else "(root)"
    parts = p.split("/")
    return "/".join(parts[:2]) + "/…"

def analyze(fp, skip):
    cwd, reads, first_edit, user_turns, greps = "", [], None, 0, 0
    with open(fp, encoding="utf-8", errors="replace") as f:
        for line in f:
            try: o = json.loads(line)
            except Exception: continue
            if o.get("sessionId") == skip: return None
            if not cwd and o.get("cwd"): cwd = o["cwd"]
            if o.get("type") == "user" and isinstance(o.get("message", {}).get("content"), str):
                user_turns += 1
            if o.get("type") != "assistant": continue
            for b in (o.get("message", {}).get("content") or []):
                if not (isinstance(b, dict) and b.get("type") == "tool_use"): continue
                name, inp = b.get("name"), b.get("input") or {}
                if name in EDIT_TOOLS:
                    first_edit = inp.get("file_path") or inp.get("notebook_path") or "?"
                    return dict(session=fp.stem[:8], cwd=cwd, reads=reads, first_edit=first_edit, turns=user_turns, greps=greps)
                if name in ("Grep", "Glob"): greps += 1
                if name == "Read" and inp.get("file_path"):
                    reads.append(inp["file_path"])
                elif name == "Bash":
                    for m in READ_CMD.finditer(inp.get("command", "")):
                        if ("/" in m.group(1) or "\\" in m.group(1)) and not m.group(1).startswith("$"): reads.append(m.group(1))
    return dict(session=fp.stem[:8], cwd=cwd, reads=reads, first_edit=None, turns=user_turns, greps=greps)

def main():
    d = Path(sys.argv[1]); n = int(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2].isdigit() else 10
    skip = sys.argv[sys.argv.index("--skip") + 1] if "--skip" in sys.argv else ""
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    rows = []
    for fp in files:
        if skip and fp.stem == skip: continue
        if fp.stat().st_size < 20000: continue
        r = analyze(fp, skip)
        if r is None: continue
        rows.append(r)
        if len(rows) >= n: break
    print(f"| session | 使用者回合(到首改) | 首改前 Read 檔數 | 跨頂層目錄 | Grep/Glob 次 | 首改檔 |")
    print("|---|---|---|---|---|---|")
    tot_r, tot_d, with_edit = 0, 0, 0
    for r in rows:
        files_ = sorted(set(norm(x) for x in r["reads"]))
        dirs = sorted(set(top_dir(x, r["cwd"]) for x in files_))
        fe = r["first_edit"]
        fe_s = norm(fe).replace(norm(r["cwd"]) + "/", "") if fe else "（整個 session 沒改檔）"
        print(f"| {r['session']} | {r['turns']} | {len(files_)} | {len(dirs)} ({', '.join(dirs)[:60]}) | {r['greps']} | {fe_s[:70]} |")
        if fe: with_edit += 1; tot_r += len(files_); tot_d += len(dirs)
    if with_edit:
        print(f"\n有改檔的 {with_edit} 個 session：首改前平均 Read {tot_r/with_edit:.1f} 檔、跨 {tot_d/with_edit:.1f} 個頂層目錄")

main()
