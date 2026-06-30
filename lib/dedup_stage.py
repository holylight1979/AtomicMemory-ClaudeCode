"""dedup_stage.py — _drafts 牢籠去蕪（截斷清除 + 近重複收斂），與確定性 classify 主路正交。

設計鐵則（見 memory/_staging/next-phase-draft-taxonomy-engine.md §3）：
  信任模型不同——classify=確定性 term-match（不可逆地寫索引/詞庫）；dedup=**可逆 soft-delete**
  （搬進 _drafts/_trash/，14 天時間閘 + /refile 救回）。故 DedupStage **絕不混入 classify 入口**，
  且**只在 _drafts/ 牢籠運作**：所有終點 path 必過 cage_assert（INV-DRAFT-STAYS-CAGED，fail-closed）。

本檔禁止引用『索引寫入』與『詞庫學習』API（CI grep 守門，見 verify_dedup_stage：
  INV-DRAFT-STAYS-CAGED / INV-DELETE-IS-SOFT-AND-REVERSIBLE）——故刻意不出現『詞庫學習 /
  索引寫入 / realm 搬移』等寫入面符號名。物理零索引/詞庫寫入。

牢籠原語（cage_assert / _drafts_root / CageEscapeError / CAGE_SEGMENT）複用 Phase 0 地基
  lib.taxonomy_jury（§9 牢籠安全地基保留複用），不重造。
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

from lib.taxonomy_jury import CAGE_SEGMENT, CageEscapeError, _drafts_root, cage_assert

TRASH = "_trash"              # _drafts/_trash/ — soft-delete 終點（仍在牢籠、仍被 sync-atom-index 排除）
SWEEP_LOCK = ".sweep.lock"    # _drafts/.sweep.lock — SessionEnd sweep 單一 advisory lock
TRASH_TTL_DAYS = 14          # 時間閘：trash 內物件存活 14 天可 /refile 救回，逾期才允許硬刪
TRASHMETA_SUFFIX = ".trashmeta.json"
_DAY_SECONDS = 86400

# 截斷訊號 2：連接符收尾（句被切在子句中途）。只取「結構性連接」字元，
# 不含 。！？」』）等正常句尾——避免合法 atom 假陽性。
_CONNECTORS = ("=", "(", "（", ":", "：", "、", "，", "/", "「", "『", "+")
# 截斷訊號 3：## 行動 區段若僅此佔位符（或空）→ 非真實行動段（builder 統一附加，80/80 皆有）。
_ACTION_PLACEHOLDER = "（依知識內容判斷）"


# ─── 區段切分（讀完整內容，不採樣）─────────────────────────────────────────
def knowledge_body(text: str) -> str:
    """取 `## 知識` 與 `## 行動`（或文末）之間的內容。無 `## 知識` → 回全文 strip。"""
    m = re.search(r"##\s*知識\s*(.*?)(?:\n##\s|\Z)", text, re.DOTALL)
    return (m.group(1).strip() if m else text.strip())


def action_section(text: str) -> Optional[str]:
    """取 `## 行動` 區段內容（不含標題）。無此區段 → None。"""
    m = re.search(r"##\s*行動\s*(.*?)(?:\n##\s|\Z)", text, re.DOTALL)
    return (m.group(1).strip() if m else None)


# ─── 截斷三訊號（§3：須三訊號全中才判；禁用全文末字，主記憶 26% 假陽性）─────
def _has_inline_unclosed(body: str) -> bool:
    """訊號①：行內未閉合——未閉 fence / 奇數行內反引號 / 圓括號不平衡。"""
    fence_count = body.count("```")
    if fence_count % 2 == 1:                       # ``` fence 未閉
        return True
    inline_bt = body.count("`") - fence_count * 3  # 扣掉 fence 佔的反引號
    if inline_bt % 2 == 1:                         # 行內 `code` 未閉
        return True
    opens = body.count("(") + body.count("（")
    closes = body.count(")") + body.count("）")
    return opens != closes                         # 圓括號不平衡（截在括號中）


def _ends_with_connector(body: str) -> bool:
    """訊號②：知識本體最後一個有意義字元為結構性連接符（句被切在中途）。"""
    lines = [ln.rstrip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return False
    last = lines[-1].rstrip()
    return bool(last) and last[-1] in _CONNECTORS


def _has_action_placeholder(text: str) -> bool:
    """訊號③：`## 行動` 區段僅佔位符（或空）。有真實行動項 → False（保護人工 curated atom）。"""
    sec = action_section(text)
    if sec is None:
        return False                               # 無 `## 行動` 區段 → 不算佔位符（保守）
    stripped = re.sub(r"^[\s\-\*]+", "", sec).strip()
    return stripped == "" or stripped == _ACTION_PLACEHOLDER


def is_truncated_fragment(text: str) -> bool:
    """三訊號**全中**才判截斷（高精度、低召回；caged fragment 留著無害，誤刪才有噪音）。

    ①行內未閉合 ②連接符收尾 ③`## 行動` 佔位符。任一不中即 False。
    讀完整 text（非截斷採樣，[[品質完整性判定須讀完整內容-勿從截斷採樣斷言]]）。
    """
    body = knowledge_body(text)
    return (
        _has_inline_unclosed(body)
        and _ends_with_connector(body)
        and _has_action_placeholder(text)
    )


# ─── per-env 去蕪策略（§3：project 叢集去重；core 碎片吸收、不去重）─────────
class DedupPolicy(NamedTuple):
    remove_truncated: bool   # 清截斷損壞碎片（可逆 soft-delete，env 無關之客觀損壞）
    cluster_dedup: bool      # 近重複叢集留最完整（僅 project；core 不去重＝尊重碎片吸收）


def resolve_dedup_policy(env: str) -> DedupPolicy:
    """env ∈ {'project','core'}。core 主記憶『近重複=0、碎片吸收』→ cluster_dedup=False；
    truncated 為客觀損壞、可逆清除，兩 env 皆清。"""
    if env == "project":
        return DedupPolicy(remove_truncated=True, cluster_dedup=True)
    return DedupPolicy(remove_truncated=True, cluster_dedup=False)


def draft_env_for(memory_dir: Path, claude_dir: Path) -> str:
    """memory_dir 在 ~/.claude 下（含等於）→ 'core'；否則 'project'（鏡 _flush_route 判定）。"""
    try:
        md, cd = memory_dir.resolve(), claude_dir.resolve()
        return "core" if md == cd or cd in md.parents else "project"
    except OSError:
        return "core"  # 安全預設：判不出當 core（不啟動 cluster_dedup）


# ─── 近重複叢集（subsumption：只刪『內容被某保留者完全涵蓋』者 → 零知識損失）──
def _norm_for_dedup(text: str) -> str:
    """知識本體正規化供涵蓋比對：只留內容字元（CJK + 英數），去標點/markdown/空白、lower。

    保守取向——**僅 substring 涵蓋（dropped 的內容字元序列完整內含於 keep）才判冗餘** →
    零知識損失。標點差異不承載知識故剝除；paraphrase（換句話說的近重複，如三份不同措辭講同
    一缺陷）**刻意不自動去**（需 LLM 語意判斷，違 dedup=可逆+確定性 信任模型）→ 留待人工 /refile。
    """
    body = knowledge_body(text)
    body = re.sub(r"\[[臨觀固]\]", "", body)                       # 去 confidence tag
    body = re.sub(r"[^0-9A-Za-z一-鿿]", "", body)         # 只留 CJK + 英數
    return body.lower()


def find_redundant(drafts: List[Path]) -> List[Tuple[Path, Path]]:
    """回 [(drop, keep), ...]：drop 的正規化內容是某 keep 的子字串（含完全相等）。

    保留最長者（同長以檔名序定錨）→ 嚴格涵蓋才 drop → **零知識損失**（INV）。
    跳過截斷碎片（那走 truncated 路徑、不作為 keep 錨）。確定性、讀完整內容。
    """
    items = []
    for p in drafts:
        try:
            t = p.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError):
            continue
        if is_truncated_fragment(t):
            continue                               # 截斷者不參與叢集（避免拿半截當錨）
        items.append((p, _norm_for_dedup(t)))
    # 最長優先、同長檔名序 → 穩定保留錨
    items.sort(key=lambda x: (-len(x[1]), x[0].name))
    kept: List[Tuple[Path, str]] = []
    drops: List[Tuple[Path, Path]] = []
    for p, norm in items:
        if not norm:
            kept.append((p, norm))
            continue
        host = next((k for k, kn in kept if norm in kn), None)
        if host is not None:
            drops.append((p, host))                # norm ⊆ host → 冗餘
        else:
            kept.append((p, norm))
    return drops


# ─── soft-delete / 救回 / 時間閘硬刪（INV-DELETE-IS-SOFT-AND-REVERSIBLE）──────
def _unique_target(dest_dir: Path, name: str) -> Path:
    """dest_dir/name 撞名 → name-2/-3…（防覆蓋既有 trash 物件）。"""
    target = dest_dir / name
    if not target.exists():
        return target
    stem, suf = Path(name).stem, Path(name).suffix
    for i in range(2, 1000):
        cand = dest_dir / f"{stem}-{i}{suf}"
        if not cand.exists():
            return cand
    raise CageEscapeError(f"trash 命名空間耗盡：{name}")


def soft_delete(draft_path: Path, memory_dir: Path, *,
                reason: str = "", now_ts: Optional[float] = None) -> Path:
    """把 draft 物理搬到 同牢籠 `_drafts/_trash/`，寫 sidecar 記原位+時戳+理由。

    終點過 cage_assert（fail-closed）→ 永不離開牢籠。回 trash 內 .md 路徑。**可逆**（restore_from_trash）。
    """
    now_ts = time.time() if now_ts is None else now_ts
    trash_dir = _drafts_root(draft_path) / TRASH
    target = _unique_target(trash_dir, draft_path.name)
    cage_assert(target, memory_dir)                # 牢籠斷言先於任何 I/O（fail-closed）
    trash_dir.mkdir(parents=True, exist_ok=True)
    orig_rel = draft_path.resolve().relative_to(memory_dir.resolve()).as_posix()
    draft_path.rename(target)
    sidecar = target.with_name(target.name + TRASHMETA_SUFFIX)
    sidecar.write_text(json.dumps(
        {"orig_rel": orig_rel, "deleted_at": now_ts, "reason": reason},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def restore_from_trash(trash_md: Path, memory_dir: Path) -> Path:
    """讀 sidecar 把 trash 內 .md 搬回原位（/refile 救回的程式化對應）。回還原後路徑。"""
    sidecar = trash_md.with_name(trash_md.name + TRASHMETA_SUFFIX)
    meta = json.loads(sidecar.read_text(encoding="utf-8"))
    dest = (memory_dir / meta["orig_rel"])
    dest.parent.mkdir(parents=True, exist_ok=True)
    target = dest if not dest.exists() else _unique_target(dest.parent, dest.name)
    trash_md.rename(target)
    try:
        sidecar.unlink()
    except OSError:
        pass
    return target


def purge_expired_trash(drafts_root: Path, *, now_ts: Optional[float] = None,
                        ttl_days: int = TRASH_TTL_DAYS) -> List[Path]:
    """**唯一硬刪路徑**：硬刪 trash 內 deleted_at 逾 ttl_days 的物件（+ sidecar）。
    14 天內者一律保留（可 /refile）。回實際硬刪的 .md 路徑清單。"""
    now_ts = time.time() if now_ts is None else now_ts
    trash_dir = drafts_root / TRASH
    if not trash_dir.exists():
        return []
    cutoff = now_ts - ttl_days * _DAY_SECONDS
    purged = []
    for sidecar in sorted(trash_dir.glob("*" + TRASHMETA_SUFFIX)):
        try:
            meta = json.loads(sidecar.read_text(encoding="utf-8"))
            deleted_at = float(meta.get("deleted_at", now_ts))
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if deleted_at > cutoff:
            continue                               # 未逾期 → 保留（時間閘）
        md = sidecar.with_name(sidecar.name[:-len(TRASHMETA_SUFFIX)])
        for f in (md, sidecar):
            try:
                f.unlink()
            except OSError:
                pass
        purged.append(md)
    return purged


# ─── SessionEnd sweep：單一 advisory file-lock，拿不到即 skip ─────────────────
def _try_acquire(lock_path: Path):
    """非阻塞 advisory lock（拿不到回 None）。win32 用 msvcrt、posix 用 fcntl
    （樣式參考 lib.atom_locations 詞庫鎖，改非阻塞 NBLCK/LOCK_NB）。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fh = open(lock_path, "ab")
        fh.seek(0)
    except OSError:
        return None
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fh
    except OSError:
        fh.close()
        return None                                # 另一 session 持鎖 → 呼叫端 skip


