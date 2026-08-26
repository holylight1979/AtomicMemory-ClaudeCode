# headless-chrome-svg轉png-windows踩坑

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: svg轉png, svg to png, headless chrome, 渲染svg, 截圖渲染, 向量轉點陣, chrome --screenshot, force-device-scale-factor, 產示意圖, 遊戲截圖svg
- Created-at: 2026-06-15
- Related: toolchain

## 知識

- [臨] **Windows 用 headless Chrome 把 SVG/HTML 轉 PNG（無需額外裝套件）**，可忠實渲染 CJK 字型、SVG 漸層/濾鏡/marker。可行指令：

```
"/c/Program Files/Google/Chrome/Application/chrome.exe" \
  --headless --no-sandbox --disable-gpu --hide-scrollbars \
  --force-device-scale-factor=2 --window-size=1920,1080 \
  --default-background-color=00000000 \
  --screenshot="C:/path/ascii_name.png" "C:/path/input.svg"
```

- [臨] 踩坑1：`--screenshot` 輸出路徑/檔名含**中文(CJK)** → Chrome 寫檔 `access denied (0x5)`。解法：先輸出 ASCII 檔名，再用 bash `mv` 改回中文名（bash 寫 CJK 檔名正常）。
- [臨] 踩坑2：不加 `--no-sandbox` 時 `--screenshot` 首次失敗；加上即可。`--force-device-scale-factor=2` 得 2x 高解析。
- [臨] SVG 內嵌 CJK 字型用 `font-family:"Microsoft JhengHei","Noto Sans TC",sans-serif` 可正常渲染。讀回 PNG（Read 工具）即可目視驗證渲染結果。
- [臨] 環境事實：網路 share `\\server01\TSLG\...` 對本帳號(holylight) **唯讀**（Write/cp 皆 EPERM/Permission denied）→ 產物需改寫本機（如 `C:\Users\holylight\...`）再回報路徑。

## 行動

- 需把 SVG/向量示意圖轉成可直接看的 PNG → 用 headless Chrome --screenshot；記得 --no-sandbox，輸出先 ASCII 名再 mv 改中文名
- 渲染完用 Read 開 PNG 目視檢查，再交付
- 目標資料夾若唯讀(EPERM) → 改寫本機並明確回報完整路徑


## 演化日誌

| 日期 | 變更 | 來源 |
|------|------|------|
| 2026-08-26 | --enforce 自動淘汰 (32d > 30d) | memory-audit --enforce |
