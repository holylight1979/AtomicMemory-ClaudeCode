# Unity YAML 序列化格式完整知識庫

- Scope: global
- Confidence: [固]
- Trigger: Unity YAML detail, 序列化格式, PrefabInstance, m_Modifications, ScriptableObject, AnimationClip, AnimatorController, Merge 衝突, fileID, YAML 1.1
- Last-used: 2026-03-25
- Confirmations: 0
- Related: unity-yaml

> 版本：Unity 2022.3.x
> 建立：2026-03-10
> 來源：某 Unity 專案用戶端的 _AIDocs，晉升至全域 2026-03-11

---

## 1. 基本格式結構

### 檔案頭

```yaml
%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!29 &1
OcclusionCullingSettings:
  m_ObjectHideFlags: 0
  ...
```

- `%YAML 1.1` — Unity 固定使用 YAML 1.1（非 1.2），`on`/`off`/`yes`/`no` 在 1.1 都是 bool
- `!u!TYPE_ID` — Unity 內部型別 ID
- `&FILE_ID` — 本檔案內的 fileID 錨點
- `---` — YAML document 分隔符

---

## 2. Unity 型別 ID（常用）

| Type ID | 型別名稱 |
|---------|---------|
| 1 | GameObject |
| 4 | Transform |
| 20 | Camera |
| 21 | Material |
| 23 | MeshRenderer |
| 33 | MeshFilter |
| 43 | Mesh |
| 48 | Shader |
| 49 | TextAsset |
| 54 | Rigidbody |
| 65 | BoxCollider |
| 74 | AnimationClip |
| 83 | AudioClip |
| 91 | AnimatorController |
| 95 | Animator |
| 102 | TextMesh |
| 104 | RenderSettings |
| 114 | MonoBehaviour / ScriptableObject |
| 115 | MonoScript |
| 128 | Font |
| 137 | SkinnedMeshRenderer |
| 164 | AudioReverbFilter |
| 198 | ParticleSystem（Shuriken） |
| 212 | SpriteRenderer |
| 213 | Sprite |
| 221 | AnimatorOverrideController |
| 222 | CanvasRenderer |
| 223 | Canvas |
| 224 | RectTransform |
| 1001 | PrefabInstance（Nested Prefab） |
| 1011 | TextureImporter（.meta） |
| 1035 | MonoImporter（.cs .meta） |
| 1089 | PrefabImporter（.prefab .meta） |

---

## 3. 參照系統

### fileID / GUID / type 格式

```yaml
# 同檔案參照
m_Transform: {fileID: 1234567890}

# 跨檔案參照
m_Mesh: {fileID: 10202, guid: 0000000000000000e000000000000000, type: 0}

# Script 參照
m_Script: {fileID: 11500000, guid: a1b2c3d4e5f6..., type: 3}

# 空參照
m_SomeRef: {fileID: 0}
```

### type 值意義

| type | 意義 |
|------|------|
| `0` | **Deprecated**，但 Unity 內建資源參照仍使用（如預設 Shader、內建 Mesh） |
| `1` | **Deprecated**，實務上不再出現 |
| `2` | Assets 資料夾可直接載入的資源（材質、.asset 等文字序列化格式） |
| `3` | 經處理後寫入 Library 資料夾的資源（Prefab、Texture、3D 模型、Script） |

### 常見固定 fileID

| 資源型別 | fileID |
|---------|--------|
| MonoScript | 11500000 |
| ScriptableObject 資源 | 11400000 |
| Material 資源 | 2100000 |
| Prefab 根物件 | 100100000 |
| Texture2D | 2800000 |
| AnimationClip | 7400000 |
| AudioClip | 8300000 |
| Mesh | 4300000 |

---

## 4. 資源型別結構

### 4.1 .unity（場景）

固定物件（&1-4）：
- `&1` OcclusionCullingSettings
- `&2` RenderSettings
- `&3` LightmapSettings
- `&4` NavMeshSettings

