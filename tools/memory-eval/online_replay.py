"""online_replay.py — 用「線上同一條管線」重播一個 prompt，唯讀、零副作用。

做什麼：把 hooks/handlers 的 collect_matched_atoms（trigger → BM25 → Supersedes → RRF×activation）
→ assemble_injection（hot/cold／預算三態／Related 擴散／硬頂）→ _truncate_context_by_activation（最終裁切）
→ reconcile_injection_after_trim（送達結算）串起來跑，回三層結果：
  候選（排序後名單）／送達形式（每顆 ok|fallback|redundant|cold|skip|pointer_trim|dropped|dropped_trim）／輸出大小。
run.py --online 用它算指標；Phase 2 的排序實驗用 config 覆寫（例 vector_search.rrf_activation_gain=0）逐項比較。

怎麼保證不落盤：
  - PYTEST_CURRENT_TEST 環境變數 → wg_core.logs_dir() 把 guard log／atom-debug 導到暫存、injection-turns log 跳過；
  - _semantic_search 換成空結果（不打 vector 服務、不寫 vector-observation.log），--with-vector 才放行；
  - discover_all_project_memory_dirs 換成空（不掃其他專案、不依機器狀態漂移）；
  - _emit_usefulness_hints 換成 no-op（不改 sidecar 曝光）；
  - wg_atoms.time 換成凍結時鐘（activation／hot-cold 不隨跑的時刻漂移）；sidecar 只讀。
"""

from __future__ import annotations

