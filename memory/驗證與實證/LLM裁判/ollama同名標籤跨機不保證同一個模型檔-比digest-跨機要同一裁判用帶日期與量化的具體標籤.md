# Ollama同名標籤跨機不保證同一個模型檔-比digest-跨機要同一裁判用帶日期與量化的具體標籤

- Scope: global
- Author: holylight
- Source: _AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/裁判模型選型-研究與實測-2026-10-21.md 4.3
- Confidence: [臨]
- Trigger: Ollama 標籤, ollama pull, digest, 模型版本, gemma4:e4b, 跨機同模型, 裁判模型, judge_model, /api/tags
- Created-at: 2026-10-21
- Related: 小模型當文字規格裁判實測-逐條是非題加程式先切範圍才準-一次全判會拿後文湊答案-裁判偏寬鬆先記帳不擋-引用對不到原文就作廢

## 知識

- [臨]（實測）Ollama 庫的標籤會原地換版：同樣叫 gemma4:e4b，較早拉的機器上是 9.61GB、digest c6eb396…，較晚拉的是 6.58GB、dc35e8d…；gemma4:e2b 同樣 7.16GB 對 4.59GB。名字一樣其實是不同檔，判分、速度都不能互相沿用。
- [臨] 要多台機器用「同一個」模型（例如裁判分數要能比）：比 `/api/tags` 的 digest，不比名字；選標籤時用帶日期與量化的具體標籤（如 qwen3:4b-instruct-2507-q4_K_M），不用 latest 或只寫尺寸的短標籤。

## 行動

- 跨機比模型或要求同一裁判前，先各台 `/api/tags` 比 digest
- 設定檔寫模型名時用帶日期與量化的完整標籤
