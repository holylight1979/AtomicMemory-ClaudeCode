# Unity YAML 序列化知識

- Scope: global
- Confidence: [固]
- Trigger: Unity YAML, fileID, GUID, PrefabInstance, .prefab, .meta, 型別ID, 序列化, Missing Script
- Last-used: 2026-03-31
- Confirmations: 19
- Type: semantic
- Tags: unity, yaml, serialization, prefab, guid
- Related: unity-yaml-detail

## 知識

### 文件位置
完整知識在同資料夾的 [unity-yaml-detail.md](unity-yaml-detail.md)
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

- 遇到 Unity YAML 問題先查同資料夾的 `unity-yaml-detail.md`
- Missing Script 修復：換 `m_Script` 的 guid，fileID=11500000，type=3
- 手改 YAML 前先 SVN commit 作為回滾點，縮排用空格不用 Tab
- 程式化建立或修改 prefab 時，MonoBehaviour 的 `m_Script` guid 一律從目標腳本的 `.cs.meta`（DLL 內類別則讀 `.dll.meta` 加對應 fileID）取得；GUID 各專案不同，專案自己的 GUID 對照表與 prefab 產生工具放在該專案的 `_AIDocs`
- 改完 prefab 先驗：fileID 交叉引用都找得到、`m_Script` 沒有 `{fileID: 0}`

## 演化日誌

| 日期 | 變更 |
|------|------|
| 2026-03-11 | 從同事的分支版本合併，修正路徑 |
| 2026-03-24 | CLASS_IDS 擴充（222-225）、Anchor presets |
