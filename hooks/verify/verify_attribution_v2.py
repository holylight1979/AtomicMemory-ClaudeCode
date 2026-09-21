"""verify_attribution_v2.py — 判用 v2 契約（行動證據優先、否定／引用線索、路標未讀不算、去路徑噪音）。

標註集依據：tools/memory-eval/usage_labels.jsonl（v1 precision 0.35 → v2 0.67，recall 0.84；
python tools/memory-eval/eval_usage_v2.py 可重跑）。這裡只守規則本身，不守數字。
"""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent.parent
CLAUDE = HOOKS_DIR.parent
for p in (str(HOOKS_DIR), str(CLAUDE), str(CLAUDE / "lib")):
    if p not in sys.path:
        sys.path.insert(0, p)

import wg_atoms  # noqa: E402
from wg_atoms import detect_atom_use_v2  # noqa: E402

NAME = "codex-exec-手動派工三旗標-skip-git-repo-check-stdin關閉-unelevated"
ATOM = (
    f"# {NAME}\n\n- [臨] 從 Bash 手動派 codex exec 必帶三件：--skip-git-repo-check、</dev/null、"
    "-c 'windows.sandbox=\"unelevated\"'。缺任一件 reply 檔 0 byte 但 exit 0。\n"
    "## 行動\n- 模板：cd <dir> && codex exec --skip-git-repo-check -c 'windows.sandbox=\"unelevated\"' \"$(cat prompt.md)\" > reply.md 2> err.txt </dev/null\n"
)
ADOPTED_TURN = (
    "執行目標：派 Codex 審查。\nBash cd /c/Users/holylight/.claude && codex exec --skip-git-repo-check "
    "-s read-only -c 'windows.sandbox=\"unelevated\"' \"$(cat prompt.md)\" > reply.md 2> err.txt </dev/null; wc -c reply.md; tail err.txt"
)


def test_rescue_specific_token_is_strong_evidence():
    det = detect_atom_use_v2(ATOM, "我照著做了", atom_name=NAME, rescue_tokens=["skip-git-repo-check"])
    assert det["used"] and det["method"] == "rescue"


def test_rescue_generic_tokens_do_not_count():
    det = detect_atom_use_v2(ATOM, "整理一下", atom_name=NAME, rescue_tokens=["~/.claude", "/dev/null", "git push"])
    assert not det["used"]


def test_negation_near_atom_piece_rejects():
    turn = "codex-exec 三旗標那顆 atom 已過時：新版不用加 --skip-git-repo-check，不要用 atom 裡的指令。\nBash codex exec \"$(cat p.md)\""
    det = detect_atom_use_v2(ATOM, turn, atom_name=NAME, rescue_tokens=["skip-git-repo-check"])
    assert not det["used"] and det["method"] == "rejected"  # 否定優先於 rescue


def test_negation_far_from_atom_does_not_reject():
    turn = "這個 CSS 不要用 flex。\n" + ("x" * 300) + "\n" + ADOPTED_TURN
    det = detect_atom_use_v2(ATOM, turn, atom_name=NAME)
    assert det["used"]


def test_cited_only_is_not_use():
    turn = f"你問的那顆 atom「{NAME}」講的是：派 codex exec 要帶 --skip-git-repo-check 與 </dev/null，缺了 reply 會 0 byte。"
    det = detect_atom_use_v2(ATOM, turn, atom_name=NAME)
    assert not det["used"] and det["method"] == "cited"


def test_pointer_form_unread_never_used():
    det = detect_atom_use_v2(ATOM, ADOPTED_TURN, atom_name=NAME, form="skip")
    assert not det["used"] and det["method"] == "pointer_unread"


def test_pointer_form_with_read_can_be_used():
    turn = f"Read C:/Users/holylight/.claude/_AIDocs/_atoms/CC與原子記憶契約/{NAME}.md\n" + ADOPTED_TURN
    det = detect_atom_use_v2(ATOM, turn, atom_name=NAME, form="skip")
    assert det["used"] and det["method"] == "read+lexical"


def test_lexical_requires_enough_clean_shared_tokens():
    assert detect_atom_use_v2(ATOM, ADOPTED_TURN, atom_name=NAME)["used"]  # 多個專屬 token
    weak = "Bash cd /c/Users/holylight/.claude/tools && python -X utf8 verify/x.py  # 路徑噪音而已"
    det = detect_atom_use_v2(ATOM, weak, atom_name=NAME)
    assert not det["used"] and det["shared"] < 6


def test_path_noise_tokens_are_dropped():
    toks = wg_atoms._attr_clean_tokens({"holylight", "users", "server.js", "~/.claude", "a/b/c", "skip-git-repo-check", "unelevated"})
    assert toks == {"skip-git-repo-check", "unelevated"}


# ─── Codex #8 反例（2026-09-21 零容忍審查）────────────────────────────────────

NAME2 = "deploy-guard"
ATOM2 = ("# deploy-guard\n\n- [臨] 部署前用 deploy_safe_mode 檢查 rollout_window 與 canary_ratio；"
         "失敗就 abort_rollout 並記 deploy_incident_log。\n")
ADOPT2 = ("遵照 deploy-guard 的做法完成部署：deploy_safe_mode 檢查 rollout_window、canary_ratio，"
          "失敗走 abort_rollout 並寫 deploy_incident_log。")


def test_negation_targeting_other_object_does_not_reject():
    # 「不要用舊指令」的受詞不是 atom → 不是拒用
    det = detect_atom_use_v2(ATOM2, ADOPT2 + "不要用舊指令。", atom_name=NAME2)
    assert det["used"] and det["method"] == "lexical"


def test_unrelated_negation_in_same_paragraph_does_not_reject():
    det = detect_atom_use_v2(ATOM2, ADOPT2 + " 旁邊的 CSS 不用 flex。", atom_name=NAME2)
    assert det["used"]


def test_cite_then_adopt_counts_as_used():
    turn = "deploy-guard 講的是部署檢查。" + ADOPT2
    det = detect_atom_use_v2(ATOM2, turn, atom_name=NAME2)
    assert det["used"]


def test_cite_only_without_adoption_is_cited():
    turn = "deploy-guard 講的是部署檢查，先記著。\nBash npm test"
    det = detect_atom_use_v2(ATOM2, turn, atom_name=NAME2)
    assert not det["used"] and det["method"] == "cited"


def test_prose_mentioning_md_is_not_read_evidence():
    turn = f"我找到 {NAME2}.md，標題提到 deploy_safe_mode 與 abort_rollout。"
    det = detect_atom_use_v2(ATOM2, turn, atom_name=NAME2, form="skip")
    assert not det["used"] and det["method"] == "pointer_unread"


def test_rescue_does_not_bypass_pointer_unread():
    det = detect_atom_use_v2(ATOM2, "跑了部署", atom_name=NAME2, form="pointer_trim",
                             rescue_tokens=["deploy_safe_mode"])
    assert not det["used"] and det["method"] == "pointer_unread"


def test_rescue_path_tokens_not_specific():
    assert wg_atoms._rescue_specific(["memory/foo.md", r"C:\x\y\z.py", "~/.claude", "/a/b/c/d/e"]) == []
    assert wg_atoms._rescue_specific(["deploy_safe_mode"]) == ["deploy_safe_mode"]