def _release(lock_path: Path, fh) -> None:
    if fh is None:
        return
    try:
        if sys.platform == "win32":
            import msvcrt
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    fh.close()
    try:
        lock_path.unlink()
    except OSError:
        pass


def _iter_drafts(drafts_root: Path):
    """掃牢籠內所有 .md，排除 _trash/（已 soft-delete 者不重複處理）。"""
    for p in sorted(drafts_root.rglob("*.md")):
        if TRASH not in p.relative_to(drafts_root).parts:
            yield p


def sweep_drafts(drafts_root: Path, memory_dir: Path, *, env: str,
                 now_ts: Optional[float] = None, dry_run: bool = False) -> Dict:
    """SessionEnd 去蕪 sweep：持單一 file-lock；拿不到即 skip（不阻塞、不重入）。

    流程（全 soft-delete，可逆）：①依 policy 清截斷碎片 ②（僅 project）近重複叢集留最完整。
    **不**碰索引/詞庫/Confidence/晉升（物理零相關 import，CI grep 守）。回報告 dict。
    dry_run=True → 只算不搬。終點皆過 cage_assert（fail-closed）。
    """
    now_ts = time.time() if now_ts is None else now_ts
    report = {"status": "ok", "env": env, "truncated": [], "redundant": [],
              "dry_run": dry_run}
    if not drafts_root.exists():
        report["status"] = "no-drafts-dir"
        return report
    policy = resolve_dedup_policy(env)
    lock_path = drafts_root / SWEEP_LOCK
    fh = _try_acquire(lock_path)
    if fh is None:
        report["status"] = "skipped-locked"       # 另一 session 正在 sweep
        return report
    try:
        all_drafts = list(_iter_drafts(drafts_root))
        truncated = set()
        if policy.remove_truncated:
            for p in all_drafts:
                try:
                    if is_truncated_fragment(p.read_text(encoding="utf-8-sig")):
                        truncated.add(p)
                        report["truncated"].append(p.name)
                        if not dry_run:
                            soft_delete(p, memory_dir, reason="truncated", now_ts=now_ts)
                except (OSError, UnicodeDecodeError):
                    continue
        if policy.cluster_dedup:
            survivors = [p for p in all_drafts if p not in truncated]
            for drop, keep in find_redundant(survivors):
                report["redundant"].append({"drop": drop.name, "keep": keep.name})
                if not dry_run:
                    soft_delete(drop, memory_dir,
                                reason=f"redundant<=:{keep.name}", now_ts=now_ts)
        return report
    finally:
        _release(lock_path, fh)
