"""atom_access.py — Atom 遙測旁路檔（access.json）讀寫單一通道

設計目標：
  - atom 的 read_hits / last_used / confirmations / last_promoted_at / first_seen
    全部寫到 <atom>.access.json，不再寫 atom .md 檔頭
  - 取代 hooks/workflow-guardian.py:1340-1375 的 raw write_text（funnel 違規修補）
  - 取代 lib/atom_io.py:update_atom_field 對 Confirmations 計數的呼叫

Schema v3（<atom>.access.json）:
  {
    "schema": "atom-access-v3",
    "read_hits": int,             # 純曝光計數（注入次數）— v3 後不再單獨晉升
    "last_used": "YYYY-MM-DD",
    "confirmations": int,         # 跨 session 萃取命中（真實確認，主軌）
    "useful_hits": number,        # α — Beta-Bernoulli「被用且成功」累積（預設 1，Laplace prior）
    "used_fail": number,          # β — Beta-Bernoulli「被用但失敗」累積（預設 1）
    "last_promoted_at": "YYYY-MM-DD" 或 None,
    "first_seen": "YYYY-MM-DD",
    "timestamps": [float epoch ...最多 50 筆],
    "confirmation_events": [{ts, ...} ...]
  }

效用閉環（Phase 2, #2）：注入→使用→結果以 (α,β) 校準信心，取代純曝光（read_hits）。
  - record_usefulness：本 turn 某 atom 被判 used 且 outcome 決定性 → success α++ / fail β++；
    unused 或 outcome=unknown 一律 no-op（防雜訊污染，關鍵守則）。
  - Wilson 下界（wilson_lower_bound / usefulness_stats）：升 ≥0.6、降候選 ≤0.35，皆需 n≥3。
  - decay_usefulness（SessionEnd 慢衰減）：α←1+λ(α−1); β←1+λ(β−1)，λ≈0.97，重啟冷啟動。
  α/β 只存兩個 scalar（不寫進 .md），零索引膨脹；succ=α−1, fail=β−1, n=succ+fail（減去 prior）。

舊 schema 偵測：confirmations 是陣列 → migrate (陣列→confirmation_events)；
  v2→v3 冪等 migration：缺 useful_hits/used_fail → 補 1（可重入，不壞既有計數）。

CLI 入口（給 tools/workflow-guardian-mcp/server.js 透過子程序呼叫）：
  python -m lib.atom_access read <path>
  python -m lib.atom_access init <path> --first-seen YYYY-MM-DD --source mcp
  python -m lib.atom_access increment-read-hits <path> --source hook:atom-inject
  python -m lib.atom_access increment-confirmation <path> --source hook:episodic-confirm [--event-json '{...}']
  python -m lib.atom_access record-usefulness <path> --used true --success true|false|unknown --source hook:usefulness
  python -m lib.atom_access decay-usefulness <path> --lambda 0.97 --source hook:atom-decay
  python -m lib.atom_access record-promotion <path> --target [固] --source mcp
  python -m lib.atom_access set <path> --field NAME --value VAL --source SRC
"""

from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# 重用 atom_io 的 audit infra（單一稽核日誌）
from .atom_io import (
    AUDIT_LOG, _gen_audit_id, _audit_log, _atomic_write,
    GLOBAL_MEMORY_DIR,
)

# 本模組合法 source 名單 — atom_io.VALID_SOURCES 的超集（保證任何 atom_io 寫入端皆可呼叫）
ACCESS_VALID_SOURCES = frozenset({
    "mcp",
    "hook:atom-inject",          # workflow-guardian.py atom 注入時 increment_read_hits
    "hook:episodic",             # episodic atom 建立時 init_access
    "hook:episodic-confirm",     # cross-session confirmation
    "hook:usefulness",           # Phase 2: stop.py 注入→使用→結果 α/β 更新
    "hook:atom-decay",           # Phase 2: SessionEnd _self_iterate_atoms 慢衰減
    "hook:user-extract",
    "hook:extract-worker",
    "tool:atom-move",
    "tool:changelog-roll",
    "tool:memory-audit",         # restore_atom 計數歸零
    "tool:migrate",              # 一次性遷移
    "tool:atom-health-audit",    # Phase B 健康診斷
    "tool:sync-atom-index",
    "tool:sync-memory-index",
    "tool:undo",
    "test",
})

SCHEMA_KEY = "schema"
SCHEMA_VERSION = "atom-access-v3"
TIMESTAMPS_MAX = 50

