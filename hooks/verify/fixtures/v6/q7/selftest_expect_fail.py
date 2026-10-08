"""q7 fixture：預期 FAIL 的自測（登記 expected=FAIL；印 SELF_CHECK FAIL、exit 1）。"""
import sys
print("SELF_CHECK FAIL")
sys.exit(1)
