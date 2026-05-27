# V4 hook archive (frozen 2026-05-26 → 2026-05-27)

> 原位 `hooks/_v4_archive/`，V5 Wave 4 P6（2026-05-27）搬到 `_AIDocs/DevHistory/` 保存為發展史證物。

V5 Wave 2 把 `hooks/wg_*.py` 16 個模組整併為 6 主模組 + 2 shim，並把 `workflow-guardian.py` 從 2651 行 dispatcher 拆為 `dispatcher.py`（75 行純路由）+ `handlers/` 目錄。

本目錄保留 V4.1 終態的 19 個檔案為「升版前」基準對照，供後續架構討論、回滾參考、或迴歸分析使用。**不被任何 import path 引用**。

## 內容索引（V4.1 hook 模組組成 → V5 去處）

| 檔案 | V4.1 行數 | V5 去處 |
|------|----------|---------|
| workflow-guardian.py | ~2651 | 拆成 `dispatcher.py` + `handlers/*.py` |
| wg_core.py | ~370 | `wg_core.py`（保留 + 加 rotate_log_if_oversized） |
| wg_paths.py | ~451 | 合入 `wg_core.py` |
| wg_atoms.py | ~800 | `wg_atoms.py`（保留 + 吸收 wg_intent trigger / BM25） |
| wg_intent.py | ~430 | trigger 部分合入 `wg_atoms.py` |
| wg_extraction.py | ~295 | `wg_extraction.py`（保留 + 合 user_extract / hot_cache） |
| wg_user_extract.py | — | 合入 `wg_extraction.py` |
| wg_hot_cache.py | ~160 | 合入 `wg_extraction.py` |
| wg_episodic.py | ~860 | `wg_episodic.py`（保留） |
| wg_iteration.py | ~450 | atom 晉升部分合入 `wg_atoms`；自評部分合入 `wg_evasion` |
| wg_evasion.py | ~177 | `wg_evasion.py`（保留 + 合 wg_session_evaluator / wg_iteration 自評） |
| wg_session_evaluator.py | — | 合入 `wg_evasion.py` |
| wg_docdrift.py | ~260 | `wg_docdrift.py`（保留獨立） |
| wisdom_engine.py | ~306 | `wisdom_engine.py`（保留獨立） |
| wg_pretool_guards.py | ~75 | 合入 `wg_core.py` |
| wg_atom_observation.py | ~205 | shim（REG-005 任務已結束，flag-gated 零開銷） |
| wg_roles.py | ~210 | shim（V4 sub-layer 探勘 thin wrapper） |
| wg_content_classify.py | — | 合入 `wg_extraction.py` |
| codex_companion.py | ~755（HTTP daemon 版） | **V5 P5b 重寫**為 subprocess 版（in-process state + spawn `tools/codex-companion/audit.py`） |

## 相關文件

- [`../../SPEC_ATOM_V5.md §5`](../../SPEC_ATOM_V5.md) — V5 hook 6+2 主模組規格
- [`../../Architecture.md`](../../Architecture.md) — V5 hook 模組拆分總覽
- [`../../V5-upgrade-plan.md`](../../V5-upgrade-plan.md) — 4-Wave 重構計畫
- [`../../../memory/v5-overhaul-audit-2026-05.md`](../../../memory/v5-overhaul-audit-2026-05.md) — 升版 audit atom
