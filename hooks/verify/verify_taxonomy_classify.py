"""verify_taxonomy_classify.py — Phase 1 單後端 batch 分類器（mock，零 LLM）。

驗 build_classify_prompt / parse / classify_batch 的正規化與防飄移：
closed-list slug 強制、is_real clamp、缺 id 補 unsure、解析失敗不爆。
"""
from __future__ import annotations

import sys
from pathlib import Path

VERIFY_DIR = Path(__file__).resolve().parent
CLAUDE = VERIFY_DIR.parent.parent
if str(CLAUDE) not in sys.path:
    sys.path.insert(0, str(CLAUDE))

from lib.taxonomy_classify import (  # noqa: E402
    build_classify_prompt, classify_batch, parse_classify_response,
)
from lib.game_taxonomy import TAXONOMY_CATCHALL, seed_slugs  # noqa: E402

VALID = seed_slugs()
DRAFTS = [
    {"id": "d1", "title": "build pipeline 崩", "excerpt": "CI 編譯失敗根因"},
    {"id": "d2", "title": "玩法數值", "excerpt": "掉落率公式調整"},
    {"id": "d3", "title": "閒聊", "excerpt": "今天天氣不錯"},
]


def _mock(payload: str):
    return lambda _prompt: payload


def test_prompt_has_seed_and_ids():
    p = build_classify_prompt(DRAFTS)
    assert "Engineering" in p and "GameBalance" in p   # seed 奠基
    assert "[d1]" in p and "[d3]" in p                  # 每條 id
    assert TAXONOMY_CATCHALL in p                        # catch-all 規則


def test_parse_valid_and_clamp():
    raw = ('前言... [{"id":"d1","slug":"Engineering","is_real":0.9,"sensitive":false,'
           '"reason":"CI根因"},{"id":"d2","slug":"GameBalance","is_real":1.5,'
           '"sensitive":false,"reason":"數值"}] 結尾')
    out = parse_classify_response(raw, VALID)
    assert [o["slug"] for o in out] == ["Engineering", "GameBalance"]
    assert out[1]["is_real"] == 1.0                      # 1.5 → clamp 1.0
    assert out[0]["slug_coerced"] is False


def test_invalid_slug_coerced_to_unsorted():
    raw = '[{"id":"d1","slug":"NotARealCat","is_real":0.5}]'
    out = parse_classify_response(raw, VALID)
    assert out[0]["slug"] == TAXONOMY_CATCHALL
    assert out[0]["slug_coerced"] is True


def test_is_real_garbage_defaults_zero():
    raw = '[{"id":"d1","slug":"Engineering","is_real":"高"}]'
    out = parse_classify_response(raw, VALID)
    assert out[0]["is_real"] == 0.0


def test_no_json_returns_empty():
    assert parse_classify_response("抱歉我無法分類", VALID) == []
    assert parse_classify_response("", VALID) == []


def test_classify_batch_fills_missing_id():
    # LLM 只回 d1、d2，漏 d3 → d3 補 _Unsorted + missing
    raw = ('[{"id":"d1","slug":"Engineering","is_real":0.9},'
           '{"id":"d2","slug":"GameBalance","is_real":0.8}]')
    out = classify_batch(DRAFTS, _mock(raw))
    assert [o["id"] for o in out] == ["d1", "d2", "d3"]   # 順序對齊輸入
    assert out[2]["slug"] == TAXONOMY_CATCHALL
    assert out[2].get("missing") is True
    assert out[2]["is_real"] == 0.0


def test_classify_batch_total_garbage_all_unsorted():
    out = classify_batch(DRAFTS, _mock("LLM 壞掉了"))
    assert all(o["slug"] == TAXONOMY_CATCHALL for o in out)
    assert all(o.get("missing") for o in out)


def test_empty_drafts():
    assert classify_batch([], _mock("[]")) == []
