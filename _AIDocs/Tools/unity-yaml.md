# Unity YAML 序列化知識

- Scope: global
- Confidence: [固]
- Trigger: Unity YAML, fileID, GUID, PrefabInstance, .prefab, .meta, 型別ID, 序列化, Missing Script
- Last-used: 2026-03-31
- Confirmations: 19
- Type: semantic
- Tags: unity, yaml, serialization, prefab, guid
- Related: unity-prefab-workflow, unity-yaml-detail

## 知識

### 文件位置
完整知識在 [memory/unity/unity-yaml-detail.md](~/.claude/memory/unity/unity-yaml-detail.md)（全域）
版本：Unity 2022.3.x

### 核心概念速查

**型別 ID（!u!）**
- 1=GameObject, 4=Transform, 224=RectTransform, 223=Canvas
- 114=MonoBehaviour/ScriptableObject, 1001=PrefabInstance
- 74=AnimationClip, 91=AnimatorController, 21=Material
- 49=TextAsset, 212=SpriteRenderer, 198=ParticleSystem
- ScriptableObject 識別：`m_GameObject: {fileID: 0}`

**參照系統**
- 同檔案：`{fileID: 123456}`
- 跨檔案：`{fileID: X, guid: Y, type: Z}`（type 0=內建資源(deprecated但仍用); 2=Assets直接載入; 3=Library處理後載入）
- MonoScript fileID 固定 `11500000`，type 固定 `3`
- Missing Script：`m_Script: {fileID: 0}`

**GUID 核心規則**
- 刪除 .meta 重新匯入 → GUID 重生 → 所有參照斷掉（最高風險）
- 移動/重命名資源時 .meta 一起移動 → GUID 不變

**Unity 2022.3 特有**
- Transform 新增 `m_ConstrainProportionsScale: 0`
- Material serializedVersion: 8（新增 `m_ValidKeywords` 陣列取代舊字串）

**Nested Prefab（2018.3+）**
- Type ID 1001 = PrefabInstance
- `m_Modifications` 陣列記錄屬性覆寫（propertyPath + value/objectReference）
- `m_RemovedComponents` / `m_AddedComponents` / `m_AddedGameObjects` / `m_RemovedGameObjects`
- Stripped 物件：嵌套 Prefab 的佔位物件，標頭加 `stripped`，只有參照無屬性
- `fileID: 100100000` = Prefab Asset Handle（匯入時建立，不在 YAML 中）
- Prefab Variant：根物件就是 PrefabInstance，`m_TransformParent: {fileID: 0}`
- 舊引用：刪除腳本變數/元件後殘留在 YAML，Build 時自動清除，Asset Bundle 不會

### 實用技巧

```bash
# 找引用特定 GUID 的檔案
grep -r "<guid>" Assets/ --include="*.unity" --include="*.prefab" -l

# 找 Missing Script
grep -r "m_Script: {fileID: 0}" Assets/ --include="*.prefab"
```

**SVN Merge**：設定 TortoiseSVN 外部 Merge Tool 指向 `UnityYAMLMerge.exe`

## 行動

- 遇到 Unity YAML 問題先查 `~/.claude/memory/unity/unity-yaml-detail.md`（全域）
- Missing Script 修復：換 `m_Script` 的 guid，fileID=11500000，type=3
- 手改 YAML 前先 SVN commit 作為回滾點，縮排用空格不用 Tab
- 操作型需求使用 `/unity-yaml` skill（parse/generate/modify/template）
- **建立 WndForm prefab**：使用 `generate-ui-prefab` 命令 + JSON spec → 自動建 root 6 元件 + RefDb（見 `unity-prefab-workflow` atom）
- **驗證 prefab**：使用 `validate` 命令檢查 fileID 交叉引用 + m_Script 非零

## 演化日誌

| 日期 | 變更 |
|------|------|
| 2026-03-11 | 從 Wells V2.5 fork 合併至 V2.10，修正路徑，補充 /unity-yaml skill 連結 |
| 2026-03-24 | 補充 generate-ui-prefab / validate 命令、CLASS_IDS 擴充（222-225）、UI_GUIDS 對照表、Anchor presets |
