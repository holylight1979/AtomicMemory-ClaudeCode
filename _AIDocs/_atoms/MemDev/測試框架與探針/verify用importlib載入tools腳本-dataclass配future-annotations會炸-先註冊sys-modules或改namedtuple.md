# verify用importlib載入tools腳本-dataclass配future-annotations會炸-先註冊sys-modules或改NamedTuple

- Scope: global
- Author: holylight
- Source: tools/verify/verify_meeting_transcribe.py；session a380adef
- Confidence: [臨]
- Trigger: importlib, spec_from_file_location, dataclass, future annotations, verify 載入, NoneType __dict__, tools/verify
- Created-at: 2026-10-06
- Quote: 「<pasted_content id="45f0"> /continue 讀 C:\Users\holylight\.claude\memory\_staging\next-phase-meeting-transcription.md 並依序執行。 開工前先問我 Step 0 的三題（錄音來源／跑語音辨識的顯卡在哪台／摘要存哪一層），一次問完。 順帶補上 Install-forAI.md Ste…」

## 知識

- [臨] tools/verify 慶例用 `importlib.util.spec_from_file_location` 載入 `tools/<name>.py`（檔名帶 `-` 無法 import）；若該腳本同時有 `from __future__ import annotations` 與 `@dataclass`，沒先 `sys.modules[name] = module` 就 `exec_module` 會在 dataclass 定義時炸 `AttributeError: 'NoneType' object has no attribute '__dict__'`（dataclasses 用 `sys.modules.get(cls.__module__)` 解析字串型別註解）。 meeting-transcribe 踩到。
- [臨] 解法二擇一：載入端先註冊 `sys.modules`（verify_meeting_transcribe 做法）；或腳本端改 `typing.NamedTuple`／普通 class，不用 dataclass。兩邊都做最穩。

## 行動

- 新 verify 用 importlib 載入腳本時一律先 `sys.modules[<name>] = mod` 再 `exec_module`
