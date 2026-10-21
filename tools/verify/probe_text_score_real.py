#!/usr/bin/env python3
"""probe_text_score_real.py：真打量尺——拿真的裁判（workflow/config.json 的 Ollama backend，預設 text_score.judge_model）對 5 份樣本
跑一次 tools/text-score.py，印每條判定與對答率、秒數。不當閘：數字是尺不是判決。

樣本：提案（_AIDocs/DevHistory/v6.0-寫程式碼的進化-2026-10/G15-規格評分表-研究與提案.md）4.5 節的原樣本沒進版控
  （S4、S5 在當時的暫存區，S1、S2 在資料根的信箱），所以這裡換成：
  W1／M1＝用提案 4.1 判例與 4.3 引文重組的「白話版／混雜版」殘留清理報告（同一件事）；
  W2／M2＝同類的設定一致性報告，白話版與寫給總控台的交付信寫法；
  P1＝提案本身第 1～25 行（真文字）。
答案是依規格標的（是原設計者判斷的替身），拿不準的條目標 None、不計分。
做法：暫存資料根放一份本樹 workflow/config.json（只用它的 backend 設定），WG_CLAUDE_DIR 指過去跑，留帳落暫存目錄、跑完刪；
  真的資料根不碰。
怎麼跑：python tools/verify/probe_text_score_real.py [--model <模型>]
尾行：`TEXT_SCORE_REAL DONE samples=<n> ran=<n> keyed=<n> correct=<n> rate=<r> void=<n> unscored=<n> false_pass=<n> false_fail=<n> secs_median=<秒>`
  （keyed＝答案表標了答案的條數，固定；沒跑成或少回的條算沒答對）。exit：5 份都跑成 0，有一份沒跑成 1。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "text-score.py"
PROPOSAL = ROOT / "_AIDocs" / "DevHistory" / "v6.0-寫程式碼的進化-2026-10" / "G15-規格評分表-研究與提案.md"

W1 = """# 全機殘留清理：結果

全機殘留清理做完了，你不需要動作。

- 結果（為了 G13「主動找出該修的並做到底」）：電腦裡各工作留下的暫存資料夾，從 180 樣降到 89 樣（試過）。
- 留下的部分（為了不刪到還在用的東西）：有 4 個是還有人在用的工作資料夾，例如一個叫 worker-1 的工作資料夾（看不出還有沒有人在用），所以先不刪。
- 之後會怎樣（為了不再堆積）：每個工作結束時會自己清掉暫存資料夾（看程式知道：收尾步驟已經加上這一段）。
"""

M1 = """# 全機殘留清理

這次因為之前 10-14 那波多軌開發時 scratchpad 沒有收尾自清，加上 list --all --json 的 key 判法在舊快照只算到 171／14，所以我改用逐 key 判並且 delete 不帶 --force 地刪了 100 項，我覺得這樣比較安全。改前 180 樣／16 session → 改後 89 樣。四個活工作樹沒記 keep，因為 keep 會永久排除提醒，這點我認為總控台會同意。
"""

W2 = """# 設定鍵一致性：第一輪量測結果

量測做完了，有一件要你拍板：3 個沒人用的設定鍵要不要刪；其餘不需要你動作。

- 要你拍板的（為了 G8「每個設定在每個地方都一致生效」）：有 3 個設定鍵寫在設定檔裡，但沒有任何程式讀它。我建議刪掉，刪了不影響現在的行為（看程式知道：整個程式碼裡找不到讀它的地方）。
- 已經修好的（為了同一個目標）：有 2 個設定鍵在兩支程式裡的預設值不一樣，已經改成同一個值（試過：重新量測後不再列出）。
- 還不能判斷的（為了不刪錯）：有 5 處程式讀設定時沒寫死鍵名，量測工具看不出它讀哪一個，先不動（推測：多半是舊寫法）。
"""

M2 = """track-config-consistency 003 交付：HEAD 4f2a9c1，tools/config-consistency.py 四類判法改完，verify_config_consistency 18 passed。

