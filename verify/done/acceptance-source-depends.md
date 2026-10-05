---
task_slug: source-depends
session_id: d892b7c9-9c98-47fc-ae48-747e217bd73f
created_at: 2026-10-01
source: multifile
status: done
---
## 目標
atom 可標來源（`- Source:`）與依賴路徑（`- Depends:`），由 funnel 渲染、py↔js byte parity——工具卡地基（`Author`＝負責人、`Source`＝進入點、`Status`、`Depends: path:<進入點>` 健檢自動 stale）。不強制、workers 不寫。SoT：`lib/atom_spec.build_atom_content`；SPEC §13。

## 必須發生
- `build_atom_content(provenance=, depends=)`：`- Source:` 在 Author 後、`- Depends:` 在 Created-at 後、Related 前；未給／空時輸出與既有 parity fixture byte-identical；js `atom-render.js buildAtomContent` 同位置 → `lib/verify/verify_atom_io_equivalence.py::test_31_provenance_py_js_byte_parity`、`test_32_depends_py_js_byte_parity`
- `write_atom(provenance=, depends=)` 透傳；replace 三態：None 保留既有行（同 Author 規則）、`""`／`[]` 清除、非空替換；append 不動檔頭 → `test_33_replace_preserves_source_and_depends`
- MCP `atom_write` 選填 `provenance`（string）、`depends`（string[]，型別錯即拒）；js replace 讀舊檔 `- Source:`／`- Depends:` 回填（`atom-tools.js readSourceLine／readDependsLine`）
- 參數名 `provenance`（`write_atom(source=)` 是稽核白名單，不可衝名）
- 既有 `verify_atom_io_equivalence.py` 全部案例不受影響

## 禁止發生
- 不改 workers（auto-captured 不寫 Source）
- 不動 `_MAP.md` 以外的 js 路由（落點仍 py `locate` 單一裁決）

## 驗證指令
- python -m pytest lib/verify/verify_atom_io_equivalence.py -q -k "31 or 32 or 33"
- python -m pytest lib/verify/verify_atom_io_equivalence.py -q（全案不回歸）
