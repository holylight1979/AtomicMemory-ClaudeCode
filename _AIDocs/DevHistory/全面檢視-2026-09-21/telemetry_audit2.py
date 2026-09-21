"""第二批統計：PAN 週趨勢、去 prior 的效用率、git 新增日期、skill 被 hook 引用、錯誤爆發分析。python -X utf8 telemetry_audit2.py"""
import json, re, subprocess, collections, datetime as dt
from pathlib import Path
ROOT = Path("C:/Users/holylight/.claude"); NOW = dt.datetime(2026, 9, 21, 15)
def days_ago(n): return NOW - dt.timedelta(days=n)
def p(*a): print(*a)
def sec(t): p("\n" + "=" * 8, t, "=" * 8)
def read_jsonl(path):
    out = []
    for l in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        try: out.append(json.loads(l))
        except: pass
    return out

sec("A. 效用率（去 Laplace prior 後）")
sidecars = list((ROOT / "memory").rglob("*.access.json")) + list((ROOT / "_AIDocs/_atoms").rglob("*.access.json"))
live = [s for s in sidecars if "_distant" not in str(s)]
p("live sidecar(非 _distant):", len(live), " distant:", len(sidecars) - len(live))
never = 0; n_pos = 0; useless3 = []; rates = []; recent30 = 0
for s in live:
    d = json.loads(s.read_text(encoding="utf-8"))
    rh = d.get("read_hits") or 0; ts = d.get("timestamps") or []
    a = float(d.get("useful_hits") or 1); b = float(d.get("used_fail") or 1)
    succ = max(0, a - 1); fail = max(0, b - 1); n = succ + fail
    if rh == 0 and not ts: never += 1
    if n > 0:
        n_pos += 1; rates.append(succ / n)
        if n >= 3 and succ == 0: useless3.append((s.stem[:45], round(n, 1)))
    if any(t >= days_ago(30).timestamp() for t in ts): recent30 += 1
p(f"從未被注入(read_hits=0 且無 timestamps): {never}/{len(live)} = {never/len(live):.1%}")
p(f"有效用樣本 n>0: {n_pos}/{len(live)}；n>=3 且 succ=0: {len(useless3)} {useless3[:8]}")
b = collections.Counter("0" if r == 0 else "<.25" if r < .25 else "<.5" if r < .5 else "<.75" if r < .75 else "<=1" for r in rates)
p("useful 率分布(去 prior):", dict(b))
p(f"近 30 天有注入 timestamps: {recent30}/{len(live)} = {recent30/len(live):.1%}")

sec("B. [臨] >60 天且效用樣本 n<3")
cnt = 0; tot = 0; sample = []
for f in list((ROOT / "memory").rglob("*.md")) + list((ROOT / "_AIDocs/_atoms").rglob("*.md")):
    if f.name.startswith("_") or "_distant" in str(f) or "episodic" in str(f) or "_staging" in str(f): continue
    t = f.read_text(encoding="utf-8", errors="ignore")
    if not re.search(r"Confidence:\s*\[臨\]", t): continue
    side = f.with_suffix(".access.json")
    if not side.exists(): continue
    d = json.loads(side.read_text(encoding="utf-8"))
    first = d.get("first_seen") or "9999"
    if first > days_ago(60).strftime("%Y-%m-%d"): continue
    tot += 1
    n = max(0, float(d.get("useful_hits") or 1) - 1) + max(0, float(d.get("used_fail") or 1) - 1)
    if n < 3: cnt += 1; sample.append((f.stem[:40], first, round(n, 1), d.get("read_hits")))
p(f"[臨] first_seen >60 天: {tot}；其中效用樣本 n<3（升不了門）: {cnt}；樣本: {sample[:8]}")

sec("C. PAN 閘週趨勢 (guard-pre-action-notice)")
rs = read_jsonl(ROOT / "Logs/guard-pre-action-notice.jsonl")
wk = collections.defaultdict(collections.Counter)
for r in rs:
    try: d = dt.datetime.fromisoformat(r["at"]).replace(tzinfo=None)
    except: continue
    wk[d.strftime("%Y-W%V")][r.get("outcome")] += 1
for k in sorted(wk):
    c = wk[k]; t = sum(c.values())
    p(f"  {k}: total {t:4d} pass {c['pass']/t:5.1%} warn {c['warn']/t:5.1%} force_release {c['force_release']/t:5.1%} fail_open {c.get('fail_open_no_state',0)}")
by_turn = collections.defaultdict(list)
for r in rs:
    by_turn[(r.get("sid"), r.get("turn"))].append(r.get("outcome"))
turns = list(by_turn.values())
first_pass = sum(1 for v in turns if v[0] == "pass"); warn_then_pass = sum(1 for v in turns if v[0] == "warn" and "pass" in v[1:]); warn_never = sum(1 for v in turns if v[0] == "warn" and "pass" not in v)
p(f"  turn 數 {len(turns)}：第一次工具呼叫就 pass {first_pass} ({first_pass/len(turns):.0%})；先 warn 後補到 pass {warn_then_pass}；warn 到底沒補 {warn_never}")