import copy
import json
import os
import sys
import time
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CLAUDE_DIR = Path(__file__).resolve().parents[2]
for _p in (str(CLAUDE_DIR / "hooks"), str(CLAUDE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 必須在 import hooks 之前設好：logs_dir() 讀環境變數
os.environ.setdefault("PYTEST_CURRENT_TEST", "memory-eval-online")

import wg_atoms  # noqa: E402
import wg_core  # noqa: E402
from handlers import ups_inject, ups_search  # noqa: E402

CONFIG_PATH = CLAUDE_DIR / "workflow" / "config.json"

FULL_FORMS = {"ok", "fallback", "redundant"}
POINTER_FORMS = {"skip", "cold", "pointer_trim"}
DROPPED_FORMS = {"dropped", "dropped_trim"}


def load_config() -> Dict[str, Any]:
    """線上同一份 config；讀不到就空 dict（hooks 各函式都有預設）。"""
    try:
        if hasattr(wg_core, "load_config"):
            cfg = wg_core.load_config()
            if isinstance(cfg, dict):
                return copy.deepcopy(cfg)
    except Exception:
        pass
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def apply_overrides(config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """dotted key 覆寫：{"vector_search.rrf_activation_gain": 0} → config["vector_search"][...]=0。"""
    cfg = copy.deepcopy(config)
    for key, val in (overrides or {}).items():
        node = cfg
        parts = key.split(".")
        for part in parts[:-1]:
            node = node.setdefault(part, {})
            if not isinstance(node, dict):
                raise ValueError(f"override path collides with non-dict: {key}")
        node[parts[-1]] = val
    return cfg


def parse_override(text: str) -> Tuple[str, Any]:
    """'a.b=0.25' → ('a.b', 0.25)；值先試 JSON，失敗當字串。"""
    if "=" not in text:
        raise ValueError(f"--set 需要 key=value：{text}")
    key, raw = text.split("=", 1)
    try:
        val = json.loads(raw)
    except json.JSONDecodeError:
        val = raw
    return key.strip(), val


class Replayer:
    """凍結時鐘＋替身的線上管線重播器。同一個 Replayer 內多次 run() 共用快照。"""

    def __init__(
        self,
        memory_dir: Path,
        overrides: Optional[Dict[str, Any]] = None,
        with_vector: bool = False,
        frozen_time: Optional[float] = None,
    ) -> None:
        self.memory_dir = Path(memory_dir)
        self.entries = wg_atoms.parse_memory_index(self.memory_dir)
        self.scopes = {n: wg_atoms.scope_from_rel_path(p, "global") for n, p, _t in self.entries}
        cfg = apply_overrides(load_config(), overrides or {})
        cfg["atom_debug"] = False
        self.config = cfg
        self.with_vector = with_vector
        self.frozen_time = float(frozen_time if frozen_time is not None else time.time())
        self._patched: List[Tuple[Any, str, Any]] = []

    # ── 替身進出 ──
    def __enter__(self) -> "Replayer":
        real_time = time.time
        frozen = self.frozen_time
        fake_time = types.SimpleNamespace(
            time=lambda: frozen, monotonic=time.monotonic, sleep=time.sleep,
            strftime=time.strftime, localtime=time.localtime, perf_counter=time.perf_counter,
        )
        self._patch(wg_atoms, "time", fake_time)
        if not self.with_vector:
            self._patch(ups_search, "_semantic_search", lambda *a, **k: [])
        self._patch(ups_search, "discover_all_project_memory_dirs", lambda: [])
        self._patch(ups_inject, "_emit_usefulness_hints", lambda *a, **k: None)
        self._real_time = real_time
        return self

    def __exit__(self, *exc: Any) -> None:
        for obj, name, orig in reversed(self._patched):
            setattr(obj, name, orig)
        self._patched.clear()

    def _patch(self, obj: Any, name: str, value: Any) -> None:
        self._patched.append((obj, name, getattr(obj, name)))
        setattr(obj, name, value)

    # ── 重播 ──
    def fresh_state(self) -> Dict[str, Any]:
        return {
            "atom_index": {
                "global": [(n, p, list(t)) for n, p, t in self.entries],
                "project": [],
                "project_memory_dir": "",
                "project_root": "",
                "project_slug": "",
                "scopes": dict(self.scopes),
            },
            "injected_atoms": [],
            "turn_seq": 0,
            "session": {"cwd": str(CLAUDE_DIR), "id": "memory-eval"},
        }

    def run(self, prompt: str, state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """回 {"candidates", "sources", "delivered", "forms", "budget", "atom_tokens", "out_chars"}。
        傳入 state 可模擬同 session 連續 prompt（already_injected 抑制）；預設每題新 session。"""
        st = state if state is not None else self.fresh_state()
        cfg = self.config
        lines: List[str] = []
        (matched, atom_source, all_atoms, _sem, hints, _alias, _intent, caches) = \
            ups_search.collect_matched_atoms("memory-eval", st, cfg, prompt, prompt.lower(), lines)
        candidates = [e[0][0] for e in matched]
        already = list(st.get("injected_atoms") or [])
        inject_lines: List[str] = []
        st.pop("injection_log", None)  # 只看本題
        _newly, dirs = ups_inject.assemble_injection(
            "memory-eval", st, cfg, matched, all_atoms, already, atom_source, hints,
            inject_lines, caches=caches, prompt=prompt,
        )
        budget = wg_core.compute_token_budget(prompt)
        final = (wg_atoms._truncate_context_by_activation(list(inject_lines), budget, dirs, cfg)
                 if inject_lines else [])
        delivered = ups_inject.reconcile_injection_after_trim("memory-eval", st, cfg, final)
        forms = {r["name"]: (r.get("form_final") or r.get("form", "")) for r in (st.get("injection_log") or [])}
        atom_tokens = sum(wg_atoms._estimate_tokens(ln) for ln in final if ln.startswith("[Atom:"))
        return {
            "candidates": candidates,
            "sources": dict(atom_source),
            "delivered": list(delivered),
            "forms": forms,
            "budget": budget,
            "atom_tokens": atom_tokens,
            "out_chars": len("\n".join(final)),
        }


def classify_form(form: str) -> str:
    if form in FULL_FORMS:
        return "full"
    if form in POINTER_FORMS:
        return "pointer"
    if form in DROPPED_FORMS:
        return "dropped"
    return "absent"