```yaml
--- !u!1 &1234567890
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {fileID: 0}
  m_PrefabInstance: {fileID: 0}
  m_PrefabAsset: {fileID: 0}
  serializedVersion: 6
  m_Component:
  - component: {fileID: 1234567891}
  m_Layer: 0
  m_Name: MyObject
  m_TagString: Untagged
  m_IsActive: 1
--- !u!4 &1234567891
Transform:
  m_GameObject: {fileID: 1234567890}
  m_LocalRotation: {x: 0, y: 0, z: 0, w: 1}
  m_LocalPosition: {x: 0, y: 0, z: 0}
  m_LocalScale: {x: 1, y: 1, z: 1}
  m_ConstrainProportionsScale: 0    # Unity 2022 新增
  m_Children: []
  m_Father: {fileID: 0}
  m_RootOrder: 0
  m_LocalEulerAnglesHint: {x: 0, y: 0, z: 0}
```

### 4.2 .prefab

Prefab 無 &1-4 固定物件。根 GameObject 的 Transform `m_Father: {fileID: 0}`。

### 4.3 .asset（ScriptableObject）

```yaml
--- !u!114 &11400000
MonoBehaviour:
  m_GameObject: {fileID: 0}        # ScriptableObject 沒有 GameObject
  m_Script: {fileID: 11500000, guid: abc123..., type: 3}
  m_Name: MyData
  myValue: 42
```

區分 ScriptableObject vs Component：`m_GameObject: {fileID: 0}` 表示 ScriptableObject。

### 4.4 .meta

```yaml
fileFormatVersion: 2
guid: a1b2c3d4e5f678901234567890abcdef
MonoImporter:
  serializedVersion: 2
  defaultReferences: []
  executionOrder: 0
  icon: {instanceID: 0}
  userData:
  assetBundleName:
  assetBundleVariant:
```

Sprite Sheet 的 `fileIDToRecycleName`：
```yaml
fileIDToRecycleName:
  21300000: sprite_0
  21300002: sprite_1    # 每個 Sprite = 21300000 + index * 2
```

### 4.5 .mat（Material）

Unity 2022 用 serializedVersion: 8，新增 m_ValidKeywords：
```yaml
--- !u!21 &2100000
Material:
  serializedVersion: 8    # 2022 升至 8（2021 是 7）
  m_ValidKeywords:
  - _NORMALMAP
  m_InvalidKeywords: []
  m_SavedProperties:
    m_TexEnvs:
    - _BaseMap:
        m_Texture: {fileID: 2800000, guid: ..., type: 3}
        m_Scale: {x: 1, y: 1}
        m_Offset: {x: 0, y: 0}
    m_Floats:
    - _Smoothness: 0.5
    m_Colors:
    - _BaseColor: {r: 1, g: 1, b: 1, a: 1}
```

### 4.6 .anim（AnimationClip）

```yaml
--- !u!74 &7400000
AnimationClip:
  m_Name: Walk
  serializedVersion: 7
  m_SampleRate: 60
  m_WrapMode: 0
  m_PositionCurves:
  - curve:
      m_Curve:
      - time: 0
        value: {x: 0, y: 0, z: 0}
        inSlope: {x: 0, y: 0, z: 0}
        outSlope: {x: 0, y: 0, z: 0}
    path: Spine/UpperArm          # 字串路徑，重命名物件時需同步更新
  m_ClipBindingConstant:
    genericBindings:
    - path: 2166136261    # path 字串的 CRC32 hash（runtime 查找用）
      attribute: 1        # 1=localPosition.x, 2=.y, 3=.z
      typeID: 4           # Transform
```

### 4.7 .controller（Animator Controller）

```yaml
--- !u!91 &9100000
AnimatorController:
  m_AnimatorParameters:
  - m_Name: Speed
    m_Type: 1    # 0=Float, 1=Int, 3=Bool, 4=Trigger
  m_AnimatorLayers:
  - m_Name: Base Layer
    m_StateMachine: {fileID: 1107892584}
--- !u!1107 &1107892584
AnimatorStateMachine:
  m_DefaultState: {fileID: 1102345678}
--- !u!1102 &1102345678
AnimatorState:
  m_Name: Idle
  m_Motion: {fileID: 7400000, guid: abc123..., type: 2}
  m_WriteDefaultValues: 1
```

---

## 5. 序列化規則

### 被序列化的欄位

```csharp
public int health;                     // public 欄位
[SerializeField] private int mana;    // [SerializeField] 私有
```

