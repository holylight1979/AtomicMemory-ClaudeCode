# 不裝VS也能用Roslyn解析C#-NET-SDK自帶在sdk版本Roslyn-bincore-HintPath參照就能離線編-build要關nodeReuse與共用編譯

- Scope: global
- Author: holylight
- Source: 2026-10-23 C# 閱讀路徑量測實作
- Confidence: [臨]
- Trigger: Roslyn, Microsoft.CodeAnalysis, C# 解析, 語法樹, bincore, HintPath, 不裝 Visual Studio, 離線編譯, nodeReuse, UseSharedCompilation, VBCSCompiler, 正則解析誤判, 輕量解析
- Created-at: 2026-10-23
- Related: 靜態分析量尺真打後先抽樣每種解析不到的原因-多數是可修的讀錯或標太寬-遮字串要留記號

## 知識

- [臨] .NET SDK 本身就附了 Roslyn（C# 官方編譯器的解析程式庫），在 `<dotnet 安裝目錄>/sdk/<版本>/Roslyn/bincore`；csproj 用 HintPath 直接參照那裡的 Microsoft.CodeAnalysis*.dll，不裝 Visual Studio、不從 NuGet 下載，就能離線編一支小解析程式。
- [臨] build 時加 `-nodeReuse:false` 並設 `UseSharedCompilation=false`，免得編完留下背景的 MSBuild 節點和編譯伺服器行程。
- [臨] 實測成本：第一次編約 7 秒、產物約 30MB，之後每批解析約 0.5 秒。
- [臨] 找不到 SDK 或編不起來時要退回輕量解析，並在結果註明這次用的是輕量解析。
- [臨] 拿同一個 115 檔專案比對，輕量正則解析的已知誤判：三元運算的 `?` 被當成 `?.`、`else if (…) {` 被當成區域函式、`#region` 讓函式起始行提前、`obj.layer = layer` 被算成參數被改、`new X().y` 被當成型別 X；Roslyn 這些都判對。

## 行動

- 要準確拿到 C# 的函式範圍、呼叫、指定時，先找 SDK 附的 Roslyn，不先寫正則
- build 一律帶 -nodeReuse:false 與 -p:UseSharedCompilation=false
- 退回輕量解析時在輸出註明，不靜默降級
