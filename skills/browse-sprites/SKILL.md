---
name: browse-sprites
description: 批次圖片預覽：拼貼縮圖 + 大張原圖讓 AI 同時看清整體與細節
---

# /browse-sprites — 批次圖片預覽

> **自動觸發**：當你在做 prefab 編輯、UI 設計、或任何需要選圖的工作時，
> 遇到不認識的圖素目錄或不確定該用哪張圖 → 直接使用本工具，不需要使用者指示。

## 參數
- `$ARGUMENTS`：資料夾路徑（必填），可加 `--filter prefix1,prefix2` 篩選檔名前綴

## 執行流程

1. 執行 contact sheet 生成：
   ```
   python ~/.claude/tools/sprite_contact_sheet.py "<資料夾路徑>" "c:/tmp/contact_sheet.png" --cols 6 --thumb 140 [--filter <prefixes>]
   ```
   - 如果圖檔超過 50 張且未指定 filter，建議分批（先列檔名分析前綴規律，再按組 filter）
   - 如果 `~/.claude/tools/sprite_contact_sheet.py` 不存在，用下方內嵌腳本

2. 用 Read 工具讀取 `c:/tmp/contact_sheet.png` 檢視

3. 根據預覽結果：
   - 描述每張圖的視覺外觀
   - 如果是為了選圖：直接推薦最匹配的圖素
   - 如果是建索引：整理成分類表格

## 自動觸發場景

以下情境應**主動**使用本工具（不需使用者明確要求）：

- 要修改 prefab 的 sprite 引用，但 Catalog 裡沒有對應圖素
- 要在功能專用目錄（如 `UITextures/Guild/`）選圖
- 使用者提供了設計稿/描述，需要從陌生目錄找匹配圖素
- 遇到 sprite Missing 需要找替代圖

## 常用路徑速查

| 目的 | 路徑 |
|------|------|
| 通用 UI 元件 | `Assets/Res/UITextures/Common/` |
| 通用動態（按鈕/資源） | `Assets/Res/UIDynamic/Common/` |
| 大型面板件 | `Assets/Res/UITextures/OverSize/` |
| 功能專用 | `Assets/Res/UITextures/{功能名}/` |
| 功能動態 | `Assets/Res/UIDynamic/{功能名}/` |
| 小圖標 | `Assets/Res/UISimpleIcon/{類型}/` |

> 完整圖素索引見 `_AIDocs/Client_UI_Sprite_Catalog.md`

## 內嵌備用腳本

如果 `~/.claude/tools/sprite_contact_sheet.py` 不存在，用 Python 執行：

```python
import sys, os, glob
from PIL import Image, ImageDraw, ImageFont

def make_sheet(src, out, cols=6, thumb=140, filt=None):
    files = sorted(glob.glob(os.path.join(src, "*.png")))
    if filt:
        px = [p.strip() for p in filt.split(",")]
        files = [f for f in files if any(os.path.basename(f).startswith(p) for p in px)]
    if not files: print("No files."); return
    lh, cw, ch = 18, thumb+10, thumb+28
    rows = (len(files)+cols-1)//cols
    canvas = Image.new("RGBA", (cols*cw+10, rows*ch+10), (40,40,40,255))
    draw = ImageDraw.Draw(canvas)
    try: font = ImageFont.truetype("arial.ttf", 11)
    except: font = ImageFont.load_default()
    for i, fp in enumerate(files):
        x, y = (i%cols)*cw+5, (i//cols)*ch+5
        cs = 8
        for cy in range(thumb//cs):
            for cx in range(thumb//cs):
                c = (60,60,60) if (cx+cy)%2==0 else (80,80,80)
                draw.rectangle([x+5+cx*cs, y+cy*cs, x+5+(cx+1)*cs, y+(cy+1)*cs], fill=c)
        try:
            img = Image.open(fp).convert("RGBA")
            img.thumbnail((thumb-10, thumb), Image.LANCZOS)
            canvas.paste(img, (x+5+(thumb-10-img.width)//2, y+(thumb-img.height)//2), img)
        except: draw.text((x+5, y+thumb//2), "ERR", fill="red", font=font)
        n = os.path.basename(fp).replace(".png","")
        draw.text((x+3, y+thumb+2), n[:17]+"…" if len(n)>18 else n, fill=(200,200,200), font=font)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    canvas.save(out)
    print(f"Done: {len(files)} sprites -> {out}")

make_sheet(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else "c:/tmp/contact_sheet.png")
```

## 範例

```
/browse-sprites C:\Projects\sgi_client\client\Assets\Res\UITextures\Guild
/browse-sprites C:\Projects\sgi_client\client\Assets\Res\UIDynamic\Common --filter Btn_,Scrollbar_
```
