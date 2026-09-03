# sync-memory-index.py 在 Windows 直接跑會 cp950 UnicodeEncodeError — 前綴 PYTHONIOENCODING=utf-8

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: sync-memory-index, cp950, UnicodeEncodeError, PYTHONIOENCODING, catalog 重生, _local_catalog, sync_doc_counts, 索引重生
- Created-at: 2026-09-01

## 知識

- [臨] `python tools/sync-memory-index.py` 在 Windows 主控台（cp950）末尾 `print(new_local)` 遇 `∈` 等字元直接 UnicodeEncodeError 收場；要用 `PYTHONIOENCODING=utf-8 python tools/sync-memory-index.py`。同批收尾工具鏈：`sync-atom-index.py --fix-scope-from-path`（去懸空）→ `atom-health-check.py --fix-refs`（Related 反向連結）→ `sync-memory-index.py`（catalog）→ `sync_doc_counts.py --write`（TECH/_INDEX/DocIndex 計數），四支跑完再 commit。
- [臨] 刪 atom 走 `git rm` 後索引不會自動掉：必跑上列四支，否則 `_local_catalog.md`／`_INDEX.md`／DocIndex 計數留舊值。

## 行動

- 跑 sync-memory-index.py 一律前綴 PYTHONIOENCODING=utf-8
- 刪／搬 atom 後依序跑 sync-atom-index --fix-scope-from-path → atom-health-check --fix-refs → sync-memory-index → sync_doc_counts --write