### 不被序列化的欄位

```csharp
private int _internal;                 // 無標記私有
[NonSerialized] public int skip;      // 明確排除
public static int count;              // static
public const int MAX = 100;           // const
public int Property { get; set; }     // 屬性
```

### 支援的型別

```csharp
// 原始型別：int, float, double, bool, string, byte, short, long, uint, ulong
// Unity struct：Vector2/3/4, Quaternion, Color, Color32, Rect, Bounds, AnimationCurve, Gradient
// 集合：T[], List<T>
// 自訂 class 需 [System.Serializable]
// Dictionary、interface、abstract class → 不支援（可用 [SerializeReference]）
```

### [SerializeReference]（Unity 2019.3+）

序列化 interface / abstract class：
```yaml
m_SerializeReferenceRegistry:
  managedreferenceregistry:
    version: 2
    RefIds:
    - rid: 1
      type: {class: ConcreteClass, ns: MyGame, asm: Assembly-CSharp}
      data:
        value: 42
myAbstractField:
  rid: 1
```

---

## 6. Prefab 系統（Unity 2018.3+ Nested Prefab）

### PrefabInstance 結構

```yaml
--- !u!1001 &2148888050
PrefabInstance:
  serializedVersion: 2
  m_Modification:
    m_TransformParent: {fileID: 1234567890}
    m_Modifications:
    - target: {fileID: <prefab內物件fileID>, guid: <prefab GUID>, type: 3}
      propertyPath: m_LocalPosition.x
      value: 5
      objectReference: {fileID: 0}
    m_RemovedComponents: []
    m_RemovedGameObjects: []
    m_AddedGameObjects: []
    m_AddedComponents: []
  m_SourcePrefab: {fileID: 100100000, guid: <prefab GUID>, type: 3}
```

### m_Modifications 詳細說明

每個 PropertyModification 條目格式：
```yaml
- target: {fileID: <prefab內物件fileID>, guid: <prefab GUID>, type: 3}
  propertyPath: m_LocalPosition.x     # 被覆寫的屬性路徑
  value: 5                            # 新值（簡單型別用 value）
  objectReference: {fileID: 0}        # 參照型別用此欄位（互斥）
```

常見覆寫：
```yaml
# 覆寫位置
propertyPath: m_LocalPosition.x / .y / .z

# 覆寫名稱
propertyPath: m_Name

# 覆寫啟用狀態
propertyPath: m_IsActive

# 覆寫 MonoBehaviour 欄位
propertyPath: myPublicField
propertyPath: mySerializedList.Array.size
propertyPath: mySerializedList.Array.data[0]
```

注意：真正的 PrefabInstance 通常有**大量** m_Modifications 條目（每個被修改的屬性一條），比 YAML 中看到的要多得多。

### m_RemovedComponents / m_RemovedGameObjects

從 Prefab 實例移除元件或 GameObject：
```yaml
m_RemovedComponents:
- {fileID: <component fileID in prefab>, guid: <prefab GUID>, type: 3}

m_RemovedGameObjects:
- {fileID: <gameobject fileID in prefab>, guid: <prefab GUID>, type: 3}
```

注意：Prefab Variant 中**無法真正刪除**繼承的 GameObject，只能停用（透過 m_Modifications 覆寫 `m_IsActive: 0`）。

### m_AddedGameObjects / m_AddedComponents

新增到 Prefab 實例的物件/元件：
```yaml
m_AddedGameObjects:
- targetCorrespondingSourceObject: {fileID: <parent transform in prefab>, guid: <prefab GUID>, type: 3}
  insertIndex: -1
  addedObject: {fileID: <新 GameObject 的 fileID（本檔案內）>}

m_AddedComponents:
- targetCorrespondingSourceObject: {fileID: <target gameobject in prefab>, guid: <prefab GUID>, type: 3}
  insertIndex: -1
  addedObject: {fileID: <新 Component 的 fileID（本檔案內）>}
```

新增的 GameObject/Component 會作為獨立的 YAML document（`--- !u!1 &xxx` / `--- !u!114 &xxx`）存在於同一檔案中。

### Stripped 物件（佔位物件）

嵌套 Prefab 的 GameObject/Component 不會在外層檔案中完整序列化，而是產生「stripped」佔位物件：

