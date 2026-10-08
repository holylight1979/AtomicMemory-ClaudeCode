"""codex_models.py：Codex 模型 slug 的唯一驗證點（精確比對 `~/.codex/models_cache.json`）。

為什麼有這支：config.json 與卡片各寫各的模型名（`gpt-5.6-sol` vs `gpt-6-astra`），沒人驗；
帶錯名（例 `gpt-6-astra-900K`）的症狀是 -o 檔不存在、錯因只在 stderr 尾。這裡把「名字在不在 cache 裡」
變成一個函式，codex-companion 與 second-opinion 都走同一條。

怎麼用：
    cache = load_models_cache()            # 缺檔／壞檔 → CodexModelsError，不回預設
    slug  = resolve_slug("gpt-6-astra", cache)   # 精確比對；查不到回 None，不做前綴猜測
    list_slugs(cache)                       # 全部 slug（依 cache 原序）
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_CACHE_PATH = Path.home() / ".codex" / "models_cache.json"


class CodexModelsError(Exception):
    """models_cache.json 缺檔、不可讀、或形狀不對。"""


def load_models_cache(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path is not None else DEFAULT_CACHE_PATH
    if not p.is_file():
        raise CodexModelsError(f"models_cache 不存在：{p}（先跑一次 codex 讓它產生，或檢查 ~/.codex）")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise CodexModelsError(f"models_cache 讀取失敗：{p}：{e}") from e
    models = data.get("models") if isinstance(data, dict) else data
    if not isinstance(models, list):
        raise CodexModelsError(f"models_cache 形狀不對（找不到 models 陣列）：{p}")
    return {"path": str(p), "models": models}


def list_slugs(cache: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for m in cache.get("models") or []:
        slug = m.get("slug") if isinstance(m, dict) else m
        if isinstance(slug, str) and slug.strip():
            out.append(slug.strip())
    return out


def resolve_slug(name: str, cache: Dict[str, Any]) -> Optional[str]:
    """精確比對（大小寫與前後空白除外）；查不到回 None。不做前綴／模糊比對，寧可查不到也不猜。"""
    want = (name or "").strip().lower()
    if not want:
        return None
    for slug in list_slugs(cache):
        if slug.lower() == want:
            return slug
    return None
