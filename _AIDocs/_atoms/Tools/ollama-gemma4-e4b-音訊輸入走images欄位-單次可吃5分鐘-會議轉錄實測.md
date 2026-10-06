# ollama-gemma4-e4b-音訊輸入走images欄位-單次可吃5分鐘-會議轉錄實測

- Scope: global
- Author: holylight
- Source: tools/meeting-transcribe.py；session a380adef 實測
- Confidence: [臨]
- Trigger: Ollama 音訊, audio, 語音辨識, 錄音轉文字, 會議錄音, 會議音檔, gemma4:e4b, images 欄位, 會議轉錄, meeting-transcribe, whisper, capabilities
- Created-at: 2026-10-06
- Related: toolchain-ollama

## 知識

- [臨] Ollama 0.30.7 的 `/api/show` 對 gemma4:e4b／e4b-64k／e2b 回 `capabilities` 含 `audio`（26b 沒有），但 API 文件沒寫怎麼送音訊：實測（2026-10-06，192.168.199.130）`/api/chat` 的 message 加 `audio`／`files` 欄位模型回「沒有提供音訊」，**放 `images`（base64 的 16kHz 單聲道 wav）才看得到**，prompt_eval_count 隨音長增加（約 26 token/s）。
- [臨] 一次吃多長：e4b 單次 284s 合成會議全文無漏（ptok 7146、13s）；同一段重複 8 次（565s）輸出會被壓成一遍，疑似去重非截斷，未定論。生產預設 180s 一段、`num_ctx` 16384。段尾偶爾回音指令全文，要截。e2b 中文辨識明顯差，不用。
- [臨] 中文辨識品質：TTS 合成音可讀但同音錯字多（由→有、待辦事項→帶版事向、企劃→氣化）；prompt 附人名術語清單可修一部分，摘要階段再用同一份清單校正效果更好。真人錄音未測。
- [臨] 192.168.199.130 的 22 port 開著但 ssh banner exchange 逾時（本機 key 認證），不能在那台裝 faster-whisper；走 Ollama 現成音訊模型零安裝。

## 行動

- 要在內網 GPU 跑語音辨識先 `curl /api/show` 看 capabilities 有沒有 audio，有就直接 `images` 欄位送 wav，不必裝 whisper
- 會議轉錄用 `python ~/.claude/tools/meeting-transcribe.py`（`--check` 先驗）
