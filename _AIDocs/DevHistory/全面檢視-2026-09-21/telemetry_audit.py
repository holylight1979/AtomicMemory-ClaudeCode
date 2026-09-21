"""原子記憶系統遙測統計（只讀）。跑法：python -X utf8 telemetry_audit.py"""
import json, os, re, glob, time, collections, datetime as dt
from pathlib import Path

ROOT = Path("C:/Users/holylight/.claude")
NOW = dt.datetime(2026, 9, 21, 15, 0, 0)
NOW_TS = NOW.timestamp()
def days_ago(n): return NOW - dt.timedelta(days=n)
def p(*a): print(*a)
def sec(t): p("\n" + "=" * 8, t, "=" * 8)

# ---------- 1. atom 曝光與效用 ----------
sec("1. atom 曝光與效用 (access sidecars)")
sidecars = list((ROOT / "memory").rglob("*.access.json")) + list((ROOT / "_AIDocs/_atoms").rglob("*.access.json"))
p("sidecar 總數:", len(sidecars))
never, exp5_useless, recent30, recent30_useful = 0, 0, 0, 0
rates = []
by_realm = collections.Counter(); never_realm = collections.Counter()
distant = 0
useless_list = []
zero_rate_list = []
for s in sidecars:
    try:
        d = json.loads(s.read_text(encoding="utf-8"))
    except Exception as e:
        p("  bad json:", s, e); continue
    realm = "local" if "_AIDocs" in str(s) else ("distant" if "_distant" in str(s) else "global")
    by_realm[realm] += 1
    rh = d.get("read_hits", 0) or 0
    uh = d.get("useful_hits", 0) or 0
    uf = d.get("used_fail", 0) or 0
    ts = d.get("timestamps") or []
    n = uh + uf
    exposed = rh > 0 or len(ts) > 0 or n > 0
    if not exposed:
        never += 1; never_realm[realm] += 1
    if n >= 5 and uh == 0:
        exp5_useless += 1; useless_list.append(s.stem)
    if n > 0:
        rates.append(uh / n)
        if uh == 0: zero_rate_list.append((s.stem, n))
    last_used = d.get("last_used")
    recent_ts = [t for t in ts if t >= days_ago(30).timestamp()]
    if recent_ts or (last_used and last_used >= days_ago(30).strftime("%Y-%m-%d")):
        recent30 += 1
        if uh > 0: recent30_useful += 1
p("依 realm:", dict(by_realm))
p(f"從未被注入(read_hits=0 且無 timestamps 且 n=0): {never} / {len(sidecars)} = {never/len(sidecars):.1%}  依realm={dict(never_realm)}")
p(f"曝光 n>=5 但 useful_hits=0: {exp5_useless}")
p(f"有效用樣本(n>0) 顆數: {len(rates)}")
if rates:
    buckets = collections.Counter()
    for r in rates:
        buckets["0" if r == 0 else "0-0.25" if r < .25 else "0.25-0.5" if r < .5 else "0.5-0.75" if r < .75 else "0.75-1"] += 1
    p("useful 率分布:", dict(sorted(buckets.items())))
    import statistics
    p(f"useful 率中位數 {statistics.median(rates):.2f}  平均 {statistics.mean(rates):.2f}")
p(f"最近 30 天有被注入: {recent30} ({recent30/len(sidecars):.1%})，其中 useful_hits>0: {recent30_useful}")
p("useful=0 且 n>=3 (前 15):", sorted(zero_rate_list, key=lambda x: -x[1])[:15])