sec("D. git 首次加入日期：各目錄近 30/60/90 天新增檔數（ctime 不可信，改 git）")
out = subprocess.run(["git", "log", "--diff-filter=A", "--date=short", "--format=@@%ad", "--name-only", "--", "memory", "_AIDocs/_atoms"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
first_add = {}; cur = None
for l in out.splitlines():
    if l.startswith("@@"): cur = l[2:]; continue
    if l.strip().endswith(".md") and not Path(l).name.startswith("_"): first_add[l] = cur  # 由新到舊，覆蓋後為最早一次 add
cats = {"memory/Failures": "Failures", "memory/episodic": "episodic(global)", "memory/_distant": "_distant", "_AIDocs/_atoms": "local atoms", "memory/_staging": "_staging"}
def cat_of(pth):
    for k, v in cats.items():
        if pth.startswith(k): return v
    return "global atoms" if pth.startswith("memory/") else "other"
agg = collections.defaultdict(collections.Counter)
for pth, d in first_add.items():
    c = cat_of(pth); agg[c]["total"] += 1
    for w in (30, 60, 90):
        if d >= days_ago(w).strftime("%Y-%m-%d"): agg[c][w] += 1
for c, v in sorted(agg.items()): p(f"  {c:18s} 累計加入 {v['total']:4d}  近30/60/90: {v[30]}/{v[60]}/{v[90]}")
out2 = subprocess.run(["git", "log", "--diff-filter=A", "--format=@@%s", "--name-only", "--", "memory/Failures"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="ignore").stdout
msgs = collections.Counter(); cur = ""
for l in out2.splitlines():
    if l.startswith("@@"): cur = l[2:]; continue
    if l.strip().endswith(".md") and (ROOT / l).exists() and not Path(l).name.startswith("_"): msgs[cur[:60]] += 1
p("  現存 Failures 依首次 commit 訊息:", msgs.most_common(8))

sec("E. skill 被 hook/tool 程式碼引用（程式化觸發，不經 Skill tool）")
names = ['atom-debug', 'browse-sprites', 'changelog-debug', 'codex-companion', 'conflict', 'consciousness-stream', 'continue', 'extract', 'fix-escalation', 'generate-episodic', 'handoff', 'harvest', 'heal-review', 'journal', 'karpathy-guidelines', 'memory', 'read-project', 'refile', 'skill-creator', 'synced', 'upgrade', 'vector']
refs = collections.defaultdict(set)
for f in list(ROOT.glob("hooks/**/*.py")) + list(ROOT.glob("tools/**/*.py")) + list(ROOT.glob("tools/workflow-guardian-mcp/**/*.js")):
    sf = str(f)
    if "verify" in sf or "node_modules" in sf or "__pycache__" in sf: continue
    t = f.read_text(encoding="utf-8", errors="ignore")
    for n in names:
        if re.search(r"/" + re.escape(n) + r"\b", t): refs[n].add(str(f.relative_to(ROOT)).replace("\\", "/"))
for n in names:
    d = ROOT / "skills" / n
    sz = sum(f.stat().st_size for f in d.rglob("*") if f.is_file()) if d.exists() else 0
    nf = sum(1 for f in d.rglob("*") if f.is_file()) if d.exists() else 0
    p(f"  /{n:22s} hook引用 {len(refs[n])} 檔 {sorted(refs[n])[:2]}  | 目錄 {nf} 檔 {sz/1024:.0f}KB")

sec("F. atom-debug ERROR 爆發分析（同秒多筆＝pytest 產生的噪音）")
errs = collections.defaultdict(list)
for f in sorted(ROOT.glob("Logs/atom-debug-2026-0[89]-*.log")):
    for l in f.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"\[(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)\]\[ERROR\] \[([^\]]+)\]", l)
        if m: errs[m.group(2)].append(m.group(1))
for k, v in sorted(errs.items(), key=lambda x: -len(x[1]))[:12]:
    secs = collections.Counter(v); bursts = sum(1 for c in secs.values() if c >= 3); lone = sum(1 for c in secs.values() if c == 1)
    p(f"  {k:40s} 總 {len(v):4d} 不同秒 {len(secs):3d} 爆發秒(>=3筆) {bursts:3d} 單筆秒 {lone:3d} 最早 {min(v)[:10]} 最晚 {max(v)[:10]}")

sec("G. session 規模")
pre = read_jsonl(ROOT / "Logs/guard-pre-action-notice.jsonl")
sids = {r.get("sid") for r in pre if r.get("at", "") >= days_ago(30).isoformat()}
p("近 30 天有 PAN 記錄的 session:", len(sids))
tf = [f for f in Path("C:/Users/holylight/.claude/projects").rglob("*.jsonl") if "_archive" not in str(f) and f.stat().st_mtime >= days_ago(30).timestamp()]
p("近 30 天 transcript 檔:", len(tf), " 依專案:", collections.Counter(f.parent.name for f in tf).most_common(6))
