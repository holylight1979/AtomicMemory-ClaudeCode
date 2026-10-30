"""verify_project_smells.py：tools/project-smells.py 讀壞味道報告用的專案根與設定（commit 前病形檢查的報告列靠它們）。

正例：專案沒設 smells_report 就用公司根的；專案蓋公司、公司蓋 config.json 根層值；公司根之上的已建表專案根仍是專案；
      沒有部位表的專案照舊用最近的 overview-hub.json 根。
反例：未知設定鍵、型別錯 → SmellsError，跟導讀卡端同一套驗證。
怎麼跑：python -X utf8 -m pytest -q tools/verify/verify_project_smells.py
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "hooks" / "verify" / "fixtures" / "v6" / "smells"
SCRIPT = ROOT / "tools" / "project-smells.py"


def _load():
    spec = importlib.util.spec_from_file_location("project_smells", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["project_smells"] = mod
    spec.loader.exec_module(mod)
    return mod


ps = _load()


@pytest.fixture(autouse=True)
def _no_live_layers(monkeypatch):
    """預設不吃本機 config.json 與公司根（合併的兩個外部輸入）；要測合併層的案自己再 setattr。"""
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({}, None))


def _project(tmp_path, hub: dict | None, report: str | None):
    root = tmp_path / "proj"
    (root / ".claude").mkdir(parents=True)
    (root / "src" / "sched").mkdir(parents=True)
    if hub is not None:
        (root / ".claude" / "overview-hub.json").write_text(json.dumps(hub, ensure_ascii=False), encoding="utf-8", newline="\n")
    if report:
        shutil.copyfile(FIX / report, root / ".claude" / "smells.json")
    return root


def _hub():
    return json.loads((FIX / "hub.json").read_text(encoding="utf-8")) | {"smells_report": ".claude/smells.json"}


# ─── 005：設定走四層合併（與導讀卡同一份 lib/hub_config） ───────────────────────────

def test_company_root_smells_report_used_when_project_unset(tmp_path, monkeypatch):
    org = tmp_path / "org"
    (org / ".claude").mkdir(parents=True)
    rpt = tmp_path / "org-smells.json"
    shutil.copyfile(FIX / "fresh.json", rpt)
    (org / ".claude" / "overview-hub.json").write_text(
        json.dumps({"smells_report": str(rpt)}), encoding="utf-8")
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({}, org))
    root = _project(tmp_path, None, None)                                  # 專案沒有 overview-hub.json
    assert ps.load_hub_cfg(root)["smells_report"] == str(rpt)               # 正例：用公司的


def test_project_overrides_company_and_config_root_value_applies(tmp_path, monkeypatch):
    org = tmp_path / "org"
    (org / ".claude").mkdir(parents=True)
    (org / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": "org.json"}), encoding="utf-8")
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({"overview_hub": {"smells_report": "cfg.json"}}, None))
    bare = _project(tmp_path / "bare", None, None)
    assert ps.load_hub_cfg(bare)["smells_report"] == "cfg.json"            # config.json overview_hub 的根層值生效
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({"overview_hub": {"smells_report": "cfg.json"}}, org))
    assert ps.load_hub_cfg(bare)["smells_report"] == "org.json"            # 公司覆蓋 config.json 根層值
    root = _project(tmp_path, {"smells_report": "proj.json"}, None)
    cfg = ps.load_hub_cfg(root)
    assert cfg["smells_report"] == "proj.json"                              # 專案覆蓋公司
    assert set(cfg) == set(ps.DEFAULT_CFG)                                 # 只取本工具要的鍵


def test_009_6_company_hub_above_mapped_project_keeps_project_root(tmp_path, monkeypatch):
    """009-4.6：公司根有 overview-hub.json、專案有 .git 與部位表、專案不另設 hub → 根是專案（與導讀卡端同一套：最近的部位表根），
    公司設定照樣繼承，相對報告路徑以專案根為基準。"""
    company = tmp_path / "company"
    proj = company / "project"
    (company / ".claude").mkdir(parents=True)
    (company / ".claude" / "overview-hub.json").write_text(json.dumps({"smells_report": "reports/smells.json"}), encoding="utf-8")
    (proj / ".git").mkdir(parents=True)
    (proj / ".claude").mkdir()
    (proj / ".claude" / "overview-map.md").write_text("| 路徑前綴 | 範疇 | 導讀卡 | 狀態 |\n|---|---|---|---|\n"
                                                     "| `src\\` | 排程器 | `x` | 有 |\n", encoding="utf-8")
    (proj / "src" / "sched").mkdir(parents=True)
    (proj / "reports").mkdir()
    shutil.copyfile(FIX / "fresh.json", proj / "reports" / "smells.json")
    monkeypatch.setattr(ps, "_hub_inputs", lambda: ({}, company))
    assert ps.find_root(str(proj / "src")) == proj
    assert ps.load_hub_cfg(proj)["smells_report"] == "reports/smells.json"   # 公司設定照樣繼承


def test_009_6_project_without_map_keeps_old_root_rule(tmp_path):
    """沒有部位表的專案照舊：最近的 overview-hub.json 根。"""
    root = _project(tmp_path, _hub(), None)
    assert ps.find_root(str(root / "src" / "sched")) == root


def test_config_errors_fail_like_overview_hub(tmp_path):
    root = _project(tmp_path, {"smells_report": "x.json", "smells_bogus": 1}, None)
    with pytest.raises(ps.SmellsError) as ei:
        ps.load_hub_cfg(root)
    assert "未知的設定鍵「smells_bogus」" in str(ei.value)                    # 反例：未知鍵與導讀卡端同樣報錯
    root2 = _project(tmp_path / "b", {"smells_report": 5}, None)
    with pytest.raises(ps.SmellsError) as ei:
        ps.load_hub_cfg(root2)
    assert "smells_report 必須是字串" in str(ei.value)                       # 反例：型別錯
