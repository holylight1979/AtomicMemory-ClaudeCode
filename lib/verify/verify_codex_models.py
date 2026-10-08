"""verify_codex_models.py：模型 slug 單一驗證點（lib/codex_models）＋ judge_backend.resolve_model_slug。

正例：精確比對命中（大小寫不計）；真 config 的 codex_companion.model 在真 cache 裡（live 兩檔唯讀）。
反例：`gpt-6-astra-900K` 這種帶後綴的名字回 None（不做前綴猜測）；cache 缺檔回 error 不回預設；
      config 沒填 model 回 error。
怎麼跑：python -X utf8 -m pytest -q lib/verify/verify_codex_models.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]  # lib/verify/ → repo 根（worktree 或 live）
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
COMPANION = ROOT / "tools" / "codex-companion"
if str(COMPANION) not in sys.path:
    sys.path.insert(0, str(COMPANION))

from lib import codex_models as cm  # noqa: E402
import judge_backend as jb  # noqa: E402

LIVE_CACHE = Path.home() / ".codex" / "models_cache.json"
LIVE_CONFIG = Path.home() / ".claude" / "workflow" / "config.json"


@pytest.fixture
def cache_file(tmp_path):
    p = tmp_path / "models_cache.json"
    p.write_text(json.dumps({
        "fetched_at": "2026-10-08", "models": [
            {"slug": "gpt-6-astra", "display_name": "GPT-6 Astra"},
            {"slug": "gpt-5.6-sol", "display_name": "GPT-5.6 Sol"},
            {"slug": "codex-auto-review"},
        ]}), encoding="utf-8", newline="\n")
    return p


def test_exact_match_only(cache_file):
    cache = cm.load_models_cache(cache_file)
    assert cm.list_slugs(cache) == ["gpt-6-astra", "gpt-5.6-sol", "codex-auto-review"]
    assert cm.resolve_slug("gpt-6-astra", cache) == "gpt-6-astra"
    assert cm.resolve_slug("GPT-6-ASTRA ", cache) == "gpt-6-astra", "大小寫與尾空白不影響，但回 cache 原字"
    # 反例：帶後綴／前綴相似的名字一律 None，不猜
    assert cm.resolve_slug("gpt-6-astra-900K", cache) is None
    assert cm.resolve_slug("gpt-6", cache) is None
    assert cm.resolve_slug("", cache) is None


def test_missing_cache_is_error_not_default(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(cm.CodexModelsError):
        cm.load_models_cache(missing)
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8", newline="\n")
    with pytest.raises(cm.CodexModelsError):
        cm.load_models_cache(bad)
    shape = tmp_path / "shape.json"
    shape.write_text(json.dumps({"models": "x"}), encoding="utf-8", newline="\n")
    with pytest.raises(cm.CodexModelsError):
        cm.load_models_cache(shape)
    # judge_backend 包裝：回 (None, 原因)，不得回預設 slug
    slug, err = jb.resolve_model_slug({"model": "gpt-6-astra"}, str(missing))
    assert slug is None and "models_cache 不存在" in err


def test_resolve_model_slug_wrapper(cache_file):
    assert jb.resolve_model_slug({"model": "gpt-5.6-sol"}, str(cache_file)) == ("gpt-5.6-sol", "")
    slug, err = jb.resolve_model_slug({"model": "gpt-6-astra-900K"}, str(cache_file))
    assert slug is None and "不在 models_cache" in err and "gpt-6-astra" in err, "錯誤要列可用 slug 供人改 config"
    slug, err = jb.resolve_model_slug({}, str(cache_file))
    assert slug is None and "未填 model" in err


def test_live_config_model_exists_in_live_cache():
    """真 config 的 codex_companion.model 必須在真 cache 裡（唯讀，不改任何檔）。"""
    if not LIVE_CACHE.is_file():
        pytest.skip(f"這台沒有 {LIVE_CACHE}（未裝 codex）")
    if not LIVE_CONFIG.is_file():
        pytest.skip(f"這台沒有 {LIVE_CONFIG}")
    config = json.loads(LIVE_CONFIG.read_text(encoding="utf-8"))
    cc = config.get("codex_companion") or {}
    slug, err = jb.resolve_model_slug(cc, str(LIVE_CACHE))
    assert slug == str(cc.get("model") or "").strip(), f"config.codex_companion.model 不在真 cache：{err}"
    so_model = str((config.get("second_opinion") or {}).get("model") or "gpt-6-astra")
    slug2, err2 = jb.resolve_model_slug({"model": so_model}, str(LIVE_CACHE))
    assert slug2 == so_model, f"second_opinion.model（或預設 gpt-6-astra）不在真 cache：{err2}"
