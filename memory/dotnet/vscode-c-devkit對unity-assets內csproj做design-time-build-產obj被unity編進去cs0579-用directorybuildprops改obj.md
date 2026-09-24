# VSCode-C#-DevKit對Unity-Assets內csproj做design-time-build-產obj被Unity編進去CS0579-用Directory.Build.props改obj~

- Scope: global
- Author: holylight
- Confidence: [臨]
- Trigger: CS0579, Duplicate Attribute, AssemblyInfo.cs, obj/Debug, C# Dev Kit, csdevkit, design-time build, projectsystem-buildhost, Directory.Build.props, BaseIntermediateOutputPath, obj~, Unity 編譯失敗, Assets 內 csproj, Unity 忽略資料夾, ~ 結尾
- Created-at: 2026-09-23

## 知識

- [臨] 症狀：Unity Console 整專案編譯失敗，錯誤全是 `Assets\...\obj\Debug\net35\Xxx.AssemblyInfo.cs: error CS0579: Duplicate 'System.Reflection.AssemblyTitleAttribute'`——Unity 把 csproj 的 obj/ 中間產物當成腳本編進 Assembly-CSharp，與原有 AssemblyInfo 重複。
- [臨] 真因：VS Code C# Dev Kit（`ms-dotnettools.csdevkit`，子行程 `dotnet visualstudio-projectsystem-buildhost` → MSBuild.dll）會對工作區內**所有** csproj 做 design-time build，包括位於 Unity `Assets/` 內的第三方套件 csproj（如 ILRuntime 的 Mono.Cecil.Pdb.csproj），obj/bin 就產在 Assets 裡。手動刪 obj 沒用：Dev Kit 幾秒內就重建（實測刪除後 3 秒內回來）。用 Win32_Process 查 dotnet.exe 的 ParentProcessId 即可確認來源。
- [臨] 解法：在那些 csproj 的共同上層放 `Directory.Build.props`，設 `BaseIntermediateOutputPath`/`MSBuildProjectExtensionsPath`=`$(MSBuildProjectDirectory)\obj~\`、`BaseOutputPath`/`OutputPath`=`bin~`——Unity 對結尾 `~` 的資料夾一律不匯入，IDE 照常建置。放了之後要讓 Dev Kit 重讀：終止 buildhost 行程（會自動重啟）或重載視窗，再刪舊 obj/bin（含 .meta）、Unity Ctrl+R。
- [臨] 旁證：這類錯誤從 Unity 側看像「專案壞了」，實則只要有人用裝 Dev Kit 的 VS Code 開過這個 repo 就會觸發；先 `svn status`/`git status` 看 obj/bin 是不是未版控新檔、再看建立時間是否等於 VS Code 開啟時間。

## 行動

- Unity 出現成批 CS0579 Duplicate Assembly*Attribute 且路徑含 obj/ → 先查誰在建（dotnet.exe 父行程），不要只刪檔
- Assets 內有 csproj 的套件 → 預防性放 Directory.Build.props 把 obj/bin 導到 ~ 結尾資料夾
