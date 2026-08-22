# dotnet的SpecialFolder不吃APPDATA環境變數-隔離測試要換別的手段

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: APPDATA, SpecialFolder, ApplicationData, 隱離測試, 第二個實例, 不動使用者設定, 環境變數, profile目錄, dotnet, 沙箱
- Created-at: 2026-08-20

## 知識

- [臨] **.NET（Core / 5+）的 `Environment.GetFolderPath(SpecialFolder.ApplicationData)` 在 Windows 走 shell API（SHGetKnownFolderPath），完全不看 `%APPDATA%` 環境變數**。实测：給子行程設 `APPDATA=<臨時目錄>` 再啟動，它照樣讀真正的 `C:\Users\<user>\AppData\Roaming`。（.NET Framework 時代讀環境變數的舊認知已不適用。）
- [臨] 影響：想「另起一個不污染使用者設定的實例」來做驗收時，**換 APPDATA 這招無效**。可行的替代：① 程式自己提供 profile 目錄的 CLI 參數／環境變數② 先備份再就地跡③ 偵測到使用者已關掉程式就直接用本體。
- [臨] 方法論：這種「以為可以隱離、其實沒隱離」的失敗是**靜默的**——程式照跑、只是讀了真的設定。隱離手段上線後要先驗一個**可觀測的差異**（例：改了 port、看它有沒有真的綁新 port），確認隱離成立再開始測。

## 行動

- 要跟使用者的實例隱離跡測試，不要靠換 APPDATA，先找程式自帶的 profile 路徑參數
- 任何隱離手段上線後，先用一個可觀測差異（port、路徑、標題）確認它真的生效
