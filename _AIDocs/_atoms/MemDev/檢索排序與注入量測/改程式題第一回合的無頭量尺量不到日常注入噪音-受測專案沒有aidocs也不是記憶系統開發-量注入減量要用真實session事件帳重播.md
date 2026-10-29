# 改程式題第一回合的無頭量尺量不到日常注入噪音-受測專案沒有AIDocs也不是記憶系統開發-量注入減量要用真實session事件帳重播

- Scope: global
- Author: holylight
- Source: merge 4f3dc85a（注入噪音減量）2026-10-27
- Confidence: [臨]
- Trigger: 第一回合量尺, 無頭量尺, 注入噪音, 注入減量量測, 日常情境, hook_additional_context, 真實 session 重播, JIT, CoordWarn, 振盪
- Created-at: 2026-10-27
- Related: 用事件帳重播量改動省多少前先拿舊碼重播跟實跑transcript逐字對帳-對上了才換新碼量-重播輸入要還原到當時, hook注入成本看同一段送幾次乘之後還有幾次呼叫-長session重複送的同一段提示是大頭-不只看單段長短

## 知識

- [臨] 改程式題第一回合的無頭量尺量不到日常注入噪音：受測專案沒有 _AIDocs、不是記憶系統開發、只有單一 session，AIDocs／JIT／CoordWarn／振盪這些提示一次都不會送，砸它們在題上必然省 0。
- [臨] 量注入類減量要拿真實 session transcript 做事件帳重播，只看 hook_additional_context 附件列。

## 行動

- 量注入減量前先問：受測情境會不會送這段？不會就改用真實 session 重播
- 題上省 0 不等於沒效，先確認分母裡有沒有這類注入
