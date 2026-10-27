# 退路與交錯案例要拿掉修補確認會紅-別的失敗會遮住要測的分支-用monkeypatch精確排出交錯-msvcrt鎖每個handle各算可同行程模擬握鎖

- Scope: global
- Author: holylight
- Source: 2026-10-23 state 讀改寫握鎖修補實測
- Confidence: [臨]
- Trigger: 拿掉修補仍綠, 退路案例, 交錯案例, 並行案例反證, monkeypatch 疊兩層, monkeypatch 包到假函式, msvcrt.locking, 模擬別人握鎖, 同行程另開 handle
- Created-at: 2026-10-22
- Related: 回歸測試先證明舊版會紅-把舊版受測檔git-show到暫存夾配新測試跑-紅要紅在斷言不是keyerror

## 知識

- [臨] 退路、交錯這類案例，要拿掉修補跑一次確認會紅：實測有兩個案拿掉修補仍綠，因為別的失敗連帶擋住了要測的分支；要用 monkeypatch 精確排出那個交錯才抓得到。
- [臨] monkeypatch 疊兩層包同一個函式時，先記住真正的原函式；否則第二層會把第一層的假函式當成真的包進去。
- [臨] Windows 的 msvcrt 鎖是每個 handle 各算：同一行程另開一個 handle 鎖同一個 byte，就能模擬「別人握著鎖」，不用起子行程。

## 行動

- 退路／交錯案例寫完：拿掉修補跑一次，仍綠就用 monkeypatch 把交錯排準再跑
- 疊 monkeypatch 前先存下原函式
