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
