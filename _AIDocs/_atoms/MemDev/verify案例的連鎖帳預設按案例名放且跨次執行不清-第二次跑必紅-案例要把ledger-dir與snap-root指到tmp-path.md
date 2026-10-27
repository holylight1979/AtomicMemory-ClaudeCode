# verify案例的連鎖帳預設按案例名放且跨次執行不清-第二次跑必紅-案例要把ledger-dir與snap-root指到tmp-path

- Scope: global
- Author: holylight
- Source: 2026-10-23 斷路器與紅測閘修補實測
- Confidence: [臨]
- Trigger: chain_store, _test_root, _ledger_dir, _snap_root, 連鎖帳, 第二次跑就紅, 判成中止中, verify 案例
- Created-at: 2026-10-22

## 知識

- [臨] lib/chain_store 在 pytest 底下用 _test_root 按案例名放連鎖帳（logs_dir/chain-tests/<案例名雜湊>），跨次執行不清；同一案第二次跑必紅，因為上一次的帳還在，第一個閘就被判成中止中。
- [臨] 解法：案例用 monkeypatch 把 chain_store._ledger_dir 與 _snap_root 指到 tmp_path（hooks/verify/verify_chain_breaker.py、verify_chain_wiring.py 已這樣寫）。_test_root 本身還沒改，新寫的案例不自己指照樣會踩。

## 行動

- 新寫會走到連鎖斷路器的 verify 案例，先把 _ledger_dir／_snap_root 指到 tmp_path
- 案例第一次綠、第二次紅 → 先查是不是上一次留下的連鎖帳
