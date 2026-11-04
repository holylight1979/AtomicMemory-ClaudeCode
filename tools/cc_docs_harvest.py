"""Claude Code 官方文件收割器。

用法（在任何目錄跑，不需 cd）：
  python ~/.claude/tools/cc_docs_harvest.py fetch   # 抓 sitemap → 下載全部 zh-TW 頁 .md（＋changelog／claude-tag 英文）
                                                     # → 依 llms.txt 分類寫入 Docs/<夾>/<slug>.md 與 _manifest.json
  python ~/.claude/tools/cc_docs_harvest.py index   # 合併各夾 _keywords*.json → _INDEX.md／_KEYWORDS.md／_GLOSSARY.md／_keywords_all.json

fetch 只更新原文與 manifest；各夾 _SUMMARY.md／_keywords.json 是 LLM 導讀卡，原文有變要另派 agent 重寫
（任務說明見 Docs/_INDEX.md 開頭「更新方式」）。落點：~/.claude/_AIDocs/ClaudeCodeInternals/Docs/
"""
import datetime
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

D = os.path.join(os.path.expanduser('~'), '.claude', '_AIDocs', 'ClaudeCodeInternals', 'Docs')
BASE = 'https://code.claude.com'
EXTRA_EN = ['changelog', 'claude-tag']  # 沒有 zh-TW 版的頁
SECDIR = {
    'Getting started': '01-getting-started', 'Build with Claude Code': '02-build', 'Plugins': '03-plugins',
    'Administration': '04-administration', 'Configuration': '05-configuration', 'Reference': '06-reference',
    'Agent SDK': '07-agent-sdk', "What's New": '08-whats-new', 'Resources': '06-reference',
}
FOLDER_DESC = {
    '01-getting-started': '入門與核心概念、平台整合、Code review',
    '02-build': '擴充與並行：subagent／agent teams／workflows／MCP／skills／hooks 指南／疑難排解',
    '03-plugins': 'Plugins 與 Mods、marketplace、plugin evals',
    '04-administration': '企業管理：受管設定、部署、閘道、用量、安全',
    '05-configuration': '設定：settings、權限、沙箱、環境、模型、介面',
    '06-reference': '參考：hooks 全事件、CLI、工具、slash 指令、詞彙表',
    '07-agent-sdk': 'Agent SDK（TypeScript／Python）',
    '08-whats-new': '每週新功能＋版本時間線＋新名詞速查',
}


def _get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'cc-docs-harvest/1.0', 'Accept': 'text/markdown, text/plain, */*'})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.read().decode('utf-8', 'replace')


# ---------------------------------------------------------------- fetch
def cmd_fetch():
    sm = _get(f'{BASE}/sitemap.xml')
    llms = _get(f'{BASE}/docs/llms.txt')
    zh = sorted({m.group(1) for m in re.finditer(r'<loc>https://code\.claude\.com/docs/zh-TW/([^<]+)</loc>', sm)})
    print(len(zh), 'zh-TW pages in sitemap')
    work = tempfile.mkdtemp(prefix='ccdocs_')
    raw = {}

    def dl(job):
        lang, slug = job
        try:
            t = _get(f'{BASE}/docs/{lang}/{slug}.md')
            if t.lstrip().startswith('<!DOCTYPE'):
                return slug, lang, None, 'html'
            return slug, lang, t, 'ok'
        except Exception as e:  # noqa: BLE001
            return slug, lang, None, f'ERR {e}'

    jobs = [('zh-TW', p) for p in zh] + [('en', p) for p in EXTRA_EN]
    with ThreadPoolExecutor(8) as ex:
        for slug, lang, txt, st in ex.map(dl, jobs):
            if st == 'ok':
                raw[slug] = (lang, txt)
            else:
                print('  skip', slug, st, file=sys.stderr)
    _organize(sm, llms, raw)
    shutil.rmtree(work, ignore_errors=True)