# Beta-Bernoulli Laplace prior：useful_hits=α、used_fail=β 預設皆 1（succ=α−1, fail=β−1）。
USEFULNESS_PRIOR = 1
# Wilson 下界預設參數（py↔js 鏡像，SYNC: tools/workflow-guardian-mcp/server.js usefulnessStats）。
WILSON_Z_DEFAULT = 1.96
PROMOTE_LB_DEFAULT = 0.6
DEMOTE_LB_DEFAULT = 0.35
USEFULNESS_MIN_N_DEFAULT = 3
DECAY_LAMBDA_DEFAULT = 0.97


# ─── 路徑 / 基本 IO ──────────────────────────────────────────────────────────


def _access_path(atom_path: Path) -> Path:
    """<atom>.md → <atom>.access.json（同層）"""
    return atom_path.with_suffix(".access.json")


def _today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _audit(op: str, source: str, atom_path: Path, **extra: Any) -> str:
    audit_id = _gen_audit_id()
    entry = {
        "audit_id": audit_id,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "op": op,
        "source": source,
        "path": str(atom_path),
    }
    entry.update(extra)
    _audit_log(entry)
    return audit_id


def _validate_source(source: str) -> None:
    if source not in ACCESS_VALID_SOURCES:
        raise ValueError(f"invalid source for atom_access: {source}")


# ─── Schema 偵測與升級 ───────────────────────────────────────────────────────


def _normalize(data: Dict[str, Any]) -> tuple[Dict[str, Any], bool]:
    """把舊 schema 的資料規整成 v3；回傳 (新 dict, 是否被改寫)。

    舊格式特徵：
      (a) {"timestamps":[], "confirmations":[]}（confirmations 是陣列）
      (b) 缺 schema key
      (c) v2 → v3：缺 useful_hits/used_fail（Phase 2 效用欄位）

    v2→v3 migration 冪等可重入：useful_hits/used_fail 僅在缺漏時補 prior（1），
    既有 (α,β) 計數一律保留，不會被重複跑壞。
    """
    upgraded = False

    # (a) confirmations 是陣列 → 搬到 confirmation_events
    if isinstance(data.get("confirmations"), list):
        events = data["confirmations"]
        data["confirmation_events"] = events
        data["confirmations"] = len(events)
        upgraded = True

    # 預設值補齊（含 v3 效用欄位 useful_hits=α / used_fail=β，預設 prior=1）
    defaults = {
        SCHEMA_KEY: SCHEMA_VERSION,
        "read_hits": 0,
        "last_used": None,
        "confirmations": 0,
        "useful_hits": USEFULNESS_PRIOR,
        "used_fail": USEFULNESS_PRIOR,
        "last_promoted_at": None,
        "first_seen": None,
        "timestamps": [],
        "confirmation_events": [],
    }
    for k, v in defaults.items():
        if k not in data:
            data[k] = v
            # 補入 schema / 效用欄位皆視為 migration（觸發寫回以落地 v3）
            if k in (SCHEMA_KEY, "useful_hits", "used_fail"):
                upgraded = True

    if data.get(SCHEMA_KEY) != SCHEMA_VERSION:
        data[SCHEMA_KEY] = SCHEMA_VERSION
        upgraded = True

    return data, upgraded


def _read_raw(access_path: Path) -> Optional[Dict[str, Any]]:
    if not access_path.exists():
        return None
    try:
        return json.loads(access_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_raw(access_path: Path, data: Dict[str, Any]) -> bool:
    """寫 access JSON；Win 平台 cross-process 競態時重試 3 次（每次 50ms backoff）。

    回傳 True=成功；False=三次都失敗（呼叫端決定要不要 audit 為 dropped）。

    使用唯一 tmp 後綴（PID + thread id）避免多執行緒共用同一 tmp file 時
    `Path.write_text("w")` truncate 競態（會導致 access.json 落入半空檔）。
    """
    import os as _os
    import threading as _threading
    payload = json.dumps(data, ensure_ascii=False)
    access_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        # 每次重試也用新的 tmp，避免上次失敗的 tmp 殘留干擾
        tmp = access_path.with_suffix(
            f"{access_path.suffix}.tmp.{_os.getpid()}.{_threading.get_ident()}.{attempt}"
        )
        try:
            tmp.write_text(payload, encoding="utf-8")
            _os.replace(str(tmp), str(access_path))
            return True
        except OSError:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            if attempt == 2:
                return False
            time.sleep(0.05)
    return False


# ─── 公開 API ────────────────────────────────────────────────────────────────


def read_access(atom_path: Path) -> Dict[str, Any]:
    """讀 atom 的 access 資料。

    一律回傳正規化後的 dict（含所有 v2 欄位 default），即使檔不存在或損毀。
    呼叫端如要區分「檔不存在 vs 檔存在但未累積」→ 看 first_seen 是 None。
    若是舊 schema → 正規化後**不寫回**（避免讀操作產生寫副作用）；
    寫回交給 increment / set / migration 觸發。
    """
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path)
    if raw is None:
        # 檔不存在或 JSON 損毀 → 仍回 v2 defaults（callers 不需 KeyError 處理）
        normalized, _ = _normalize({})
        return normalized
    normalized, _upgraded = _normalize(raw)
    return normalized


