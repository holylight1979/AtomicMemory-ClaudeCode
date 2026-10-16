"""verify_aec_hud_inner_js.py — AEC HUD 內層瀏覽器 <script> 語法防呆。

aec-hud-html.js 的 render() 回傳整頁 HTML，內含一整塊瀏覽器端 <script>——但它是包在
外層 render() 的 template literal（backtick）裡的字串。因此內層 JS 字串/comment 中的反斜線
必須 \\ 跳脫，否則 render 時會被 outer JS 當跳脫序列吃掉（如 "\\n" 未跳脫 → 實際換行 →
破壞整塊 script → 頁面靜止、不 poll/beat/render）。

`node --check aec-hud-html.js` 只驗**外層模組**語法，抓不到內層字串裡的瀏覽器-JS 錯。
本測 render() → 抽 <script> → 對其單獨 node --check，補這個盲點。node 不在則 skip。
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent  # hooks/verify → hooks → .claude
HUD = ROOT / "tools" / "workflow-guardian-mcp" / "lib" / "aec-hud-html.js"

_NODE_CHECK = r"""
const h = require(process.argv[1]);
const html = h.render();
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.error("no <script> block found in render()"); process.exit(2); }
const os = require("os"), fs = require("fs"), path = require("path"), cp = require("child_process");
const f = path.join(os.tmpdir(), "hud_inner_verify.js");
fs.writeFileSync(f, m[1]);
const r = cp.spawnSync(process.execPath, ["--check", f], { encoding: "utf-8" });
if (r.status !== 0) { console.error(r.stderr || "check failed"); process.exit(1); }
console.log("ok");
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_render_module_valid():
    """外層模組本身可 require + render()（回傳非空 HTML）。"""
    js = "const h=require(process.argv[1]); const s=h.render(); process.exit(s && s.length>500?0:1);"
    res = subprocess.run(["node", "-e", js, str(HUD)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, f"render() failed:\n{res.stdout}\n{res.stderr}"


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_inner_browser_script_syntax():
    """render() 內層瀏覽器 <script> 必須語法合法（防未跳脫反斜線破壞整塊 script）。"""
    res = subprocess.run(["node", "-e", _NODE_CHECK, str(HUD)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert res.returncode == 0, f"inner browser script syntax error:\n{res.stdout}\n{res.stderr}"


_DELETABLE_CHECK = r"""
const h = require(process.argv[1]);
const html = h.render();
const s = html.match(/<script>([\s\S]*?)<\/script>/)[1];
// 抽 esc/escAttr/tempRow 三函式單獨 eval（tempRow 依賴前兩者）。
// 單行函式（esc/escAttr 那種 `function f(x) { ... }` 一行寫完）取該行；多行取到下一個行首 `}`。
function grab(name) {
  const i = s.indexOf("function " + name + "(");
  if (i < 0) { console.error(name + " not found in inner script"); process.exit(2); }
  const eol = s.indexOf("\n", i);
  const line = s.slice(i, eol < 0 ? s.length : eol);
  if (/\}\s*$/.test(line)) return line;
  const end = s.indexOf("\n}", i);
  return s.slice(i, end + 2);
}
const kindDef = s.match(/var KIND = \{[\s\S]*?\};/)[0];
eval(kindDef + "\nvar rowMsg = {};\n" + grab("esc") + "\n" + grab("escAttr") + "\n" + grab("tempRow"));
const sid = "abc12345-0000";
const base = { key: "k1", kind: "worktree", title: "wt/x", path: "C:\\Users\\u\\wt\\x", label: "乾淨", can_delete: true,
               confirm: null, note: "用完可刪", decision: null, decision_message: "" };
// 能刪：兩鈕都在（使用者決定權：即使 AI 說要留也不藏刪除鈕），白話類別、狀態、AI 備註都在
let row = tempRow(sid, base);
if (!/data-action="keep"/.test(row) || !/data-action="delete"/.test(row)) { console.error("both buttons expected:\n" + row); process.exit(1); }
if (!/data-key="k1"/.test(row) || !/工作樹/.test(row) || !/乾淨/.test(row) || !/AI 說：用完可刪/.test(row)) { console.error("row content missing:\n" + row); process.exit(1); }
if (/dec-done/.test(row)) { console.error("undecided row must not be dec-done"); process.exit(1); }
// 不能刪：刪除鈕換成停用的「不能刪」，滑鼠提示寫原因
row = tempRow(sid, Object.assign({}, base, { kind: "branch", can_delete: false, label: "工作樹正在用，先刪工作樹" }));
if (/data-action="delete"/.test(row) || !/disabled/.test(row) || !/不能刪/.test(row)) { console.error("undeletable row wrong:\n" + row); process.exit(1); }
// 選過保留：標示、仍可改按刪除
row = tempRow(sid, Object.assign({}, base, { decision: "keep" }));
if (!/你選了保留/.test(row) || !/dec-done/.test(row) || !/data-action="delete"/.test(row)) { console.error("kept row wrong:\n" + row); process.exit(1); }
// 要再確認的項目把確認句帶在按鈕上
row = tempRow(sid, Object.assign({}, base, { confirm: "有改動，確定？" }));
if (!/data-confirm="有改動，確定？"/.test(row)) { console.error("confirm text not carried:\n" + row); process.exit(1); }
// XSS 防護：名稱與路徑中的 < 與 " 必須被跳脫
row = tempRow(sid, Object.assign({}, base, { title: '<x>"y', path: '/tmp/<x>"y' }));
if (/<x>/.test(row) || /title="\/tmp\/<x>"y"/.test(row)) { console.error("escape failed:\n" + row); process.exit(1); }
// 刪除先 confirm()，要再確認的再問一次才帶 force
if (!/window\.confirm\("確定刪除？\\n"/.test(s) || !/force = true/.test(s)) { console.error("confirm guard missing in onDecClick"); process.exit(1); }
console.log("ok");
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_temp_panel_row():
    """「這個 session 留下的東西」tempRow：能刪就兩鈕都給（使用者決定權，不看 AI 備註）、不能刪換停用鈕寫原因、
    選過保留標示但可改按、確認句帶在按鈕上、名稱路徑跳脫、刪除經 confirm()。"""
    res = subprocess.run(
        ["node", "-e", _DELETABLE_CHECK, str(HUD)], capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    assert res.returncode == 0, f"tempRow mismatch:\n{res.stdout}\n{res.stderr}"


def test_hud_temp_panel_wiring():
    """面板由 /api/aec/tempfiles/<sid> 驅動（不從 (d) prose 猜）；(d) 區退回純文字顯示。"""
    src = HUD.read_text(encoding="utf-8")
    assert '"/api/aec/tempfiles/"' in src
    assert 'id="temp-slot"' in src
    assert "isDeletable" not in src and "sectionHtmlD" not in src
    assert 'sectionHtml("d",' in src