def _organize(sm, llms, raw):
    lastmod = {}
    for m in re.finditer(r'<loc>https://code\.claude\.com/docs/(zh-TW|en)/([^<]+)</loc>\s*<lastmod>([^<]+)</lastmod>', sm):
        lastmod.setdefault((m.group(1), m.group(2)), m.group(3)[:10])
    # llms.txt：## = section，#### = subsection；每頁取第一次出現
    l2 = l3 = None
    pages = {}
    for line in llms.splitlines():
        if line.startswith('## '):
            l2, l3 = line[3:].strip(), None
        elif line.startswith('#### '):
            l3 = line[5:].strip()
        elif line.startswith('### ') and l3 is None:
            l3 = line[4:].strip()
        m = re.match(r'- \[([^\]]+)\]\(https://code\.claude\.com/docs/en/([^)]+)\.md\)(?:: (.*))?', line)
        if m and m.group(2) not in pages:
            pages[m.group(2)] = dict(title_en=m.group(1), desc_en=(m.group(3) or '').strip(), section=l2, subsection=l3)
    # 清掉舊原文（保留 _ 開頭的導讀卡與索引）
    for dd in [d for d in os.listdir(D) if re.match(r'\d\d-', d)] if os.path.exists(D) else []:
        for f in os.listdir(os.path.join(D, dd)):
            if not f.startswith('_') and not f.startswith('TIMELINE'):
                os.remove(os.path.join(D, dd, f))
    today = datetime.date.today().isoformat()
    manifest = []
    for slug in sorted(raw):
        lang, txt = raw[slug]
        info = pages.get(slug) or pages.get(slug + '/index') or dict(title_en=slug, desc_en='', section='Reference', subsection='Misc')
        txt = re.sub(r'\A(> ## Documentation Index\n(>.*\n)*\n?)', '', txt)
        m = re.search(r'^# (.+)$', txt, re.M)
        title_zh = m.group(1).strip() if m else info['title_en']
        d = SECDIR.get(info['section'] or 'Reference', '06-reference')
        rel = f'{d}/{slug.replace("/", "__")}.md'
        os.makedirs(os.path.join(D, d), exist_ok=True)
        url = f'{BASE}/docs/{lang}/{slug}'
        lm = lastmod.get((lang, slug), '')
        header = (f'<!-- harvested: {today} | source: {url} | lastmod: {lm} | section: {info["section"]} / {info["subsection"]} -->\n'
                  f'> 來源：{url}（官方 {lang}，lastmod {lm}）｜分類：{info["section"]} › {info["subsection"]}｜EN 摘要：{info["desc_en"]}\n\n')
        open(os.path.join(D, rel), 'w', encoding='utf-8', newline='\n').write(header + txt)
        manifest.append(dict(slug=slug, path=rel, lang=lang, title_zh=title_zh, title_en=info['title_en'], desc_en=info['desc_en'],
                             section=info['section'], subsection=info['subsection'], lastmod=lm,
                             bytes=len(txt.encode('utf-8')), url=url))
    json.dump(manifest, open(os.path.join(D, '_manifest.json'), 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
    print(len(manifest), 'pages written;', sum(m['bytes'] for m in manifest) // 1024, 'KB')


# ---------------------------------------------------------------- index
def _esc(s):
    return (s or '').replace('|', '\\|')


def _key(k):
    return (0 if re.match(r'[A-Za-z/`$\-_.]', k) else 1, k.lower())


def cmd_index():
    man = {m['slug']: m for m in json.load(open(f'{D}/_manifest.json', encoding='utf-8'))}
    rows = []
    for f in sorted(glob.glob(f'{D}/*/_keywords*.json')):
        folder = os.path.basename(os.path.dirname(f))
        sumf = os.path.basename(f).replace('_keywords', '_SUMMARY').replace('.json', '.md')
        for r in json.load(open(f, encoding='utf-8')):
            m = man.get(r['slug']) or man.get(r['slug'].replace('__', '/'))
            r.update(folder=folder, summary_file=sumf,
                     path=m['path'] if m else f"{folder}/{r['slug'].replace('/', '__')}.md",
                     lastmod=m['lastmod'] if m else '', url=m['url'] if m else '')
            rows.append(r)
    json.dump(rows, open(f'{D}/_keywords_all.json', 'w', encoding='utf-8', newline='\n'), ensure_ascii=False, indent=1)
    slug2path = {r['slug']: r['path'] for r in rows}
    byf = defaultdict(list)
    for r in rows:
        byf[r['folder']].append(r)
    today = datetime.date.today().isoformat()
    n_zh = sum(1 for m in man.values() if m['lang'] == 'zh-TW')
    n_en = len(man) - n_zh

    # 關鍵字反查、詞條
    inv, terms = defaultdict(set), defaultdict(list)
    for r in rows:
        for k in r['keywords']:
            inv[k.strip()].add(r['slug'])
        for t in r.get('terms') or []:
            if isinstance(t, dict) and t.get('term'):
                inv[t['term'].strip()].add(r['slug'])
                terms[t['term'].strip()].append((t.get('zh', '').strip(), r['slug']))

    out = [
        '# Claude Code 官方文件收割 — 高速閱讀索引\n',
        f'> 來源：https://code.claude.com/docs/zh-TW（sitemap 全部 {n_zh} 頁 zh-TW ＋ 英文 {n_en} 頁：{"、".join(EXTRA_EN)}）｜收割日 {today}｜原文照官方 markdown 落檔，每檔第 1～2 行為來源與 lastmod。',
        '> 怎麼用：**找功能** → [_KEYWORDS.md](_KEYWORDS.md) 關鍵字反查或下方各頁一句話；**看新名詞** → [_GLOSSARY.md](_GLOSSARY.md)（詞條白話）或 [TIMELINE](08-whats-new/TIMELINE-新功能與新名詞.md)（含首次出現版本）；**查某頁重點不想讀原文** → 該夾 `_SUMMARY.md` 導讀卡（一句話／何時讀／關鍵內容／新名詞／記憶系統接點）；**機器檢索** → `_keywords_all.json`。',
        '> 更新方式：`python ~/.claude/tools/cc_docs_harvest.py fetch` 重抓原文與 manifest → 派 agent 依 lastmod 變動的頁重寫該夾 `_SUMMARY.md`／`_keywords.json` → `… index` 重建本索引。導讀卡是 LLM 摘要，數字與鍵名以原文為準。',
        f'> 關鍵字反查（{len(inv)} 詞）與「記憶系統接點」彙整在 [_KEYWORDS.md](_KEYWORDS.md)，本檔只留總覽與各頁一句話。\n',
        '## 資料夾總覽\n', '| 夾 | 頁數 | 內容 | 導讀卡 |', '|---|---|---|---|',
    ]
    for fo in sorted(FOLDER_DESC):
        sums = sorted({r['summary_file'] for r in byf[fo]})
        extra = ' ＋ [TIMELINE](08-whats-new/TIMELINE-新功能與新名詞.md)' if fo == '08-whats-new' else ''
        out.append(f'| [{fo}/]({fo}/) | {len(byf[fo])} | {FOLDER_DESC[fo]} | ' + '、'.join(f'[{s}]({fo}/{s})' for s in sums) + extra + ' |')
    out.append('\n## 各頁一句話（依夾、依官方 subsection）\n')
    for fo in sorted(FOLDER_DESC):
        out += [f'### {fo}\n', '| 頁 | 一句話 | 何時讀 | 關鍵字 |', '|---|---|---|---|']
        for r in sorted(byf[fo], key=lambda r: (r.get('subsection') or '', r['slug'])):
            out.append(f"| [{r['title_zh']}]({r['path']}) `{r['slug']}` | {_esc(r['one_liner'])} | {_esc(r.get('when'))} | {_esc('、'.join(r['keywords'][:8]))} |")
        out.append('')
    open(f'{D}/_INDEX.md', 'w', encoding='utf-8', newline='\n').write('\n'.join(out).rstrip() + '\n')

    kw = ['# Claude Code 官方文件 — 關鍵字反查與記憶系統接點彙整\n',
          '> 由 `_keywords_all.json` 產生；總覽與各頁一句話在 [_INDEX.md](_INDEX.md)。\n',
          '## 記憶系統接點（各頁導讀卡「記憶系統接點」欄彙整，只列有內容的）\n']
    for fo in sorted(FOLDER_DESC):
        hs = [(r, h) for r in byf[fo] for h in (r.get('memory_hooks') or []) if h and h.strip() not in ('無', '無。')]
        if hs:
            kw.append(f'**{fo}**')
            kw += [f"- [{r['slug']}]({r['path']})：{h}" for r, h in hs]
            kw.append('')
    kw.append(f'## 關鍵字反查（{len(inv)} 詞 → 頁）\n')
    for k in sorted(inv, key=_key):
        pages = sorted(inv[k])
        kw.append(f'- **{_esc(k)}** → ' + '、'.join(f'[{s}]({slug2path[s]})' for s in pages[:12]) + (f' …(+{len(pages) - 12})' if len(pages) > 12 else ''))
    open(f'{D}/_KEYWORDS.md', 'w', encoding='utf-8', newline='\n').write('\n'.join(kw) + '\n')

    g = ['# Claude Code 新名詞／術語白話表（_GLOSSARY）\n',
         f'> 來源：各夾導讀卡「新名詞」欄彙整（{len(terms)} 詞），白話是 LLM 依官方原文改寫；官方詞彙表在 [glossary.md](06-reference/glossary.md)；首次出現版本見 [TIMELINE](08-whats-new/TIMELINE-新功能與新名詞.md) 第一節。\n',
         '| 詞 | 白話 | 出處頁 |', '|---|---|---|']
    for k in sorted(terms, key=_key):
        zh = max((z for z, _ in terms[k]), key=len)
        pages = sorted({s for _, s in terms[k]})
        g.append(f'| `{_esc(k)}` | {_esc(zh)} | ' + '、'.join(f'[{s}]({slug2path[s]})' for s in pages[:6]) + ' |')
    open(f'{D}/_GLOSSARY.md', 'w', encoding='utf-8', newline='\n').write('\n'.join(g) + '\n')
    print(f'pages {len(rows)} keywords {len(inv)} terms {len(terms)} → _INDEX.md / _KEYWORDS.md / _GLOSSARY.md / _keywords_all.json')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'index'
    if cmd in ('-h', '--help') or cmd not in ('fetch', 'index'):
        print(__doc__); sys.exit(0 if cmd in ('-h', '--help') else 2)
    {'fetch': cmd_fetch, 'index': cmd_index}[cmd]()