- 改檔：tools/config-consistency.py、tools/verify/verify_config_consistency.py、TECH.md §12。
- 量測：CONFIG_CONSISTENCY DONE keys=412 read_not_defined=3 defined_not_read=3 default_mismatch=2 path_self_computed=0。
- 偏離派工單：(c) 類的 js `|| 預設` 只做近似比對，因為 regex 抓不到巢狀物件，我認為夠用。
- 我在等：總控台對帳後合併。
"""

YES, NO = "是", "否"
ALL_YES = dict.fromkeys(["R1", "R2", "R3", "R4", "R5", "R6", "R7"], YES)
ALL_NO = dict.fromkeys(["R1", "R2", "R3", "R4", "R5", "R6", "R7"], NO)
KEYS: Dict[str, Dict[str, Optional[str]]] = {
    "W1": ALL_YES,
    "M1": ALL_NO,
    "W2": {**ALL_YES, "R4": None},                     # 「我建議刪掉…」算不算混了解法與個人解讀，拿不準
    "M2": {"R1": YES, "R2": NO, "R3": NO, "R4": NO, "R5": NO, "R6": NO, "R7": None},
    "P1": {"R2": YES, "R7": YES},
}


def samples() -> Dict[str, str]:
    head = "\n".join(PROPOSAL.read_text(encoding="utf-8").splitlines()[:25]) + "\n"
    return {"W1": W1, "M1": M1, "W2": W2, "M2": M2, "P1": head}


def main() -> int:
    for s in (sys.stdout, sys.stderr):
        if hasattr(s, "reconfigure"):
            s.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="真裁判對 5 份樣本跑一次 text-score，印對答率與秒數（量尺）")
    ap.add_argument("--model", help="裁判模型；不給就用 text_score.judge_model")
    args = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="g15-real-"))
    try:
        (tmp / "workflow").mkdir()
        shutil.copy(ROOT / "workflow" / "config.json", tmp / "workflow" / "config.json")
        env = {**os.environ, "WG_CLAUDE_DIR": str(tmp)}
        keyed = sum(1 for k in KEYS.values() for v in k.values() if v)   # 分母固定：沒跑成、少回的條都算沒答對
        correct = void = unscored = false_pass = false_fail = 0
        secs = []
        for name, text in samples().items():
            src = tmp / f"{name}.md"
            src.write_text(text, encoding="utf-8", newline="\n")
            cmd = [sys.executable, "-X", "utf8", str(TOOL), str(src), "--json"] + (["--model", args.model] if args.model else [])
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=1200)
            if p.returncode != 0:
                print(f"{name}: text-score exit {p.returncode}，這份沒跑成：{p.stderr.strip()[:300]}")
                continue
            rec = json.loads(p.stdout.strip().splitlines()[0])
            secs.append(rec["secs"])
            got_ids = {it["id"] for it in rec["items"]}
            lost = [k for k, v in KEYS[name].items() if v and k not in got_ids]
            if lost:
                print(f"{name}: 評分表缺條目 {'、'.join(lost)}")
            marks, misses = [], []
            for it in rec["items"]:
                key = KEYS[name].get(it["id"])
                got = it["verdict"] if it["status"] == "判定" else it["status"]
                void += it["status"] == "作廢"
                unscored += it["status"] == "未評"
                if key is None:
                    marks.append(f"{it['id']}={got}")
                    continue
                ok = got == key
                correct += ok
                false_pass += key == NO and got == YES
                false_fail += key == YES and got == NO
                marks.append(f"{it['id']}={got}{'✓' if ok else '✗(答案' + key + ')'}")
                if it["status"] == "作廢":
                    marks[-1] += f"〔{it['why']}〕"
                if not ok:   # 錯的印出引用與理由，讓人分得出是裁判錯還是答案標錯
                    misses.append(f"    {it['id']} 引用「{it['quote'][:80]}」理由：{it['reason'][:120]}")
            print(f"{name} {rec['secs']:.1f}s tok={rec['prompt_tokens']}/{rec['answer_tokens']} {rec['summary']}｜" + " ".join(marks))
            for line in misses:
                print(line)
        rate = correct / keyed if keyed else 0.0
        med = statistics.median(secs) if secs else 0.0
        print(f"對答 {correct}/{keyed}（{rate:.0%}）；壞文字判成過 {false_pass}、好文字判成不過 {false_fail}；作廢 {void}、未評 {unscored}")
        print(f"TEXT_SCORE_REAL DONE samples={len(KEYS)} ran={len(secs)} keyed={keyed} correct={correct} rate={rate:.2f} "
              f"void={void} unscored={unscored} false_pass={false_pass} false_fail={false_fail} secs_median={med:.1f}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if len(secs) == len(KEYS) else 1   # 有樣本沒跑成＝量測不完整，不是數字問題


if __name__ == "__main__":
    sys.exit(main())
