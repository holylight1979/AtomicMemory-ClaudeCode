# 多模態感官 — 會議 STT、即時翻譯、出圖、螢幕理解

> 所屬：[JARVIS 企業 AI 平台發想](README.md) · 對應願景 #7 #9 #15

---

## 1. 對應願景需求

把「文字大腦」長出**感官**：能聽（會議）、能跨語（翻譯）、能畫（出圖）、能看（螢幕）。本檔覆蓋四條，缺口性質各不同：

| # | 願景原文（節錄） | 現況覆蓋 | 缺口性質 |
|---|---|---|---|
| **#9** | 「會議只要拉一個麥克風、銜接上獨立客戶端，就可以充當紀錄甚至即時翻譯」 | 🔴 **0%**：完全無 audio 管線 | **感官地基缺**（最硬） |
| **#7** | 「若語言需求也可負責翻譯」 | 🟡 LLM 本身能翻，但無 pipeline / 術語庫 / 即時通道 | 體驗缺（門檻低） |
| **#15** | 「更好的畫面檢視能力」 | 🔴 **10%**：playwright/excel 截圖 + browse-sprites 雛形，但無通用螢幕理解 | 感官缺（半成品） |
| 關聯 **#4** | 「跨企劃/程式/美術…整合」之美術側「連結 SD 或 MJ 出圖」 | 🔴 **0%**：無 image-gen connector | 觸手缺 |

一句話定位：**#9 是「耳朵」、#7 是「翻譯中樞」、#15 是「眼睛」、#4 出圖是「畫筆」。** 四者共用一條底層約束——**本地單張 3090 的算力要和對話 LLM 搶**（見 §4），所以本檔的設計重點不只是「能做」，而是「在單 GPU 序列約束下怎麼排程」。

> 定位提醒：本檔是大腦的**感官皮層**。聽到 / 看到的東西要變成可檢索知識，靠的是 [README](README.md) 第三層治理知識層（[記憶作為共享皮層](01-memory-as-shared-cortex.md)）；會議落 atom 走現有 [知識攝取](05-knowledge-ingestion.md) 同一條萃取管線；隱私紅線與「Recall 教訓」見 [作業紀錄與月誌](07-work-journal-and-activity.md) 與 [安全治理](08-security-governance-compliance.md)。

---

## 2. 現有方案比對表

> 數字會過時，皆附來源 URL。查證時點：2026-06-26。

### 2.1 STT / 語者分離 / 即時翻譯

