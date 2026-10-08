"""q7 反例四：先印 PASS 再炸（traceback、exit 1）。尾行不是哨兵、exit 非零，expected PASS 必紅。"""
print("SELF_CHECK PASS")
raise RuntimeError("boom after pass")