def init_access(atom_path: Path, *, first_seen: Optional[str] = None, source: str) -> str:
    """為 atom 建立新的 access 檔（覆蓋既存）。

    用於：MCP atom_write create / hook:episodic atom 建立時。
    若已存在 → 不覆蓋既有計數，只補齊缺欄並保留現值。
    """
    _validate_source(source)
    access_path = _access_path(atom_path)
    today = _today_str()
    raw = _read_raw(access_path) or {}
    raw, _ = _normalize(raw)
    if not raw.get("first_seen"):
        raw["first_seen"] = first_seen or today
    if not raw.get("last_used"):
        raw["last_used"] = today
    _write_raw(access_path, raw)
    return _audit("access_init", source, atom_path, first_seen=raw["first_seen"])


def increment_read_hits(atom_path: Path, *, source: str) -> int:
    """read_hits++、刷 last_used=today、append timestamp（最多 50 筆）。

    對拍 hooks/workflow-guardian.py:1350-1375 行為（取代直接 .write_text）。
    """
    _validate_source(source)
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path) or {}
    raw, _ = _normalize(raw)
    raw["read_hits"] = int(raw.get("read_hits") or 0) + 1
    raw["last_used"] = _today_str()
    if not raw.get("first_seen"):
        raw["first_seen"] = raw["last_used"]
    timestamps = list(raw.get("timestamps") or [])
    timestamps.append(time.time())
    raw["timestamps"] = timestamps[-TIMESTAMPS_MAX:]
    if not _write_raw(access_path, raw):
        _audit("access_increment_dropped", source, atom_path,
               field="read_hits", reason="write_contention")
        return int(raw["read_hits"]) - 1  # 視同未生效
    _audit("access_increment", source, atom_path,
           field="read_hits", new_count=raw["read_hits"])
    return raw["read_hits"]


def increment_confirmation(
    atom_path: Path, *, event: Optional[Dict[str, Any]] = None, source: str,
) -> int:
    """confirmations++、append event 到 confirmation_events、刷 last_used。

    對拍 hooks/wg_episodic.py:370-373 cross-session confirmation 行為。
    """
    _validate_source(source)
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path) or {}
    raw, _ = _normalize(raw)
    raw["confirmations"] = int(raw.get("confirmations") or 0) + 1
    raw["last_used"] = _today_str()
    if not raw.get("first_seen"):
        raw["first_seen"] = raw["last_used"]
    events: List[Dict[str, Any]] = list(raw.get("confirmation_events") or [])
    if event is None:
        event = {}
    if "ts" not in event:
        event["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    events.append(event)
    raw["confirmation_events"] = events
    if not _write_raw(access_path, raw):
        _audit("access_increment_dropped", source, atom_path,
               field="confirmations", reason="write_contention")
        return int(raw["confirmations"]) - 1
    _audit("access_increment", source, atom_path,
           field="confirmations", new_count=raw["confirmations"])
    return raw["confirmations"]


def record_promotion(atom_path: Path, *, target_confidence: str, source: str) -> str:
    """寫 last_promoted_at = today、刷 last_used。

    對拍 tools/workflow-guardian-mcp/server.js:1501 atom_promote 行為。
    """
    _validate_source(source)
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path) or {}
    raw, _ = _normalize(raw)
    today = _today_str()
    raw["last_promoted_at"] = today
    raw["last_used"] = today
    if not raw.get("first_seen"):
        raw["first_seen"] = today
    _write_raw(access_path, raw)
    return _audit("access_promote", source, atom_path,
                  target_confidence=target_confidence)