```yaml
--- !u!4 &1234567890 stripped
Transform:
  m_CorrespondingSourceObject: {fileID: <source transform>, guid: <prefab GUID>, type: 3}
  m_PrefabInstance: {fileID: <PrefabInstance fileID>}
  m_PrefabAsset: {fileID: 0}
```

特徵：
- 標頭加上 `stripped` 標記
- **不含**正常屬性（無 m_LocalPosition 等）
- 只有 `m_CorrespondingSourceObject` 和 `m_PrefabInstance` 參照
- 用途：讓外層物件能引用嵌套 Prefab 內的物件（如設為子物件的 m_Father）

### 100100000 = Prefab Asset Handle

`m_SourcePrefab` 中的 `fileID: 100100000` 是 **Prefab 匯入時自動建立的 Handle**，不出現在 Prefab 的 YAML 原始碼中。這是用來指向整個 Prefab 資產根物件的固定 ID。

### Prefab Variant

Variant 的根物件本身就是 PrefabInstance，`m_TransformParent: {fileID: 0}`（無父節點）。
Variant 中無法 reparent 繼承的 GameObject，也無法真正移除，只能停用。

### 舊引用（Stale References）

以下情況會產生 YAML 中的殘留引用：
- **刪除腳本變數**：引用值留在 YAML，直到重新修改並儲存該資產
- **刪除嵌套 Prefab 的物件**：stripped 佔位物件仍留在 YAML
- **刪除元件後未重新序列化**：元件的 YAML document 殘留

清理方式：
- 手動修改並儲存資產
- `AssetDatabase.ForceReserializeAssets()` 強制重新序列化
- **Build / Addressable 打包時會自動清除**舊引用
- **Asset Bundle 不會自動清除**，可能導致不必要的依賴（需注意）

---

## 7. 常見欄位對照

### GameObject

| 欄位 | 說明 |
|------|------|
| `m_ObjectHideFlags` | 0=正常, 1=HideInHierarchy, 2=HideInInspector |
| `m_CorrespondingSourceObject` | Prefab 實例指向原始物件；否則 {fileID:0} |
| `m_PrefabInstance` | 所屬 PrefabInstance；否則 {fileID:0} |
| `m_Layer` | Layer 數字（0=Default, 5=UI...） |
| `m_StaticEditorFlags` | Static bitmask（1=Lightmap, 2=Occluder...） |
| `m_IsActive` | 0 = SetActive(false) |

### Transform

| 欄位 | 說明 |
|------|------|
| `m_LocalRotation` | Quaternion {x,y,z,w} |
| `m_ConstrainProportionsScale` | Unity 2022 新增，等比縮放鎖定 |
| `m_Father` | 父 Transform；根物件為 {fileID:0} |
| `m_RootOrder` | 在父物件下的排序索引 |
| `m_LocalEulerAnglesHint` | Inspector 顯示用 Euler 角（不影響實際旋轉）|

### RectTransform（額外欄位）

```yaml
m_AnchorMin: {x: 0, y: 0}
m_AnchorMax: {x: 1, y: 1}
m_AnchoredPosition: {x: 0, y: 0}
m_SizeDelta: {x: 0, y: 0}
m_Pivot: {x: 0.5, y: 0.5}
```

---

## 8. GUID 系統

- 每個資源都有對應 .meta 存 GUID（32 位十六進制）
- 移動/重命名資源時，.meta 一起移動 → GUID 不變，參照保持有效
- **刪除 .meta 重新匯入 → GUID 重新生成 → 所有參照斷掉（最高風險）**
- 資料夾的 .meta：`folderAsset: yes`

---

## 9. Unity 2022.3 特有改動

| 改動 | 說明 |
|------|------|
| `m_ConstrainProportionsScale` | Transform 新增欄位，等比縮放鎖定 |
| Material serializedVersion 8 | 取代單一 `m_ShaderKeywords` 字串，改為 `m_ValidKeywords` 陣列 |
| TextureImporter serializedVersion 12 | 更多平台 Override 設定 |
| RenderSettings 新增欄位 | `m_IndirectSpecularColor`, `m_UseRadianceAmbientProbe` |

---

