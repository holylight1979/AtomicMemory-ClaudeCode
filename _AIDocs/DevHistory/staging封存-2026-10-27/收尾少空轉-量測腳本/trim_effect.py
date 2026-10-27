"""收尾瘦身的預估效果：指定窗（UTC）內根層每則收尾擋下，照新政策分「還會擋」「不再擋」，各自擋下後跑了幾次 pytest／run_verify。
新政策會擋：✗ (a)／(d) 條目（但 CASE_DECLARED_FOR_CHANGE 屬驗證範圍宣告，不算）、TestFailGate、KnowledgeHarvest、SyncReminder、
Workflow Guardian、DeferralGate、DeepPostMortem、Cleanup、ReloadAdvice、AEC-Pending。其餘（VerifyScope、ScanReport、AtomAudit、
需求目標對照 (f*)、(b)(c)(e)(v)）不再擋。
跑法：python -X utf8 trim_effect.py <起 ISO> <迄 ISO>
"""
import glob, os, re, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stop_measure as sm
from catch_cases import scan

KEEP_TAGS = {"Guardian:TestFailGate", "Guardian:KnowledgeHarvest", "Guardian:SyncReminder", "Workflow Guardian",
             "Guardian:DeferralGate", "Guardian:DeepPostMortem", "Guardian:Cleanup", "Guardian:ReloadAdvice", "Guardian:AEC-Pending"}
PY = re.compile(r"pytest|run_verify")


def still_blocks(text):
    tags = set(sm.TAG.findall(text))
    if tags & KEEP_TAGS:
        return True
    for letter, rule in re.findall(r"✗ \((\w+)\) ([A-Z][A-Z0-9_]+)", text):
        if letter in ("a", "d") and rule != "CASE_DECLARED_FOR_CHANGE" and not rule.startswith("SCOPE_"):
            return True
    return False


def main():
    lo, hi = sys.argv[1], sys.argv[2]
    n, py = Counter(), Counter()
    for fp in glob.glob(sm.ROOT + "/*/*.jsonl"):
        if not os.path.basename(os.path.dirname(fp)).lower().startswith("c--users-holylight--claude"):
            continue
        cur = None
        for e in scan(fp) + [("turn", "9999")]:
            if e[0] in ("turn", "block"):
                if cur:
                    n[cur[0]] += 1
                    py[cur[0]] += cur[1]
                cur = None
                if e[0] == "block" and lo <= e[1] < hi:
                    cur = ["keep" if still_blocks(e[2]) else "gone", 0]
                continue
            if cur and e[0] == "tool" and e[2] in ("Bash", "PowerShell") and PY.search(e[3].get("command", "")):
                cur[1] += 1
    for k in ("keep", "gone"):
        print(f"{k}: 擋下 {n[k]} 次，擋下後 pytest {py[k]} 次")
    print(f"TRIM_EFFECT DONE keep_blocks={n['keep']} gone_blocks={n['gone']} keep_py={py['keep']} gone_py={py['gone']}")


if __name__ == "__main__":
    main()
