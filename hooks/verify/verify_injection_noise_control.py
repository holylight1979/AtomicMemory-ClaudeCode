"""verify_injection_noise_control.py — 注入端噪音控制三項迴歸。

1. 寧缺勿截：最終 budget 裁切的 truncated 指標行有上限（injection.truncated_pointer_max，
   預設 3），超出者整塊不注入；犧牲順序按 activation 低→高，留指標的是被犧牲者中
   activation 較高的；尾行 budget 標記附 trim 統計（可觀測性）。
2. 截斷行不顯示 activation 數值（ACT-R log 尺度天然跨零，負值≠不相關，顯示易誤讀；
   不做 activation<=0 注入過濾——相關性由 trigger/BM25/vector 入場閘把關）。
3. same_file_3x 覆轍信號白名單：索引/編年類高頻正常改動檔（README/_CHANGELOG/
   DocIndex-*/各種 _INDEX/acceptance-*）不產生、不採計信號；真實 rut（如 code 檔）照報。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HOOKS_DIR))

import wg_atoms  # noqa: E402
import wg_evasion  # noqa: E402
from wg_core import is_rut_whitelisted, RUT_FILE_WHITELIST_DEFAULT  # noqa: E402

_CJK_400 = "測" * 400  # _estimate_tokens ≈ 600 tokens


def _write_access(d: Path, name: str, ts_list):
    (d / f"{name}.access.json").write_text(
        json.dumps({"timestamps": ts_list}), encoding="utf-8")


# ─── 1. 寧缺勿截：pointer 上限 + 超出者整塊移除 ──────────────────────


def test_truncated_pointer_cap_and_drop(tmp_path):
    """6 顆大 atom 全數超支：只留 truncated_pointer_max 顆指標行，其餘整塊消失；
    留指標的是被犧牲者中 activation 較高的（越舊 access → activation 越低 → 先整塊丟）。"""
    d = tmp_path / "m"
    d.mkdir()
    names = [f"a{i}" for i in range(6)]
    for i, n in enumerate(names):
        # a0 最舊（activation 最低）→ a5 最新（最高）
        _write_access(d, n, [time.time() - (60 - i * 10) * 86400])
    lines = [f"[Atom:{n}]\n{_CJK_400}" for n in names]
    src = {n: d for n in names}

    out = wg_atoms._truncate_context_by_activation(
        list(lines), limit=100, source_dirs=src,
        config={"injection": {"truncated_pointer_max": 2}},
    )
    joined = "\n".join(out)
    pointer_lines = [l for l in out if "(truncated)" in l]
    assert len(pointer_lines) == 2, f"指標行應恰為上限 2，實得 {len(pointer_lines)}"
    # activation 最高的 a4/a5 留指標；最低的 a0..a3 整塊消失（連指標都沒有）
    assert "[Atom:a5] (truncated)" in joined and "[Atom:a4] (truncated)" in joined
    for gone in ("a0", "a1", "a2", "a3"):
        assert f"[Atom:{gone}]" not in joined, f"{gone} 應整塊不注入"
    # 尾行附 trim 統計（降級不得無聲）
    assert "trim: 2 pointer, 4 dropped" in out[-1]


def test_no_trim_keeps_plain_budget_tail(tmp_path):
    """未超支：不裁切、尾行維持原格式（無 trim 統計）。"""
    out = wg_atoms._truncate_context_by_activation(["[Atom:x]\nshort"], limit=10_000)
    assert "trim:" not in out[-1]
    assert "[Context budget:" in out[-1]


# ─── 2. 截斷行不顯示 activation（負值易誤讀為負相關性） ──────────────


def test_pointer_line_has_no_activation_display(tmp_path):
    d = tmp_path / "m"
    d.mkdir()
    _write_access(d, "neg", [time.time() - 30 * 86400])
    assert wg_atoms.compute_activation("neg", d) < 0  # 前提：確為負 activation
    out = wg_atoms._truncate_context_by_activation(
        [f"[Atom:neg]\n{_CJK_400}"], limit=50, source_dirs={"neg": d},
    )
    joined = "\n".join(out)
    assert "(truncated)" in joined, "負 activation 者仍可注入（指標形式），不得被相關性誤殺"
    assert "activation=" not in joined


# ─── 3. same_file_3x 白名單 ──────────────────────────────────────────


def test_rut_whitelist_defaults():
    for hit in ("README.md", "readme.txt", "_CHANGELOG.md", "DocIndex-System.md",
                "_INDEX.md", "MEMORY.md", "_ATOM_INDEX.md", "_atom_index.json",
                "acceptance-atom-locate-index-sot.md"):
        assert is_rut_whitelisted(hit), f"{hit} 應在預設白名單"
    for miss in ("MainForm.cs", "wg_atoms.py", "server.js"):
        assert not is_rut_whitelisted(miss), f"{miss} 不該被白名單吃掉"


def test_rut_whitelist_config_override():
    cfg = {"self_iteration": {"rut_file_whitelist": ["only-this*"]}}
    assert is_rut_whitelisted("only-this-file.md", cfg)
    assert not is_rut_whitelisted("README.md", cfg), "config 覆寫後預設清單不再生效"


def test_detect_rut_patterns_filters_whitelisted(tmp_path, monkeypatch):
    """掃描端：既存 episodic 舊信號中的白名單檔不採計，真實 rut 照報（降噪非關警報）。"""
    ep = tmp_path / "memory" / "episodic"
    ep.mkdir(parents=True)
    for i in range(2):
        (ep / f"episodic-2026080{i + 1}-t.md").write_text(
            "# t\n- [臨] 覆轍信號: same_file_3x:README.md, same_file_3x:MainForm.cs\n",
            encoding="utf-8",
        )
    monkeypatch.setattr(wg_evasion, "MEMORY_DIR", tmp_path / "memory")
    monkeypatch.setattr(wg_evasion, "get_project_memory_dir", lambda _cwd: None)

    msg = wg_evasion._detect_rut_patterns({"session": {"cwd": ""}}, {})
    assert msg is not None and "MainForm.cs" in msg, "真實 rut 信號不得被降噪吃掉"
    assert "README.md" not in msg, "白名單檔不該進覆轍警報"


def test_rut_whitelist_single_source():
    """預設清單單一來源健檢：at least 覆蓋使用者實測誤報的四類檔。"""
    joined = ",".join(RUT_FILE_WHITELIST_DEFAULT)
    for frag in ("readme", "_changelog", "docindex-", "_index"):
        assert frag in joined