## 10. Merge 衝突處理

### SVN 環境設定 UnityYAMLMerge

```
# svn config 設定外部 merge tool（TortoiseSVN 設定路徑）
Merge Tool = "C:/Program Files/Unity/Hub/Editor/2022.3.62f1/Editor/Data/Tools/UnityYAMLMerge.exe" merge -p %base %theirs %mine %merged
```

SmartMerge 原理：
- 以 fileID 為 key 識別物件（不依賴行位置）
- `m_Component` 陣列：ordered merge（保留順序語意）
- 場景物件：unordered merge（物件獨立，不因插入位移）
- 同一 fileID 內同一欄位衝突才標真正衝突

---

## 11. 實用技巧

### 找資源依賴（grep）

```bash
# 找所有引用特定 GUID 的檔案
grep -r "abc123def456..." Assets/ --include="*.unity" --include="*.prefab" -l

# 找 Missing Script
grep -r "m_Script: {fileID: 0}" Assets/ --include="*.prefab"

# 找 GameObject 名稱
grep -r "m_Name: PlayerHero" Assets/ --include="*.unity"
```

### Missing Script YAML 表現

```yaml
m_Script: {fileID: 0}    # fileID 為 0 = Missing
```

修復：換上正確腳本的 GUID，fileID 固定 `11500000`，type 固定 `3`。

### 手動修改 YAML 注意事項

- 修改前關閉 Unity Editor（或開啟時點刷新）
- 修改前先 SVN commit 作為回滾點
- 縮排用**空格**，不用 Tab（Unity 用 2 空格）
- 浮點數保留足夠精度（Unity 輸出通常到小數點後 7 位）
- `m_Children` 和 `m_Father` 必須雙向一致
- 不要直接改 AnimationClip curve 數據、Mesh 頂點數據

### Editor 工具 vs 直接改 YAML

| 操作 | 建議方式 |
|------|---------|
| 批量修改欄位值 | 直接改 YAML（文字替換快） |
| 修復 Missing Script | 直接改 YAML（換 GUID） |
| 資產替換（A→B） | grep 找到所有引用 A 的 GUID → 全部替換成 B 的 GUID |
| 檔案格式轉換 | 刪原資產 → 同名新資產 → 修改 .meta 副檔名 |
| 修復斷掉的引用 | 用新 GUID 替換舊 GUID（資產刪除後） |
| 重命名物件修動畫 | 搜尋替換 .anim 的 `path:` 字串（批量） |
| 移動 Prefab 依賴 | Project 窗口操作（自動更新參照） |
| 添加元件 | 只能用 Editor |
| 分析依賴關係 | grep GUID 最快 |
| Merge 衝突 | UnityYAMLMerge |

### TMP 常用 GUID

| 元件 | GUID |
|------|------|
| TextMeshPro UI | `f4688fdb7bfbe46488eddcd950e76b98` |
| TextMeshPro 3D | `9541d86e2fd84c1d9990edf0852d74ab` |

---

## 12. 型別 ID 快速逆查

```
!u!1    → GameObject
!u!4    → Transform（3D）
!u!20   → Camera
!u!21   → Material
!u!23   → MeshRenderer
!u!33   → MeshFilter
!u!43   → Mesh
!u!48   → Shader
!u!49   → TextAsset
!u!54   → Rigidbody
!u!65   → BoxCollider
!u!74   → AnimationClip
!u!83   → AudioClip
!u!91   → AnimatorController
!u!95   → Animator 元件
!u!102  → TextMesh
!u!104  → RenderSettings
!u!114  → MonoBehaviour / ScriptableObject
!u!115  → MonoScript
!u!128  → Font
!u!137  → SkinnedMeshRenderer
!u!164  → AudioReverbFilter
!u!198  → ParticleSystem（Shuriken）
!u!212  → SpriteRenderer
!u!213  → Sprite
!u!221  → AnimatorOverrideController
!u!222  → CanvasRenderer
!u!223  → Canvas
!u!224  → RectTransform（UGUI）
!u!1001 → PrefabInstance
!u!1011 → TextureImporter（.png .meta）
!u!1035 → MonoImporter（.cs .meta）
!u!1089 → PrefabImporter（.prefab .meta）
```