| 系統 | 能力 | 自託管 / 隱私 | 多語言 / diarization | 可仿效 | 來源 |
|---|---|---|---|---|---|
| **Whisper（OpenAI）** | 通用 ASR + 翻譯（譯成英文）；強韌雜音 / 口音 / 術語 | ✅ 開源、可全本地（隱私友善） | 99 語言；large=1,150M params；訓練 680,000 小時（large-v3 達 100 萬小時弱標）；**本身無 diarization** | ASR 底座直接沿用；turbo 版（2024-10）約快 8x | [openai.com/index/whisper](https://openai.com/index/whisper/) · [gladia.io](https://www.gladia.io/blog/what-is-openai-whisper) |
| **WhisperX** | Whisper 增強：字級時戳（wav2vec2 強制對齊，sub-100ms）+ 語者分離（pyannote-audio）+ faster-whisper 後端**批次推論 60–70x realtime**、<8GB GPU | ✅ 全本地（**最適合我們的 3090**） | 繼承 Whisper 多語；diarization 需 **HF token**；多人重疊易亂；非官方維護 | **本平台 STT 首選**：隱私 + 本地 + 字級時戳 + 語者標籤一條龍 | [github.com/m-bain/whisperX](https://github.com/m-bain/whisperX) · [modal.com/blog](https://modal.com/blog/choosing-whisper-variants) |
| **Fireflies.ai** | 多語會議轉錄 + AI 摘要 + 行動項；自動語言偵測；2026 起加即時建議與桌面 App（錄實體會議） | ❌ SaaS、雲端（**會議內容外流**） | 100+ 語言、自動偵測；內建語者標籤 | 產品形態可仿（摘要 + 行動項 + 推播）；但隱私上**不可直接用** | [fireflies.ai](https://fireflies.ai/) · [guide.fireflies.ai](https://guide.fireflies.ai/articles/1193528158-what-is-fireflies-ai) |
| **Otter.ai** | 英文特化、實時直播字幕（會議內可見）、簡化 | ❌ SaaS | 語言少、摘要品質遜 Fireflies | 「實時字幕」互動形態值得借 | （業界常識，未逐一查證） |
| **whisper_streaming（ufal）** | Whisper 即時串流長語音轉錄 / 翻譯（LocalAgreement policy） | ✅ 開源、可本地 | 繼承 Whisper 多語 | 即時 buffer 策略的開源參考實作 | [github.com/ufal/whisper_streaming](https://github.com/ufal/whisper_streaming) |

**即時翻譯延遲工程（業界實證，供 #7+#9 即時通道設計參考）：**

| 手法 | 效果 | 來源 |
|---|---|---|
| **管線並行**（async queue：STT 處理 chunk N、MT 翻 N-1、TTS 合成 N-2） | 實測最高 **3.1x** 延遲降低 | [deepgram.com](https://deepgram.com/learn/real-time-speech-to-speech-translation) · [weblineglobal.com](https://www.weblineglobal.com/blog/optimizing-real-time-speech-translation-latency/) |
| **串流 MT「Wait-k」**（每收 3 source token 才吐 1 譯詞，不等整句） | 邊說邊譯、不等句尾 | 同上 |
| **語言偵測並行**（投機啟動 ASR，LID 並行跑） | 85% 情況省約 **600ms** | 同上 |
| **句界聚合**（MT 輸出 buffer 到句界才送下游） | 譯文更通順、減半句閃動 | 同上 |
| WebSocket chunk 切片標準 | 16kHz 下 **20ms** chunk 為生產標準；高吞吐用 100ms 降 round-trip；單 Sherpa server 約 **100 並發**後延遲明顯劣化（1.41s→2.45–3.24s @300） | 同上 |

> 端到端開源實作可達**約 1 秒（700–1500ms）** 任意語→任意語（[medium.com Simul-Translator](https://medium.com/@menes.onus/talk-30-languages-in-1-sec-an-open-source-real-time-speech-translator-i-built-single-handedly-5f461d4cf45e)）。我們的會議場景延遲容忍度比同聲傳譯寬（字幕 2–3s 可接受），工程難度低一截（推測）。

### 2.2 出圖（關聯 #4 美術整合）

| 系統 | 能力 | 自託管 / API | 整合方式 | 可仿效 | 來源 |
|---|---|---|---|---|---|
| **Stable Diffusion（本地 / ComfyUI）** | SDXL / SD3.5 / Flux 等；text2img、img2img、inpaint、upscale、batch | ✅ 全本地（**隱私 + 無單次費用**）；Stability 另有 platform.stability.ai REST API（4 端點） | **ComfyUI node 工作流 + API**（生成/放大/去背/換臉/批次一條 pipeline）；AUTOMATIC1111 / Forge 亦可 | **本平台出圖首選**：可程式化、本地隱私、與美術角色工作流接得起來 | [aicomparison.ai](https://aicomparison.ai/midjourney-vs-stable-diffusion/) · [medium ComfyUI](https://medium.com/code-canvas/comfyui-is-about-to-become-more-popular-than-midjourney-e981c5e6f1ac) |
| **Midjourney** | 美感品質頂尖、上手快 | ❌ **無官方公開 API**；綁 Discord / 網頁手動工作流 | 只能走 Discord bot 自動化或第三方非官方 API（**合規風險**） | 品質標竿；但**不適合做平台內建 connector**（API 缺口＋ToS 風險） | [aicomparison.ai](https://aicomparison.ai/midjourney-vs-stable-diffusion/) · [contentbeta.com](https://www.contentbeta.com/blog/midjourney-vs-stable-diffusion/) |

### 2.3 螢幕理解（#15）

| 系統 | 能力 | 自託管 / GPU | 螢幕 / UI 場景 | 可仿效 | 來源 |
|---|---|---|---|---|---|
| **Qwen2.5-VL（7B Instruct）** | 分析文字 / 圖表 / icon / 版面；強化 OCR 多語多向；可解析網頁 / 論文 / **手機桌面截圖**；可當 visual agent 直接點按鈕 / 填資料 | ✅ 本地：**7B 4-bit 約 16GB VRAM**、可走 Ollama | 「截圖 → 結構化理解 / 定位元素」正中 #15 | **本平台螢幕理解首選**：本地 + Ollama 既有通道 + 通用螢幕語意 | [huggingface Qwen2.5-VL-7B](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) · [qwenlm blog](https://qwenlm.github.io/blog/qwen2.5-vl/) |
| 既有 playwright / excel MCP 截圖 | 抓網頁 / Excel 畫面 | ✅ 本地 | **只截圖、不理解**（理解仍丟給對話 LLM 的 vision） | 已是「眼睛的視網膜」，缺「視覺皮層」 | （本系統現況） |
| 既有 browse-sprites skill | 批次縮圖拼貼 + 大圖，讓 AI 同時看整體 + 細節 | ✅ 本地 | 多圖檢視的人機介面範式 | 多圖 / 長畫面餵 VLM 的**前處理**直接可用 | （本系統現況） |

---

## 3. 推薦設計取捨

### 3.1 四感官的優選（給內部平台）

| 感官 | 優選 | 否決項 | 理由 |
|---|---|---|---|
| **STT + diarization（#9）** | **自託管 WhisperX**（faster-whisper 後端 + wav2vec2 字級 + pyannote 語者） | Fireflies/Otter（雲端） | 會議內容是公司最敏感資料，**不能外流 SaaS**；WhisperX 本地、<8GB GPU、字級時戳 + 語者一條龍 |
| **即時翻譯（#7）** | 本地優先：偵測非母語 → 本地 LLM（Ollama）翻；高品質需求 fallback 雲端 Translator | 預設走雲端 | 隱私優先；但本地翻譯品質 / 速度若不足，**讓使用者按敏感度選通道**（內部會議本地、對外文件可雲端） |
| **出圖（#4）** | **SD 本地（ComfyUI API）** | Midjourney 內建 connector | MJ 無官方 API + ToS 風險（§5）；SD 可程式化 + 本地隱私 + node 工作流接美術角色 |
| **螢幕理解（#15）** | **Qwen2.5-VL（Ollama 本地）+ 既有截圖管線 + browse-sprites 前處理** | 雲端 vision API（隱私 + 成本） | 截圖能力已有，缺的是「視覺皮層」；Qwen2.5-VL 7B 約 16GB 可上 3090，且走既有 Ollama 通道零新基礎設施 |

### 3.2 會議即時翻譯 pipeline 架構（#9 核心動線）

```
[麥克風/獨立客戶端]
   │ audio stream（WebSocket，16kHz；buffer 2–3s）
   ▼
[STT：WhisperX]──字級時戳 + 語者分離（pyannote）
   │ partial transcript（含 speaker 標籤）
   ▼
[語言偵測]──偵測非母語段落？
   │  ├─是→[平行翻譯：本地 LLM / fallback 雲端 Translator]（Wait-k 串流、句界聚合）
   │  └─否→直通
   ▼
[字幕顯示]──原文逐字 + 翻譯平行（WebSocket / Slack 推播；2–3s 可接受）
   ▼
[會後處理]──完整轉錄 + 多語摘要 + 行動項 + 議題/決策提取
   │
   ▼
[落 atom / episodic]──走現有萃取管線（quick/deep/SessionEnd）→ 變可檢索知識
```

**隱私關鍵**：整條 STT + 翻譯若全本地（WhisperX + Ollama），會議內容**完全不出公司網路**——這是相對所有雲端會議工具的根本差異化（也是唯一能讓法務點頭的版本）。

### 3.3 螢幕理解的分層（#15）

| 層 | 職責 | 用什麼 | 狀態 |
|---|---|---|---|
| 視網膜（截圖） | 抓畫面 | playwright / excel MCP screenshot | ✅ 已有 |
| 前處理 | 長畫面 / 多圖整理成 VLM 好吃的形式 | browse-sprites（拼貼縮圖 + 大圖） | ✅ 已有 |
| 視覺皮層（理解） | 截圖 → 結構化語意 / 定位元素 / OCR | **Qwen2.5-VL（Ollama）** | 🔴 必新建（但通道現成） |
| 行動 | 看懂後點按鈕 / 填表 | VLM as visual agent（接 [編排核心](02-orchestration-core.md)） | 🔴 遠期 |

---

## 4. ★落地切入點

**核心洞察：四感官裡，「眼睛」和「落知識」的零件大多已在，缺的是「耳朵（audio 全棧）」和把感官輸出接上 VLM/翻譯的中段。** 誠實標注：

| 能力 | 狀態 | 說明 |
|---|---|---|
| 本地算力跑 Whisper 類模型 | ✅ **能用** | Ollama Dual-Backend 已有本地 3090；WhisperX/faster-whisper 可掛同一張卡 |
| 螢幕截圖（視網膜） | ✅ **能用** | playwright / excel MCP 的 screenshot/capture 現成 |
| 多圖 / 長畫面前處理 | ✅ **能用** | browse-sprites skill 直接拿來餵 VLM |
| 網頁內容抓取 | ✅ **能用** | harvest skill（Playwright + cookie） |
| 會議摘要 → 可檢索知識 | ✅ **能用（須接線）** | 萃取管線（quick/deep/SessionEnd）+ episodic 已能把摘要落 atom；只差「轉錄文字餵進管線」這一接口 |
| 螢幕**理解**（視覺皮層） | 🟡 **半成品** | 截圖有了，缺通用 VLM 理解層；Qwen2.5-VL 走既有 Ollama 通道即可補（無新基礎設施） |
| **audio 擷取 + STT 全棧** | 🔴 **必新建** | 麥克風擷取、WebSocket 串流、WhisperX 部署、pyannote diarization、HF token 管理全缺 |
| **即時翻譯 pipeline** | 🔴 **必新建** | 串流 MT、Wait-k、句界聚合、術語庫、字幕通道全缺 |
| **術語庫**（#7 品質關鍵） | 🔴 **必新建** | 公司專有名詞 / 產品名 / 縮寫的譯名對照——**這正好可以是 atom**（術語 = 一類知識，落現有記憶庫） |
| **出圖 connector** | 🔴 **必新建** | ComfyUI API client + 美術角色工作流接線全缺 |

### ⚠️ 單張 3090 序列硬約束（本檔最關鍵的工程現實）

現有 toolchain 記憶已明載：**對話 LLM 與本地判斷共用單張 3090，序列執行、LLM 呼叫要節流。** 一旦加上會議 STT，搶 GPU 問題立刻浮現：

| 衝突情境 | 問題 | 緩解方向（推測） |
|---|---|---|
| 會議進行中 STT 即時跑 + 同時要對話 LLM 回應 | 兩者搶同一張卡、序列化 → 卡頓 | 排程器：會議 STT 標高優先即時、對話 LLM 降批次 / 排隊；或 STT 用小模型（distil / turbo）省算力 |
| STT + 螢幕 VLM + 出圖同時被要求 | 三個重模型擠一卡 | 任務佇列 + 時間片；非即時任務（出圖 / 會後摘要）排到會議結束後 |
| 即時翻譯要再加一個 LLM | 翻譯 LLM 又搶卡 | 翻譯走更小模型或雲端 fallback；或翻譯與 STT 共用同一 Whisper 的譯英能力先頂著 |

> 一句話：**單 GPU 是「能不能即時」的真正天花板。** 認真做 #9 即時翻譯，要嘛加卡、要嘛接受「會議當下只做轉錄、翻譯 / 摘要排到會後」的降級方案。建議起步：**先做「會後處理」版（非即時，無搶卡問題），把 WhisperX→萃取管線→atom 閉環跑通；即時翻譯列為加卡後的 P2+。** 演進全圖見 [從現有系統如何長出來](09-evolution-from-current-system.md)。

### 最小可行起步（推測）

1. 部署 WhisperX（單機、faster-whisper 後端），餵一段錄好的會議音檔 → 出「字級時戳 + 語者標籤」轉錄。
2. 轉錄文字丟進現有萃取管線 → 產會議摘要 / 行動項 atom（**復用 #8 攝取與既有萃取，零新管線**）。
3. 螢幕理解：Qwen2.5-VL 上 Ollama，把 playwright 截圖丟進去問「畫面上有什麼 / 哪個按鈕在哪」，驗證視覺皮層。
4. 全部跑順、確認單 GPU 排程可接受後，再碰「即時」與「翻譯 pipeline」這兩塊硬骨頭。

---

## 5. 已知風險 / 紅線 / 待驗證假設

| 類別 | 項目 | 說明 / 緩解 |
|---|---|---|
| 🔴 紅線 | **會議錄音的隱私與同意** | 錄音 = 個資 / 商業機密 + 法律同意問題（多方錄音須告知）。**全本地（WhisperX+Ollama，內容不出網）是法務唯一能接受的版本**；雲端 SaaS（Fireflies/Otter）直接否決。呼應 [作業紀錄](07-work-journal-and-activity.md) 的「Recall 教訓」與 [安全治理](08-security-governance-compliance.md) |
| 🔴 紅線 | **單 GPU 算力瓶頸** | 見 §4：會議即時 STT 與對話 LLM 搶同一張 3090。**這是「能不能即時」的硬天花板**，不是調參能繞過的。誠實結論：即時翻譯要嘛加卡、要嘛降級為會後處理 |
| 🔴 紅線 | **Midjourney 無官方 API 的合規** | MJ 無公開 API（[來源](https://aicomparison.ai/midjourney-vs-stable-diffusion/)），第三方非官方 API / Discord 自動化違反 ToS、隨時可能被封 + 法律風險。**平台內建出圖一律走 SD 本地**，MJ 只當人工參考、不做 connector |
| 🟡 風險 | **diarization 多人重疊精度** | pyannote 在多人搶話 / 重疊語音下易標錯語者；會議室遠場麥克風更糟。緩解：好的收音（指向 / 陣列麥）> 軟體；標錯語者要可人工修正 |
| 🟡 風險 | **即時翻譯延遲與品質權衡** | Wait-k 越激進（k 小）延遲越低但越易誤譯（上下文不足）。會議場景建議放寬到字幕 2–3s、句界聚合再譯，犧牲一點即時換通順（推測會議比同傳寬鬆） |
| 🟡 風險 | **diarization 需 HF token** | WhisperX 的 pyannote 需 HuggingFace token + 模型授權同意。離線 / 內網部署要先把模型快取進來，否則首次跑會卡在下載 / 授權 |
| 🟡 風險 | **術語庫缺失致專有名詞亂譯** | 公司產品名 / 縮寫被通用模型亂翻。緩解：術語庫當 atom 維護（§4），翻譯前注入 glossary 約束 |
| ❓ 待驗證 | 本地翻譯 LLM 品質是否夠用 | 假設「Ollama 本地小模型翻譯品質可接受」。實測可能不如雲端 Translator，屆時要做「敏感度分級選通道」（內部本地 / 對外雲端） |
| ❓ 待驗證 | WhisperX 60–70x realtime 在 3090 + 含 diarization 是否仍成立 | 該數字是 large-v2 純轉錄批次推論（[來源](https://github.com/m-bain/whisperX)）；加 diarization + 對齊 + 與對話 LLM 共卡後實際吞吐待實測，**勿直接拿 70x 當即時保證** |
| ❓ 待驗證 | Qwen2.5-VL 7B 螢幕理解精度 | 假設 7B 4-bit（約 16GB）對「複雜 UI / 密集文字截圖」夠用；密集表格 / 小字場景可能要 72B 或雲端，與單 GPU 約束衝突 |

---

> 互引：感官輸出落知識 [記憶作為共享皮層](01-memory-as-shared-cortex.md)｜會議摘要走 [知識攝取](05-knowledge-ingestion.md) 萃取管線｜螢幕理解接 [編排核心](02-orchestration-core.md) 當 visual agent｜隱私紅線與 Recall 教訓 [作業紀錄與月誌](07-work-journal-and-activity.md) · [安全治理](08-security-governance-compliance.md)｜單 GPU 演進路徑 [從現有系統如何長出來](09-evolution-from-current-system.md)｜回 [README](README.md)