def write_access_field(
    atom_path: Path, *, field: str, value: Any, source: str,
) -> str:
    """通用單欄位寫入（給 tool:memory-audit restore 等少見場景）。"""
    _validate_source(source)
    allowed = {
        "read_hits", "last_used", "confirmations", "last_promoted_at",
        "first_seen",
    }
    if field not in allowed:
        raise ValueError(f"field not allowed via write_access_field: {field}")
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path) or {}
    raw, _ = _normalize(raw)
    raw[field] = value
    _write_raw(access_path, raw)
    return _audit("access_field", source, atom_path, field=field, value=str(value))


# ─── 效用閉環 (α,β)：Phase 2 (#2) ────────────────────────────────────────────


def record_usefulness(
    atom_path: Path, *, used: bool, success: Optional[bool], source: str,
) -> tuple[float, float]:
    """記錄一次注入→使用→結果的歸因，更新 (useful_hits=α, used_fail=β)。

    參數三值語意（防雜訊污染的關鍵守則）：
      - used=False           → no-op（atom 未被本 turn 使用）
      - used=True, success=None → no-op（outcome=unknown，無決定性訊號）
      - used=True, success=True → α += 1（被用且成功）
      - used=True, success=False → β += 1（被用但失敗）

    回傳更新後 (α, β)。no-op 時回現值、不寫檔。走 _write_raw funnel + audit。
    """
    _validate_source(source)
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path) or {}
    raw, _ = _normalize(raw)
    alpha = float(raw.get("useful_hits") or USEFULNESS_PRIOR)
    beta = float(raw.get("used_fail") or USEFULNESS_PRIOR)

    if not used or success is None:
        # no-op：不動 (α,β)，僅留 audit 供觀測（不寫檔）
        _audit("usefulness_noop", source, atom_path,
               used=bool(used), success=("unknown" if success is None else bool(success)))
        return alpha, beta

    if success:
        alpha += 1
        field = "useful_hits"
    else:
        beta += 1
        field = "used_fail"
    raw["useful_hits"] = _coerce_num(alpha)
    raw["used_fail"] = _coerce_num(beta)
    raw["last_used"] = _today_str()
    if not raw.get("first_seen"):
        raw["first_seen"] = raw["last_used"]
    if not _write_raw(access_path, raw):
        _audit("usefulness_dropped", source, atom_path,
               field=field, reason="write_contention")
        return alpha - (1 if success else 0), beta - (0 if success else 1)
    _audit("usefulness_update", source, atom_path,
           field=field, alpha=raw["useful_hits"], beta=raw["used_fail"])
    return float(raw["useful_hits"]), float(raw["used_fail"])


def decay_usefulness(
    atom_path: Path, *, lam: float = DECAY_LAMBDA_DEFAULT, source: str,
) -> tuple[float, float]:
    """慢衰減（SessionEnd）：α←1+λ(α−1); β←1+λ(β−1)，把證據往 prior(1,1) 拉。

    λ≈0.97 → 單次衰減僅 3%，重啟冷啟動、防僵化。α/β 皆已在 prior 之上（≥1），
    衰減後仍 ≥1。若 α≈β≈1（無證據）→ 不寫檔（避免無意義 churn）。
    回傳衰減後 (α, β)。
    """
    _validate_source(source)
    access_path = _access_path(atom_path)
    raw = _read_raw(access_path)
    if raw is None:
        return float(USEFULNESS_PRIOR), float(USEFULNESS_PRIOR)
    raw, _ = _normalize(raw)
    alpha = float(raw.get("useful_hits") or USEFULNESS_PRIOR)
    beta = float(raw.get("used_fail") or USEFULNESS_PRIOR)
    prior = float(USEFULNESS_PRIOR)
    # 無證據（在 prior 上幾乎不動）→ 不寫
    if abs(alpha - prior) < 1e-9 and abs(beta - prior) < 1e-9:
        return alpha, beta
    new_alpha = prior + lam * (alpha - prior)
    new_beta = prior + lam * (beta - prior)
    raw["useful_hits"] = _coerce_num(new_alpha)
    raw["used_fail"] = _coerce_num(new_beta)
    if not _write_raw(access_path, raw):
        _audit("usefulness_decay_dropped", source, atom_path, reason="write_contention")
        return alpha, beta
    _audit("usefulness_decay", source, atom_path,
           lam=lam, alpha=raw["useful_hits"], beta=raw["used_fail"])
    return float(raw["useful_hits"]), float(raw["used_fail"])


