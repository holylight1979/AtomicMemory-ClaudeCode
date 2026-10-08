"""verify_plan_bash_guard — plan_bash_guard.judge() 的攔截／放行契約。

怎麼跑：python -m pytest hooks/verify/verify_plan_bash_guard.py -q（或直接 python 執行）
"""
import pathlib
import runpy
import sys

mod = runpy.run_path(str(pathlib.Path(__file__).resolve().parents[1] / "plan_bash_guard.py"))
judge = mod["judge"]
CWD = "C:/Users/holylight/.claude"

DENY = {
    "sed 正則位址觸及 .claude": "sed -n '/## 知識/,$p' /c/Users/holylight/.claude/_AIDocs/README.md; echo ====",
    "sed -e 不算唯讀": "sed -n -e 1,5p _AIDocs/README.md",
    "sed -i": "sed -i 's/a/b/' x.md",
    "cd 任何形式": "cd /c/Users/holylight/.claude; grep -n x hooks/wg_core.py | head -5",
    "重導向": "cat a.md > b.md",
    "rm": "rm -f hooks/x.py",
}
PASS = {
    "sed N,Mp": "sed -n 1,5p _AIDocs/README.md",
    "sed 多段 p": "sed -n '3p;7p' _AIDocs/README.md",
    "sed 合併旗標": "sed -nE '1,5p' _AIDocs/README.md",
    "sed 正則但不在 .claude": "sed -n '/a/,$p' /c/Work/README.md",
    "grep 管線": "grep -n foo /c/Users/holylight/.claude/hooks/wg_core.py | head",
    "引號內的分隔符不切段": "grep -n 'a;b>c' hooks/wg_core.py",
}


def test_deny_cases():
    missed = [name for name, cmd in DENY.items() if judge(cmd, CWD) is None]
    assert not missed, f"應攔未攔：{missed}"


def test_pass_cases():
    wrongly = [name for name, cmd in PASS.items() if judge(cmd, CWD) is not None]
    assert not wrongly, f"誤攔：{wrongly}"


if __name__ == "__main__":
    failed = []
    for fn in (test_deny_cases, test_pass_cases):
        try:
            fn()
        except AssertionError as e:
            failed.append(str(e))
    for f in failed:
        print("FAIL", f)
    print(f"{2 - len(failed)}/2 groups passed")
    sys.exit(1 if failed else 0)
