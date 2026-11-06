# 測試種的設定會帶真外呼-自動開窗會在使用者桌面開空Edge-msedge的app參數會交棒給主瀏覽器-查行程清單證明不了沒開窗

- Scope: global
- Author: holylight
- Source: session:6df28d76 2026-11-06 核心切包第二階段 E 的插件檢查
- Confidence: [臨]
- Trigger: msedge, --app, 空白 Edge, 空 edge 網頁, 自動開窗, 測試開瀏覽器, Popen 外呼, audit hook
- Created-at: 2026-11-06

## 知識

- [臨] 使用者回報空 Edge 視窗跳出：根因是檢查腳本種的設定帶 hud_autospawn=true，模擬事件走到 Popen(msedge --app=http://127.0.0.1:<測試埠>)，那個埠沒服務。
- [臨] 判斷有沒有開窗不能只查行程清單：Edge 已開著時，新行程把視窗交給主瀏覽器後立刻退出。可靠的證據是 Python audit hook 記 subprocess.Popen。
- [臨] 真缺陷同時存在：連線完全不通（服務沒起來）時仍開窗。應只在伺服器有回應但沒有頁面連著時才開。

## 行動

- 測試與對帳環境關掉會真外呼的設定並設防呆環境變數
- 要證明沒開窗就用 audit hook 記 Popen，不靠行程清單
- 連線不通時不開窗，只落 log