def _coerce_num(x: float) -> Any:
    """整數值存 int（零索引膨脹），非整數存 6 位小數 float。"""
    r = round(float(x), 6)
    if abs(r - round(r)) < 1e-9:
        return int(round(r))
    return r


def wilson_lower_bound(successes: float, n: float, z: float = WILSON_Z_DEFAULT) -> float:
    """二項比例 p̂=successes/n 的 Wilson score 下界（單一壞 turn 幾乎不動分數）。

    SYNC: tools/workflow-guardian-mcp/server.js wilsonLowerBound（py↔js 鏡像）。
    n≤0 → 回 0.0（無證據時保守）。
    """
    if n <= 0:
        return 0.0
    phat = successes / n
    denom = 1.0 + (z * z) / n
    centre = phat + (z * z) / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + (z * z) / (4.0 * n)) / n)
    lb = (centre - margin) / denom
    return max(0.0, min(1.0, lb))


def usefulness_stats(
    access: Dict[str, Any], *, z: float = WILSON_Z_DEFAULT,
) -> Dict[str, float]:
    """從 access dict 算 (α,β)→succ/fail/n/mean/lower_bound。

    succ=α−1, fail=β−1（減去 Laplace prior）、n=succ+fail（有效樣本）。
    SYNC: server.js usefulnessStats。
    """
    alpha = float(access.get("useful_hits") or USEFULNESS_PRIOR)
    beta = float(access.get("used_fail") or USEFULNESS_PRIOR)
    succ = max(0.0, alpha - USEFULNESS_PRIOR)
    fail = max(0.0, beta - USEFULNESS_PRIOR)
    n = succ + fail
    mean = (succ / n) if n > 0 else 0.0
    lb = wilson_lower_bound(succ, n, z)
    return {
        "alpha": alpha, "beta": beta,
        "successes": succ, "failures": fail, "n": n,
        "mean": mean, "lower_bound": lb,
    }


def usefulness_promote_eligible(
    access: Dict[str, Any], *,
    promote_lb: float = PROMOTE_LB_DEFAULT,
    min_n: int = USEFULNESS_MIN_N_DEFAULT,
    z: float = WILSON_Z_DEFAULT,
) -> bool:
    """效用晉升資格：Wilson 下界 ≥ promote_lb 且 n ≥ min_n（遲滯帶上緣）。"""
    st = usefulness_stats(access, z=z)
    return st["n"] >= min_n and st["lower_bound"] >= promote_lb


def usefulness_demote_candidate(
    access: Dict[str, Any], *,
    demote_lb: float = DEMOTE_LB_DEFAULT,
    min_n: int = USEFULNESS_MIN_N_DEFAULT,
    z: float = WILSON_Z_DEFAULT,
) -> bool:
    """效用降級候選：Wilson 下界 ≤ demote_lb 且 n ≥ min_n（遲滯帶下緣）。"""
    st = usefulness_stats(access, z=z)
    return st["n"] >= min_n and st["lower_bound"] <= demote_lb


# 升門下方此寬度內視為「接近」，給注入時的主動晉升提示提早觸發。
USEFULNESS_HINT_NEAR_BAND = 0.1


def usefulness_hint_tier(
    access: Dict[str, Any], *,
    promote_lb: float = PROMOTE_LB_DEFAULT,
    min_n: int = USEFULNESS_MIN_N_DEFAULT,
    near_band: float = USEFULNESS_HINT_NEAR_BAND,
    z: float = WILSON_Z_DEFAULT,
) -> Optional[str]:
    """注入時的晉升提示分級（非晉升判定本身，純提醒人/AI 主動確認）。

    回傳：
      - 'eligible'：Wilson 下界 ≥ promote_lb（已具備效用晉升資格）
      - 'near'    ：promote_lb − near_band ≤ lb < promote_lb（接近升門）
      - None      ：lb 離升門尚遠 **或** n < min_n（無樣本不提示，防純曝光雜訊）

    Phase 2 (#2)：ReadHits 降為純曝光、退出晉升路徑後，UPS 注入提示改由本函式驅動。
    SYNC: usefulness_promote_eligible（'eligible' 與其同義）、server.js usefulnessStats。
    """
    st = usefulness_stats(access, z=z)
    if st["n"] < min_n:
        return None
    lb = st["lower_bound"]
    if lb >= promote_lb:
        return "eligible"
    if lb >= promote_lb - near_band:
        return "near"
    return None


