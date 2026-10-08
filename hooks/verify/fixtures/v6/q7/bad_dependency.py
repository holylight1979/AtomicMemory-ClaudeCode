"""q7 反例一：壞依賴：import 不存在的模組，沒印到哨兵就死。"""
import module_that_does_not_exist_q7  # noqa: F401
print("SELF_CHECK PASS")
