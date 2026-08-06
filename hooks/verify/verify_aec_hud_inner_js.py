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
    res = subprocess.run(["node", "-e", js, str(HUD)], capture_output=True, text=True)
    assert res.returncode == 0, f"render() failed:\n{res.stdout}\n{res.stderr}"


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_inner_browser_script_syntax():
    """render() 內層瀏覽器 <script> 必須語法合法（防未跳脫反斜線破壞整塊 script）。"""
    res = subprocess.run(["node", "-e", _NODE_CHECK, str(HUD)], capture_output=True, text=True)
    assert res.returncode == 0, f"inner browser script syntax error:\n{res.stdout}\n{res.stderr}"


_DELETABLE_CHECK = r"""
const h = require(process.argv[1]);
const html = h.render();
const s = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const fn = s.match(/function isDeletable\(item\) \{[\s\S]*?\n\}/);
if (!fn) { console.error("isDeletable not found in inner script"); process.exit(2); }
const isDeletable = eval("(" + fn[0].replace(/^function isDeletable/, "function") + ")");
const cases = [
  ["workflow/acceptance-audit.jsonl — 非暫存，影子期數據檔（gitignored），保留", false],
  ["memory/_staging/x.py — 屬任務交付物，不刪", false],
  ["%TEMP%/acceptance-backtest-specs/（回測規格暫存檔 20 份）— 回測結束後刪", true],
  ["背景任務輸出 tasks/bco06fu6h.output — session 暫存自清", true],
  ["C:\\Users\\u\\AppData\\Local\\Temp\\foo.txt — 暫存檔", true],
  ["純 prose 說明行，沒有任何路徑可定位", false],
  ["無", false],
];
for (const [item, want] of cases) {
  const got = isDeletable(item);
  if (got !== want) { console.error(`isDeletable(${JSON.stringify(item)}) = ${got}, want ${want}`); process.exit(1); }
}
console.log("ok");
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not available")
def test_hud_delete_button_heuristic():
    """isDeletable：可定位路徑且未標「保留/不刪/非暫存」才給刪除鈕；prose/保留行不給。"""
    res = subprocess.run(
        ["node", "-e", _DELETABLE_CHECK, str(HUD)], capture_output=True, text=True
    )
    assert res.returncode == 0, f"isDeletable heuristic mismatch:\n{res.stdout}\n{res.stderr}"


def test_hud_delete_button_gated_by_heuristic():
    """decRow 渲染：刪除鈕必在 isDeletable 條件內，保留鈕無條件。"""
    src = HUD.read_text(encoding="utf-8")
    assert "if (isDeletable(item)) {" in src
    idx_keep = src.index('data-action="keep"')
    idx_gate = src.index("if (isDeletable(item))")
    idx_del = src.index('data-action="delete"')
    assert idx_keep < idx_gate < idx_del