def bulk_read(memory_root: Optional[Path] = None) -> Dict[str, Dict[str, Any]]:
    """掃描 memory 樹下所有 *.access.json，回傳 {atom_id: access_dict}。

    給 hooks/wg_iteration.py 衰退掃描 / tools/memory-audit.py / tools/atom-health-audit.py 用。
    atom_id = access 檔 stem（不含 .access）；跨 scope 統一 namespace。
    """
    root = memory_root or GLOBAL_MEMORY_DIR
    out: Dict[str, Dict[str, Any]] = {}
    for p in root.rglob("*.access.json"):
        # stem = "foo.access" → atom_id = "foo"
        atom_id = p.name[:-len(".access.json")]
        raw = _read_raw(p)
        if raw is None:
            continue
        normalized, _ = _normalize(raw)
        out[atom_id] = normalized
    return out


# ─── CLI 入口（給 server.js 子程序呼叫） ──────────────────────────────────────


def _cli() -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="atom_access")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_read = sub.add_parser("read")
    p_read.add_argument("path")

    p_init = sub.add_parser("init")
    p_init.add_argument("path")
    p_init.add_argument("--first-seen", default=None)
    p_init.add_argument("--source", required=True)

    p_inc_rh = sub.add_parser("increment-read-hits")
    p_inc_rh.add_argument("path")
    p_inc_rh.add_argument("--source", required=True)

    p_inc_cf = sub.add_parser("increment-confirmation")
    p_inc_cf.add_argument("path")
    p_inc_cf.add_argument("--source", required=True)
    p_inc_cf.add_argument("--event-json", default="{}")

    p_use = sub.add_parser("record-usefulness")
    p_use.add_argument("path")
    p_use.add_argument("--used", default="true")
    p_use.add_argument("--success", default="unknown")  # true|false|unknown
    p_use.add_argument("--source", required=True)

    p_decay = sub.add_parser("decay-usefulness")
    p_decay.add_argument("path")
    p_decay.add_argument("--lambda", dest="lam", type=float, default=DECAY_LAMBDA_DEFAULT)
    p_decay.add_argument("--source", required=True)

    p_promo = sub.add_parser("record-promotion")
    p_promo.add_argument("path")
    p_promo.add_argument("--target", required=True)
    p_promo.add_argument("--source", required=True)

    p_set = sub.add_parser("set")
    p_set.add_argument("path")
    p_set.add_argument("--field", required=True)
    p_set.add_argument("--value", required=True)
    p_set.add_argument("--source", required=True)

    args = parser.parse_args()
    atom_path = Path(args.path)

    try:
        if args.cmd == "read":
            data = read_access(atom_path)
            print(json.dumps(data, ensure_ascii=False))
        elif args.cmd == "init":
            init_access(atom_path, first_seen=args.first_seen, source=args.source)
            print(json.dumps({"ok": True}))
        elif args.cmd == "increment-read-hits":
            n = increment_read_hits(atom_path, source=args.source)
            print(json.dumps({"ok": True, "read_hits": n}))
        elif args.cmd == "increment-confirmation":
            event = json.loads(args.event_json) if args.event_json else {}
            n = increment_confirmation(atom_path, event=event, source=args.source)
            print(json.dumps({"ok": True, "confirmations": n}))
        elif args.cmd == "record-usefulness":
            used = str(args.used).strip().lower() in ("1", "true", "yes", "y")
            sv = str(args.success).strip().lower()
            success: Optional[bool]
            if sv in ("true", "1", "yes", "y"):
                success = True
            elif sv in ("false", "0", "no", "n"):
                success = False
            else:
                success = None  # unknown → no-op
            a, b = record_usefulness(
                atom_path, used=used, success=success, source=args.source,
            )
            print(json.dumps({"ok": True, "useful_hits": a, "used_fail": b}))
        elif args.cmd == "decay-usefulness":
            a, b = decay_usefulness(atom_path, lam=args.lam, source=args.source)
            print(json.dumps({"ok": True, "useful_hits": a, "used_fail": b}))
        elif args.cmd == "record-promotion":
            record_promotion(
                atom_path, target_confidence=args.target, source=args.source,
            )
            print(json.dumps({"ok": True}))
        elif args.cmd == "set":
            # value 嘗試解析為 int，失敗則維持 str
            v: Any = args.value
            try:
                v = int(v)
            except (ValueError, TypeError):
                pass
            write_access_field(
                atom_path, field=args.field, value=v, source=args.source,
            )
            print(json.dumps({"ok": True}))
    except (ValueError, OSError) as e:
        print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