# ---------- 2. 晉升迴路 ----------
sec("2. 晉升迴路 (_promotion_audit.jsonl)")
rows = [json.loads(l) for l in (ROOT / "memory/_promotion_audit.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
p("總筆數:", len(rows))
for win in (30, 90):
    cut = days_ago(win).isoformat()
    sub = [r for r in rows if r.get("ts", "") >= cut]
    c = collections.Counter((r.get("action"), r.get("from"), r.get("to"), r.get("method")) for r in sub)
    p(f"近 {win} 天: {len(sub)} 筆")
    for k, v in c.most_common(): p("   ", k, v)
    p("   distinct atoms:", len({r.get('atom') for r in sub}))
    p("   distinct sessions:", len({r.get('session_id') for r in sub}))
    if win == 90:
        top = collections.Counter(r.get("atom") for r in sub).most_common(8)
        p("   重複 hint 最多的 atom:", top)
# [臨] 超過 60 天未晉升
sec("2b. [臨] 存在 >60 天且從未晉升")
atoms_md = [f for f in list((ROOT / "memory").rglob("*.md")) + list((ROOT / "_AIDocs/_atoms").rglob("*.md")) if not f.name.startswith("_") and "_distant" not in str(f) and "episodic" not in str(f) and "_staging" not in str(f)]
conf_c = collections.Counter(); old_tent = []; tent_total = 0
for f in atoms_md:
    try: txt = f.read_text(encoding="utf-8", errors="ignore")
    except: continue
    m = re.search(r"Confidence:\s*\[(臨|觀|固)\]", txt)
    if not m: continue
    conf_c[m.group(1)] += 1
    if m.group(1) != "臨": continue
    tent_total += 1
    side = f.with_suffix(".access.json")
    first = None
    if side.exists():
        try: first = json.loads(side.read_text(encoding="utf-8")).get("first_seen")
        except: pass
    if not first:
        first = dt.datetime.fromtimestamp(f.stat().st_ctime).strftime("%Y-%m-%d")
    if first <= days_ago(60).strftime("%Y-%m-%d"):
        n = 0
        if side.exists():
            try:
                d = json.loads(side.read_text(encoding="utf-8")); n = (d.get("useful_hits") or 0) + (d.get("used_fail") or 0)
            except: pass
        old_tent.append((f.stem[:50], first, round(n, 1)))
p("Confidence 分布(含 atom md):", dict(conf_c))
p(f"[臨] 存在 >60 天: {len(old_tent)} / {tent_total}")
p("   其中 n=0(從未有效用樣本):", sum(1 for x in old_tent if x[2] == 0))
p("   樣本:", old_tent[:10])

# ---------- 3. 自動萃取產出 ----------
sec("3. 自動萃取產出")
def count_new(dirs, pattern="*.md"):
    out = {}
    files = []
    for d in dirs:
        files += [f for f in Path(d).rglob(pattern) if not f.name.startswith("_")]
    for win in (30, 60, 90):
        cut = days_ago(win).timestamp()
        out[win] = sum(1 for f in files if f.stat().st_ctime >= cut)
    return len(files), out, files
for label, dirs in [("Failures", [ROOT / "memory/Failures"]), ("episodic(global)", [ROOT / "memory/episodic"]), ("_staging", [ROOT / "memory/_staging"]), ("_distant", [ROOT / "memory/_distant"])]:
    tot, wins, files = count_new(dirs)
    p(f"{label}: 總 {tot}, 新增 30/60/90 天 = {wins[30]}/{wins[60]}/{wins[90]}")
    if files:
        newest = max(files, key=lambda f: f.stat().st_mtime)
        p("   最新檔:", newest.name[:70], dt.datetime.fromtimestamp(newest.stat().st_mtime).strftime("%Y-%m-%d"))
# pending
for d in ROOT.rglob("_pending*"):
    if d.is_dir() and "node_modules" not in str(d):
        fs = list(d.rglob("*"))
        p(f"pending dir {d.relative_to(ROOT)}: {len([f for f in fs if f.is_file()])} files")
# episodic 依日期名（檔名前綴 YYYY-MM-DD）
ep = sorted((ROOT / "memory/episodic").glob("*.md"))
dates = collections.Counter(f.name[:7] for f in ep)
p("episodic 依月份:", dict(sorted(dates.items())))
p("episodic 檔名日期最後:", ep[-1].name if ep else None)
# 專案層 episodic
for proj in ["C:/Projects", "D:/AI-PLAY", "C:/TSLG"]:
    for d in Path(proj).rglob("episodic") if Path(proj).exists() else []:
        if ".claude" in str(d) and d.is_dir():
            fs = sorted(d.glob("*.md"))
            if fs: p(f"專案 episodic {d}: {len(fs)} 最後 {fs[-1].name[:40]}")
# extract-worker.log
ew = (ROOT / "workflow/extract-worker.log").read_text(encoding="utf-8", errors="ignore").splitlines()
p("extract-worker.log 行數:", len(ew), "mtime", dt.datetime.fromtimestamp((ROOT / "workflow/extract-worker.log").stat().st_mtime))
p("   行型態:", collections.Counter(re.sub(r"\d+", "N", l)[:60] for l in ew).most_common(8))
# Failures 依來源（auto vs manual）：檔名含 feedback- 視為手動；檢查 frontmatter source 欄
src_c = collections.Counter()
for f in (ROOT / "memory/Failures").rglob("*.md"):
    if f.name.startswith("_"): continue
    t = f.read_text(encoding="utf-8", errors="ignore")[:1500]
    m = re.search(r"(?:Source|source|來源)\s*[:：]\s*(\S+)", t)
    src_c[m.group(1)[:30] if m else "(無source欄)"] += 1
p("Failures source 欄分布:", src_c.most_common(8))

# ---------- 4. 守門閘觸發率 ----------
sec("4. 守門閘觸發率 (近 30 天)")
cut30 = days_ago(30)
def read_jsonl(path):
    out = []
    for l in Path(path).read_text(encoding="utf-8", errors="ignore").splitlines():
        l = l.strip()
        if not l: continue
        try: out.append(json.loads(l))
        except: pass
    return out
def ts_of(r):
    v = r.get("at") or r.get("ts")
    if isinstance(v, (int, float)): return dt.datetime.fromtimestamp(v)
    if isinstance(v, str):
        try: return dt.datetime.fromisoformat(v.replace("Z", "")).replace(tzinfo=None)
        except: return None
    return None
for f in sorted((ROOT / "Logs").glob("guard-*.jsonl")):
    rs = read_jsonl(f)
    r30 = [r for r in rs if (ts_of(r) or dt.datetime(2000, 1, 1)) >= cut30]
    p(f"{f.name}: 總 {len(rs)}, 近30天 {len(r30)}, sessions(30d) {len({r.get('session_id') or r.get('sid') for r in r30})}")
    if f.name == "guard-pre-action-notice.jsonl":
        p("   outcome×mode:", collections.Counter((r.get("mode"), r.get("outcome")) for r in r30).most_common())
        p("   fail_code:", collections.Counter(r.get("fail_code") for r in r30 if r.get("fail_code")).most_common(6))
    if f.name == "guard-docdrift.jsonl":
        p("   doc:", collections.Counter(r.get("doc") for r in r30).most_common(5))
        p("   source:", collections.Counter(r.get("source") for r in r30).most_common(5))
# aec-report / decision / pan
def dir_stats(d, exts=None):
    fs = [f for f in (ROOT / "workflow" / d).iterdir() if f.is_file()]
    r30 = [f for f in fs if dt.datetime.fromtimestamp(f.stat().st_mtime) >= cut30]
    return len(fs), len(r30), fs
for d in ["aec-report", "aec-decision", "pan-deny", "pan-pass", "dpm-done", "acceptance-spec", "aec-tempfiles"]:
    tot, n30, fs = dir_stats(d)
    p(f"workflow/{d}: 總 {tot}, 近30天 {n30}")
    if d == "aec-report":
        sev = collections.Counter(); upg = 0
        for f in fs:
            try: j = json.loads(f.read_text(encoding="utf-8"))
            except: continue
            sev[j.get("severity")] += 1; upg += 1 if j.get("severity_upgraded_by") else 0
        p("   severity:", dict(sev), "hook 升級數:", upg)
    if d == "pan-deny":
        cnts = collections.Counter()
        for f in fs:
            try: cnts[json.loads(f.read_text(encoding="utf-8")).get("count")] += 1
            except: cnts["?"] += 1
        p("   deny count 分布(3=強制放行):", dict(cnts))
# acceptance-audit
aa = read_jsonl(ROOT / "workflow/acceptance-audit.jsonl")
aa30 = [r for r in aa if (r.get("at") or r.get("ts") or "") and (ts_of(r) or dt.datetime(2000, 1, 1)) >= cut30]
if not aa30:  # 無時間欄 → 用 session 對照 aec-report 時間
    p("acceptance-audit: 無 at/ts 欄，欄位=", list(aa[-1].keys())[:20])
p(f"acceptance-audit: 總 {len(aa)}, 近30天 {len(aa30)}")
p("   verdict(全):", collections.Counter(r.get("verdict") for r in aa).most_common())
p("   verdict(30d):", collections.Counter(r.get("verdict") for r in aa30).most_common())
p("   trigger(30d):", collections.Counter(r.get("trigger") for r in aa30).most_common())
p("   judge_backend(30d):", collections.Counter(r.get("judge_backend") for r in aa30).most_common())
# companion-metrics
agg = collections.Counter()
for f in (ROOT / "workflow").glob("companion-metrics-*.json"):
    try: agg.update(json.loads(f.read_text(encoding="utf-8")))
    except: pass
p("companion-metrics 彙總(9 檔):", dict(agg))
# outcome_stats
os_ = read_jsonl(ROOT / "workflow/outcome_stats.jsonl")
p("outcome_stats:", len(os_), "近30天", len([r for r in os_ if (ts_of(r) or dt.datetime(2000,1,1)) >= cut30]), "平均 unknown ratio", round(sum(r.get("ratio", 0) for r in os_) / max(1, len(os_)), 2))
# injection-turns
it = read_jsonl(ROOT / "Logs/injection-turns.jsonl")
it30 = [r for r in it if (ts_of(r) or dt.datetime(2000,1,1)) >= cut30]
p(f"injection-turns: 總 {len(it)}, 近30天 {len(it30)}")
if it30:
    tot_ok = sum(r.get("ok", 0) for r in it30); tot_skip = sum(r.get("skip", 0) for r in it30); tot_cold = sum(r.get("cold", 0) for r in it30); tot_fb = sum(r.get("fallback", 0) for r in it30); tot_red = sum(r.get("redundant", 0) for r in it30)
    p(f"   ok {tot_ok} skip {tot_skip} cold {tot_cold} fallback {tot_fb} redundant {tot_red}; 平均 used_tokens {sum(r.get('used_tokens',0) for r in it30)/len(it30):.0f}/limit; 撞頂(used>=limit*0.95) {sum(1 for r in it30 if r.get('used_tokens',0) >= r.get('limit',1200)*0.95)}")
    p("   skip 率(被 budget 砍):", f"{tot_skip/max(1,tot_ok+tot_skip):.1%}")

# ---------- 5. skill 使用 ----------
sec("5. skill 使用 (近 60 天 transcript)")
idx = json.load(open(ROOT / "skills/_skill_index.json", encoding="utf-8"))
skills = idx["skills"]
names = [s["name"] if isinstance(s, dict) else s for s in skills] if isinstance(skills, list) else list(skills.keys())
p("skill 數:", len(names), names)
cut60 = days_ago(60).timestamp()
tfiles = [f for f in Path("C:/Users/holylight/.claude/projects").rglob("*.jsonl") if f.stat().st_mtime >= cut60 and "_archive" not in str(f)]
p("transcript 檔數(60d):", len(tfiles))
tool_calls = collections.Counter(); slash = collections.Counter(); sessions_with = collections.defaultdict(set)
pat_tool = re.compile(r'"name":\s*"Skill"[^}]{0,400}?"skill":\s*"([\w\-:]+)"')
pat_tool2 = re.compile(r'"skill":\s*"([\w\-:]+)"')
pat_slash = re.compile(r'"content":\s*"(?:<command-name>)?/([\w\-]+)')
pat_cmd = re.compile(r'<command-name>/?([\w\-]+)</command-name>')
for f in tfiles:
    try: txt = f.read_text(encoding="utf-8", errors="ignore")
    except: continue
    for m in pat_tool2.finditer(txt):
        tool_calls[m.group(1)] += 1; sessions_with[m.group(1)].add(f.name)
    for m in pat_cmd.finditer(txt):
        slash[m.group(1)] += 1; sessions_with[m.group(1)].add(f.name)
p("Skill tool 呼叫:", tool_calls.most_common(30))
p("<command-name> 出現:", slash.most_common(30))
zero = [n for n in names if tool_calls.get(n, 0) + slash.get(n, 0) == 0]
p(f"0 次使用的 skill ({len(zero)}):", zero)
p("有使用的 skill → (tool+slash, sessions):", {n: (tool_calls.get(n, 0) + slash.get(n, 0), len(sessions_with.get(n, ()))) for n in names if n not in zero})

# ---------- 6. recall-miss / rescue-log ----------
sec("6. recall-miss / rescue-log")
rm = read_jsonl(ROOT / "Logs/recall-miss.jsonl")
rm30 = [r for r in rm if (ts_of(r) or dt.datetime(2000,1,1)) >= cut30]
p(f"recall-miss: 總 {len(rm)}, 近30天 {len(rm30)}; source:", collections.Counter(r.get("source") for r in rm).most_common())
p("   涉及 atom:", collections.Counter(r.get("atom")[:40] for r in rm).most_common(6))
rl = read_jsonl(ROOT / "Logs/rescue-log.jsonl")
rl30 = [r for r in rl if (ts_of(r) or dt.datetime(2000,1,1)) >= cut30]
p(f"rescue-log: 總 {len(rl)}, 近30天 {len(rl30)}; sessions(30d) {len({r.get('session_id') for r in rl30})}; distinct atoms(30d) {len({r.get('atom') for r in rl30})}")
p("   top atoms(30d):", collections.Counter(r.get("atom")[:45] for r in rl30).most_common(6))
p("   tool:", collections.Counter(r.get("tool") for r in rl30).most_common())
# 誰消費：grep 所有 hooks/tools/skills 讀這兩個檔
consumers = collections.defaultdict(list)
for f in list(ROOT.glob("hooks/**/*.py")) + list(ROOT.glob("tools/**/*.py")) + list(ROOT.glob("tools/**/*.js")) + list(ROOT.glob("skills/**/*.py")) + list(ROOT.glob("skills/**/*.md")):
    if "node_modules" in str(f) or "__pycache__" in str(f): continue
    try: t = f.read_text(encoding="utf-8", errors="ignore")
    except: continue
    for key in ("recall-miss.jsonl", "rescue-log.jsonl", "recall_miss", "rescue_log", "guard-lang", "guard-docdrift", "guard-deferral", "guard-evasion", "guard-aec_pending", "outcome_stats", "companion-metrics", "injection-turns", "_promotion_audit", "acceptance-audit"):
        if key in t: consumers[key].append(str(f.relative_to(ROOT)))
for k, v in consumers.items(): p(f"  提及 {k}: {len(v)} 檔 → {v[:8]}")
# atom 內容是否引用 recall-miss / rescue
ref = 0
for f in atoms_md:
    t = f.read_text(encoding="utf-8", errors="ignore")
    if "recall-miss" in t or "rescue-log" in t or "rescue_log" in t: ref += 1
p("atom 內文提及 recall-miss/rescue-log 顆數:", ref)

# ---------- 7. always-load 大小 ----------
sec("7. always-load 大小")
def tok(txt):
    cjk = len(re.findall(r"[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef]", txt))
    other = len(txt) - cjk
    return cjk * 1.5 + other * 0.25, cjk, other
tot = 0
files = [ROOT / "IDENTITY.md", ROOT / "USER.md", ROOT / "memory/MEMORY.md", ROOT / "_local_catalog.md", ROOT / "CLAUDE.md"] + sorted((ROOT / "rules").glob("*.md"))
for f in files:
    if not f.exists(): p("  (缺)", f.name); continue
    t = f.read_text(encoding="utf-8", errors="ignore")
    est, cjk, oth = tok(t)
    tot += est
    p(f"  {str(f.relative_to(ROOT)):40s} bytes={len(t.encode('utf-8')):6d} chars={len(t):5d} cjk={cjk:5d} ~tok={est:6.0f}")
p(f"  合計 ~{tot:.0f} tok")
# auto-memory MEMORY.md
am = Path("C:/Users/holylight/.claude/projects/c--Users-holylight--claude/memory/MEMORY.md")
if am.exists():
    t = am.read_text(encoding="utf-8", errors="ignore"); p("  auto-memory MEMORY.md ~tok", round(tok(t)[0]))
